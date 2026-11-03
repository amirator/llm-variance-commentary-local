# Evaluation results

35 fact sheets (16 SAMA quarters, 5 Costco fiscal years, 12 LA City months, 2 LA City budget years).
Each sheet gets up to 3 model attempts; if none passes the validator, the deterministic template is used.
Temperature 0.3, top-p 0.9, seed 7 + attempt number, CPU only (8 threads).

## Headline

| Model | First-attempt pass | Passed within 3 attempts | Template fallback | Attempt pass rate | Mean s / attempt |
|---|---|---|---|---|---|
| Qwen2.5-1.5B-Instruct Q4_K_M | 24/35 (69%) | 30/35 (86%) | 5/35 (14%) | 58% of 52 | 15.4 |
| Qwen2.5-0.5B-Instruct Q4_K_M | 6/35 (17%) | 7/35 (20%) | 28/35 (80%) | 8% of 93 | 6.3 |

## By source

| Source | Qwen2.5-1.5B-Instruct Q4_K_M: first / within 3 | Qwen2.5-0.5B-Instruct Q4_K_M: first / within 3 |
|---|---|---|
| SAMA POS (quarterly YoY) | 11/16 / 14/16 | 3/16 / 4/16 |
| Costco SEC (fiscal-year YoY) | 2/5 / 2/5 | 2/5 / 2/5 |
| LA City GF (monthly YoY) | 10/12 / 12/12 | 1/12 / 1/12 |
| LA City GF (budget vs actual) | 1/2 / 2/2 | 0/2 / 0/2 |

## Why drafts were rejected

Share of all model attempts that had at least one issue of each type (an attempt can have several).

| Issue type | Qwen2.5-1.5B-Instruct Q4_K_M | Qwen2.5-0.5B-Instruct Q4_K_M |
|---|---|---|
| unsupported_number | 7 of 52 | 43 of 93 |
| missing_driver | 2 of 52 | 44 of 93 |
| wrong_direction | 7 of 52 | 44 of 93 |
| unsupported_claim | 14 of 52 | 9 of 93 |
| unit_mismatch | 0 of 52 | 0 of 93 |
| unsupported_entity | 0 of 52 | 5 of 93 |
| missing_headline | 0 of 52 | 33 of 93 |
| unsupported_period | 0 of 52 | 0 of 93 |
| wrong_currency | 0 of 52 | 0 of 93 |
| format | 2 of 52 | 63 of 93 |

## Validator stress test

Synthetic corruptions applied to every model draft that passed (see `src/vcomm/mutate.py`).

| Corruption | Cases | Caught | Rate |
|---|---|---|---|
| hallucinated_number | 37 | 37 | 100% |
| flipped_direction | 36 | 34 | 94% |
| unsupported_entity | 37 | 37 | 100% |
| unsupported_claim | 37 | 37 | 100% |
| dropped_required_driver | 37 | 37 | 100% |
