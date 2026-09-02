# Changelog

## [1.2.2] - 2026-09-02

### Fixed

- **The composer row rule is one classification per physical row (#907).** A row
  continues an open block when it is bordered or when it is unbordered and
  indented past the marker column; a blank, a horizontal rule, a marker, or a
  row at or left of the marker ends the block.
- **A resend inspects when the pane is unowned or the launcher already typed
  into it (#907).** The inspection sits immediately before the write it
  authorises.
- **Adjacent glyph-led rows stay `unclassifiable` when the viewport cannot prove
  a new box (#907).**
- **`input_box_text_chars` is the visible length of the absorbed draft (#907).**
  One definition, recorded only when the box is staged.

## [1.2.1] - 2026-08-31

### Fixed

- **Composer geometry no longer turns pane chrome into a draft or an ambiguous draft into empty
  (#907).** Paired borders are structural, blank and merely indented rows no longer become input
  continuations, and adjacent glyph-led rows produce `unclassifiable` when the viewport cannot
  prove whether they are a new box. Marker detection remains anchored at the row prefix.
- **Every unowned-pane resend performs a fresh input inspection (#907).** A successful agent-prompt
  send no longer lets a later pane fallback bypass the staged-input guard.
- **The composer loader owns its source location and produces a named stop (#907).** Standalone and
  Orchestrate-ingested launchers resolve `composer.py` from the compiled launcher path without a
  caller-injected global; missing or unreadable parser files no longer escape as tracebacks.
- **The serialized input-box receipt is now documented as a complete contract (#907).** The skill
  and README enumerate every `input_box` value and the conditional redacted
  `input_box_text_chars` field.

## [1.2.0] - 2026-08-30

### Fixed

- **The unowned-pane guard no longer mistakes scrollback for the live composer (#907).** Composer
  parsing now lives in a bounded terminal parser, selects the last block positionally, terminates
  it at the first non-continuation row, understands bordered composers and per-attribute terminal
  resets, and covers the complete vendor roster. Claude, Codex, Grok, Agy, and Qwen have verified
  glyphs; Muse and OpenCode are explicit unsupported cases. Receipts distinguish
  `unclassifiable`, `not_found`, `unsupported_vendor`, `read_failed`, and `read_timeout`; an
  unambiguous staged draft still stops with only `input_box_text_chars`, never the text.
- **Launch and teardown failures retain recoverable session identity (#907).** A create timeout
  reconciles the target workspace's tab set into a minimal receipt, a genuine wrapper exit 124 is
  no longer confused with a synthesized timeout, and an already-absent owned tab is an idempotent
  successful close. Pane reads and close calls are bounded.
- **Receipt evidence now says exactly which checks ran (#907).** One receipt shape is completed in
  place, empty permission-token lists no longer claim argv confirmation, malformed receipt files
  produce a named recovery stop, and transcript files removed during preflight are skipped.

## [1.1.0] - 2026-08-30

### Fixed

- **A hanging session create is a named stop, not a blocked launch (#890).** `launch` runs the
  wrapper under an explicit deadline (`LAUNCH_CREATE_SECONDS`, 120 seconds — larger than every
  other deadline because it may reach another machine and cold-start a vendor CLI) and stops with
  a named message when the create times out or exits nonzero, instead of blocking without bound.
- **A pane this launch did not create is inspected before it is prompted (#897).** A session
  whose tab already existed may hold text somebody staged in its input box, and a prompt typed
  behind it can submit that text. The guard reads the box with styling intact and stops on
  unambiguous staged text, recorded only by character count and never cleared. Fully styled text
  can be byte-indistinguishable from a placeholder; version 1.2.0 records that case separately
  instead of claiming a distinction. The guard keys on tab ownership, not the wrapper's `reused`
  bit, which names the workspace and would inspect the ordinary create path.
- **A declared permission is honoured and confirmed, never silently downgraded (#896).** A
  permission value outside the vendor's map stops with a named message instead of falling back to
  the auto flags, and preflight confirms the declared posture against the launch argv, recording
  `permission_resolved` in the receipt distinctly from the requested value.
- **A stale transcript can no longer certify a launch's account (#889).** `launch` captures the
  create instant and passes it as a recency floor, so a statusline-silent session is confirmed
  only from a transcript written at or after that instant (one second of mtime slack absorbs
  filesystem granularity). The receipt records `account_evidence` — statusline, transcript, or
  none — beside the requested account.
- **A failing owned close is surfaced instead of swallowed (#888).** `close_run_session` returns
  the Herdr result and records a failing close (returncode and error text) on the unit note;
  `close_owned_session`, the CLI-facing variant, exits nonzero on the same failure. Unowned
  sessions still close nothing and report nothing.
- **A missing receipt path stops with a cause and a recovery, not a traceback (#887).**
  `close --receipt-json` on an argument that is neither an existing file nor inline JSON raises a
  `SystemExit` naming the path and the remedy. Inline JSON — object or array — keeps its existing
  behaviour, including the `receipt must be a JSON object` stop.
- **The skill stops overselling `--dry-run` (#880).** The guidance now names what dry-run confirms
  (resolved working directory, Herdr workspace, flag ordering, exact command) and what it does not
  validate (model, reasoning effort, account), and documents the real preflight — a bounded live
  launch with a read-back — under an ordering rule with secret-safety safeguards.

## [1.0.0] - 2026-08-25

### Added

- **Portable single-session launch contract (#777).** New plugin owns create-via-`agents`,
  verify-via-Herdr, prompt delivery, and owned cleanup. An ordinary session can launch one
  verified agent without starting an Orchestrate run. Orchestrate consumes the same module
  (`skills/agent-launcher/scripts/launcher.py`) and no longer keeps a private copy of the
  launcher seam. Explicit dependency on the canonical `herdr` skill for every interaction
  after the session exists; this plugin does not duplicate it. The Agent Plugins port is
  tracked at infiquetra-agent-plugins#22 and does not gate this release.
