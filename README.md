# Encrypted math questions

This project asks whether a language model can recover an encrypted math question and then solve it.

The questions come from three datasets: GSM8K (1,319), SVAMP (1,000), and MATH-500 (500). Each question is stored in plain English and encrypted with six cipher families. The encrypted tables are already built and live in `data/encrypted/`.

## The six ciphers

These are the only ciphers written into the tables, in this order:

1. **Caesar** — substitution, shift 3 only
2. **Columnar transposition** — key `CRYPTO`, pad with `X`, column order `(key[i], i)`
3. **LFSR** — a stream cipher; the ciphertext is hex
4. **Block cipher** — a small educational cipher, not DES or AES
5. **DES and AES** — DES-CBC and AES-128-CBC
6. **RSA** — RSA-OAEP wraps an AES session key; the question body is AES-CBC

A second Caesar shift is implemented in `encyption.py` and is not written into the tables.

## Where the files are

```text
data/encrypted/
  plaintext/     original questions
  1_caesar/      Caesar, shift 3
  2_columnar/    columnar transposition
  3_lfsr/        LFSR
  4_block/       block cipher
  5_des_aes/     DES and AES
  6_rsa/         RSA hybrid
```

Each of those folders has `gsm8k.csv`, `svamp.csv`, and `math500.csv`.

There are 2,819 questions. Each one becomes 15 rows: the plaintext, plus 7 cipher methods times 2 conditions. That is 42,285 rows.

## How to read a row

| Column | Meaning |
| --- | --- |
| `encrypted_question` | The ciphertext. This is the text a model would see. |
| `original_question` | The English question, kept so decryption can be checked. |
| `answer` | The gold answer. |
| `condition` | `plaintext`, `disclosed`, or `undisclosed`. |
| `method_name` | The cipher name used in a disclosed prompt. |

`disclosed` tells the model the cipher name and how to decrypt. `undisclosed` uses the same ciphertext and does not name the cipher. Caesar and columnar ciphertext look like letters. LFSR, the block cipher, DES, AES, and RSA are hex.

GSM8K and SVAMP answers are numbers. MATH-500 answers are stored as text, including LaTeX, and are not scored as numbers.

## Prompts

The role line is: "You are an expert in cryptography and mathematical reasoning."

A prompt can include a worked example of the same cipher, or no example. An undisclosed example shows ciphertext and a decryption, and it does not name the cipher. The model is asked to print `Decrypted: ...` and end with `Final Answer: <number>`. Plaintext prompts ask only for the final answer.

## Run it

Requires Python 3.10 or newer and [PyCryptodome](https://www.pycryptodome.org/).

```bash
python3 -m pip install pycryptodome
python3 -m research
```

That rebuilds every encrypted CSV from `data/clean_math_data_gsm_svamp_math500.csv` and checks that each ciphertext decrypts back to the original question.

```bash
python3 -m research --dry-run
```

That scores handwritten stand-in answers for a 30-question GSM8K check (plaintext, Caesar, and columnar). It does not download a model, and those scores are not a research result.

## What each file does

| File | Role |
| --- | --- |
| `encyption.py` | The cipher code. The filename is spelled that way on purpose. Other code imports this file. |
| `research/dataset.py` | Reads the questions, encrypts them once, and writes one CSV per cipher folder and dataset. |
| `research/prompts.py` | Builds the disclosed and undisclosed prompts. |
| `research/score.py` | Checks the final answer and whether `Decrypted:` matches the original question. |
| `research/pilot.py` | Runs the 30-question check. |
| `research/mocks.py` | The stand-in answers used when no model is loaded. |
| `data/README.md` | Short note on the question counts and folder names. |

The RSA key inside `encyption.py` is a fixed research key so the RSA rows can be decrypted again. It is not a key for anything outside this study.
