"""
Central configuration for the PRESCRIPTION server.
All provider toggles live here — change one string to swap engines.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (parent of this file's package dir)
load_dotenv(Path(__file__).parent.parent / ".env")

# ── Project Paths ────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent
CSV_PATH = (
    ROOT_DIR
    / "archive (2)"
    / "A_Z_medicines_dataset_of_India.csv"
)
OUTPUT_DIR = ROOT_DIR / "server" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── STT Plugin ───────────────────────────────────────────────────────
# Options: "faster_whisper" | "openai_whisper" | "groq_whisper"
STT_PROVIDER: str = os.getenv("STT_PROVIDER", "faster_whisper")

# tiny | base | small | medium | large
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")

# Options: "general" | "pediatrics" | "dermatology" | "cardiology"
CLINIC_SPECIALTY: str = os.getenv("CLINIC_SPECIALTY", "general")

# ── LLM Plugin ───────────────────────────────────────────────────────
# Options: "ollama" | "groq"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")

OLLAMA_MODEL: str = "llama3.2:3b"
OLLAMA_BASE_URL: str = "http://localhost:11434"

GROQ_MODEL: str = "llama-3.3-70b-versatile"
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# ── Audio Settings ───────────────────────────────────────────────────
AUDIO_SAMPLE_RATE: int = 16_000   # Hz — Whisper standard
AUDIO_CHANNELS: int = 1           # Mono
AUDIO_MAX_SECONDS: int = 60       # Hard upper bound; timer auto-stops

# ── Fuzzy Search ─────────────────────────────────────────────────────
# Min score (0-100) to accept a medicine match
FUZZY_SCORE_THRESHOLD: int = 75
# Return top K candidates per medicine
FUZZY_TOP_K: int = 3

# ── PDF / Clinic Branding ────────────────────────────────────────────
CLINIC_NAME: str = "PRESCRIPTION CLINIC"
CLINIC_ADDRESS: str = "123 Medical Street, Your City"
CLINIC_PHONE: str = "+91-XXXXXXXXXX"
DOCTOR_NAME: str = "Dr. Physician"
DOCTOR_REG: str = "REG/XXXX/XXXX"
