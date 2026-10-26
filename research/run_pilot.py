"""Run the 30-question pilot through Ollama.

Python has already encrypted the questions. This script only sends prompts
and scores the replies. The default model is gemma4 in Ollama's cloud, which
needs you to run ``ollama signin`` yourself.

    python -m research.run_pilot --check
    python -m research.run_pilot --models gemma4
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from research.llm_client import OllamaError, api_key, call_ollama, installed_models, model_ready
from research.paths import ENCRYPTED_DIR, ROOT
from research.prompts import prompt_for_row
from research.score import score_completion

PILOT_N = 30
OUTPUT_DIR = ROOT / "results" / "pilot"
# Names from https://ollama.com/api/tags. These run in Ollama's cloud, not on this Mac.
# gemma4 is already scored. Qwen and Llama are not in this cloud list.
MODELS = {
    "gemma4": "gemma4:31b",
    "beam": "beam",
    "clef": "clef:27b",
    "deepseek-v4-pro": "deepseek-v4-pro:0813",
    "deepseek-v4.1-flash": "deepseek-v4.1-flash",
    "glm-5.2": "glm-5.2",
    "glm-5.3": "glm-5.3",
    "glm-5.3-flash": "glm-5.3-flash",
    "gpt-oss-20b": "gpt-oss:20b",
    "gpt-oss-120b": "gpt-oss:120b",
    "kimi-k2.6": "kimi-k2.6",
    "kimi-k2.7-code": "kimi-k2.7-code",
    "kimi-k3": "kimi-k3",
    "minimax-m2.7": "minimax-m2.7",
    "minimax-m3": "minimax-m3",
    "minimax-m3.1-flash": "minimax-m3.1-flash",
    "mistral-large-3": "mistral-large-3:675b",
    "mistral-large-4": "mistral-large-4",
    "muse-spark-open": "muse-spark-open",
    "nemotron-3-nano": "nemotron-3-nano:30b",
    "nemotron-3-super": "nemotron-3-super",
    "nemotron-3-ultra": "nemotron-3-ultra",
}
SOURCES = (
    ENCRYPTED_DIR / "plaintext" / "gsm8k.csv",
    ENCRYPTED_DIR / "1_caesar" / "gsm8k.csv",
    ENCRYPTED_DIR / "2_columnar" / "gsm8k.csv",
)
RESULT_COLUMNS = (
    "id",
    "dataset",
    "condition",
    "encryption_method",
    "method_name",
    "gold_answer",
    "pred",
    "correct",
    "decryption_exact",
    "decryption_f1",
    "model",
    "model_response",
    "prompt",
)


def pilot_ids(n: int) -> set[str]:
    return {f"gsm_{i}" for i in range(n)}


def load_pilot_rows(n: int = PILOT_N) -> list[dict[str, str]]:
    """First n GSM8K questions, plain plus Caesar and columnar, named and unnamed."""
    wanted = pilot_ids(n)
    rows: list[dict[str, str]] = []
    for path in SOURCES:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["id"] not in wanted:
                    continue
                if row["encryption_method"] not in {"none", "caesar_3", "columnar"}:
                    continue
                rows.append(row)
    rows.sort(
        key=lambda row: (
            int(row["id"].split("_", 1)[1]),
            row["encryption_method"],
            row["condition"],
        )
    )
    return rows


def _done_keys(path: Path) -> set[tuple[str, str, str]]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            (row["id"], row["condition"], row["encryption_method"])
            for row in csv.DictReader(handle)
        }


def _append(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow({column: "" if row[column] is None else row[column] for column in RESULT_COLUMNS})


def run_model(model_key: str, rows: list[dict[str, str]], few_shot: bool) -> Path:
    model_name = MODELS[model_key]
    out_path = OUTPUT_DIR / f"pilot_{model_key}.csv"
    done = _done_keys(out_path)
    pending = [
        row
        for row in rows
        if (row["id"], row["condition"], row["encryption_method"]) not in done
    ]
    print(f"{model_key} ({model_name}): {len(pending)} left, {len(done)} already saved")
    for index, row in enumerate(pending, start=1):
        prompt = prompt_for_row(row, few_shot=few_shot)
        print(f"  {index}/{len(pending)} {row['id']} {row['condition']} {row['encryption_method']}")
        try:
            response = call_ollama(model_name, prompt, cloud=True, timeout=1800)
        except OllamaError as exc:
            message = str(exc)
            blocked = any(
                token in message
                for token in ("HTTP 401", "HTTP 402", "HTTP 403", "HTTP 404")
            )
            if blocked:
                print(f"  skipped {model_key}: {message[:180]}")
                return out_path
            raise
        gold_question = None if row["condition"] == "plaintext" else row["original_question"]
        scored = score_completion(response, row["answer"], gold_question)
        _append(
            out_path,
            {
                "id": row["id"],
                "dataset": row["dataset"],
                "condition": row["condition"],
                "encryption_method": row["encryption_method"],
                "method_name": row["method_name"],
                "gold_answer": row["answer"],
                "pred": scored["pred"],
                "correct": scored["correct"],
                "decryption_exact": scored["decryption_exact"],
                "decryption_f1": scored["decryption_f1"],
                "model": model_name,
                "model_response": response,
                "prompt": prompt,
            },
        )
    return out_path


def print_summary(path: Path) -> None:
    if not path.exists():
        return
    buckets: dict[tuple[str, str], list[bool]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        buckets[(row["condition"], row["encryption_method"])].append(row["correct"] == "True")
    print(f"Scores in {path.name} ({len(rows)} replies)")
    for key in sorted(buckets):
        values = buckets[key]
        correct = sum(values)
        print(f"  {key[0]} {key[1]}: {correct}/{len(values)}")


def check(rows: list[dict[str, str]]) -> int:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        counts[(row["condition"], row["encryption_method"])] += 1
    print(f"Pilot rows ready: {len(rows)}")
    for key in sorted(counts):
        print(f"  {key[0]} {key[1]}: {counts[key]}")
    try:
        installed = installed_models()
    except OllamaError as exc:
        print(exc)
        return 1
    print("Ollama is running. Installed:", ", ".join(installed) or "(none)")
    cloud = [name for name in MODELS.values() if name.endswith(":cloud")]
    missing = [name for name in MODELS.values() if not model_ready(name, installed)]
    if cloud:
        print("Cloud model:", ", ".join(cloud))
        print("Sign in yourself before the run: ollama signin")
    if missing:
        print("Still need a local download:")
        for name in missing:
            print(f"  ollama pull {name}")
        return 1
    print("Pilot model is ready to call.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score local models on the 30-question pilot.")
    parser.add_argument(
        "--models",
        default=",".join(key for key in MODELS if key != "gemma4"),
        help="Comma-separated keys. Default is every cloud model except gemma4, which is already scored.",
    )
    parser.add_argument("--limit", type=int, default=PILOT_N, help="How many GSM8K questions, from gsm_0.")
    parser.add_argument("--example", action="store_true", help="Add the worked example to each prompt.")
    parser.add_argument("--check", action="store_true", help="Count rows and list Ollama models. Do not call a model.")
    args = parser.parse_args(argv)

    rows = load_pilot_rows(args.limit)
    if args.check:
        return check(rows)

    chosen = [key.strip() for key in args.models.split(",") if key.strip()]
    unknown = [key for key in chosen if key not in MODELS]
    if unknown:
        raise SystemExit(f"Unknown model key: {', '.join(unknown)}. Use {', '.join(MODELS)}.")
    if not api_key():
        raise SystemExit("OLLAMA_API_KEY is missing. Put it in .env. Do not paste it into chat.")
    for key in chosen:
        path = run_model(key, rows, few_shot=args.example)
        print_summary(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
