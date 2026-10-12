# Question data

Source file: `/Users/knowledge/Documents/encryption research/data/clean_math_data_gsm_svamp_math500.csv`

GSM8K: 1319 questions (test-split size; `gsm_0` is the Janet item). SVAMP: 1000 questions. MATH-500: 500 questions. GSM8K and SVAMP answers are numbers. MATH-500 answers are kept as text, including LaTeX, and are not scored with numeric matching.

Local copies: `questions.csv` (GSM8K, SVAMP, and MATH-500) and `gsm8k.csv` (GSM8K only).

Encrypted files live under `encrypted/`, split by cipher and then by dataset (42285 rows = 2819 questions × 15). Caesar is shift 3 only.

`encrypted_question` is the ciphertext. `original_question` stays in English on every row so decryption can be scored. Disclosed and undisclosed share one ciphertext.

- `encrypted/plaintext/` — original questions
- `encrypted/1_caesar/` — substitution, shift 3
- `encrypted/2_columnar/` — transposition, key CRYPTO
- `encrypted/3_lfsr/` — stream cipher
- `encrypted/4_block/` — block cipher (not DES or AES)
- `encrypted/5_des_aes/` — DES and AES
- `encrypted/6_rsa/` — RSA-OAEP + AES

Each cipher folder contains `gsm8k.csv`, `svamp.csv`, and `math500.csv`. GSM8K and SVAMP answers are numbers. MATH-500 answers are stored as text, including LaTeX, and are not passed through numeric matching.
