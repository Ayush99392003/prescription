"""
STT provider using faster-whisper (CTranslate2 backend).
Primary local engine — CPU-compatible, int8 quantized, no GPU needed.
"""

from __future__ import annotations

from rich.console import Console

from server import config
from server.voice.base import STTProvider

console = Console()

# Module-level lazy cache — model loads once, stays in memory
_model = None


def _get_model():
    """Lazy-load the faster-whisper model on first call."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel  # noqa: PLC0415

        with console.status(
            f"[cyan]Loading Whisper "
            f"'[bold]{config.WHISPER_MODEL}[/bold]'…[/cyan]"
        ):
            _model = WhisperModel(
                config.WHISPER_MODEL,
                device="cpu",
                compute_type="int8",
            )
        console.print(
            f"[green]✓ Whisper model "
            f"'[bold]{config.WHISPER_MODEL}[/bold]' loaded[/green]"
        )
    return _model


class FasterWhisperSTT(STTProvider):
    """
    Transcribes audio using the faster-whisper CTranslate2 backend.
    Runs fully offline on CPU with int8 quantization.
    """

    def is_available(self) -> bool:
        """Return True if faster-whisper is importable."""
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe a WAV file using faster-whisper.

        Args:
            audio_path: Path to a 16kHz mono WAV file.

        Returns:
            Cleaned transcript string.

        Raises:
            RuntimeError: If package missing or transcription fails.
        """
        if not self.is_available():
            raise RuntimeError(
                "faster-whisper not installed. "
                "Run: uv add faster-whisper"
            )

        model = _get_model()

        with console.status(
            "[cyan]Transcribing audio…[/cyan]"
        ):
            try:
                segments, info = model.transcribe(
                    audio_path,
                    beam_size=5,
                    language="en",
                )
                text_parts = [seg.text for seg in segments]
            except Exception as exc:
                raise RuntimeError(
                    f"Transcription failed: {exc}"
                ) from exc

        transcript = " ".join(text_parts).strip()
        transcript = _clean_fillers(transcript)

        console.print(
            f"[green]✓ Transcribed[/green] "
            f"([dim]{info.duration:.1f}s audio[/dim])"
        )
        return transcript


def _clean_fillers(text: str) -> str:
    """
    Strip common filler words and normalize whitespace.

    Args:
        text: Raw transcript from Whisper.

    Returns:
        Cleaned transcript string.
    """
    _FILLERS = {"um", "uh", "hmm", "er", "ah", "like"}
    words = text.split()
    cleaned = [w for w in words if w.lower() not in _FILLERS]
    return " ".join(cleaned)
