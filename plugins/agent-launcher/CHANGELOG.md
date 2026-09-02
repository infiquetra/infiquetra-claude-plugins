# Changelog

## [1.3.0] - 2026-09-02

### Added

- **`redeliver` subcommand (#907).** The standalone retry for a staged-input stop. It takes the
  tab, pane and ownership from the receipt the stop wrote and the task from the same flags
  `launch` takes; it refuses a receipt written for another task, one that does not record a
  staged-input stop, or one with no pane; it never runs the wrapper create; and it exits
  nonzero when the prompt was not observed to be taken. Before, the only visible recovery was
  a second `launch`, which created a second session over the first owned tab.

### Changed

- **Every pane write after the first is inspected, whatever the ownership (#907).** The write
  half of the guard predicate now records that the launcher wrote into the session, not which
  door carried the line. Before, a successful `herdr agent prompt` left it false, so an owned
  session's two resends -- and every write of a redelivery -- went out with no composer
  inspection. The rule has one owner, `should_guard_pane_write`, which Orchestrate's later
  senders call too. The 1.2.2 line below describing the resend rule as "unowned or the launcher
  already typed into it" described the defective predicate.
- **`redeliver()` refuses a session that has left idle (#907).** It inherits the resend loop's
  own precondition: a working, blocked or gone session may already hold the task, so the retry
  route closes as `prompt_undelivered` for the operator to check instead of risking a second
  delivery.
- **Both pane writes carry a timeout, `PANE_WRITE_SECONDS` (#907).** They were the only Herdr
  calls with no bound. A prompt that times out is a named stop and never falls through to the
  pane door.
- **The composer parser is linear on unterminated OSC sequences, and is handed at most
  `PANE_INSPECT_MAX_CHARS` characters from the tail of the pane (#907).**
- **`say()` and `send()` return nothing; `pane_input_text()` is removed (#907).** No caller was
  left that could use either safely.

## [1.2.2] - 2026-09-02

### Fixed

- **A broken composer parser is one named stop in both entry modes (#907).** A parser file
  that raises on import stops `launch` with the exception type and message, standalone and
  ingested by Orchestrate, instead of escaping as a traceback.
- **A failed tab close records its note once (#907).** `close_run_session` is the single
  writer of the close-failure note and tests membership on the whole note, so repeated
  failures no longer stack copies.

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
