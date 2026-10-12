# Pilot notes

No language model was loaded. No cached Qwen2.5 0.5B or 1.5B Instruct weights were found, and none were downloaded. Completions in `pilot_results.csv` come from the deterministic mock in `research/mocks.py`.

These accuracy numbers check that prompts, extraction, and the grouped table run. They are a pipeline check on scripted completions.

Extraction failures (`pred` null): 6 of 300.
Plaintext accuracy on this run: 0.9000.

## Grouped accuracy

| condition | encryption_method | with_example | n | accuracy |
|---|---|---|---|---|
| plaintext | none | false | 30 | 0.8000 |
| plaintext | none | true | 30 | 1.0000 |
| disclosed | caesar_3 | false | 30 | 0.5000 |
| disclosed | caesar_3 | true | 30 | 0.5000 |
| disclosed | columnar | false | 30 | 0.0000 |
| disclosed | columnar | true | 30 | 0.0000 |
| undisclosed | caesar_3 | false | 30 | 0.0000 |
| undisclosed | caesar_3 | true | 30 | 0.0000 |
| undisclosed | columnar | false | 30 | 0.0000 |
| undisclosed | columnar | true | 30 | 0.0000 |

## Disclosed Caesar samples

A completion counts as a decryption attempt when it contains a `Decrypted:` line. A completion with only a final answer counts as a guess.

Decryption attempt: gsm_0, gsm_2, gsm_4.
Guess only: gsm_1, gsm_3.

On this dry run the mock writes a `Decrypted:` line equal to the original question for even GSM8K ids, and writes `Final Answer: 0` with no decryption line for odd ids. That alternation is scripted so both scorer paths can be inspected.

### 1. gsm_0 (decryption attempt)

```
Shift each letter backward.
Decrypted: Janet’s ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins for her friends every day with four. She sells the remainder at the farmers' market daily for $2 per fresh duck egg. How much in dollars does she make every day at the farmers' market?
Final Answer: 18
```

### 2. gsm_1 (guess only)

```
I will guess a number.
Final Answer: 0
```

### 3. gsm_2 (decryption attempt)

```
Shift each letter backward.
Decrypted: Josh decides to try flipping a house.  He buys a house for $80,000 and then puts in $50,000 in repairs.  This increased the value of the house by 150%.  How much profit did he make?
Final Answer: 70000
```

### 4. gsm_3 (guess only)

```
I will guess a number.
Final Answer: 0
```

### 5. gsm_4 (decryption attempt)

```
Shift each letter backward.
Decrypted: Every day, Wendi feeds each of her chickens three cups of mixed chicken feed, containing seeds, mealworms and vegetables to help keep them healthy.  She gives the chickens their feed in three separate meals. In the morning, she gives her flock of chickens 15 cups of feed.  In the afternoon, she gives her chickens another 25 cups of feed.  How many cups of feed does she need to give her chickens in the final meal of the day if the size of Wendi's flock is 20 chickens?
Final Answer: 20
```

## Scorer checks

Hand-written completions passed: decrypt_and_correct, dollar_and_commas, missing_final_answer, guess_without_decrypt, partial_decrypt, last_final_answer_wins, negative_answer.

## Mock policy

- Plaintext, no example, id number divisible by 5: omit `Final Answer` so extraction fails.
- Other plaintext rows: `Final Answer` is the gold number.
- Disclosed Caesar, even id: decrypt line is the original question, and the gold answer is given.
- Disclosed Caesar, odd id: guess `0` and do not decrypt.
- Disclosed columnar: decrypt line is the original question, and the answer is `0`.
- Undisclosed: guess `0` and do not decrypt.
- `with_example` does not change the mock text, except that the plaintext extraction failure is only on the no-example variant.

The pilot uses `none`, `caesar_3`, and `columnar`. `caesar_7` is in the encrypted table and is not in this 30-question run.
