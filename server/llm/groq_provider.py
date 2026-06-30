"""
LLM provider using Groq cloud API via the OpenAI Responses endpoint.

Uses the openai SDK pointed at Groq's OpenAI-compatible base URL:
    https://api.groq.com/openai/v1

Requires GROQ_API_KEY in the environment (auto-loaded from .env).
Default model: llama-3.3-70b-versatile — change in config.py.
"""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI
from rich.console import Console

from server import config
from server.core.schemas import PrescriptionSchema
from server.llm.base import LLMProvider

console = Console()

# Groq OpenAI-compatible base URL
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_SYSTEM_PROMPT = """\
You are a medical transcription assistant.
Extract structured data from a doctor's voice transcript.
Return ONLY a valid JSON object — no markdown, no explanation.

JSON schema:
{
  "patient": {
    "name": "string",
    "age": "string or null",
    "gender": "string or null",
    "id": "string or null"
  },
  "complaints": ["string"],
  "diagnosis": "string",
  "medications": [
    {
      "name": "string",
      "dosage": "string",
      "frequency": "string",
      "duration": "string",
      "instructions": "string"
    }
  ],
  "investigations": ["string"],
  "notes": "string"
}

Rules:
- Output ONLY the raw JSON object.
- Use "Not specified" for missing string values.
- Extract symptoms / chief complaints into the complaints list. Include the
  full symptom description along with any specified durations, severity,
  or remarks (e.g., "vomiting for 4 days") instead of single keywords.
- Extract ordered tests/scans/diagnostics into the investigations list.
- Extract every drug mentioned into the medications list.
- Use exact brand/generic names as spoken.
"""


class GroqProvider(LLMProvider):
    """
    Parses prescriptions via the OpenAI Responses API routed through
    Groq's ultra-low-latency inference endpoint.

    Uses ``openai.responses.create()`` (not chat.completions) as
    mandated by the project's LLM integration rule.
    Requires internet and a valid GROQ_API_KEY env var.
    """

    def is_available(self) -> bool:
        """Return True if the Groq API key is configured."""
        return bool(config.GROQ_API_KEY)

    def parse_prescription(
        self, transcript: str
    ) -> PrescriptionSchema:
        """
        Send transcript to Groq via openai.responses.create() and
        parse the structured JSON response.

        Args:
            transcript: Cleaned STT voice transcript.

        Returns:
            Validated PrescriptionSchema.

        Raises:
            RuntimeError: If API key missing, call fails, or parse
                          fails.
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

        user_msg = (
            f"Transcript:\n{transcript}\n\n"
            "Extract the prescription data as JSON."
        )

        with console.status(
            f"[cyan]Calling Groq via Responses API "
            f"([bold]{config.GROQ_MODEL}[/bold])...[/cyan]"
        ):
            try:
                response = client.responses.create(
                    model=config.GROQ_MODEL,
                    instructions=_SYSTEM_PROMPT,
                    input=user_msg,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Groq Responses API call failed: {exc}"
                ) from exc

        raw: str = response.output_text or ""
        console.print("[green]Groq response received[/green]")
        return _parse_llm_response(raw)


def _extract_json_block(content: str) -> str:
    """
    Extract the first balanced JSON object from an LLM response.
    """
    start = content.find("{")
    if start == -1:
        raise RuntimeError(
            "LLM output contains no JSON object (no '{' found).\n"
            f"Raw output:\n{content[:300]}"
        )

    depth = 0
    in_string = False
    escape_next = False

    for idx in range(start, len(content)):
        ch = content[idx]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return content[start: idx + 1]

    raise RuntimeError(
        "LLM output has unbalanced braces — cannot extract JSON.\n"
        f"Raw output:\n{content[:300]}"
    )


def _parse_llm_response(content: str) -> PrescriptionSchema:
    """
    Validate a raw JSON string against the PrescriptionSchema.

    Extracts balanced JSON first to handle markdown fences or preamble.

    Args:
        content: Raw LLM output string.

    Returns:
        Validated PrescriptionSchema.

    Raises:
        RuntimeError: On JSON parse or schema validation failure.
    """
    raw_json = _extract_json_block(content)
    try:
        data: dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Groq returned invalid JSON: {exc}\n"
            f"Raw output:\n{content[:300]}"
        ) from exc

    try:
        return PrescriptionSchema.model_validate(data)
    except Exception as exc:
        raise RuntimeError(
            f"Schema validation failed: {exc}"
        ) from exc
