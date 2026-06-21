"""
Abstract base class for all Speech-To-Text provider plugins.
New STT engines must implement this interface to plug in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class STTProvider(ABC):
    """
    Plugin interface for Speech-To-Text engines.

    Usage::

        provider = FasterWhisperSTT()
        transcript = provider.transcribe("path/to/audio.wav")
    """

    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """
        Convert an audio file to a cleaned text transcript.

        Args:
            audio_path: Absolute path to a WAV file (16kHz mono).

        Returns:
            Cleaned text transcript string.

        Raises:
            RuntimeError: If transcription fails.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the underlying model/service is ready.

        Returns:
            True if the provider can process audio.
        """
        ...
