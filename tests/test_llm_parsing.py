"""
Tests for LLM JSON parsing — covers Fix 2 (brittle JSON extraction).

Exercises _extract_json_block and _parse_llm_response directly,
plus validates the Groq provider's simpler strip-based parser still
handles clean JSON correctly.
"""

from __future__ import annotations

import json

import pytest

# ── Helpers ──────────────────────────────────────────────────────────

_VALID_JSON = {
    "patient": {
        "name": "Priya Sharma",
        "age": "28",
        "gender": "F",
        "id": None,
    },
    "complaints": ["Headache", "Fever"],
    "diagnosis": "Viral Fever",
    "medications": [
        {
            "name": "Paracetamol",
            "dosage": "500mg",
            "frequency": "TDS",
            "duration": "3 days",
            "instructions": "After meals",
        }
    ],
    "investigations": ["Dengue NS1 Antigen"],
    "notes": "Drink plenty of fluids.",
}

_VALID_JSON_STR = json.dumps(_VALID_JSON)


# ── _extract_json_block ───────────────────────────────────────────────


class TestExtractJsonBlock:
    """Tests for the brace-depth JSON extractor (Fix 2 — Ollama)."""

    def test_plain_json(self):
        """Clean JSON with no preamble is returned verbatim."""
        from server.llm.ollama_provider import _extract_json_block

        result = _extract_json_block(_VALID_JSON_STR)
        assert json.loads(result) == _VALID_JSON

    def test_json_with_preamble_text(self):
        """
        LLM preamble before the object must be ignored — this was the
        bug that caused startswith('```') to miss the JSON.
        """
        from server.llm.ollama_provider import _extract_json_block

        raw = (
            "Here is the extracted prescription as requested:\n\n"
            + _VALID_JSON_STR
            + "\n\nLet me know if you need changes."
        )
        result = _extract_json_block(raw)
        assert json.loads(result) == _VALID_JSON

    def test_json_inside_markdown_fence(self):
        """Full markdown fence with preamble must be handled."""
        from server.llm.ollama_provider import _extract_json_block

        raw = "Sure!\n```json\n" + _VALID_JSON_STR + "\n```"
        result = _extract_json_block(raw)
        assert json.loads(result) == _VALID_JSON

    def test_json_with_nested_braces_in_string(self):
        """
        Escaped braces inside a string value must NOT confuse the
        brace-depth counter.
        """
        from server.llm.ollama_provider import _extract_json_block

        tricky = {"key": 'value with {"nested": "json"} inside'}
        raw = json.dumps(tricky)
        result = _extract_json_block(raw)
        assert json.loads(result) == tricky

    def test_no_opening_brace_raises(self):
        """If there is no '{' at all, RuntimeError must be raised."""
        from server.llm.ollama_provider import _extract_json_block

        with pytest.raises(RuntimeError, match="no '\\{' found"):
            _extract_json_block("This is plain text without JSON.")

    def test_unbalanced_braces_raises(self):
        """Unmatched '{' must raise RuntimeError."""
        from server.llm.ollama_provider import _extract_json_block

        with pytest.raises(RuntimeError, match="unbalanced braces"):
            _extract_json_block('{ "key": "value" ')


# ── _parse_llm_response (Ollama) ──────────────────────────────────────


class TestOllamaParseResponse:
    """End-to-end parsing via the Ollama provider's _parse_llm_response."""

    def test_valid_clean_json(self):
        """Plain JSON string must parse into PrescriptionSchema."""
        from server.llm.ollama_provider import _parse_llm_response

        schema = _parse_llm_response(_VALID_JSON_STR)
        assert schema.patient.name == "Priya Sharma"
        assert schema.complaints == ["Headache", "Fever"]
        assert len(schema.medications) == 1
        assert schema.medications[0].name == "Paracetamol"
        assert schema.investigations == ["Dengue NS1 Antigen"]

    def test_json_with_preamble_parses(self):
        """Preamble text before the JSON must not prevent parsing."""
        from server.llm.ollama_provider import _parse_llm_response

        raw = "Sure, here it is:\n" + _VALID_JSON_STR
        schema = _parse_llm_response(raw)
        assert schema.patient.name == "Priya Sharma"

    def test_invalid_json_raises_runtime_error(self):
        """Non-parseable text after '{' must raise RuntimeError."""
        from server.llm.ollama_provider import _parse_llm_response

        with pytest.raises(RuntimeError, match="invalid JSON"):
            _parse_llm_response("{ this is not valid json }")

    def test_schema_validation_failure_raises_runtime_error(self):
        """
        Valid JSON that does NOT match PrescriptionSchema must raise
        RuntimeError (not a raw Pydantic ValidationError).
        """
        from server.llm.ollama_provider import _parse_llm_response

        bad = json.dumps({"unexpected_key": 42})
        # Pydantic will accept extra keys with defaults, so we test a
        # case where 'medications' has a wrong type.
        bad_meds = json.dumps(
            {**_VALID_JSON, "medications": "not a list"}
        )
        with pytest.raises(RuntimeError, match="Schema validation failed"):
            _parse_llm_response(bad_meds)


# ── _parse_llm_response (Groq) ────────────────────────────────────────


class TestGroqParseResponse:
    """
    Groq returns clean JSON via the OpenAI Responses API
    (openai.responses.create).  Tests here cover the JSON parser
    directly; integration tests for the full provider call are in
    TestGroqProviderIntegration below.
    """

    def test_valid_clean_json(self):
        from server.llm.groq_provider import _parse_llm_response

        schema = _parse_llm_response(_VALID_JSON_STR)
        assert schema.diagnosis == "Viral Fever"

    def test_invalid_json_raises_runtime_error(self):
        from server.llm.groq_provider import _parse_llm_response

        with pytest.raises(RuntimeError, match="invalid JSON"):
            _parse_llm_response("{ \"broken\": oops }")

    def test_schema_mismatch_raises_runtime_error(self):
        from server.llm.groq_provider import _parse_llm_response

        bad = json.dumps({**_VALID_JSON, "medications": "wrong"})
        with pytest.raises(RuntimeError, match="Schema validation failed"):
            _parse_llm_response(bad)


# ── GroqProvider.parse_prescription — integration ─────────────────────


class TestGroqProviderIntegration:
    """
    Integration tests for GroqProvider.parse_prescription().

    The OpenAI client is fully mocked so no real network call is made.
    Verifies that openai.responses.create() is called with the correct
    model/instructions/input, and that the output_text is parsed into
    a PrescriptionSchema.
    """

    def _make_mock_response(self, text: str):
        """Return a mock object that mimics an openai Response."""
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.output_text = text
        return mock_resp

    def test_parse_prescription_calls_responses_create(
        self, mocker
    ):
        """
        GroqProvider must call client.responses.create (not
        chat.completions.create).
        """
        from server.llm.groq_provider import GroqProvider

        mock_create = mocker.patch(
            "server.llm.groq_provider.OpenAI"
        )
        mock_client = mock_create.return_value
        mock_client.responses.create.return_value = (
            self._make_mock_response(_VALID_JSON_STR)
        )

        mocker.patch("server.config.GROQ_API_KEY", "gsk_test")
        mocker.patch("server.llm.groq_provider.console")

        provider = GroqProvider()
        schema = provider.parse_prescription("Patient transcript here.")

        # Must have called responses.create, NOT chat.completions
        mock_client.responses.create.assert_called_once()
        call_kwargs = mock_client.responses.create.call_args.kwargs
        assert "instructions" in call_kwargs, (
            "System prompt must be passed as 'instructions='"
        )
        assert "input" in call_kwargs, (
            "User transcript must be passed as 'input='"
        )
        assert schema.patient.name == "Priya Sharma"
        assert schema.complaints == ["Headache", "Fever"]
        assert schema.investigations == ["Dengue NS1 Antigen"]

    def test_parse_prescription_uses_configured_model(self, mocker):
        """The model name from config.GROQ_MODEL must be forwarded."""
        from server.llm.groq_provider import GroqProvider

        mock_create = mocker.patch(
            "server.llm.groq_provider.OpenAI"
        )
        mock_client = mock_create.return_value
        mock_client.responses.create.return_value = (
            self._make_mock_response(_VALID_JSON_STR)
        )
        mocker.patch("server.config.GROQ_API_KEY", "gsk_test")
        mocker.patch(
            "server.config.GROQ_MODEL", "llama-3.3-70b-versatile"
        )
        mocker.patch("server.llm.groq_provider.console")

        GroqProvider().parse_prescription("Test.")

        call_kwargs = mock_client.responses.create.call_args.kwargs
        assert call_kwargs["model"] == "llama-3.3-70b-versatile"

    def test_api_exception_raises_runtime_error(self, mocker):
        """Any exception from the API must be wrapped in RuntimeError."""
        from server.llm.groq_provider import GroqProvider

        mock_create = mocker.patch(
            "server.llm.groq_provider.OpenAI"
        )
        mock_client = mock_create.return_value
        mock_client.responses.create.side_effect = Exception(
            "Network error"
        )
        mocker.patch("server.config.GROQ_API_KEY", "gsk_test")
        mocker.patch("server.llm.groq_provider.console")

        with pytest.raises(
            RuntimeError, match="Groq Responses API call failed"
        ):
            GroqProvider().parse_prescription("Test.")

    def test_missing_api_key_raises_runtime_error(self, mocker):
        """RuntimeError when GROQ_API_KEY is empty string."""
        from server.llm.groq_provider import GroqProvider

        mocker.patch("server.config.GROQ_API_KEY", "")

        with pytest.raises(RuntimeError, match="GROQ_API_KEY not set"):
            GroqProvider().parse_prescription("Test.")

    def test_is_available_false_without_key(self, mocker):
        from server.llm.groq_provider import GroqProvider

        mocker.patch("server.config.GROQ_API_KEY", "")
        assert GroqProvider().is_available() is False

    def test_is_available_true_with_key(self, mocker):
        from server.llm.groq_provider import GroqProvider

        mocker.patch("server.config.GROQ_API_KEY", "gsk_test")
        assert GroqProvider().is_available() is True

