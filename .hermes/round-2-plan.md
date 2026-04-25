# Round 2 plan

## Classification

- F1: MUST_FIX — Add non-mutation test to verify source dict remains unchanged → tests/test_dict_helpers.py, est lines: 8
- F2: MUST_FIX — Add type annotation for `default` parameter → scripts/dict_helpers.py, est lines: 1
- F3: MUST_FIX — The AC gap is the same as F1 (non-mutation verification) → tests/test_dict_helpers.py, est lines: 8
  Note: F1 and F3 are essentially the same finding from different reviewers (plan_fidelity and test_presence both reference the missing non-mutation test). I'll combine into ONE test.

## Budget check

- Total est lines: 9 (8 for test + 1 for type hint)
- Files touched: 2 (scripts/dict_helpers.py, tests/test_dict_helpers.py)
- Within R2 budget? YES (9 < 30)

## Verification commands to run after fix

- pytest tests/test_dict_helpers.py -v
- ruff check scripts/dict_helpers.py tests/test_dict_helpers.py
