"""
Utility script to test run the prescription pipeline on a sample audio file.

Usage:
    uv run python server/test_pipeline.py DATA/filename.ogg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from server import config
from server.core.session import PrescriptionSession
from server.main import (
    _get_llm_provider,
    _get_stt_provider,
    _stage_export,
    _stage_parse,
    _stage_transcribe,
    _stage_validate,
)
from server.ui import dashboard

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run prescription pipeline on sample audio"
    )
    parser.add_argument(
        "audio_path",
        type=str,
        help="Path to the sample ogg/wav audio file",
    )
    args = parser.parse_args()

    audio_file = Path(args.audio_path)
    if not audio_file.exists():
        console.print(
            f"[red]Error: Audio file not found at {audio_file}[/red]"
        )
        sys.exit(1)

    console.print(
        f"[cyan]Running full pipeline on audio:[/cyan] "
        f"[bold]{audio_file.name}[/bold]"
    )

    # Initialize a new session
    session = PrescriptionSession()
    session.audio_path = str(audio_file)

    # Load providers
    stt = _get_stt_provider()
    llm = _get_llm_provider()

    # Pre-flight checks
    if not stt.is_available():
        console.print(
            f"[red]STT Provider '{config.STT_PROVIDER}' is not ready.[/red]"
        )
        sys.exit(1)

    if not llm.is_available():
        console.print(
            f"[red]LLM Provider '{config.LLM_PROVIDER}' is not ready.[/red]"
        )
        sys.exit(1)

    # Execute stages
    _stage_transcribe(session, stt)
    _stage_parse(session, llm)
    _stage_validate(session)
    _stage_export(session)

    # Display results
    dashboard.print_prescription_table(session)
    dashboard.print_session_summary(session)


if __name__ == "__main__":
    main()
