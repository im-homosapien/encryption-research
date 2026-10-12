"""30-question GSM8K pilot: prompts, scoring, and a mock dry run."""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from pathlib import Path

from research.mocks import mock_completion, run_handwritten_checks
from research.paths import PILOT_NOTES, PILOT_PROMPTS, PILOT_RESULTS
from research.prompts import build_prompt
from research.score import extract_decrypted, score_completion

PILOT_N = 30
PILOT_METHODS = ("none", "caesar_3", "columnar")
RESULT_COLUMNS = (
    "id",
    "dataset",
    "condition",
    "encryption_method",
    "with_example",
    "pred",
    "correct",
    "decryption_exact",
    "decryption_f1",
    "raw",
)
_CONDITION_ORDER = {"plaintext": 0, "disclosed": 1, "undisclosed": 2}
_METHOD_ORDER = {"none": 0, "caesar_3": 1, "caesar_7": 2, "columnar": 3}
_CANDIDATE_CACHE_DIRS = (
    "models--Qwen--Qwen2.5-0.5B-Instruct",
    "models--Qwen--Qwen2.5-1.5B-Instruct",
)


def select_pilot_rows(records: list[dict[str, str]]) -> list[dict[str, str]]:
    ids: list[str] = []
    seen: set[str] = set()
    for row in records:
        if row["dataset"] != "GSM8K" or row["id"] in seen:
            continue
        seen.add(row["id"])
        ids.append(row["id"])
        if len(ids) == PILOT_N:
            break
    if len(ids) < PILOT_N:
        raise AssertionError(f"need {PILOT_N} GSM8K questions, found {len(ids)}")
    chosen = set(ids)
    return [
        row
        for row in records
        if row["id"] in chosen and row["encryption_method"] in PILOT_METHODS
    ]


def find_cached_model() -> str | None:
    """Return a small local instruct model id, if its Hugging Face cache exists."""
    roots: list[Path] = []
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        roots.append(Path(hf_home) / "hub")
    roots.append(Path.home() / ".cache" / "huggingface" / "hub")
    for root in roots:
        for name in _CANDIDATE_CACHE_DIRS:
            if (root / name).is_dir():
                return name[len("models--") :].replace("--", "/")
    return None


def _load_generator(repo_id: str):
    """Load a cached model without downloading weights. Return None if that fails."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        from transformers import pipeline
    except ModuleNotFoundError:
        print("transformers is not installed. Using mock completions.")
        return None
    try:
        return pipeline(
            "text-generation",
            model=repo_id,
            device_map="auto",
            local_files_only=True,
        )
    except Exception as exc:
        print(f"Could not load cached model {repo_id} ({exc}). Using mock completions.")
        return None


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _grouped(results: list[dict[str, object]]) -> list[tuple[tuple[str, str, str], float, int]]:
    buckets: dict[tuple[str, str, str], list[bool]] = defaultdict(list)
    for row in results:
        key = (
            str(row["condition"]),
            str(row["encryption_method"]),
            str(row["with_example"]),
        )
        buckets[key].append(bool(row["correct"]))
    ordered = sorted(
        buckets,
        key=lambda key: (
            _CONDITION_ORDER.get(key[0], 9),
            _METHOD_ORDER.get(key[1], 9),
            key[2],
        ),
    )
    table = []
    for key in ordered:
        values = buckets[key]
        table.append((key, sum(values) / len(values), len(values)))
    return table


def _render_notes(
    results: list[dict[str, object]],
    model_note: str,
    check_names: list[str],
    nulls: int,
    plain_accuracy: float,
) -> str:
    samples = [
        row
        for row in results
        if row["condition"] == "disclosed"
        and row["encryption_method"] == "caesar_3"
        and row["with_example"] == "false"
    ][:5]
    attempts = [str(row["id"]) for row in samples if extract_decrypted(str(row["raw"]))]
    guesses = [str(row["id"]) for row in samples if not extract_decrypted(str(row["raw"]))]
    lines = [
        "# Pilot notes",
        "",
        model_note,
        "",
        "These accuracy numbers check that prompts, extraction, and the grouped table run. "
        "They are a pipeline check on scripted completions.",
        "",
        f"Extraction failures (`pred` null): {nulls} of {len(results)}.",
        f"Plaintext accuracy on this run: {plain_accuracy:.4f}.",
        "",
        "## Grouped accuracy",
        "",
        "| condition | encryption_method | with_example | n | accuracy |",
        "|---|---|---|---|---|",
    ]
    for (condition, method, with_example), mean, count in _grouped(results):
        lines.append(f"| {condition} | {method} | {with_example} | {count} | {mean:.4f} |")
    lines.extend(
        [
            "",
            "## Disclosed Caesar samples",
            "",
            "A completion counts as a decryption attempt when it contains a `Decrypted:` line. "
            "A completion with only a final answer counts as a guess.",
            "",
            f"Decryption attempt: {', '.join(attempts) if attempts else 'none'}.",
            f"Guess only: {', '.join(guesses) if guesses else 'none'}.",
            "",
            "On this dry run the mock writes a `Decrypted:` line equal to the original question "
            "for even GSM8K ids, and writes `Final Answer: 0` with no decryption line for odd ids. "
            "That alternation is scripted so both scorer paths can be inspected.",
            "",
        ]
    )
    for index, row in enumerate(samples, start=1):
        kind = "decryption attempt" if extract_decrypted(str(row["raw"])) else "guess only"
        lines.append(f"### {index}. {row['id']} ({kind})")
        lines.append("")
        lines.append("```")
        lines.append(str(row["raw"]))
        lines.append("```")
        lines.append("")
    lines.extend(
        [
            "## Scorer checks",
            "",
            "Hand-written completions passed: " + ", ".join(check_names) + ".",
            "",
            "## Mock policy",
            "",
            "- Plaintext, no example, id number divisible by 5: omit `Final Answer` so extraction fails.",
            "- Other plaintext rows: `Final Answer` is the gold number.",
            "- Disclosed Caesar, even id: decrypt line is the original question, and the gold answer is given.",
            "- Disclosed Caesar, odd id: guess `0` and do not decrypt.",
            "- Disclosed columnar: decrypt line is the original question, and the answer is `0`.",
            "- Undisclosed: guess `0` and do not decrypt.",
            "- `with_example` does not change the mock text, except that the plaintext extraction failure is only on the no-example variant.",
            "",
            "The pilot uses plaintext, Caesar shift 3, and columnar.",
            "",
        ]
    )
    return "\n".join(lines)


def print_summary(results: list[dict[str, object]], nulls: int, plain_accuracy: float) -> None:
    print(f"null preds: {nulls} / {len(results)}")
    print(f"plaintext accuracy: {plain_accuracy:.4f}")
    print("correct mean by condition, encryption_method, with_example")
    for (condition, method, with_example), mean, count in _grouped(results):
        print(f"  {condition:12} {method:10} with_example={with_example:5} {mean:.4f}  n={count}")


def run_pilot(records: list[dict[str, str]], dry_run: bool = False) -> list[dict[str, object]]:
    check_names = run_handwritten_checks()
    print("Hand-written scorer checks passed: " + ", ".join(check_names))
    rows = select_pilot_rows(records)
    repo_id = None if dry_run else find_cached_model()
    generator = None
    if repo_id:
        print(f"Found cached model {repo_id}. Loading with local files only.")
        generator = _load_generator(repo_id)
    if generator is None:
        model_note = (
            "No language model was loaded. "
            + (
                "The run was forced to a dry run."
                if dry_run
                else "No cached Qwen2.5 0.5B or 1.5B Instruct weights were found, and none were downloaded."
            )
            + " Completions in `pilot_results.csv` come from the deterministic mock in `research/mocks.py`."
        )
        print(model_note)
    else:
        model_note = f"Completions were generated with cached model `{repo_id}`."

    results: list[dict[str, object]] = []
    prompts: list[dict[str, str]] = []
    for row in rows:
        for with_example in (False, True):
            prompt = build_prompt(row, with_example)
            prompts.append(
                {
                    "id": row["id"],
                    "condition": row["condition"],
                    "encryption_method": row["encryption_method"],
                    "with_example": "true" if with_example else "false",
                    "prompt": prompt,
                }
            )
            if generator is None:
                raw = mock_completion(row, with_example)
            else:
                generated = generator(
                    prompt,
                    max_new_tokens=512,
                    do_sample=False,
                    return_full_text=False,
                )[0]["generated_text"]
                raw = str(generated)
            gold_question = None if row["condition"] == "plaintext" else row["original_question"]
            scored = score_completion(raw, row["answer"], gold_question)
            results.append(
                {
                    "id": row["id"],
                    "dataset": row["dataset"],
                    "condition": row["condition"],
                    "encryption_method": row["encryption_method"],
                    "with_example": "true" if with_example else "false",
                    "pred": scored["pred"],
                    "correct": scored["correct"],
                    "decryption_exact": scored["decryption_exact"],
                    "decryption_f1": scored["decryption_f1"],
                    "raw": raw,
                }
            )

    with PILOT_RESULTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        for row in results:
            writer.writerow({column: _cell(row[column]) for column in RESULT_COLUMNS})
    with PILOT_PROMPTS.open("w", encoding="utf-8") as handle:
        for row in prompts:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    nulls = sum(row["pred"] is None for row in results)
    plain = [row for row in results if row["condition"] == "plaintext"]
    plain_accuracy = sum(bool(row["correct"]) for row in plain) / len(plain)
    PILOT_NOTES.write_text(
        _render_notes(results, model_note, check_names, nulls, plain_accuracy),
        encoding="utf-8",
    )
    print_summary(results, nulls, plain_accuracy)
    print(f"wrote {PILOT_RESULTS}")
    print(f"wrote {PILOT_PROMPTS}")
    print(f"wrote {PILOT_NOTES}")
    return results
