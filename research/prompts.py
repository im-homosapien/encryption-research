"""Prompt templates: role, condition, optional worked example."""

from __future__ import annotations

from collections.abc import Mapping

from research.ciphers import load_encyption

ROLE = "You are an expert in cryptography and mathematical reasoning."
EXAMPLE_QUESTION = "Tom has 5 apples and buys 3 more. How many apples does he have?"
EXAMPLE_ANSWER = "8"

_FINAL = "End with a line exactly like: Final Answer: <number>"
_DECRYPT = (
    "Print a line exactly like: Decrypted: <recovered question>. "
    "End with a line exactly like: Final Answer: <number>"
)


def _example_block(method_key: str) -> str:
    """Worked example encrypted with the same cipher. The cipher is not named here."""
    encrypted = load_encyption().get_cipher(method_key).encrypt(EXAMPLE_QUESTION)
    return (
        "Example:\n"
        f"Problem: {encrypted}\n"
        f"Decrypted: {EXAMPLE_QUESTION}\n"
        f"Final Answer: {EXAMPLE_ANSWER}\n\n"
    )


def build_prompt(row: Mapping[str, str], with_example: bool) -> str:
    """Build one prompt.

    Disclosed and undisclosed rows must already carry the same ciphertext.
    Only the instructions change. The undisclosed prompt does not name the cipher.
    """
    condition = row["condition"]
    method = row["encryption_method"]
    question = row["encrypted_question"]
    if condition == "plaintext":
        context = "Solve the math problem below."
        fmt = f"Think step by step. {_FINAL}"
        example = ""
        if with_example:
            example = (
                "Example:\n"
                f"Problem: {EXAMPLE_QUESTION}\n"
                f"Final Answer: {EXAMPLE_ANSWER}\n\n"
            )
    elif condition == "disclosed":
        blurb = load_encyption().get_cipher(method).disclosed_blurb
        context = (
            f"The problem below is encrypted with {row['method_name']}. "
            f"{blurb} "
            "First decrypt it, then solve the original problem."
        )
        fmt = f"Think step by step. {_DECRYPT}"
        example = _example_block(method) if with_example else ""
    elif condition == "undisclosed":
        context = "Solve the problem below."
        fmt = f"Think step by step. {_DECRYPT}"
        example = _example_block(method) if with_example else ""
    else:
        raise ValueError(f"unknown condition {condition!r}")
    return f"{ROLE}\n{context}\n{fmt}\n\n{example}Problem: {question}\n"


def problem_text(prompt: str) -> str:
    marker = "\nProblem: "
    index = prompt.rfind(marker)
    if index < 0:
        raise AssertionError("prompt is missing the problem line")
    return prompt[index + len(marker) :].removesuffix("\n")


def assert_prompt_contract(records: list[dict[str, str]]) -> None:
    """Fail if a prompt names a cipher in the undisclosed condition, or drops the ciphertext."""
    by_key = {(row["id"], row["condition"], row["encryption_method"]): row for row in records}
    item_id = next(row["id"] for row in records if row["condition"] == "plaintext")
    plain = by_key[(item_id, "plaintext", "none")]
    for method in ("caesar_3", "columnar"):
        disclosed = by_key[(item_id, "disclosed", method)]
        hidden = by_key[(item_id, "undisclosed", method)]
        if disclosed["encrypted_question"] != hidden["encrypted_question"]:
            raise AssertionError(f"{method} ciphertext differs across conditions")
        for with_example in (False, True):
            disclosed_prompt = build_prompt(disclosed, with_example)
            hidden_prompt = build_prompt(hidden, with_example)
            if problem_text(disclosed_prompt) != disclosed["encrypted_question"]:
                raise AssertionError("disclosed prompt changed the ciphertext")
            if problem_text(hidden_prompt) != hidden["encrypted_question"]:
                raise AssertionError("undisclosed prompt changed the ciphertext")
            if disclosed["method_name"] not in disclosed_prompt:
                raise AssertionError("disclosed prompt does not name the method")
            if "First decrypt it" not in disclosed_prompt:
                raise AssertionError("disclosed prompt does not ask for decryption first")
            hidden_head = hidden_prompt.split("\nProblem:", 1)[0]
            for banned in (
                hidden["method_name"],
                "Caesar Cipher",
                "Columnar Transposition",
                "CRYPTO",
                "encrypted with",
                "First decrypt it",
            ):
                if banned in hidden_head:
                    raise AssertionError(f"undisclosed prompt leaks {banned!r}")
            if "Decrypted:" not in disclosed_prompt or "Final Answer:" not in disclosed_prompt:
                raise AssertionError("encrypted prompt is missing the output format")
    for with_example in (False, True):
        plain_prompt = build_prompt(plain, with_example)
        if "Decrypted:" in plain_prompt:
            raise AssertionError("plaintext prompt asks for a decryption line")
        if problem_text(plain_prompt) != plain["original_question"]:
            raise AssertionError("plaintext prompt changed the question")
    ciphers = load_encyption()
    for method in ciphers.PILOT_CIPHERS:
        if not ciphers.verify_roundtrip(EXAMPLE_QUESTION, method):
            raise AssertionError(f"example question does not round-trip for {method}")
