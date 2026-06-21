"""
Abstract base class for all LLM provider plugins.
New LLM engines must implement this interface to plug in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from server.core.schemas import PrescriptionSchema


class LLMProvider(ABC):
    """
    Plugin interface for LLM-based prescription parsers.

    Usage::

        provider = OllamaProvider()
        schema = provider.parse_prescription("Patient John, 35...")
    """

    @abstractmethod
    def parse_prescription(
        self, transcript: str
    ) -> PrescriptionSchema:
        """
        Parse a raw voice transcript into a structured schema.

        Args:
            transcript: Cleaned text from the STT engine.

        Returns:
            A validated PrescriptionSchema instance.

        Raises:
            RuntimeError: On LLM call failure or JSON parse error.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the underlying model/service is reachable.

        Returns:
            True if the provider is ready to handle requests.
        """
        ...
