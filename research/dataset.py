"""Build the encrypted table for GSM8K, SVAMP, and MATH-500."""

from __future__ import annotations

import csv
import json
import urllib.request
from collections import Counter

from research.ciphers import load_encyption
from research.paths import (
    CLEAN_CSV_CANDIDATES,
    DATA_DIR,
    DATA_README,
    ENCRYPTED_DIR,
    GSM8K_CSV,
    OFFICIAL_GSM8K_TEST_URL,
    QUESTIONS_CSV,
)

DATASETS = ("GSM8K", "SVAMP", "MATH-500")
NUMERIC_DATASETS = {"GSM8K", "SVAMP"}
# One Caesar shift. caesar_7 stays implemented in encyption.py and is not written out.
OUTPUT_METHODS = ("caesar_3", "columnar", "lfsr", "toy_block", "des", "aes", "rsa")
FOLDER_BY_METHOD = {
    "none": "plaintext",
    "caesar_3": "1_caesar",
    "columnar": "2_columnar",
    "lfsr": "3_lfsr",
    "toy_block": "4_block",
    "des": "5_des_aes",
    "aes": "5_des_aes",
    "rsa": "6_rsa",
}
FILE_BY_DATASET = {
    "GSM8K": "gsm8k.csv",
    "SVAMP": "svamp.csv",
    "MATH-500": "math500.csv",
}
METHOD_SORT = {name: index for index, name in enumerate(("none",) + OUTPUT_METHODS)}

TABLE_COLUMNS = (
    "id",
    "dataset",
    "notes_item",
    "family",
    "condition",
    "encryption_method",
    "method_name",
    "answer",
    "encrypted_question",
    "original_question",
)

# Display names. notes_item and family come from the catalog in encyption.py.
METHOD_NAMES = {
    "caesar_3": "Caesar Cipher (shift=3)",
    "caesar_7": "Caesar Cipher (shift=7)",
    "columnar": "Columnar Transposition (key=CRYPTO)",
    "lfsr": "LFSR stream cipher",
    "toy_block": "Block cipher",
    "des": "DES-CBC",
    "aes": "AES-128-CBC",
    "rsa": "RSA-OAEP + AES-128-CBC",
}


def store_answer(dataset: str, raw: str, item_id: str) -> str:
    """Keep MATH-500 LaTeX as text. GSM8K and SVAMP answers are numbers."""
    text = raw.strip()
    if text == "":
        raise ValueError(f"{item_id} has an empty answer")
    if dataset not in NUMERIC_DATASETS:
        return text
    text = text.replace(",", "").replace("$", "")
    try:
        float(text)
    except ValueError as exc:
        raise ValueError(f"{item_id} has a non-numeric answer {raw!r}") from exc
    return text


def _write_question_copy(path, questions: list[dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("id", "dataset", "question", "answer"))
        writer.writeheader()
        for row in questions:
            writer.writerow(
                {
                    "id": row["id"],
                    "dataset": row["dataset"],
                    "question": row["question"],
                    "answer": row["answer"],
                }
            )


def _read_clean_csv(path) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"dataset", "id", "question", "answer"}
        if not required.issubset(set(reader.fieldnames or ())):
            raise ValueError(f"{path} is missing columns {sorted(required)}")
        for row in reader:
            dataset = row["dataset"].strip()
            if dataset not in DATASETS:
                continue
            item_id = row["id"].strip()
            if item_id in seen:
                raise ValueError(f"duplicate id {item_id}")
            seen.add(item_id)
            question = row["question"].strip()
            if not question:
                raise ValueError(f"{item_id} has an empty question")
            questions.append(
                {
                    "id": item_id,
                    "dataset": dataset,
                    "question": question,
                    "answer": store_answer(dataset, row["answer"], item_id),
                }
            )
    if not questions:
        raise ValueError(f"{path} has no GSM8K, SVAMP, or MATH-500 rows")
    return questions


def _download_official_test() -> list[dict[str, str]]:
    """Download the OpenAI GSM8K test split. Used only when no local file exists."""
    with urllib.request.urlopen(OFFICIAL_GSM8K_TEST_URL, timeout=60) as response:
        payload = response.read().decode("utf-8")
    questions: list[dict[str, str]] = []
    for index, line in enumerate(payload.splitlines()):
        if not line.strip():
            continue
        obj = json.loads(line)
        answer_field = str(obj["answer"])
        if "####" not in answer_field:
            raise ValueError(f"GSM8K line {index} has no #### answer")
        gold = answer_field.split("####")[-1].strip()
        item_id = f"gsm8k_test_{index:04d}"
        questions.append(
            {
                "id": item_id,
                "dataset": "GSM8K",
                "question": str(obj["question"]).strip(),
                "answer": store_answer("GSM8K", gold, item_id),
            }
        )
    if not questions:
        raise ValueError("official GSM8K download was empty")
    return questions


def _dataset_counts(questions: list[dict[str, str]]) -> dict[str, int]:
    return {name: sum(item["dataset"] == name for item in questions) for name in DATASETS}


def load_questions() -> tuple[list[dict[str, str]], str]:
    """Load GSM8K, SVAMP, and MATH-500 from the cleaned CSV when it is present."""
    source = next((path for path in CLEAN_CSV_CANDIDATES if path.is_file()), None)
    if source is not None:
        questions = _read_clean_csv(source)
        counts = _dataset_counts(questions)
        note = (
            f"Source file: `{source}`\n\n"
            f"GSM8K: {counts['GSM8K']} questions (test-split size; `gsm_0` is the Janet item). "
            f"SVAMP: {counts['SVAMP']} questions. "
            f"MATH-500: {counts['MATH-500']} questions. "
            "GSM8K and SVAMP answers are numbers. MATH-500 answers are kept as text, "
            "including LaTeX, and are not scored with numeric matching.\n"
        )
    elif QUESTIONS_CSV.is_file():
        questions = _read_clean_csv(QUESTIONS_CSV)
        note = f"Source file: `{QUESTIONS_CSV}` ({len(questions)} questions).\n"
    elif GSM8K_CSV.is_file():
        questions = _read_clean_csv(GSM8K_CSV)
        note = f"Source file: `{GSM8K_CSV}` ({len(questions)} GSM8K questions).\n"
    else:
        questions = _download_official_test()
        note = (
            "No local clean_math_data CSV was found.\n\n"
            f"Downloaded the official GSM8K test split from {OFFICIAL_GSM8K_TEST_URL} "
            f"({len(questions)} questions). Gold answers are the number after `####`. "
            "SVAMP and MATH-500 were not in that download.\n"
        )
    _write_question_copy(QUESTIONS_CSV, questions)
    _write_question_copy(
        GSM8K_CSV, [item for item in questions if item["dataset"] == "GSM8K"]
    )
    return questions, note


def _method_rows(ciphers) -> list[dict[str, str]]:
    """Six notes families. Caesar is shift 3 only. DES and AES share family 5."""
    rows: list[dict[str, str]] = []
    for item in ciphers.NOTES_CIPHERS:
        for method in item["method_ids"]:
            if method not in OUTPUT_METHODS:
                continue
            if method not in METHOD_NAMES:
                raise KeyError(f"no display name for {method}")
            rows.append(
                {
                    "notes_item": str(item["notes_item"]),
                    "family": str(item["family"]),
                    "encryption_method": str(method),
                    "method_name": METHOD_NAMES[str(method)],
                }
            )
    return rows


def build_records(questions: list[dict[str, str]]) -> list[dict[str, str]]:
    """One plaintext row, then disclosed and undisclosed for every notes cipher."""
    ciphers = load_encyption()
    methods = _method_rows(ciphers)
    records: list[dict[str, str]] = []
    trailing_x = 0
    for item in questions:
        question = item["question"]
        if question.endswith(ciphers.COLUMNAR_PAD):
            trailing_x += 1
        base = {
            "id": item["id"],
            "dataset": item["dataset"],
            "answer": item["answer"],
            "original_question": question,
        }
        records.append(
            {
                **base,
                "notes_item": "0",
                "family": "plaintext",
                "condition": "plaintext",
                "encryption_method": "none",
                "method_name": "none",
                "encrypted_question": question,
            }
        )
        for spec in methods:
            cipher = ciphers.get_cipher(spec["encryption_method"])
            encrypted = cipher.encrypt(question)
            if spec["encryption_method"] == "columnar":
                expected = question.rstrip(ciphers.COLUMNAR_PAD)
            else:
                expected = question
            recovered = cipher.decrypt(encrypted)
            if recovered != expected:
                raise AssertionError(
                    f"{spec['encryption_method']} round-trip failed for {item['id']}"
                )
            if encrypted == question:
                raise AssertionError(
                    f"{spec['encryption_method']} left {item['id']} unchanged"
                )
            for condition in ("disclosed", "undisclosed"):
                records.append(
                    {
                        **base,
                        **spec,
                        "condition": condition,
                        "encrypted_question": encrypted,
                    }
                )
    if trailing_x:
        print(
            f"Columnar note: {trailing_x} questions end with the pad character "
            f"{ciphers.COLUMNAR_PAD!r}. Decrypt strips those characters."
        )
    expected_rows = len(questions) * (1 + 2 * len(methods))
    if len(records) != expected_rows:
        raise AssertionError(f"expected {expected_rows} rows, built {len(records)}")
    _assert_ciphertext_pairs(records)
    return records


def _assert_ciphertext_pairs(records: list[dict[str, str]]) -> None:
    paired: dict[tuple[str, str], dict[str, str]] = {}
    for row in records:
        if row["condition"] == "plaintext":
            continue
        key = (row["id"], row["encryption_method"])
        paired.setdefault(key, {})[row["condition"]] = row["encrypted_question"]
    for key, sides in paired.items():
        if sides.get("disclosed") != sides.get("undisclosed"):
            raise AssertionError(f"disclosed and undisclosed ciphertext differ for {key}")


def _record_sort_key(row: dict[str, str]) -> tuple[int, int, int, int]:
    condition_order = {"plaintext": 0, "disclosed": 1, "undisclosed": 2}
    return (
        int(row["id"].rsplit("_", 1)[-1]),
        int(row["notes_item"]),
        condition_order[row["condition"]],
        METHOD_SORT[row["encryption_method"]],
    )


def write_table(records: list[dict[str, str]]) -> None:
    """One folder per cipher family, and one CSV per dataset inside it."""
    for stale in (
        DATA_DIR / "encrypted_math_dataset.csv",
        DATA_DIR / "encrypted_math_dataset.jsonl",
    ):
        if stale.is_file():
            stale.unlink()
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in records:
        folder = FOLDER_BY_METHOD[row["encryption_method"]]
        filename = FILE_BY_DATASET[row["dataset"]]
        grouped.setdefault((folder, filename), []).append(row)
    for (folder, filename), rows in grouped.items():
        path = ENCRYPTED_DIR / folder / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        rows.sort(key=_record_sort_key)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=TABLE_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {path} ({len(rows)} rows)")


def write_data_readme(source_note: str, n_questions: int, n_rows: int) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    text = (
        "# Question data\n\n"
        f"{source_note}\n"
        "Local copies: `questions.csv` (GSM8K, SVAMP, and MATH-500) and `gsm8k.csv` (GSM8K only).\n\n"
        f"Encrypted files live under `encrypted/`, split by cipher and then by dataset "
        f"({n_rows} rows = {n_questions} questions × {n_rows // n_questions}). "
        "Caesar is shift 3 only.\n\n"
        "`encrypted_question` is the ciphertext. `original_question` stays in English "
        "on every row so decryption can be scored. Disclosed and undisclosed share one ciphertext.\n\n"
        "- `encrypted/plaintext/` — original questions\n"
        "- `encrypted/1_caesar/` — substitution, shift 3\n"
        "- `encrypted/2_columnar/` — transposition, key CRYPTO\n"
        "- `encrypted/3_lfsr/` — stream cipher\n"
        "- `encrypted/4_block/` — block cipher (not DES or AES)\n"
        "- `encrypted/5_des_aes/` — DES and AES\n"
        "- `encrypted/6_rsa/` — RSA-OAEP + AES\n\n"
        "Each cipher folder contains `gsm8k.csv`, `svamp.csv`, and `math500.csv`. "
        "GSM8K and SVAMP answers are numbers. MATH-500 answers are stored as text, "
        "including LaTeX, and are not passed through numeric matching.\n"
    )
    DATA_README.write_text(text, encoding="utf-8")


def print_table_summary(records: list[dict[str, str]]) -> None:
    print(len(records))
    conditions = Counter(row["condition"] for row in records)
    methods = Counter(row["encryption_method"] for row in records)
    datasets = Counter(row["dataset"] for row in records)
    print("dataset")
    for name in DATASETS:
        print(f"  {name} {datasets[name]}")
    print("condition")
    for name in ("plaintext", "disclosed", "undisclosed"):
        print(f"  {name} {conditions[name]}")
    print("encryption_method")
    order = ("none",) + OUTPUT_METHODS
    for name in order:
        print(f"  {name} {methods[name]}")
    print("disclosed samples (ciphertext is encrypted_question, not original_question)")
    for method in ("caesar_3", "columnar", "lfsr", "toy_block", "des", "aes", "rsa"):
        sample = next(
            row
            for row in records
            if row["condition"] == "disclosed" and row["encryption_method"] == method
        )
        scrambled = sample["encrypted_question"] != sample["original_question"]
        print(
            f"  {sample['notes_item']}. {sample['method_name']}: "
            f"{sample['encrypted_question'][:72]}"
        )
        if not scrambled:
            raise AssertionError(f"{method} sample was not scrambled")


def generate() -> list[dict[str, str]]:
    questions, source_note = load_questions()
    records = build_records(questions)
    write_table(records)
    write_data_readme(source_note, len(questions), len(records))
    print_table_summary(records)
    return records
