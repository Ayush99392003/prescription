# PRESCRIPTION — AI-Powered Voice Medical Assistant

A sophisticated, privacy-focused Python application that converts
doctor-patient voice sessions into professional, validated medical
prescriptions.

---

## 🎯 Project Intention

To provide healthcare providers with a zero-friction way to generate
digital, printable prescriptions using high-speed Voice-to-JSON
parsing, cross-referenced against a database of 30,000+ Indian
medicines.

---

## 🏗️ Architecture

The system uses a **5-layer modular stack**, all wired through a
single `PrescriptionSession` data bus:

| Layer | Module | Technology |
|-------|--------|------------|
| Terminal Dashboard | `server/ui/dashboard.py` | `rich` |
| Voice Processing | `server/voice/` | `faster-whisper` / OpenAI Whisper |
| Hybrid AI Brain | `server/llm/` | Ollama (local) · Groq (cloud) |
| Data Engine | `server/data/` | in-memory CSV + `rapidfuzz` |
| PDF Export | `server/export/` | `fpdf2` |

### Swappable providers (edit `server/config.py`)

```
STT_PROVIDER = "faster_whisper"  # or "openai_whisper"
LLM_PROVIDER = "ollama"          # or "groq"
```

---

## 🔄 Core Pipeline

```
Record → Transcribe → LLM Parse → Validate → Review → Export PDF
  1           2            3           4          5          6
```

1. **Record** — Microphone captured via `sounddevice`; hard
   upper-bound timer prevents unbounded recording.
2. **Transcribe** — Local Whisper converts speech to text; filler
   words (`um`, `uh`) stripped automatically.
3. **LLM Parse** — Transcript sent to Ollama or Groq; response
   parsed with brace-depth JSON extractor (immune to any LLM
   preamble text).
4. **Validate** — Each medicine fuzzy-matched against the
   `A_Z_medicines_dataset_of_India.csv` (30,000+ entries,
   deduplicated in-memory index).
5. **Review** — Rich terminal table displayed; user confirms export.
6. **Export** — A4 PDF generated with clinic branding, patient info,
   full medication table (no truncation), and doctor's signature line.

---

## 📋 Product Requirements

- **Privacy** — Local-first processing; Ollama mode is fully
  air-gapped.
- **Speed** — End-to-end target under 10 seconds.
- **Accuracy** — 90%+ drug name identification via phonetic fuzzy
  matching (`rapidfuzz.WRatio`).
- **Safety** — No medical data silently truncated in the PDF output.
- **Auditability** — Each session produces a uniquely timestamped
  audio file and PDF.

---

## 🛠️ Quick Start

```bash
# Install dependencies (Python 3.11+)
uv sync

# Copy and configure environment
cp .env.example .env          # set GROQ_API_KEY if using Groq
```

### Terminal Interface

To run the terminal-based interactive dashboard:

```bash
uv run prescription
# or
uv run python -m server.main
```

### Web Interface (Server & Client)

To run the Web UI dashboard (starts the FastAPI backend which serves the
frontend SPA client):

```bash
uv run prescription-web
# or
uv run python -m server.web.app
```

Once running, open your browser and navigate to:
[http://localhost:8000](http://localhost:8000)

---

## 🧪 Tests

```bash
uv run pytest tests/ -v
```

**48 tests · 0 failures** covering:

| Test file | What it covers |
|-----------|----------------|
| `test_recorder.py` | Timer auto-stop, unique filenames, mic errors |
| `test_llm_parsing.py` | Brace-depth JSON extractor, Groq Responses API integration, schema validation |
| `test_pdf_generator.py` | `_safe_text` Latin-1 sanitiser, `_measure_cell_height`, full PDF generation, long instructions |
| `test_indexer.py` | Deduplication, last-write-wins, progress accuracy, idempotency |
| `test_fuzzy_matcher.py` | Exact match, phonetic variants, below-threshold, duplicate regression |

---

## 🩺 Logic Fixes Applied

| # | Fix | File |
|---|-----|------|
| 1 | Bounded recording via `threading.Timer` | `voice/recorder.py` |
| 2 | Brace-depth JSON extractor replaces brittle `startswith` | `llm/ollama_provider.py` |
| 3 | `multi_cell()` replaces `str(val)[:20]` truncation in PDF | `export/pdf_generator.py` |
| 4 | Progress bar advances by actual row byte length | `data/indexer.py` |
| 5 | `seen` set deduplicates `_NAMES` list | `data/indexer.py` |
| 6 | Per-session timestamped audio filenames | `voice/recorder.py`, `config.py` |
| 7 | Groq migrated to `openai.responses.create()` via Responses API | `llm/groq_provider.py` |
| 8 | `_safe_text()` Latin-1 sanitiser prevents PDF Unicode crashes | `export/pdf_generator.py` |
| 9 | `.env` auto-loaded via `python-dotenv` | `config.py` |

---

*This document serves as the primary hub for the PRESCRIPTION project.*

