"""Paths for the GSM8K encryption pipeline."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GSM8K_CSV = DATA_DIR / "gsm8k.csv"
QUESTIONS_CSV = DATA_DIR / "questions.csv"
ENCRYPTED_DIR = DATA_DIR / "encrypted"
DATA_README = DATA_DIR / "README.md"
PILOT_RESULTS = ROOT / "pilot_results.csv"
PILOT_PROMPTS = ROOT / "pilot_prompts.jsonl"
PILOT_NOTES = ROOT / "pilot_notes.md"

# Local cleaned file, if the user already has one. Official download is the fallback.
CLEAN_CSV_CANDIDATES = (
    DATA_DIR / "clean_math_data_gsm_svamp_math500.csv",
    Path.home() / "Downloads" / "clean_math_data_gsm_svamp_math500.csv",
    Path.home() / "Documents" / "clean_math_data_gsm_svamp_math500.csv",
)

OFFICIAL_GSM8K_TEST_URL = (
    "https://raw.githubusercontent.com/openai/grade-school-math/"
    "master/grade_school_math/data/test.jsonl"
)
