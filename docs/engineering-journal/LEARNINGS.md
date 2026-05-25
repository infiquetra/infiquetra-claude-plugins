# Learnings — Infiquetra Claude Plugins

> **Empirical findings + mechanisms + fixes + validations.** When something turns out to be true that wasn't obvious — about a plugin's runtime behavior, the marketplace registry, hook timing, skill activation, MCP env propagation, build/test tooling, or a deploy gotcha — it goes here. Include the **evidence** (PR / commit / file:line / reproduction) and the **mechanism** (why it's true), not just the observation.
>
> **Append new entries to the top.** Most-recent first. Format:
>
> ```markdown
> ## YYYY-MM-DD
>
> ### Short descriptive title  {#slug}
>
> **Context.** One paragraph framing the situation.
> **Evidence.** Specific PR / commit / file:line / reproduction recipe.
> **Mechanism.** Why it happened (or why it's true) — root cause, not just symptoms.
> **Fix (or queued).** Concrete action + commit hash, OR a QUEUED.md ref if deferred.
> **Validation (if applicable).** What later run / test / install proved the fix.
> **What surprised (optional).** The thing that wasn't in the original mental model.
> **Generalizable rule.** The lesson stripped of this specific incident — what would I tell a future-me hitting a similar shape?
> **Refs.** Cross-links to DECISIONS / QUEUED / narratives / other LEARNINGS entries.
> ```
>
> The `{#slug}` HTML anchor on the entry title makes the entry linkable from `README.md` quick-nav and from cross-references. Keep slugs short and stable.
>
> When new evidence invalidates a learning, **update inline AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED**. Never silently overwrite.

---

## 2026-05-25

### Redis password URL-injection broke on URL-special characters  {#redis-url-password-encoding}

**Context.** Phase 2 headless integration test against live olympus-bus Redis failed at the `redis_bridge_connect` call with `"Port could not be cast to integer value as 'YPPu3qQ0VkURKkkm1J81l4'"`. The "port" was actually a suffix of the 44-char Hermes Redis password. fakeredis unit tests had passed because the test password was the literal string `"password"` with no URL-special chars; the bug was invisible in unit tests.

**Evidence.** `plugins/redis-bridge/server/redis_client.py:resolve_url_with_password` was building the netloc as `f":{password}@{host}:{port}"` with the raw password. When the password contained `:` (the user:password separator) or `@` (the auth:host separator), redis-py's URL parser tokenized it wrong and tried to interpret a substring as the port number.

**Mechanism.** Real Redis passwords from password generators or `openssl rand -base64 32` contain `:`, `+`, `/`, `=`, `@` etc. URL syntax for `://user:pass@host:port/db` is positional: the parser scans for the next `:` after the user (which would be inside our unencoded password). The fix is straightforward — `urllib.parse.quote(password, safe="")` — but the bug class is wider: **any URL component built from external input MUST be URL-encoded if not coming from a URL itself**.

**Fix.** `urllib.parse.quote(password, safe="")` on both the password and username before injection. Eight new regression tests in `tests/test_redis_bridge_redis_client.py` covering: no password / unset env / empty env / simple password / password with `:` / with `@` / with `/` / base64-shaped 44-char password / db-index preservation. Commit on Phase 2 follow-up.

**Validation.** Headless integration test rerun: all 4 phases pass end-to-end against live olympus-bus Redis. Real password (44 chars, base64-style) connects cleanly; redis-py URL parser doesn't barf.

**What surprised.** That the unit test suite — which had 76 fakeredis-backed cases by that point — never caught it. The seam was at the URL-build → `redis.Redis.from_url` boundary, and our fakeredis fixture bypasses URL parsing entirely (you instantiate `FakeRedis()` directly). A integration test against real Redis was the first thing that exercised the URL parser.

**Generalizable rule.** **Anytime you interpolate a value into a URL component, URL-encode it.** Doubly true when the value comes from an environment variable / user config / secret that you don't control the shape of. And: **fakeredis-backed unit tests don't exercise the URL parser** — for any plugin that builds Redis URLs, an integration test against real Redis is the only way to catch URL-formatting bugs.

**Refs.** `plugins/redis-bridge/server/redis_client.py`, `tests/test_redis_bridge_redis_client.py`, headless integration test at `$CLAUDE_JOB_DIR/integ_test.py`.

---

### FastMCP stdio loop doesn't exit on SIGTERM  {#fastmcp-stdio-sigterm}

**Context.** Phase 2 integration test's MCPClient.shutdown() called `proc.terminate()` (sends SIGTERM) and waited 5s, then fell back to SIGKILL. Every shutdown of the server process logged `[harness] server didn't exit on terminate; SIGKILL`. The redis-bridge server installs SIGTERM handlers, but they don't fire fast enough for shutdown to complete in 5s.

**Evidence.** `plugins/redis-bridge/server/channel.py:_install_signal_handlers` installs a handler that calls `_STATE.shutdown()` then `sys.exit(0)`. In practice the server only exits when its stdin closes (FastMCP's stdio transport blocks on the read loop). SIGTERM gets queued but doesn't interrupt the async stdin reader.

**Mechanism.** FastMCP runs the MCP server inside an `asyncio.run()` that drives `stdio_server()`. The stdio transport reads from stdin via `anyio` streams, which on macOS uses kqueue-backed file descriptors. SIGTERM is delivered to the Python process but the asyncio loop doesn't have a signal handler for it (we install a *signal* handler, not a *loop signal handler* via `loop.add_signal_handler`), so the handler runs synchronously on the main thread but can't preempt the blocking read.

**Fix (queued, not blocking).** Adding `loop.add_signal_handler(SIGTERM, ...)` would let asyncio receive the signal and cancel the stdio task. Out of scope for Phase 2's headless test (the integration test works fine with the SIGKILL fallback); queued for Phase 6 polish.

**Validation.** Integration test passes end-to-end despite the SIGKILL fallback. Server's atexit-registered cleanup still fires before kill (registry HDEL + hb DEL via the previous disconnect call in phase C; SIGKILL'd-phase server in phase D was *meant* to skip cleanup to test the stale-GC path).

**What surprised.** That the signal handler we installed runs but doesn't actually break the server out of its async loop within a useful timeframe. The classic Python signal trap — synchronous handlers can't interrupt blocking syscalls cleanly.

**Generalizable rule.** **In FastMCP-based stdio servers, use `asyncio.get_running_loop().add_signal_handler(...)` instead of `signal.signal(...)` for graceful shutdown.** Plain `signal.signal()` works at the language level but the asyncio loop doesn't see it, so it can't cancel the stdio read task. For tests / orchestration: don't rely on SIGTERM-then-wait for a clean exit; close stdin or fall back to SIGKILL.

**Refs.** `plugins/redis-bridge/server/channel.py:_install_signal_handlers`. Queued follow-up.

---

### Headless integration test caught two bugs unit tests didn't  {#integ-test-value}

**Context.** Built a headless harness that drives `python -m server` over real JSON-RPC stdio against live olympus-bus Redis. 4 phases: connect+inbound+notification round-trip, reply outbound XADD, graceful disconnect, SIGKILL+lazy GC. First run failed phase A with the Redis password URL-encoding bug above; second run (after fix) passed all 4 phases.

**Evidence.** Harness lives in `$CLAUDE_JOB_DIR/integ_test.py`. Bugs caught:
1. **Password URL-encoding** ([see entry above](#redis-url-password-encoding)) — would have shipped to first manual user run.
2. **FastMCP SIGTERM behavior** ([see entry above](#fastmcp-stdio-sigterm)) — known FastMCP-side issue but our wrapper code didn't paper over it.

Validated:
- Real `XREADGROUP` + `XADD` round-trip against Redis 7.0.15.
- AsyncNotifier successfully marshals `notifications/claude/channel` from the consumer thread → asyncio loop → JSON-RPC stdout.
- `_msg_id` correlation works end-to-end.
- `reply` tool XADDs the full Outbound payload with all fields (session_name, endpoint, chat_id, text, voice, in_reply_to, ts) round-tripping correctly.
- Lazy stale-GC: kill server without unregister → fresh server's `list` call lazily HDELs the stale registry entry.

**Mechanism.** fakeredis is a pure-Python redis-protocol implementation that doesn't go through redis-py's URL parser — you construct `FakeRedis()` directly. Anything that breaks at the URL-build → `Redis.from_url()` boundary is invisible to fakeredis-backed tests. Real Redis exercises the full stack including URL parsing, authentication handshake, stream consumer groups, and pubsub.

**Fix (artifact).** Promoting the harness into `plugins/redis-bridge/scripts/integ_test.py` so it lives with the plugin. Won't run in CI (needs real Redis + a keychain password) but documented as the way to verify before manual ship.

**Generalizable rule.** **For Redis-backed plugins, a live-Redis integration test is non-optional.** Unit tests with fakeredis verify the plugin's own logic; they cannot verify URL encoding, auth handshake, or any behavior that depends on the real wire protocol. Write the integration test as soon as you have a Redis to point at — even a synthetic harness like the one for redis-bridge catches real bugs the unit suite can't.

**Refs.** `$CLAUDE_JOB_DIR/integ_test.py` (transient), `plugins/redis-bridge/scripts/integ_test.py` (after promotion).

---

### Wrong-hostname propagation: stale plan + memory beats current inventory  {#redis-host-mac-mini-vs-olympus-bus}

**Context.** Plan + Phase 1 example config + Phase 2 PR body all asserted Redis lived at `jeffs-mac-mini.infiquetra.com:6379`. User caught it during verification-recipe handoff: Redis is actually on `olympus-bus.infiquetra.com` (10.220.1.64), a Proxmox-cluster VM. Migration off the Mac mini happened 2026-04-26 per `home-lab/ansible/inventory/hosts.yml` (`redis_bus` group, comment: "Renamed from olympus_bus 2026-04-26 (legacy pull-queue scaffolding stripped)").

**Evidence.**
- `home-lab/ansible/inventory/hosts.yml` redis_bus group: `olympus-bus.infiquetra.com → 10.220.1.64`.
- `host olympus-bus.infiquetra.com` → `10.220.1.64` (resolved).
- `nc -zv olympus-bus.infiquetra.com 6379` → Connection succeeded.
- The redis-bridge plan I'd written days earlier included this in its "Resolved by verification" section: `Redis auth + reachability: 10.220.1.64:6379 reachable`. The IP was right; I just paired it with the wrong hostname.
- Wrong references shipped in three files: `plugins/redis-bridge/docs/registry.example.json`, `plugins/redis-bridge/commands/redis-bridge-configure.md`, `plugins/redis-bridge/skills/redis-bridge/SKILL.md`. All fixed in this PR.

**Mechanism.** The plan was written from incomplete-context exploration, and the "Mac mini" / "Hermes Redis" association got cemented before I'd re-verified the actual host. Memory carried the IP forward but lost the hostname/host-association. When I wrote the example registry config in Phase 1, I reached for a hostname from conversation context (Mac mini) without re-checking the inventory. Twice in Phase 2 follow-up writeups I propagated the same wrong fact. The user's CLAUDE.md explicitly warns against this pattern ("Validation Discipline — NEVER assert without checking"), and I violated it.

**Fix.** Corrected the three files. Saved a feedback memory ([[verify-infra-facts-against-home-lab]]) + a reference memory ([[redis-bus-location]]) so future-me has both the rule and the canonical fact in one place. MEMORY.md updated to surface both at the top of the index.

**Validation.** `grep -rn jeffs-mac-mini plugins/redis-bridge/ docs/` now empty for the redis-bridge references. `host olympus-bus.infiquetra.com` and `nc -zv ... 6379` both succeed.

**What surprised.** That the wrong fact survived three writeups (Phase 0 plan, Phase 1 PR, Phase 2 PR body) even though my memory had the correct IP. The IP and the hostname are normally bound; here they got decoupled because I'd seen `10.220.1.64` in one context (Hermes Redis) and "Mac mini" in another (voice work) and merged them.

**Generalizable rule.** **Don't write infrastructure facts (hostnames, IPs, service-host mappings) into shipped code or docs without grepping `home-lab/ansible/inventory/` or live-probing first.** Plan documents and conversation context are not authoritative for infra — the home-lab inventory is. Plans from N days ago describing "where service X runs" are especially suspect because of the ongoing Mac-mini→Proxmox migrations. If you can't verify in the current context, say "I'd need to check — let me verify" instead of asserting. Mac mini hostnames are the highest-risk class because they're the legacy location for many services that have since moved.

**Refs.** [[verify-infra-facts-against-home-lab]] memory, [[redis-bus-location]] memory, `home-lab/ansible/inventory/hosts.yml` redis_bus group.

---

### Emitting custom MCP notification methods from FastMCP  {#fastmcp-custom-notification}

**Context.** Phase 2 of `redis-bridge` needs the MCP server to emit `notifications/claude/channel` — a notification type that's specific to Claude Code's channel protocol and **not** part of the upstream MCP spec. FastMCP's `Context` exposes `log/info/debug/error/elicit` but none of those emit a custom method name. The underlying `ServerSession.send_notification` accepts a typed `SendNotificationT` union, and Claude's `notifications/claude/channel` is not in that union.

**Evidence.**
- `[m for m in dir(Context) if not m.startswith('_')]` → no raw `send_notification` exposed.
- `ServerSession.send_notification` signature: `(notification: SendNotificationT, related_request_id)`. `SendNotificationT` is a discriminated union over Pydantic Notification subclasses keyed on the method literal — no `"notifications/claude/channel"` variant.
- But `mcp.types` also exports `Notification[Union[dict[str, Any], NoneType], str]` — a fully-generic Notification[params, method-as-str] form. This is the escape hatch.

**Mechanism.** `send_notification` doesn't actually validate that the notification method is in the spec union — it just calls `notification.model_dump(by_alias=True, mode='json', exclude_none=True)` and wraps the result in a `JSONRPCNotification`. The discrimination happens via Pydantic, but a generic `Notification[dict, str]` instance has `method: str` so it passes through verbatim. Static typing rejects it (`type: ignore[arg-type]` needed), runtime accepts it.

**Fix.** `plugins/redis-bridge/server/notifier.py` constructs `Notification[dict, str](method="notifications/claude/channel", params=payload)` and passes it to `session.send_notification(notif)` with a type-ignore. Threadsafe scheduling via `asyncio.run_coroutine_threadsafe` because the consumer thread isn't on the asyncio loop.

**Validation.** Phase 2 unit test `test_async_notifier_schedules_coroutine` constructs an AsyncNotifier with a stub session + a real asyncio loop running on a side thread, calls emit, and verifies the stub session's `send_notification` was awaited with `method="notifications/claude/channel"` and `params` matching.

**What surprised.** The MCP SDK exports a fully-generic `Notification[params, method-as-str]` type. Looking at the dir() of `mcp.types`, the entry `'Notification[Union[dict[str, Any], NoneType], str]'` was the giveaway — that's exactly the escape hatch for vendor-specific notification methods.

**Generalizable rule.** When you need to emit an MCP notification method that isn't in the SDK's `ServerNotificationType` union (Claude-specific extensions like `notifications/claude/channel`, or any other downstream extension): use the generic `Notification[dict, str]` form with a string method, accept the `type: ignore[arg-type]` on `send_notification`, and don't try to wedge it into the typed union. Static typing was wrong to demand discrimination here — the JSON-RPC protocol itself doesn't care.

**Refs.** `plugins/redis-bridge/server/notifier.py`; Phase 2 PR.

---

### `@dataclass(slots=True)` doesn't expose class-level field defaults  {#dataclass-slots-class-defaults}

**Context.** While building `plugins/redis-bridge/server/registry.py`, the loader read each config field via `defaults_raw.get(key, Defaults.heartbeat_seconds)` — reaching into the dataclass class to pull the field default. Five tests failed with `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'member_descriptor'`.

**Evidence.** Reproducer:

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class D:
    n: int = 10

print(type(D.n))  # <class 'member_descriptor'>  ← not int!
print(D().n)     # 10  ← only an *instance* has the value
```

`pytest` failure trail at `plugins/redis-bridge/server/registry.py:130` calling `int(Defaults.heartbeat_seconds)`. Fix commit in this PR replaces `Defaults.<field>` with `base = Defaults(); base.<field>`.

**Mechanism.** With `slots=True`, the dataclass `__slots__` machinery installs *descriptors* on the class to mediate per-instance attribute storage. Looking up `D.field` returns the descriptor object itself, not the field's default. Without `slots=True`, the class still has plain class attributes that happen to equal the defaults — so the pattern works by accident, masking the bug for any non-slotted dataclass. `dataclasses.fields(D)[i].default` is the *correct* way to read a field's default without instantiating.

**Fix.** Construct a `Defaults()` instance first and pull values off it; commit on branch `worktree-redis-bridge-phase1` (this PR).

**Validation.** 35 unit tests across session_id, registry, and presence now pass (was 30 passing + 5 failing).

**What surprised.** The error message ("not a real number") gives no hint that the issue is `slots=True`. I assumed a JSON-parsing bug for several minutes before the traceback pointed at `int(Defaults.heartbeat_seconds)`.

**Generalizable rule.** When you put `slots=True` on a dataclass, **do not read field defaults via `Class.field`** — that pattern returns the slot descriptor, not the default. Either (a) instantiate a default object and read from it, (b) call `dataclasses.fields(Class)`, or (c) drop `slots=True` if you want the convenience. This bug is invisible without slots, so it only shows up after you turn slots on for memory/lookup reasons.

**Refs.** Phase 1 PR for redis-bridge.

---

### MCP Python SDK's `RedisLike` Protocol stricter than the runtime  {#redis-like-protocol-too-strict}

**Context.** I declared a `RedisLike` `typing.Protocol` in `redis_client.py` to allow both `redis.Redis` and `fakeredis.FakeRedis` (used in tests) as Presence inputs without circular typing. mypy rejected `Presence(redis.Redis(...), ...)` because `redis.Redis.exists` returns `Awaitable[Any] | Any` (covering both sync and async clients) and my Protocol declared `-> int`.

**Evidence.** mypy on `channel.py:78`:

```
error: Argument 1 to "Presence" has incompatible type "Redis"; expected "RedisLike"
note: Following member(s) of "Redis" have conflicts:
note:     Expected: def delete(self, *names: str) -> int
note:     Got: def delete(self, *names: bytes|str|memoryview[int]) -> Awaitable[Any]|Any
```

**Mechanism.** `redis-py` types its client union-style (sync + async share one class hierarchy) so every call returns `Awaitable[Any] | Any`. A narrowed Protocol that promises a concrete return type can never be satisfied by such a wide union, even though the runtime behavior is exactly what we want.

**Fix.** `RedisLike = typing.Any`. Code keeps duck-typing; mypy is unblocked. Both `redis.Redis` and `fakeredis.FakeRedis` work at runtime as before. Commit on branch `worktree-redis-bridge-phase1`.

**Generalizable rule.** When a client library exposes both sync + async via one wide-union type, narrowing it via `Protocol` to be more useful in your code's signatures will fight you. Use `Any` (or accept that you're going to lose mypy coverage on those calls). The dynamic-typing escape hatch is the right tool here — Protocol is for protocols you actually want to enforce, not for shaving down third-party type uncertainty.

**Refs.** `plugins/redis-bridge/server/redis_client.py`.

---

### Verification findings while planning the `redis-bridge` plugin  {#redis-bridge-verification}

**Context.** During design of the `redis-bridge` + `hermes-claude-code-router` plan, several "obvious" claims about the Hermes-side infrastructure turned out to be wrong in ways that meaningfully reshaped the architecture. This entry captures the surprises for future plan-verification work.

**Evidence.**
- An earlier exploration agent reported voice-forge on Mac mini as listening at `0.0.0.0:9876` reachable from the LAN. Direct `lsof` proved it bound to `127.0.0.1:9876` only. Not a blocker (Hermes consumes it locally) but the initial plan's "127.0.0.1:9876 from laptop" wiring was wrong.
- `home-lab/ansible/inventory/group_vars/all/all.yml` was assumed to be whole-file vault-encrypted. `ansible-vault view` fails with "Input is not vault encrypted data" — the file uses inline `!vault` tags (field-level encryption). For per-secret extraction, must use `ansible -m debug -a "var=<name>"` or the Python `VaultLib` API, not the CLI.
- Discord voice-receive code was assumed to live in `home-lab/.../asgard_voice_arbiter/`. It doesn't — the arbiter is routing-only (~250 LoC). The actual sink/decode/buffer logic is in closed-source `hermes-agent.gateway.platforms.discord`. Mirroring it from the visible code was impossible; this killed the plan's original "plugin holds Discord directly" architecture and forced the Hermes-router pattern.
- Hermes plugins CAN register MCP-style tools the LLM can call: `ctx.register_tool(name, schema, handler)` at `hermes-extensions/docs/plugin-authoring.md:54`. No existing plugin uses the API yet; the new router will be the first.
- The Claude Code channels protocol does NOT have a native facility for `AskUserQuestion`-style structured questions. Verified by reading the official Discord channel plugin source and `https://code.claude.com/docs/en/channels-reference`. Coaching Claude is insufficient; the CC plugin must intercept the tool call deterministically.
- The Mimir Discord bot (ID `1486896133660868758`, Mount Olympus guild) does NOT currently have a Hermes profile on Mac mini — `~/.hermes/profiles/mimir/` doesn't exist. Building the bridge requires creating the profile first.

**Mechanism.** Earlier exploration agents conflated **proximity** ("X is referenced near Y") with **availability** ("X is implemented in this repo"). Clearest examples: voice-receive (referenced in arbiter, implemented in hermes-agent) and voice-forge (running on Mac mini, but as a local-bound daemon, not LAN-reachable). The agents reported the references; the implementation locations weren't independently verified.

**Fix.** Build proceeds with the architecture the actual ground truth supports: `redis-bridge` stays Hermes-agnostic; Hermes does all voice work via its existing pipeline; vault extraction switches to Python-based per-field; Mimir profile is a prereq before any bridge code runs. The plan's "Prerequisites" section codifies this; the LEARNINGS-flagged "I should have looked here first" findings shaped Decisions [redis-bridge-decoupled](DECISIONS.md#redis-bridge-decoupled) and [askuserquestion-interception](DECISIONS.md#askuserquestion-interception).

**What surprised.** That `ctx.register_tool` exists at all — initially I assumed Hermes plugins were hook-only and the LLM-fallback path would require modifying Hermes core. Reading `hermes-extensions/docs/plugin-authoring.md` end-to-end found the API in the first place I should have looked.

**Generalizable rule.** When a plan rests on "we can mirror Asgard's X" or similar reuse claims, **verify the implementation actually lives where the reference points** before committing to it. Two grep passes are cheaper than a 3–5 day rebuild. Specifically for reuse-of-existing-system claims, check that the visible code is the implementation, not just a thin wrapper around closed-source bits elsewhere.

**Refs.** [redis-bridge-decoupled](DECISIONS.md#redis-bridge-decoupled); plan at `/Users/jefcox/.claude/plans/i-would-like-to-distributed-hanrahan.md`.

---

## 2026-05-08

### Missing optional validator dependencies can hide invalid manifests  {#jsonschema-hidden-validation}

**Context.** CI consolidation restored `marketplace/validator/validate.py` and added `jsonschema` to dev dependencies so schema validation runs in normal CI installs.

**Evidence.** `python3 marketplace/validator/validate.py` passed in the system environment while warning `jsonschema not installed, skipping schema validation`. Running the same validator inside a temporary environment after `pip install -e ".[dev]"` failed on `plugins/sdlc-manager/.claude-plugin/plugin.json` because its description exceeded `marketplace/validator/schema.json`'s 200 character limit.

**Mechanism.** The validator treats missing `jsonschema` as a warning and continues. That made schema validation effectively optional in local and previous CI paths, so an invalid manifest could sit in the repository undetected until the dependency became available.

**Fix.** Added `jsonschema` to project dev dependencies and shortened the `sdlc-manager` plugin description to satisfy the schema limit.

**Validation.** `/tmp/infiquetra-plugins-verify-venv/bin/python marketplace/validator/validate.py` passes with `jsonschema` installed.

**Generalizable rule.** A validator's optional dependency is part of the validation contract. CI must install it, or invalid inputs can pass under a degraded "warning only" path.

**Refs.** `.github/workflows/ci.yml`; `pyproject.toml`; `marketplace/validator/validate.py`; `marketplace/validator/schema.json`.

---

## 2026-05-01

### Plugin code can ship without marketplace registration — the registry is a separate source of truth  {#marketplace-drift}

**Context.** A user reported that the `blueprint-reviewer` plugin did not appear when they tried to install plugins from this marketplace. The plugin's code lived under `plugins/blueprint-reviewer/` on `main` and was fully functional, but it was invisible to the marketplace UI.

**Evidence.**
- `plugins/blueprint-reviewer/` was added by PR #110 (merge commit `ae93035`) and Phase B work merged via PR #111 (commit `a7fea08`).
- Neither PR modified `.claude-plugin/marketplace.json`.
- At time of report: 15 plugin directories under `plugins/` but only 14 entries in `marketplace.json`.
- Fixed in PR #112 (commit `4da5705`).

**Mechanism.** Plugin code in `plugins/<name>/` and the marketplace registry in `.claude-plugin/marketplace.json` are independent files. PR review focused on the new plugin's code (skills, commands, scripts) and overlooked the one-line registry diff. Two PRs in a row missed it because the omission isn't visible in the plugin's own diff — it's a *missing* edit to a sibling file. Reviewers don't see absences.

**Fix.** PR #112 added the `blueprint-reviewer` entry to `marketplace.json` (mirrors `sdlc-manager`'s shape: `source`, `version`, `category: development`, keywords copied from the plugin manifest).

**Validation.** Post-merge: `python3 -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); print(len(d['plugins']))"` returns `15`; `'blueprint-reviewer' in [p['name'] for p in d['plugins']]` is `True`.

**What surprised.** That the bug shipped *twice* in a row (#110 and #111). The second PR was specifically follow-up work on the same plugin; the registry omission was right there to be noticed but wasn't.

**Generalizable rule.** When two files must stay in sync (plugin dir + registry, schema + migration, code + docs index, env var + Lambda config), reviewers will drift one against the other given enough opportunities. Add a CI assertion that fails on drift — don't rely on PR review.

**Refs.**
- [QUEUED.md](QUEUED.md#marketplace-ci-guard) — P1 work item for the CI guard.
- [DECISIONS.md](DECISIONS.md#gitignore-claude-and-no-uv-lock) — repo hygiene shipped alongside.
- [ARCHIVE.md](ARCHIVE.md#pr-112-marketplace-fix) — SHIPPED record.

---

### `marketplace.json` `Edit` calls must include the array's closing `]` in `old_string`  {#marketplace-edit-guard}

**Context.** When appending a new plugin entry to `.claude-plugin/marketplace.json`, the `Edit` tool can produce invalid JSON if the `old_string` doesn't include enough context to capture the array's closing bracket. This has misfired multiple times.

**Evidence.** Repeated occurrences traced through prior memory record `marketplace.json Editing Guard`. The wrong-pattern shape:

```json
    }
  ],
    {
      "name": "new-plugin",
      ...
    }
  ],
  "version": "2.0.0"
}
```

— two closing `]`, parser fails. Caught only by post-edit validation.

**Mechanism.** When `old_string` ends at the last entry's closing `}`, the `Edit` tool inserts the new content *after* the line, which lands it after the array's `]` rather than inside the array. The fix is to include both the previous last entry's closing `}` AND the array's `]` in the `old_string`, so the new entry can be inserted *before* the `]` (with a `,` added to the prior `}`).

**Fix.** Standard pattern — `old_string` extends through the array's closing `]` and at least the next line:

```
old_string: "      \"workflow\"\n      ],\n      \"category\": \"development\"\n    }\n  ],\n  \"version\": \"2.0.0\"\n}"
```

Always validate immediately: `python3 -m json.tool .claude-plugin/marketplace.json > /dev/null`.

**Validation.** PR #112 (commit `4da5705`) used this exact pattern and produced valid JSON on first try.

**Generalizable rule.** When using `Edit` on a JSON/YAML file to append into a nested array, the `old_string` MUST include the array's closing bracket. Inserting "before the `]`" is correct; inserting "after the prior entry's `}`" is wrong because edits land on the line *after* the match. Always validate the file with the language's parser immediately after the edit.

**Refs.** Same lesson cached in `~/.claude/projects/.../memory/marketplace_editing_guard.md` for runtime convenience; this file is the durable project record.

---
