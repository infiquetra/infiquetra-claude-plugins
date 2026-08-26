#!/usr/bin/env bash
#
# Local pre-merge gate — runs every substantive CI step and proves that it did.
#
# WHY THIS EXISTS
#
# CLAUDE.md documents four quality commands. CI runs twenty-four pre-merge steps.
# An earlier ad-hoc version of this script ran ten of them and printed
# "GATE GREEN — 10/10 steps ran", because its completeness assertion compared the
# number of steps it ran against EXPECTED_STEPS=10 — a constant chosen by the same
# author whose coverage it was supposed to be checking. A self-check calibrated by
# its own author checks nothing.
#
# So the assertion here compares coverage against .github/workflows/ci.yml itself.
# Add a step to the workflow and this gate FAILS until the step is covered below.
# That is the only property of this script that must not be weakened.
#
# BLOCKING vs ADVISORY
#
# A step is advisory here only where CI itself does not block on it — a trailing
# `|| true`, or a live-gated check the runner cannot perform. Advisory steps still
# run and still print their findings; they do not fail the gate, because the gate's
# job is to predict CI. Never mark a step advisory to make the gate pass.
#
# USAGE
#   # Supported long-run background invocation:
#   GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1 &
#   # Foreground inner-loop invocation:
#   scripts/gate.sh
#   GATE_LOG_DIR=/tmp/g scripts/gate.sh
#
# RESULT CAPTURE & SAFE RE-ENTRY
#   - Stable result marker: writes $LOG_DIR/result.txt on completion or interruption.
#   - Safe re-entry rule: if a prior gate run timed out, was killed, or is already running:
#       1. Check for running gate processes: pgrep -fl "scripts/gate.sh"
#       2. Kill the stale pid that step 1 named: kill <pid>.  Do NOT reach for
#          `pkill -f "scripts/gate.sh"` by reflex — it kills every gate on the machine,
#          including live gate runs in your other worktrees.
#       3. Clean up or set a fresh GATE_LOG_DIR and re-run.
#
# Exit: 0 green · 1 a blocking step failed · 2 coverage is short of ci.yml · 3 precondition failed

set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

CI=.github/workflows/ci.yml
LOG_DIR="${GATE_LOG_DIR:-$(mktemp -d)}"
RESULT_FILE="$LOG_DIR/result.txt"

# Stable result marker capture: write the final status line to $LOG_DIR/result.txt
# so backgrounded runs can be inspected without scraping live terminal output. The one
# outcome with no marker is an unwritable LOG_DIR — by definition nothing can be written
# there; that failure reports itself on stderr instead.
_on_term() {
  echo "GATE INTERRUPTED — killed by SIGTERM before completing all steps" > "$RESULT_FILE"
  exit 143
}
trap _on_term TERM

_on_int() {
  echo "GATE INTERRUPTED — killed by SIGINT before completing all steps" > "$RESULT_FILE"
  exit 130
}
trap _on_int INT

_on_exit() {
  local rc=$?
  if [ ! -f "$RESULT_FILE" ]; then
    if [ "$rc" -ne 0 ]; then
      echo "GATE INTERRUPTED — exited with code $rc before completing all steps" > "$RESULT_FILE"
    fi
  fi
}
trap _on_exit EXIT

# Every step redirects into LOG_DIR. If it does not exist or is not writable, the
# redirect fails before the command runs and *every* step reports failure — which
# reads as twenty broken checks rather than one broken directory. Fail here instead,
# with the actual reason.
mkdir -p "$LOG_DIR" 2>/dev/null || true
if ! : > "$LOG_DIR/.gate-writable" 2>/dev/null; then
  echo "gate.sh: log directory is not writable: $LOG_DIR" >&2
  echo "  (set GATE_LOG_DIR to a writable path, or unset it to use a temp dir)" >&2
  exit 3
fi
rm -f "$LOG_DIR/.gate-writable"

# A reused GATE_LOG_DIR (the documented /tmp/gate-run) can still hold the PREVIOUS
# run's verdict. A run killed with an untrappable signal never overwrites it, so the
# documented `cat $LOG_DIR/result.txt` would report that older run's GATE GREEN as
# this run's outcome. Clear it: while a run is in flight the marker is simply absent.
rm -f "$RESULT_FILE"

# Same class of precondition. A checkout synced without the dev extra has no ruff, no
# mypy and no pytest, so those steps fail with "No module named ..." and the run reads
# as a broken codebase rather than an unprovisioned environment. This bites hardest in
# a fresh git worktree, which does not inherit the parent checkout's .venv.
missing_tools=""
for tool in ruff mypy pytest; do
  uv run python -c "import $tool" >/dev/null 2>&1 || missing_tools="$missing_tools $tool"
done
if [ -n "$missing_tools" ]; then
  echo "gate.sh: the dev toolchain is not installed in this environment:$missing_tools" >&2
  echo "  run: uv sync --locked --extra dev" >&2
  echo "  (a fresh git worktree does not inherit the parent checkout's .venv)" >&2
  echo "GATE PRECONDITION FAILED — dev toolchain not installed:$missing_tools" > "$RESULT_FILE"
  exit 3
fi

# #405: mermaid.parse() runs in Node. Missing Node is the same class of
# unprovisioned-environment failure as missing ruff — not a red codebase.
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "gate.sh: node and npm are required for the mermaid syntax check" >&2
  echo "  install Node.js 22+ (CI uses actions/setup-node node-version 22)" >&2
  echo "GATE PRECONDITION FAILED — node/npm not installed" > "$RESULT_FILE"
  exit 3
fi

ran=0 failed=0 advisory_failed=0
declare -a FAILED_NAMES=() ADVISORY_NAMES=() COVERED=()

# The diff-aware guards need a base ref. For the release-surface bump guard, that is the
# authoritative tip of origin/main (to ensure versions advance over main's current tip).
# For the journal newest-first lint, that is the merge base with main.
git fetch -q origin main 2>/dev/null || true
RELEASE_BASE_REF="${RELEASE_BASE_REF:-origin/main}"
PR_BASE_SHA="$(git merge-base HEAD origin/main 2>/dev/null || git rev-parse HEAD)"
export PR_BASE_SHA

_run() {                       # _run <blocking|advisory> "<ci.yml step name>" cmd...
  local mode="$1" name="$2"; shift 2
  COVERED+=("$name")
  ran=$((ran + 1))
  local slug; slug=$(printf '%s' "$name" | tr -c 'a-zA-Z0-9' '_' | cut -c1-60)
  local marker=""; [ "$mode" = advisory ] && marker=" [advisory — CI does not block]"
  printf '=== %02d %s%s\n' "$ran" "$name" "$marker"
  if "$@" > "$LOG_DIR/$slug.log" 2>&1; then
    tail -3 "$LOG_DIR/$slug.log" | sed 's/^/    /'
    return 0
  fi
  if [ "$mode" = advisory ]; then
    advisory_failed=$((advisory_failed + 1)); ADVISORY_NAMES+=("$name")
    echo "    ADVISORY FINDING — does not fail the gate, but read it:"
    tail -12 "$LOG_DIR/$slug.log" | sed 's/^/    /'
  else
    failed=$((failed + 1)); FAILED_NAMES+=("$name")
    echo "    *** FAILED — full log: $LOG_DIR/$slug.log"
    tail -25 "$LOG_DIR/$slug.log" | sed 's/^/    /'
  fi
}
step()     { _run blocking "$@"; }
advisory() { _run advisory "$@"; }

# CI checks out clean, so it never sees a local .venv. This one does, and the lint
# walks whatever it is given. Report only violations in tracked, non-ignored paths.
tracked_test_shape() {
  local out; out="$(uv run python scripts/lint_test_shape.py tests plugins --prod-module server 2>&1)"
  local rc=$? real=0
  while IFS= read -r line; do
    case "$line" in
      VIOLATION*)
        local p="${line##*: }"
        if git check-ignore -q "$p" 2>/dev/null; then
          echo "ignored (not in CI's checkout): $p"
        else
          real=$((real + 1)); echo "$line"
        fi ;;
      *) echo "$line" ;;
    esac
  done <<< "$out"
  [ "$real" -eq 0 ] && return 0
  return "${rc:-1}"
}

# --- tests -------------------------------------------------------------------
step "Issue-contract vendored parity (consumer-side gate)" \
  python3 plugins/mission-control/config/generated/check_issue_contract_parity.py
step "Run tests with coverage" \
  uv run python -m pytest -q --cov=plugins --cov-report=term-missing

# --- validate ----------------------------------------------------------------
step "Validate plugin manifests"     uv run python scripts/validate_plugins.py
step "Validate marketplace registry" uv run python marketplace/validator/validate.py
step "Validate ownership lanes"      uv run python scripts/check_ownership_lanes.py --verbose
step "Engine Registry"               uv run python plugins/saga/scripts/check_engine_registry.py
step "Engine Registry Conformance"   uv run python plugins/saga/scripts/engine_registry_conformance.py
step "Agent-file spec lint (frontmatter, role-class tiers, tool-scope floor)" \
  uv run python tools/agent_spec.py --report
step "Mission-control pagination-completeness lint" \
  uv run python plugins/mission-control/scripts/check_pagination.py
# Live-gated: the CI runner has no Projects-scoped token and exits 0 as SKIPPED, so
# CI cannot block on this and neither does the gate. A developer machine WITH a
# token is the only place it really runs — which is why a real drift can sit here
# unnoticed. Read the finding when it appears.
advisory "Board schema census drift check (best-effort, live-gated)" \
  uv run python plugins/mission-control/scripts/board_census.py --check

# --- release surfaces --------------------------------------------------------
step "marketplace.json matches plugin.json (generator --check)" \
  uv run python scripts/sync_marketplace.py --check
step "Tri-lock release-surface parity (plugin.json == marketplace == CHANGELOG)" \
  uv run python scripts/check_release_surface_parity.py
step "CHANGELOG heading grammar lint (fleet baseline)" \
  uv run python -m pytest tests/test_changelog_heading_lint.py -k fleet_baseline -q
step "Diff-aware release-surface bump guard" \
  uv run python tools/release_surface_diff_guard.py --base-ref "$RELEASE_BASE_REF"
step "Journal newest-first guard (new entries)" \
  uv run python scripts/lint_journal_order.py --base-ref "$PR_BASE_SHA"

# --- lint --------------------------------------------------------------------
step "Run ruff check"        uv run python -m ruff check .
step "Run ruff format check" uv run python -m ruff format --check .
step "Test-shape lint (fake-only test suites)" tracked_test_shape
advisory "Golden-fixture drift check (advisory)" \
  uv run python scripts/check_fake_fixtures.py --check --advisory
step "Gate operator-absence contract lint" \
  uv run python plugins/saga/scripts/lint_gate_absence_contract.py
step "Engineering-journal ordering lint" uv run python scripts/lint_journal_order.py
step "Mermaid syntax check" bash -c 'npm ci --prefix scripts/mermaid && uv run python scripts/check_mermaid.py'

# --- type check + security ---------------------------------------------------
step "Run mypy" uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports
# CI ends this step with `|| true`, so bandit findings never block a merge there.
advisory "Run bandit security scan" \
  uv run python -m bandit -r plugins/ scripts/ tests/ tools/ -ll -f json -o "$LOG_DIR/bandit.json"
advisory "Report security findings" \
  bash -c 'f="$0/bandit.json"; [ -f "$f" ] && python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(\"bandit results:\",len(d[\"results\"]))" "$f"' "$LOG_DIR"

# --- completeness, measured against the pipeline -----------------------------
echo
echo "================ GATE SUMMARY ================"
missing="$(python3 - "$CI" "${COVERED[@]}" <<'PY'
import re, sys, pathlib
ci = pathlib.Path(sys.argv[1]).read_text().splitlines()
covered = set(sys.argv[2:])
skip = ("Checkout", "Set up", "Install dependencies", "Upload", "Cache")
job = name = None
for line in ci:
    j = re.match(r"^  ([a-z][a-z0-9_-]*):\s*$", line)
    if j:
        job = j.group(1)
    m = re.match(r"\s+- name: (.+)", line)
    if m:
        name = m.group(1)
    if re.match(r"\s+run:", line):
        if name and job != "publish" and not any(name.startswith(s) for s in skip):
            if name not in covered:
                print(name)
        name = None
PY
)"
echo "steps ran:      $ran"
echo "blocking fails: $failed"
echo "advisory notes: $advisory_failed"
if [ "$advisory_failed" -ne 0 ]; then
  printf '  ! %s\n' "${ADVISORY_NAMES[@]}"
fi
if [ -n "$missing" ]; then
  echo
  echo "GATE INCOMPLETE — ci.yml has pre-merge steps this gate does not cover:"
  printf '%s\n' "$missing" | sed 's/^/  - /'
  echo "NOT a pass. Cover them above, then re-run."
  echo "GATE INCOMPLETE — ci.yml has pre-merge steps this gate does not cover" > "$RESULT_FILE"
  exit 2
fi
echo "coverage:       every pre-merge step in $CI is covered"
if [ "$failed" -ne 0 ]; then
  echo
  echo "GATE RED — ${failed} blocking step(s) failed:"
  printf '  - %s\n' "${FAILED_NAMES[@]}"
  echo "GATE RED — ${failed} blocking step(s) failed: ${FAILED_NAMES[*]}" > "$RESULT_FILE"
  exit 1
fi
echo "GATE GREEN — ${ran} steps ran, 0 blocking failures, 0 uncovered."
echo "logs: $LOG_DIR"
echo "GATE GREEN — ${ran} steps ran, 0 blocking failures, 0 uncovered." > "$RESULT_FILE"
