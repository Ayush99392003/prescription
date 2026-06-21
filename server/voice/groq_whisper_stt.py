"""STT provider using Groq cloud API via OpenAI transcriptions endpoint.
"""

from __future__ import annotations

from openai import OpenAI
from rich.console import Console

from server import config
from server.voice.base import STTProvider

console = Console()


class GroqWhisperSTT(STTProvider):
    """Transcribes audio using Groq's high-speed Whisper cloud API.

    Requires a valid GROQ_API_KEY env var and internet access.
    """

    def is_available(self) -> bool:
        """Return True if GROQ_API_KEY is configured."""
        return bool(config.GROQ_API_KEY)

    def transcribe(self, audio_path: str) -> str:
        """Transcribe an audio file using Groq's Whisper API.

        Args:
            audio_path: Path to the audio file.

        Returns:
            Cleaned transcript string.

        Raises:
            RuntimeError: If key missing or API call fails.
        """
        if not self.is_available():
            raise RuntimeError(
                "GROQ_API_KEY not set. "
                "Add it to your .env file: GROQ_API_KEY=gsk_..."
            )

        client = OpenAI(
            api_key=config.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )

        from server.voice.prompts import get_initial_prompt  # noqa: PLC0415
        prompt_str = get_initial_prompt(config.CLINIC_SPECIALTY)

        with console.status(
            "[cyan]Transcribing via Groq API (whisper-large-v3)…[/cyan]"
        ):
            try:
                with open(audio_path, "rb") as f:
                    response = client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=f,
                        language="en",
                        prompt=prompt_str,
                    )
                transcript = response.text.strip()
            except Exception as exc:
                raise RuntimeError(
                    f"Groq transcription failed: {exc}"
                ) from exc

        transcript = _clean_fillers(transcript)
        console.print("[green]✓ Transcribed via Groq API[/green]")
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
