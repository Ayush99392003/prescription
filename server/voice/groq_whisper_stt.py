"""STT provider using the Groq Cloud API (Whisper-large-v3 model).

Extremely fast, cloud-based alternative to local models.
"""

from __future__ import annotations

from pathlib import Path
from openai import OpenAI
from rich.console import Console

from server import config
from server.voice.base import STTProvider

console = Console()

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqWhisperSTT(STTProvider):
    """Transcribes audio using Whisper-large-v3 on Groq's cloud API.

    Requires internet and a valid GROQ_API_KEY env var.
    """

    def is_available(self) -> bool:
        """Return True if the Groq API key is configured."""
        return bool(config.GROQ_API_KEY)

    def transcribe(self, audio_path: str) -> str:
        """Transcribe a WAV file using Whisper via Groq cloud API.

        Args:
            audio_path: Path to the audio file.

        Returns:
            Cleaned transcript string.

        Raises:
            RuntimeError: If API key missing or transcription fails.
        """
        if not self.is_available():
            raise RuntimeError(
                "GROQ_API_KEY not set. "
                "Add it to your .env file: GROQ_API_KEY=gsk_..."
            )

        client = OpenAI(
            api_key=config.GROQ_API_KEY,
            base_url=_GROQ_BASE_URL,
        )

        path = Path(audio_path)
        if not path.exists():
            raise RuntimeError(f"Audio file not found: {audio_path}")

        status_text = (
            "[cyan]Transcribing audio via Groq (whisper-large-v3)…[/cyan]"
        )
        with console.status(status_text):
            try:
                with path.open("rb") as audio_file:
                    translation = client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=audio_file,
                    )
                transcript = translation.text
            except Exception as exc:
                raise RuntimeError(
                    f"Groq Whisper transcription failed: {exc}"
                ) from exc

        transcript = transcript.strip()
        transcript = _clean_fillers(transcript)

        console.print("[green]✓ Transcribed via Groq[/green]")
        return transcript


def _clean_fillers(text: str) -> str:
    """Strip common filler words and normalize whitespace.

    Args:
        text: Raw transcript.

    Returns:
        Cleaned transcript string.
    """
    _FILLERS = {"um", "uh", "hmm", "er", "ah", "like"}
    words = text.split()
    cleaned = [w for w in words if w.lower() not in _FILLERS]
    return " ".join(cleaned)
