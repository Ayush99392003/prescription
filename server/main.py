"""
PRESCRIPTION Server — Main CLI entry point.
Orchestrates the full pipeline: Record → Transcribe → Parse
→ Validate → Export PDF.

Run:
    uv run python -m server.main
    # or after `uv install`:
    prescription
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.prompt import Confirm

from server import config
from server.core.schemas import PrescriptionSchema
from server.core.session import PrescriptionSession, ValidatedMedication
from server.data import fuzzy_matcher, indexer
from server.export.pdf_generator import generate_pdf
from server.ui import dashboard

console = Console()


# ── Provider factory functions ────────────────────────────────────────

def _get_stt_provider():
    """
    Instantiate the configured STT provider.

    Returns:
        An STTProvider instance based on config.STT_PROVIDER.

    Raises:
        ValueError: If the configured provider name is unknown.
    """
    name = config.STT_PROVIDER.lower()
    if name == "faster_whisper":
        from server.voice.faster_whisper_stt import (  # noqa: PLC0415
            FasterWhisperSTT,
        )
        return FasterWhisperSTT()
    if name == "openai_whisper":
        from server.voice.openai_whisper_stt import (  # noqa: PLC0415
            OpenAIWhisperSTT,
        )
        return OpenAIWhisperSTT()
    if name == "groq_whisper":
        from server.voice.groq_whisper_stt import (  # noqa: PLC0415
            GroqWhisperSTT,
        )
        return GroqWhisperSTT()
    raise ValueError(
        f"Unknown STT_PROVIDER: '{name}'. "
        "Options: 'faster_whisper', 'openai_whisper', 'groq_whisper'"
    )


def _get_llm_provider():
    """
    Instantiate the configured LLM provider.

    Returns:
        An LLMProvider instance based on config.LLM_PROVIDER.

    Raises:
        ValueError: If the configured provider name is unknown.
    """
    name = config.LLM_PROVIDER.lower()
    if name == "ollama":
        from server.llm.ollama_provider import (  # noqa: PLC0415
            OllamaProvider,
        )
        return OllamaProvider()
    if name == "groq":
        from server.llm.groq_provider import (  # noqa: PLC0415
            GroqProvider,
        )
        return GroqProvider()
    raise ValueError(
        f"Unknown LLM_PROVIDER: '{name}'. "
        "Options: 'ollama', 'groq'"
    )


# ── Pipeline stages ───────────────────────────────────────────────────

def _stage_record(session: PrescriptionSession) -> None:
    """Stage 1: Capture microphone audio."""
    dashboard.print_step("Stage 1", "Voice Capture")
    from server.voice.recorder import record_audio  # noqa: PLC0415
    try:
        session.audio_path = record_audio()
    except RuntimeError as exc:
        dashboard.print_error("Microphone Error", str(exc))
        sys.exit(1)


def _stage_transcribe(
    session: PrescriptionSession,
    stt,
) -> None:
    """Stage 2: Transcribe audio to text."""
    dashboard.print_step("Stage 2", "Speech-to-Text")
    try:
        session.transcript = stt.transcribe(
            session.audio_path  # type: ignore[arg-type]
        )
    except RuntimeError as exc:
        dashboard.print_error("Transcription Error", str(exc))
        sys.exit(1)

    dashboard.print_transcript(session.transcript)


def _stage_parse(
    session: PrescriptionSession,
    llm,
) -> None:
    """Stage 3: Parse transcript into structured schema."""
    dashboard.print_step("Stage 3", "LLM Parsing")
    try:
        session.prescription = llm.parse_prescription(
            session.transcript  # type: ignore[arg-type]
        )
    except RuntimeError as exc:
        dashboard.print_error("LLM Parse Error", str(exc))
        sys.exit(1)


def _stage_validate(session: PrescriptionSession) -> None:
    """Stage 4: Fuzzy-match each medication against the database."""
    dashboard.print_step("Stage 4", "Medicine Validation")

    if session.prescription is None:
        return

    try:
        indexer.load_index()
    except FileNotFoundError as exc:
        dashboard.print_error("Database Error", str(exc))
        sys.exit(1)

    for med in session.prescription.medications:
        result = fuzzy_matcher.find_best_match(
            med.name, specialty=config.CLINIC_SPECIALTY
        )
        vm = ValidatedMedication(
            name=med.name,
            dosage=med.dosage,
            frequency=med.frequency,
            duration=med.duration,
            instructions=med.instructions,
        )
        if result is not None:
            matched_name, score, row = result
            vm.matched_name = matched_name
            vm.match_score = score
            vm.price = row.get("price", None)
            vm.manufacturer = row.get("manufacturer", None)
            vm.pack_size = row.get("pack_size", None)
        else:
            vm.matched_name = None
            vm.match_score = 0
            console.print(
                f"[yellow]⚠ No match found for: "
                f"[bold]{med.name}[/bold][/yellow]"
            )
        session.validated_meds.append(vm)


def _stage_review(session: PrescriptionSession) -> bool:
    """Stage 5: Show table and ask user to confirm PDF export."""
    dashboard.print_step("Stage 5", "Review & Export")
    dashboard.print_prescription_table(session)
    return Confirm.ask(
        "[bold cyan]Generate PDF prescription?[/bold cyan]",
        default=True,
    )


def _stage_export(session: PrescriptionSession) -> None:
    """Stage 6: Generate the PDF."""
    try:
        session.pdf_path = generate_pdf(session)
    except (ValueError, RuntimeError) as exc:
        dashboard.print_error("PDF Export Error", str(exc))
        sys.exit(1)


# ── Main loop ─────────────────────────────────────────────────────────

def _run_once() -> None:
    """Execute a single prescription session end-to-end."""
    session = PrescriptionSession()

    stt = _get_stt_provider()
    llm = _get_llm_provider()

    # Pre-flight checks
    if not stt.is_available():
        dashboard.print_error(
            "STT Unavailable",
            f"Provider '{config.STT_PROVIDER}' is not ready. "
            "Check installation.",
        )
        sys.exit(1)

    if not llm.is_available():
        dashboard.print_error(
            "LLM Unavailable",
            f"Provider '{config.LLM_PROVIDER}' is not ready. "
            "Check config/credentials.",
        )
        sys.exit(1)

    _stage_record(session)
    _stage_transcribe(session, stt)
    _stage_parse(session, llm)
    _stage_validate(session)

    if _stage_review(session):
        _stage_export(session)

    dashboard.print_session_summary(session)


def main() -> None:
    """
    Application entry point — main session loop.
    Keeps running until the user declines to continue.
    """
    dashboard.print_banner()
    dashboard.print_config_summary()

    while True:
        try:
            _run_once()
        except KeyboardInterrupt:
            console.print(
                "\n[bold yellow]Session interrupted.[/bold yellow]"
            )
            break

        again = Confirm.ask(
            "\n[bold cyan]Start another session?[/bold cyan]",
            default=True,
        )
        if not again:
            break

    console.print(
        "\n[bold green]Goodbye![/bold green] "
        "[dim]PRESCRIPTION session ended.[/dim]\n"
    )


if __name__ == "__main__":
    main()
