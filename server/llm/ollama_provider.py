"""
LLM provider using Ollama local inference.
Requires Ollama daemon running at localhost:11434.
Default model: llama3.2:3b — change in config.py.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from rich.console import Console

from server import config
from server.core.schemas import PrescriptionSchema
from server.llm.base import LLMProvider

console = Console()

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
  "notes": "string"
}

Rules:
- Output ONLY the raw JSON object.
- Use "Not specified" for missing string values.
- Extract every drug mentioned into the medications list.
- Use exact brand/generic names as spoken.
"""


class OllamaProvider(LLMProvider):
    """
    Parses prescriptions using a locally-running Ollama model.
    No internet required — fully air-gapped capable.
    """

    def is_available(self) -> bool:
        """Ping Ollama to verify the daemon is running."""
        try:
            resp = httpx.get(
                config.OLLAMA_BASE_URL,
                timeout=2.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def parse_prescription(
        self, transcript: str
    ) -> PrescriptionSchema:
        """
        Send transcript to Ollama and parse structured JSON.

        Args:
            transcript: Cleaned STT voice transcript.

        Returns:
            Validated PrescriptionSchema.

        Raises:
            RuntimeError: If Ollama unreachable or parse fails.
        """
        try:
            import ollama  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "ollama package not installed. Run: uv add ollama"
            ) from exc

        if not self.is_available():
            raise RuntimeError(
                "Ollama daemon not running. "
                f"Start it — expected at {config.OLLAMA_BASE_URL}"
            )

        user_msg = (
            f"Transcript:\n{transcript}\n\n"
            "Extract the prescription data as JSON."
        )

        with console.status(
            f"[cyan]Calling Ollama "
            f"([bold]{config.OLLAMA_MODEL}[/bold])…[/cyan]"
        ):
            try:
                response = ollama.chat(
                    model=config.OLLAMA_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": _SYSTEM_PROMPT,
                        },
                        {"role": "user", "content": user_msg},
                    ],
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Ollama call failed: {exc}"
                ) from exc

        raw: str = response["message"]["content"]
        console.print("[green]✓ Ollama response received[/green]")
        return _parse_llm_response(raw)


def _extract_json_block(content: str) -> str:
    """
    Extract the first balanced JSON object from an LLM response.

    Handles any preamble text, nested markdown fences, or mixed
    content by scanning for the first ``{`` and matching its closing
    ``}`` via a simple brace-depth counter.

    Args:
        content: Raw LLM output string.

    Returns:
        The extracted JSON substring.

    Raises:
        RuntimeError: If no valid JSON object boundary is found.
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
    Extract and validate JSON from a raw LLM response string.

    Uses brace-depth scanning instead of ``startswith('```')`` so
    that any preamble text or malformed markdown fences are safely
    ignored.

    Args:
        content: Raw LLM output (may include markdown fences or
                 explanatory text before the JSON block).

    Returns:
        Validated PrescriptionSchema.

    Raises:
        RuntimeError: If JSON is malformed or schema mismatch.
    """
    raw_json = _extract_json_block(content)

    try:
        data: dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"LLM returned invalid JSON: {exc}\n"
            f"Raw output:\n{content[:300]}"
        ) from exc

    try:
        return PrescriptionSchema.model_validate(data)
    except Exception as exc:
        raise RuntimeError(
            f"Schema validation failed: {exc}"
        ) from exc
