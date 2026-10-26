"""Extract a final answer and score decryption against the original question."""

from __future__ import annotations

import re
from collections import Counter

_FINAL_RE = re.compile(r"Final Answer:\s*\$?(-?[\d,]*\.?\d+)")
_DECRYPT_RE = re.compile(r"^Decrypted(?: Question)?:\s*(.+)$", re.MULTILINE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def extract_pred(text: str) -> str | None:
    """Return the last Final Answer number, or None when the line is missing."""
    found = _FINAL_RE.findall(text or "")
    if not found:
        return None
    return found[-1].replace(",", "")


def answers_match(pred: str | None, gold: str) -> bool:
    if pred is None:
        return False
    try:
        return abs(float(pred) - float(str(gold).replace(",", "").replace("$", ""))) < 1e-4
    except ValueError:
        return False


def extract_decrypted(text: str) -> str | None:
    found = _DECRYPT_RE.findall(text or "")
    if not found:
        return None
    return found[-1].strip()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def decryption_exact(recovered: str | None, original: str) -> bool:
    if recovered is None:
        return False
    return normalize(recovered) == normalize(original)


def token_f1(pred: str | None, gold: str) -> float:
    if not pred:
        return 0.0
    pred_tokens = _TOKEN_RE.findall(pred.casefold())
    gold_tokens = _TOKEN_RE.findall(gold.casefold())
    if not pred_tokens or not gold_tokens:
        return 0.0
    overlap = sum((Counter(pred_tokens) & Counter(gold_tokens)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def score_completion(
    raw: str,
    gold_answer: str,
    gold_question: str | None,
) -> dict[str, object]:
    """Score one completion.

    ``gold_question`` is None for plaintext, where decryption is not applicable.
    """
    pred = extract_pred(raw)
    scored: dict[str, object] = {
        "pred": pred,
        "correct": answers_match(pred, gold_answer),
        "decryption_exact": None,
        "decryption_f1": None,
    }
    if gold_question is not None:
        recovered = extract_decrypted(raw)
        scored["decryption_exact"] = bool(
            recovered is not None and normalize(recovered) == normalize(gold_question)
        )
        scored["decryption_f1"] = token_f1(recovered, gold_question)
    return scored
