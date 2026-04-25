# Round 2 plan

## Classification

- F1: MUST_FIX — Add verification that pytest was run and tests passed to satisfy plan fidelity → file(s): PR body/testing section, est lines: 5
- F2: MUST_FIX — Tighten the type annotation for the data parameter from bare `dict` to `dict[str, Any]` → file(s): scripts/dict_helpers.py:6, est lines: 1
- F3: MUST_FIX — Add a test to verify that get_nested() does not mutate the original input data → file(s): tests/test_dict_helpers.py, est lines: 8

## Budget check

- Total est lines: 14
- Files touched: 2
- Within R2 budget? YES

## Verification commands to run after fix

- pytest tests/test_dict_helpers.py -v
- ruff check scripts/dict_helpers.py tests/test_dict_helpers.py
- mypy scripts/dict_helpers.py