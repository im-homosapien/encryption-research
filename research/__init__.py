"""Encrypted-math research pipeline.

``python -m research`` builds the GSM8K table.
``python -m research --pilot`` scores a 30-question pilot.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
