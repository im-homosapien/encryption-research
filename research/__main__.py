"""Run the encrypted GSM8K pipeline: ``python -m research``."""

from __future__ import annotations

import argparse

from research.ciphers import load_encyption
from research.dataset import generate
from research.pilot import run_pilot
from research.prompts import assert_prompt_contract


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Encrypted GSM8K research pipeline")
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="After building the table, run the 30-question pilot (none, caesar_3, columnar).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Score mock completions. Do not load a model.",
    )
    args = parser.parse_args(argv)

    ciphers = load_encyption()
    ciphers.assert_invariants()
    vector = ciphers.columnar_encrypt("HELLO", "CRYPTO")
    if vector != "HXLEOL":
        raise AssertionError(f"Columnar known vector failed: {vector!r}")
    print("Round-trip asserts passed, including columnar HELLO + CRYPTO -> HXLEOL")

    records = generate()
    assert_prompt_contract(records)
    print("Prompt checks passed")
    if args.pilot or args.dry_run:
        run_pilot(records, dry_run=args.dry_run or not _model_requested(args))
    return 0


def _model_requested(args: argparse.Namespace) -> bool:
    """A plain pilot may use a cached model. --dry-run never does."""
    return bool(args.pilot and not args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
