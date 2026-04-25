# Round 3 plan

## Classification

- F1: MUST_FIX — Remove .hermes/round-2-plan.md from the PR (file violates scope) → .hermes/round-2-plan.md (delete), est lines: 0
- F2: MUST_FIX — Remove .hermes/round-2-plan.md from the PR (file violates scope) → .hermes/round-2-plan.md (delete), est lines: 0
- F3: MUST_FIX — Remove .hermes/round-2-plan.md from the PR (file violates scope) → .hermes/round-2-plan.md (delete), est lines: 0
- F4: MUST_FIX — Remove .hermes/round-2-plan.md from the PR (file violates scope) → .hermes/round-2-plan.md (delete), est lines: 0
- F5: MUST_FIX — Remove .hermes/round-2-plan.md from the PR (file violates scope) → .hermes/round-2-plan.md (delete), est lines: 0
- F6: MUST_FIX — Remove .hermes/round-2-plan.md from the PR (file violates scope) → .hermes/round-2-plan.md (delete), est lines: 0
- F7: MUST_FIX — Remove .hermes/round-2-plan.md from the PR (file violates scope) → .hermes/round-2-plan.md (delete), est lines: 0

ALL FINDINGS ARE THE SAME ISSUE: The `round-2-plan.md` file is outside the card's allowed scope.

## Budget check

- Total est lines: 0 (just removing a file that already exists)
- Files touched: 1 (.hermes/round-2-plan.md - deletion)
- Within R3 budget? YES (0 < 20)

## Verification commands to run after fix

- pytest tests/test_dict_helpers.py -v
- ruff check scripts/dict_helpers.py tests/test_dict_helpers.py
