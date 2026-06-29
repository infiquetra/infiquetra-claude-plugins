# agy plugin — hardening + fork/copy decision (deferred dossier)

> **Status:** living dossier, **decision deferred until dogfooding is done.** Do NOT fork or copy yet.
> This file accumulates the hard-won mechanics of getting `/agy:delegate` to work, validates what we can,
> and frames the fork-vs-copy-vs-leave decision so we can make it deliberately **before the delegation
> practice goes into full/regular use** — not in the middle of a battle.

## Why this exists

Getting agy to run reliably through the Claude Code harness via `/agy:delegate` cost real, repeated
struggle across n=1 (#275) and n=2 (#277): a 21-minute zero-byte hang, a "teammate can't spawn a teammate"
error that somehow recovered, and a persistent fog over *why* the working invocation works. The behavior
is good enough to dogfood, but it is **not** good enough to hand to a future operator as-is. Before we rely
on it, we decide: leave the upstream plugin alone, fork + patch it, or copy it into our own.

This is **Track 1 (harness-coupled)** material from the [README](README.md) — it feeds capability **#287 /
#289**. It is explicitly *not* a build plan.

## The plugin as it actually is (validated from the installed code)

Source read: `~/.claude/plugins/cache/antigravity-cc/agy/0.4.1/` (upstream `antigravity-cc`, v0.4.1).

| Piece | What it does | Confirmed behavior |
|---|---|---|
| `commands/delegate.md` | The `/agy:delegate` slash command (`allowed-tools: Agent`) | Spawns `agy:runner` (**no `name`** → plain subagent). `--background` → `run_in_background: true` on the subagent; `--model <alias>` is forwarded; both flags stripped from the task text. |
| `agents/runner.md` | The `agy:runner` subagent (`tools: Bash` only, `model: sonnet`) | Makes **exactly one** `Bash` call to `agy-run.sh ask …` and returns stdout verbatim. **No custom Bash timeout set.** Cannot spawn agents (Bash-only). |
| `scripts/agy-run.sh` | The wrapper | `cmd_ask` → `"$agy" -p "$prompt" "$@"` — a **blocking foreground** call. **Never self-backgrounds.** `--model` patches `settings.json` under a `mkdir` lock (waits up to `AGY_LOCK_WAIT_SECONDS:-600`s, PID dead-holder detection), restored on EXIT/INT/TERM/HUP. |
| `skills/antigravity-cli/SKILL.md` | Internal runtime contract for the runner | "One wrapper call per task." Strip `--background` before forwarding. agy-native flags (`--sandbox`, `--print-timeout`, `--add-dir`) go *after* the prompt. |

**Key structural facts that resolve (or reframe) our battles:**

1. **The wrapper is blocking and never backgrounds.** Any backgrounding in the system is the *harness*
   backgrounding the runner subagent, never the script. So a fix for the `--background` hang lives at the
   spawn layer, not in `agy-run.sh`.
2. **The plugin's designed happy path is a plain foreground subagent** with no name and a default-timeout
   Bash call. For a *short* agy task that is fine; for a multi-minute coding run it collides with the main
   loop's ~2-min Bash cap (see Open Puzzle 2).
3. **The "teammate" framing is ours, not the plugin's.** The plugin never names the runner. We added a name
   to survive long runs — which is what introduced the "teammate can't spawn a teammate" error. That dance
   is a harness behavior layered on the plugin.

## The hard-fought battles (the record)

- **B1 — the 21-minute zero-byte hang (n=2/U1).** Launched with `--background` + cargo flags
  (`--add-dir`, `--dangerously-skip-permissions`, `--print-timeout 15m`, a `timeout: 900000` override).
  agy produced 0 bytes for 21 min. Fix: drop all of it; plain `/agy:delegate --model flash <task>`,
  foreground.
- **B2 — "use delegate, not the runner directly."** Spawning `agy:runner` by hand (bypassing
  `Skill(agy:delegate)`) is an anti-pattern; always go through the skill/command front door.
- **B3 — the named-runner / "teammate can't spawn a teammate" recovery.** Spawning the runner *with a
  name* (to survive a long run) threw `Teammates cannot spawn other teammates — omit the name parameter`,
  then **recovered** (prompt→file → shell fallback → success). Empirically: the **named** spawn succeeds
  for long runs; the **nameless** one dies under the ~2-min cap. We trusted the outcome over the error.
- **B4 — the orphan agent.** A thrashing runner spawned a stray agent that ran ~72 min and wrote to the
  tree *after* the PR was open. Mitigation: commit each unit immediately; `git status` before trusting "done".

## Validated findings (evidence-backed)

- ✅ **The wrapper does not self-background** — code-level (`agy-run.sh:317` `cmd_ask`). *Confirmed.*
- ✅ **`--background` is the only background vector, and it breaks long runs** — code-level
  (`delegate.md:15-16` → `run_in_background: true`) + empirical (B1: 0 bytes / 21 min). *Confirmed for the
  one path that exists.* The break is the harness detaching the runner, not the script.
- ✅ **The runner sets no Bash timeout** — code-level (`runner.md`, one `Bash` call, no `timeout`). So the
  default cap applies to the agy call. *Confirmed.*
- ✅ **The NAMED spawn is the ONLY working invocation — SETTLED (operator-confirmed).** Spawning
  `agy:runner` **with a `name`** (a persistent teammate) is the only way a real multi-minute delegation
  completes; the nameless plain subagent dies under the ~2-min cap, and **a long Bash `timeout` instead of
  a name is NOT a substitute** (only the name works). This is no longer an open "which mechanism" question.
  The named spawn's *first action* fails (`Teammates cannot spawn other teammates`) and then **recovers** —
  that failure-then-recovery is expected; do not strip the name over it.
- ⚠️ **Latent: the `settings.json` model-lock serializes concurrent `--model` calls** (up to 600s wait,
  `agy-run.sh:198`). Harmless for serial delegation; a real hang/contention surface for **parallel or
  distributed** delegation — book it for the distributed topology.

## Settled vs open

**SETTLED (operator-confirmed, do not re-litigate): the named spawn is the only solution.** Always spawn
`agy:runner` with a `name`. The nameless variant and the "long Bash timeout instead of a name" variant do
**not** work. This governs the rest of dogfooding — every delegation uses the named spawn and tolerates its
first-action failure.

**OPEN (deferred — not resolvable from code; need an experiment):**

1. **How to go straight to the recovery (skip the failed first action).** The named spawn's first action
   always fails with `Teammates cannot spawn other teammates — omit the name parameter`, then the runner
   recovers (prompt→file → shell fallback → success). We want to invoke the recovery path *directly* and
   skip the guaranteed-failing first attempt. The recovery is undocumented and unowned; characterize it
   first.
2. **Why does only the named spawn work?** Mechanism unknown (teammate persistence past the ~2-min cap is
   the leading guess, but unconfirmed). Lower priority than #1 — we can keep shipping with the named spawn
   regardless; this is a "understand it before we fork" item.

### The experiment to run (when we pick this up)

Goal is no longer "which spawn works" (settled = named). It is to **characterize the first-action failure +
recovery** so we can skip straight to it, and secondarily to explain *why* named works. One trivial agy
task (~3-min run), **reading agy's output from a file**, recording wall-time + bytes + rc + the exact
failure/recovery trace:

| Probe | What to capture | Question it answers |
|---|---|---|
| Named spawn, instrument the first action | the exact tool call + error + what the runner does next to recover | What IS the recovery path, and can we issue it directly? |
| Named spawn, vary how the runner is addressed on the first message | does a different first action avoid the error entirely? | Can the failed first attempt be designed out? |
| (control) nameless + `timeout: 900000` | wall-time + rc | re-confirm it still fails (named is required), for the record |
| (control) named + `--background` | wall-time + bytes | re-confirm the B1 hang — `--background` is the trap |

## The decision: leave / fork+patch / copy

| Option | What it means | Pros | Cons |
|---|---|---|---|
| **Leave upstream as-is** (default for now) | Keep using `antigravity-cc/agy`; encode the workarounds in our runbook + prompts | Zero maintenance; we get upstream fixes; the workaround already ships #275 + #277 | The traps stay; every operator must re-learn them from the runbook; we don't control regressions |
| **Fork + patch** | Fork `antigravity-cc/agy` (likely into the existing **`infiquetra-antigravity-plugins`** fork repo), patch the runner | Fixes the battles at the source; small surface (one runner + one script) | Maintenance + upstream-drift tracking; must re-point the marketplace install |
| **Copy into our own plugin** | New first-party plugin in this repo (or the fork repo), our naming | Full control; integrates with our release discipline | Largest ownership cost; reinvents what upstream maintains; we own all of agy's surface |

**What a fork/copy would concretely change (the patch list — pending the experiment):**
- Set a long **Bash `timeout`** (≈900s) on the runner's wrapper call so long agy runs don't hit the ~2-min cap.
- **Repair or remove `--background`:** either make a backgrounded run actually stream/capture output, or
  delete the flag and document that delegation is foreground-only.
- **Spawn the runner as a named teammate by default** (this is settled — the only working invocation), and
  **design out / skip the guaranteed-failing first action** so we go straight to the recovery path.
- **Capture agy output to a file** and read it back (robust to the stdout-compression hook), rather than
  relying on stdout.
- Optionally raise/parameterize `AGY_LOCK_WAIT_SECONDS` behavior for parallel use.

## Decision criteria + revisit trigger

**Revisit when** any of:
- We start using delegation **regularly** (beyond operator-initiated dogfood runs), OR
- the friction recurs on n≥3 despite the runbook, OR
- we begin the **distributed-delegation** topology (the model-lock + coordination concerns compound).

**Decide to fork/copy if** the experiment shows a small, stable patch set fixes the traps AND upstream is
unresponsive/slow. **Stay on upstream if** the runbook workaround proves reliable across more runs and
upstream stays maintained. Bias: **smallest durable change** — a one-line timeout patch beats a full copy.

## Pointers

blueprint [`blueprint.md`](blueprint.md) (Track 1 launch notes + per-engine adapter) · README + matrix
[`README.md`](README.md) · n=2 narrative
[`../engineering-journal/narratives/2026-06-29-agy-as-coder-dogfood-277.md`](../engineering-journal/narratives/2026-06-29-agy-as-coder-dogfood-277.md)
· LEARNINGS `#agy-delegate-plain-is-the-path` · enforcement home **#287** · existing fork repo
`infiquetra-antigravity-plugins` · upstream `antigravity-cc/agy` v0.4.1.
