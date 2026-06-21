"""
STT provider using the original openai-whisper library.
Fallback option — same model weights, slower than faster-whisper.
Install separately: uv add openai-whisper
"""

from __future__ import annotations

from rich.console import Console

from server import config
from server.voice.base import STTProvider

console = Console()

_model = None


def _get_model():
    """Lazy-load the openai-whisper model on first call."""
    global _model
    if _model is None:
        import whisper  # noqa: PLC0415

        with console.status(
            f"[cyan]Loading OpenAI Whisper "
            f"'[bold]{config.WHISPER_MODEL}[/bold]'…[/cyan]"
        ):
            _model = whisper.load_model(config.WHISPER_MODEL)
        console.print(
            f"[green]✓ OpenAI Whisper "
            f"'[bold]{config.WHISPER_MODEL}[/bold]' loaded[/green]"
        )
    return _model


class OpenAIWhisperSTT(STTProvider):
    """
    Transcribes audio using the original openai-whisper library.
    Use as a fallback when faster-whisper is unavailable.
    """

    def is_available(self) -> bool:
        """Return True if openai-whisper is importable."""
        try:
            import whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe a WAV file using openai-whisper.

        Args:
            audio_path: Path to a 16kHz mono WAV file.

        Returns:
            Cleaned transcript string.

        Raises:
            RuntimeError: If package missing or transcription fails.
        """
        if not self.is_available():
            raise RuntimeError(
                "openai-whisper not installed. "
                "Run: uv add openai-whisper"
            )

        model = _get_model()

        from server.voice.prompts import get_initial_prompt  # noqa: PLC0415
        prompt_str = get_initial_prompt(config.CLINIC_SPECIALTY)

        with console.status(
            "[cyan]Transcribing (OpenAI Whisper)…[/cyan]"
        ):
            try:
                result = model.transcribe(
                    audio_path,
                    language="en",
                    fp16=False,
                    initial_prompt=prompt_str,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"OpenAI Whisper failed: {exc}"
                ) from exc

        transcript = result.get("text", "").strip()
        console.print(
            "[green]✓ Transcribed (OpenAI Whisper)[/green]"
        )
        return transcript
