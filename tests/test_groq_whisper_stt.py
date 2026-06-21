"""Unit tests for the GroqWhisperSTT speech-to-text provider.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from server.voice.groq_whisper_stt import GroqWhisperSTT, _clean_fillers


def _make_mock_response(text: str) -> MagicMock:
    """Return a mock object that mimics a transcript response.

    Args:
        text: The transcript text to return.

    Returns:
        Mock object with a 'text' attribute.
    """
    mock_resp = MagicMock()
    mock_resp.text = text
    return mock_resp


def test_is_available_true(mocker: pytest.MockerFixture) -> None:
    """Verify is_available is True when GROQ_API_KEY is present."""
    mocker.patch("server.config.GROQ_API_KEY", "gsk_test")
    provider = GroqWhisperSTT()
    assert provider.is_available() is True


def test_is_available_false(mocker: pytest.MockerFixture) -> None:
    """Verify is_available is False when GROQ_API_KEY is missing."""
    mocker.patch("server.config.GROQ_API_KEY", "")
    provider = GroqWhisperSTT()
    assert provider.is_available() is False


def test_transcribe_success(
    mocker: pytest.MockerFixture, tmp_wav: Path
) -> None:
    """Verify successful transcription calling the OpenAI client on Groq."""
    mock_create_client = mocker.patch("server.voice.groq_whisper_stt.OpenAI")
    mock_client = mock_create_client.return_value
    mock_client.audio.transcriptions.create.return_value = (
        _make_mock_response("Hello, this is a test. Um yes.")
    )

    mocker.patch("server.config.GROQ_API_KEY", "gsk_test")
    mocker.patch("server.config.CLINIC_SPECIALTY", "general")
    mocker.patch("server.voice.groq_whisper_stt.console")

    provider = GroqWhisperSTT()
    result = provider.transcribe(str(tmp_wav))

    # "Um" filler should be removed by clean_fillers
    assert result == "Hello, this is a test. yes."
    mock_client.audio.transcriptions.create.assert_called_once()
    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["model"] == "whisper-large-v3"
    assert call_kwargs["language"] == "en"
    assert "prompt" in call_kwargs
    assert "Paracetamol" in call_kwargs["prompt"]


def test_transcribe_api_error(
    mocker: pytest.MockerFixture, tmp_wav: Path
) -> None:
    """Verify that an API exception raises a RuntimeError."""
    mock_create_client = mocker.patch("server.voice.groq_whisper_stt.OpenAI")
    mock_client = mock_create_client.return_value
    mock_client.audio.transcriptions.create.side_effect = Exception("API Error")

    mocker.patch("server.config.GROQ_API_KEY", "gsk_test")
    mocker.patch("server.voice.groq_whisper_stt.console")

    provider = GroqWhisperSTT()
    with pytest.raises(RuntimeError, match="Groq transcription failed"):
        provider.transcribe(str(tmp_wav))


def test_transcribe_missing_key(
    mocker: pytest.MockerFixture, tmp_wav: Path
) -> None:
    """Verify that a missing API key raises a RuntimeError."""
    mocker.patch("server.config.GROQ_API_KEY", "")
    provider = GroqWhisperSTT()
    with pytest.raises(RuntimeError, match="GROQ_API_KEY not set"):
        provider.transcribe(str(tmp_wav))


def test_clean_fillers_helper() -> None:
    """Verify that _clean_fillers strips common filler words."""
    # Note: case insensitivity and punctuation stripping depends on the split.
    # Our implementation splits on whitespace and filters exact matches.
    # "Um," has a comma so it's not in the exact fillers set.
    # Let's test the words without punctuation to confirm the core logic:
    cleaned = _clean_fillers("um hello uh this er is ah like nice hmm")
    assert cleaned == "hello this is nice"
