"""Hand-written completions used to check extraction when no model is loaded."""

from __future__ import annotations

from research.score import score_completion

_EXAMPLE_Q = "Tom has 5 apples and buys 3 more. How many apples does he have?"

# Literal completions. These are not produced from GSM8K rows.
HANDWRITTEN: tuple[dict[str, object], ...] = (
    {
        "name": "decrypt_and_correct",
        "raw": (
            "The letters are shifted.\n"
            f"Decrypted: {_EXAMPLE_Q}\n"
            "Final Answer: 8"
        ),
        "gold_answer": "8",
        "gold_question": _EXAMPLE_Q,
        "pred": "8",
        "correct": True,
        "decryption_exact": True,
        "f1": 1.0,
    },
    {
        "name": "dollar_and_commas",
        "raw": "Final Answer: $1,000",
        "gold_answer": "1000",
        "gold_question": None,
        "pred": "1000",
        "correct": True,
    },
    {
        "name": "missing_final_answer",
        "raw": "I think the answer is eight.",
        "gold_answer": "8",
        "gold_question": _EXAMPLE_Q,
        "pred": None,
        "correct": False,
        "decryption_exact": False,
        "f1": 0.0,
    },
    {
        "name": "guess_without_decrypt",
        "raw": "Final Answer: 3",
        "gold_answer": "8",
        "gold_question": _EXAMPLE_Q,
        "pred": "3",
        "correct": False,
        "decryption_exact": False,
        "f1": 0.0,
    },
    {
        "name": "partial_decrypt",
        "raw": (
            "Decrypted: Tom has five apples and buys three more. How many apples does he have?\n"
            "Final Answer: 8"
        ),
        "gold_answer": "8",
        "gold_question": _EXAMPLE_Q,
        "pred": "8",
        "correct": True,
        "decryption_exact": False,
        "f1_min": 0.5,
        "f1_max": 0.99,
    },
    {
        "name": "last_final_answer_wins",
        "raw": "Final Answer: 4\nFinal Answer: 8",
        "gold_answer": "8",
        "gold_question": None,
        "pred": "8",
        "correct": True,
    },
    {
        "name": "negative_answer",
        "raw": "Final Answer: -3",
        "gold_answer": "-3",
        "gold_question": None,
        "pred": "-3",
        "correct": True,
    },
)


def run_handwritten_checks() -> list[str]:
    """Score the literal completions. Raise if extraction drifts."""
    passed: list[str] = []
    for case in HANDWRITTEN:
        raw = str(case["raw"])
        gold_answer = str(case["gold_answer"])
        gold_question = case["gold_question"]
        question = gold_question if isinstance(gold_question, str) else None
        scored = score_completion(raw, gold_answer, question)
        name = str(case["name"])
        if scored["pred"] != case["pred"]:
            raise AssertionError(f"{name}: pred {scored['pred']!r} != {case['pred']!r}")
        if scored["correct"] != case["correct"]:
            raise AssertionError(f"{name}: correct {scored['correct']!r} != {case['correct']!r}")
        if "decryption_exact" in case and scored["decryption_exact"] != case["decryption_exact"]:
            raise AssertionError(
                f"{name}: decryption_exact {scored['decryption_exact']!r} != {case['decryption_exact']!r}"
            )
        f1 = scored["decryption_f1"]
        if "f1" in case:
            if not isinstance(f1, float) or abs(f1 - float(case["f1"])) > 1e-9:
                raise AssertionError(f"{name}: f1 {f1!r} != {case['f1']!r}")
        if "f1_min" in case:
            if not isinstance(f1, float) or f1 < float(case["f1_min"]) or f1 > float(case["f1_max"]):
                raise AssertionError(f"{name}: f1 {f1!r} outside expected range")
        passed.append(name)
    return passed


def _item_number(item_id: str) -> int:
    return int(item_id.rsplit("_", 1)[-1])


def mock_completion(row: dict[str, str], with_example: bool) -> str:
    """Deterministic stand-in for a model completion.

    The text is scripted from the row so the scorer and the grouped table can
    be checked. It is not a language-model output.
    """
    number = _item_number(row["id"])
    condition = row["condition"]
    method = row["encryption_method"]
    answer = row["answer"]
    original = row["original_question"]
    if condition == "plaintext":
        if number % 5 == 0 and not with_example:
            return "The total comes out even, but this completion omits the required final line."
        return f"Working from the problem.\nFinal Answer: {answer}"
    if condition == "disclosed" and method == "caesar_3":
        if number % 2 == 0:
            return f"Shift each letter backward.\nDecrypted: {original}\nFinal Answer: {answer}"
        return "I will guess a number.\nFinal Answer: 0"
    if condition == "disclosed" and method == "columnar":
        return f"Undo the column permutation.\nDecrypted: {original}\nFinal Answer: 0"
    if condition == "undisclosed":
        return "Final Answer: 0"
    raise ValueError(f"no mock completion for {condition} / {method}")
