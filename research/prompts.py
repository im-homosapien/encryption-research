# research/prompts.py

from __future__ import annotations


def get_prompt(encrypted_question: str, cipher_name: str | None = None, few_shot: bool = False) -> str:
    """
    Five-part prompt.
    cipher_name = None  → Undisclosed
    cipher_name = "Caesar" / "Columnar" / etc. → Disclosed
    """

    # ---------- 1. ROLE ----------
    role = (
        "You are a careful mathematical reasoning assistant that can also recover "
        "text that has been encrypted with classical or modern ciphers."
    )

    # ---------- 2. CONTEXT ----------
    if cipher_name is not None:
        context = (
            f"The following text is a math word problem that has been encrypted "
            f"using the {cipher_name} cipher. "
            "Your job is to recover the original English question and then solve it."
        )
    else:
        context = (
            "The following text is a math word problem that has been encrypted "
            "with an unknown classical or modern cipher. "
            "Your job is to recover the original English question and then solve it."
        )

    # ---------- 3. TASK ----------
    task = (
        "1. Decrypt the given text back into the original English math question.\n"
        "2. Solve the recovered math question step by step.\n"
        "3. Report the final numerical (or symbolic) answer."
    )

    # ---------- 4. CONSTRAINTS ----------
    constraints = (
        "- Do not invent extra information that is not in the recovered question.\n"
        "- Keep the reasoning short and clear.\n"
        "- If you cannot fully decrypt the text, still attempt the best recovery you can "
        "and solve whatever question you obtain."
    )

    # ---------- 5. FORMAT ----------
    format_ = (
        "Write your reply in exactly this layout:\n\n"
        "Decrypted Question: <the recovered English question>\n"
        "Reasoning: <brief step-by-step solution>\n"
        "Final Answer: <the answer only>"
    )

    # Optional format example. It does not name a cipher, so an undisclosed prompt stays unnamed.
    example = ""
    if few_shot:
        example = (
            "\n\nHere is a short example of the expected style:\n"
            "Encrypted: Wklv lv d whvw.\n"
            "Decrypted Question: This is a test.\n"
            "Reasoning: The text was recovered.\n"
            "Final Answer: ...\n"
        )

    full_prompt = (
        f"{role}\n\n"
        f"{context}\n\n"
        f"{task}\n\n"
        f"{constraints}\n\n"
        f"{format_}"
        f"{example}\n\n"
        f"Encrypted text:\n{encrypted_question}"
    )
    return full_prompt


def prompt_for_row(row: dict[str, str], few_shot: bool = False) -> str:
    """Build the five-part prompt for one saved table row."""
    condition = row["condition"]
    text = row["encrypted_question"]
    if condition == "plaintext":
        return _plaintext_prompt(text, few_shot)
    if condition == "disclosed":
        return get_prompt(text, row["method_name"], few_shot)
    if condition == "undisclosed":
        return get_prompt(text, None, few_shot)
    raise ValueError(f"unknown condition {condition!r}")


def _plaintext_prompt(question: str, few_shot: bool) -> str:
    """Same five parts, for a question that was never encrypted."""
    role = (
        "You are a careful mathematical reasoning assistant."
    )
    context = "The following text is a math word problem written in ordinary English."
    task = (
        "1. Read the question.\n"
        "2. Solve it step by step.\n"
        "3. Report the final numerical (or symbolic) answer."
    )
    constraints = (
        "- Do not invent extra information that is not in the question.\n"
        "- Keep the reasoning short and clear."
    )
    format_ = (
        "Write your reply in exactly this layout:\n\n"
        "Reasoning: <brief step-by-step solution>\n"
        "Final Answer: <the answer only>"
    )
    example = ""
    if few_shot:
        example = (
            "\n\nHere is a short example of the expected style:\n"
            "Question: Tom has 5 apples and buys 3 more. How many apples does he have?\n"
            "Reasoning: 5 + 3 = 8.\n"
            "Final Answer: 8\n"
        )
    return (
        f"{role}\n\n"
        f"{context}\n\n"
        f"{task}\n\n"
        f"{constraints}\n\n"
        f"{format_}"
        f"{example}\n\n"
        f"Question:\n{question}"
    )


def assert_prompt_contract(records: list[dict[str, str]]) -> None:
    """Fail if a prompt names a cipher when it should stay unnamed, or drops the ciphertext."""
    by_key = {(row["id"], row["condition"], row["encryption_method"]): row for row in records}
    item_id = next(row["id"] for row in records if row["condition"] == "plaintext")
    plain = by_key[(item_id, "plaintext", "none")]
    for method in ("caesar_3", "columnar"):
        disclosed = by_key[(item_id, "disclosed", method)]
        hidden = by_key[(item_id, "undisclosed", method)]
        if disclosed["encrypted_question"] != hidden["encrypted_question"]:
            raise AssertionError(f"{method} ciphertext differs across conditions")
        for few_shot in (False, True):
            disclosed_prompt = prompt_for_row(disclosed, few_shot)
            hidden_prompt = prompt_for_row(hidden, few_shot)
            if not disclosed_prompt.endswith(disclosed["encrypted_question"]):
                raise AssertionError("disclosed prompt changed the ciphertext")
            if not hidden_prompt.endswith(hidden["encrypted_question"]):
                raise AssertionError("undisclosed prompt changed the ciphertext")
            disclosed_head = disclosed_prompt.split("Encrypted text:", 1)[0]
            hidden_head = hidden_prompt.split("Encrypted text:", 1)[0]
            if disclosed["method_name"] not in disclosed_head:
                raise AssertionError("disclosed prompt does not name the method")
            if "Decrypted Question:" not in disclosed_prompt or "Final Answer:" not in disclosed_prompt:
                raise AssertionError("encrypted prompt is missing the output format")
            for banned in (hidden["method_name"], "Caesar", "Columnar", "CRYPTO"):
                if banned in hidden_head:
                    raise AssertionError(f"undisclosed prompt leaks {banned!r}")
    for few_shot in (False, True):
        plain_prompt = prompt_for_row(plain, few_shot)
        if "Decrypted Question:" in plain_prompt:
            raise AssertionError("plaintext prompt asks for a decryption line")
        if plain["original_question"] not in plain_prompt:
            raise AssertionError("plaintext prompt changed the question")