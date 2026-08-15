"""Tests for the `/orchestrate` Claude command loader and `/outcome`'s mechanical deprecation.

`/outcome` is deprecated without deleting anything, across TWO independent selection surfaces:

- Its COMMAND `description:` frontmatter (`plugins/saga/commands/outcome.md`) is rewritten so it
  no longer reads like a general orchestration request — this is the field a model matches intent
  against when picking a command; a deprecation notice in the command body changes nothing about
  that decision. The approved text is pinned verbatim (section 2,
  `test_outcome_description_is_the_pinned_approved_text`) — that pin is the actual guard against a
  future rewrite reading as a general orchestration pitch. Sections 2 and 2b also keep a
  fixed-stem check and a structural pitch-vocabulary check as readable diagnostics for WHY a
  candidate text was rejected, but neither is exhaustive and neither decides what's accepted —
  see the design points below.
- Its SKILL `description:` frontmatter (`plugins/saga/skills/outcome/SKILL.md`) is a second,
  independent selection surface — Claude can invoke a same-named skill on its own initiative from
  a natural-language request, not just via the command. Rewriting that text would replay the same
  synonym-dodging problem the paragraph below names, so it is left untouched and
  `disable-model-invocation: true` is added instead, which stops model-initiated selection
  structurally rather than lexically. Section 3 covers this.

Three design points worth stating plainly, since each was the actual failure mode found here:

- **A vocabulary list is only as good as the text it's checked against, and it is never
  exhaustive.** A list declared but never run against real description text is a test that reports
  safety that is not there — fixed by running the fixed-stem checker against the captured ORIGINAL
  pre-rewrite text (`test_vocabulary_checker_flags_the_original_pre_rewrite_description`). A fixed
  word set can also always be dodged by a synonym nobody added yet; the structural pitch-vocabulary
  check in section 2b closes part of that gap by deriving banned words from `/orchestrate`'s own
  live description instead of a hardcoded guess-list
  (`test_pitch_checker_catches_adversarial_rewrites_the_fixed_stem_list_misses`) — but even it only
  watches words `/orchestrate`'s description currently uses, so a rewrite using neither a banned
  stem nor one of those current words still slips past both heuristics
  (`test_pitch_checker_has_a_real_blind_spot_the_pinned_description_closes` names one). Growing the
  word list further would not fix that; it is the same defeatable shape at a longer length. The
  fixture-pinned exact-match test is what actually closes it: a candidate either matches the
  approved text byte-for-byte or it doesn't ship, independent of what any heuristic catches.
- **A command's own selection field is not the only one that matters.** The first round of this
  work treated `plugins/saga/commands/outcome.md`'s `description:` as the whole deprecation
  surface; the same-named skill's OWN `description:` was a second, live surface carrying the exact
  vocabulary the command fix removed. Section 3 closes it.
- **A regression fixture that's also caught by an unrelated check doesn't prove the checker it's
  attached to does anything.** The adversarial rewrites in section 2b originally all led with
  `start`, so a later, separate `start`-absence check would have caught them independently of
  pitch-checking. They're written without `start` now, so each one is caught by the mechanism its
  test actually names.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent

ORCHESTRATE_CMD = ROOT / "plugins" / "orchestrate" / "commands" / "orchestrate.md"
ORCHESTRATE_SKILL = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "SKILL.md"
ORCHESTRATE_PLUGIN_JSON = ROOT / "plugins" / "orchestrate" / ".claude-plugin" / "plugin.json"

OUTCOME_CMD = ROOT / "plugins" / "saga" / "commands" / "outcome.md"
OUTCOME_SKILL = ROOT / "plugins" / "saga" / "skills" / "outcome" / "SKILL.md"
SAGA_SCRIPTS_DIR = ROOT / "plugins" / "saga" / "scripts"

MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"

REPLACEMENT_COMMAND = "/orchestrate"

# The ORIGINAL description this unit replaced (captured verbatim, not re-derived from the current
# file), used only to prove the checker below is behavioural — see the module docstring.
ORIGINAL_OUTCOME_DESCRIPTION = (
    "Coordinate a whole outcome as a durable DAG of leaf sagas — start, advance the ready "
    "frontier, attend a leaf, resume, graph, export/import. The coordinator routes and "
    "dispatches to executors; it never runs leaf work itself, and status is derived on read."
)

# The APPROVED current `/outcome` description, pinned verbatim. This — not the fixed-stem or
# pitch-vocabulary checks below — is the actual guard against a future rewrite reading as a
# general orchestration pitch: a candidate either matches this byte-for-byte or it doesn't ship.
# A future, legitimate copy change updates THIS constant as a conscious, reviewed act; the
# heuristic checks below keep running and keep explaining WHY a rejected candidate was rejected,
# when they're able to, but they are diagnostics now, not the thing that decides acceptance.
APPROVED_OUTCOME_DESCRIPTION = (
    "Operate on an outcome already split into a DAG of leaf sagas — advance the ready frontier, "
    "attend a leaf, resume, graph, discover, handoff, attach. Each leaf's work happens through "
    "its own native saga command, never inline here, and status is derived on read rather than "
    "stored. Deprecated in favor of /orchestrate, which takes the outcome as its argument and "
    "discovers the work's shape during planning instead of requiring the DAG decomposed up front."
)

# Orchestration-intent vocabulary `/outcome`'s description must no longer contain. Each entry is a
# word STEM, matched as a lowercase substring, so one entry catches every inflection (verb, noun,
# plural) without hand-listing each form. A word that legitimately describes what `/outcome` itself
# still does is deliberately NOT here — see the "kept" note after the list.
#
# - "coordinat"  — coordinate / coordinator. The generic verb for cross-vendor orchestration work;
#                  that job now belongs to /orchestrate, whose own description uses it instead.
# - "dispatch"   — dispatch / dispatches / dispatched. /orchestrate's register dispatches vendor
#                  children (R1/R4 of the orchestrate plan); reusing it in /outcome's description
#                  would describe the same product twice.
# - "executor"   — executor / executors. /orchestrate's whole model is vendor children being routed
#                  and dispatched to; /outcome hands a leaf to its own native saga command
#                  (`/resume`, `/work`, `/code-review`, `/qa`), never to an abstract executor pool.
# - "route"      — route / routes / routing / router. Vendor selection and routing for capacity and
#                  capability is /orchestrate's job (R8); /outcome doesn't choose among vendors at
#                  all, so this word never described a capability /outcome has.
#
# Kept (deliberately absent from the banned list) because /outcome genuinely still does or is this:
# "outcome" (the object both commands act on — it's literally /outcome's own name), "DAG" / "leaf
# saga(s)" / "frontier" (the specific data structure /outcome manages — a graph-theory term, not a
# generic pitch for orchestration), and the verbs the description names: advance, attend, resume,
# graph, discover, handoff, attach. ("start" is deliberately NOT in the description even though the
# command still runs it — see `test_outcome_description_does_not_lead_with_start`; "export"/"import"
# are deliberately NOT in the description even though `argument-hint` still lists them, because
# they're a retired read-only-alias pair, not a live capability — see
# `test_outcome_description_names_live_verbs_not_the_retired_export_import_pair`.)
BANNED_ORCHESTRATION_VOCABULARY = ("coordinat", "dispatch", "executor", "route")

# Scripts the outcome skill documents by name (`plugins/saga/skills/outcome/SKILL.md`), plus every
# outcome_*.py module in the same scripts directory — globbed rather than hand-enumerated so this
# stays accurate without being re-edited every time an unrelated /outcome change adds one.
OUTCOME_DOCUMENTED_SCRIPTS = ("outcome.py", "intent_envelope.py", "spec_table.py", "status_card.py")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _split_frontmatter(text: str) -> dict:
    """Parse a ``---``-delimited YAML frontmatter block. Raises if the block is missing or
    malformed, unlike a permissive "treat missing as empty" helper — a command file with broken
    frontmatter is a build defect, not a legitimate state to silently tolerate here."""
    assert text.startswith("---\n"), "file has no frontmatter block"
    end = text.find("\n---", 4)
    assert end != -1, "frontmatter block is not closed"
    parsed = yaml.safe_load(text[4:end])
    assert isinstance(parsed, dict), "frontmatter did not parse to a mapping"
    return parsed


def _vocabulary_hits(description: str) -> list[str]:
    """Return every banned stem that is present (case-insensitive substring) in `description`."""
    lowered = description.lower()
    return [stem for stem in BANNED_ORCHESTRATION_VOCABULARY if stem in lowered]


def _frontmatter_is_complete(front: dict) -> bool:
    """The actual production check: `name`/`description`/`argument-hint` are all present and
    non-empty. Both the real-file test and the mutation-detection test below call this SAME
    function — a mutation test that re-implements its own inline assertion instead of calling the
    production check can pass while the real check is broken; this one can't."""
    return (
        front.get("name") == "orchestrate"
        and isinstance(front.get("description"), str)
        and bool(front["description"].strip())
        and isinstance(front.get("argument-hint"), str)
        and bool(front["argument-hint"].strip())
    )


# ---------------------------------------------------------------------------
# 1. The /orchestrate loader's frontmatter
# ---------------------------------------------------------------------------


def test_orchestrate_loader_frontmatter_carries_name_description_argument_hint():
    front = _split_frontmatter(_read(ORCHESTRATE_CMD))

    assert _frontmatter_is_complete(front)


def test_orchestrate_loader_frontmatter_mutation_is_detected():
    """Deletion proof, in memory: a frontmatter block missing `argument-hint` must fail the SAME
    `_frontmatter_is_complete` check the real file passes above — not a hand-rolled assertion that
    only proves a dict lost a key. A prior version of this test did exactly that: it deleted a key,
    asserted the key was gone, and never called the production check at all, so it would have kept
    passing even if `_frontmatter_is_complete` were replaced with `return True`."""
    front = _split_frontmatter(_read(ORCHESTRATE_CMD))
    mutated = dict(front)
    del mutated["argument-hint"]

    assert _frontmatter_is_complete(front)  # sanity: the real file passes
    assert not _frontmatter_is_complete(mutated)  # the production check catches the mutation


def test_orchestrate_loader_loads_the_skill_and_forwards_arguments():
    body = _read(ORCHESTRATE_CMD)

    assert "orchestrate/skills/orchestrate/SKILL.md" in body
    assert "$ARGUMENTS" in body


def test_orchestrate_loader_target_skill_actually_exists():
    """The check above only proves the command body CONTAINS the load-path STRING — a deleted or
    renamed skill file would keep it green, since a string match doesn't touch the filesystem. This
    is the missing other half: the path the loader names is a real file."""
    assert ORCHESTRATE_SKILL.exists(), (
        f"{ORCHESTRATE_CMD} loads {ORCHESTRATE_SKILL}, which does not exist"
    )


def test_orchestrate_loader_argument_hint_takes_the_outcome_as_its_argument():
    """KTD1: orchestrate is a verb taking the outcome as its argument, not the other way round —
    the argument-hint should read as the outcome forms it accepts, not as sub-verbs of a noun
    command (contrast `/outcome`'s `start <id> | advance <id> | ...` shape)."""
    front = _split_frontmatter(_read(ORCHESTRATE_CMD))
    hint = front["argument-hint"]

    assert "issue" in hint.lower()
    assert "requirements doc" in hint.lower()
    assert "prose prompt" in hint.lower()


# ---------------------------------------------------------------------------
# 2. `/outcome`'s description no longer matches orchestration intent, and names /orchestrate
# ---------------------------------------------------------------------------


def test_outcome_description_is_the_pinned_approved_text():
    """The primary guard, not a diagnostic: exact identity with the approved text catches ANY
    future rewrite, whether or not it happens to trip a fixed stem or borrow a word the pitch
    checker below currently watches for. See the module docstring's first design point."""
    front = _split_frontmatter(_read(OUTCOME_CMD))

    assert front["description"] == APPROVED_OUTCOME_DESCRIPTION


def test_outcome_description_contains_none_of_the_banned_vocabulary():
    front = _split_frontmatter(_read(OUTCOME_CMD))
    description = front["description"]

    hits = _vocabulary_hits(description)

    assert hits == [], f"description still contains orchestration-intent vocabulary: {hits}"


def test_outcome_description_names_orchestrate_as_the_replacement():
    front = _split_frontmatter(_read(OUTCOME_CMD))

    assert REPLACEMENT_COMMAND in front["description"]


def test_outcome_description_still_describes_what_outcome_actually_does():
    """The rewrite must not have swung so far it stopped describing /outcome. Its own domain words
    (not on the banned list — see the list's own comment) must survive."""
    front = _split_frontmatter(_read(OUTCOME_CMD))
    description = front["description"].lower()

    for still_true in ("dag", "leaf saga", "outcome", "status is derived on read"):
        assert still_true in description, (
            f"rewrite dropped a real /outcome property: {still_true!r}"
        )


def test_vocabulary_checker_flags_the_original_pre_rewrite_description():
    """The behavioural proof this file's docstring promises: run the SAME checker function the
    tests above use against the description this unit actually replaced, captured verbatim as a
    module constant (not re-derived from the current file — that would make this test trivially
    circular). Every declared stem must be caught, or the vocabulary list is decorative."""
    hits = _vocabulary_hits(ORIGINAL_OUTCOME_DESCRIPTION)

    assert set(hits) == set(BANNED_ORCHESTRATION_VOCABULARY)


def test_outcome_description_does_not_lead_with_start():
    """`start <id> <objective>` is how an operator began a brand-new outcome under the old
    product — the exact on-ramp a not-yet-decomposed request should now reach through
    `/orchestrate` instead. `argument-hint` still lists `start` (an operator who already knows to
    reach for `/outcome` directly keeps it), but the DESCRIPTION — the field a model matches
    intent against — must not invite a new "start an outcome" request by naming the verb at all."""
    front = _split_frontmatter(_read(OUTCOME_CMD))

    assert "start" not in front["description"].lower()
    assert "start" in front["argument-hint"]  # still real, still discoverable once selected


def test_outcome_description_names_live_verbs_not_the_retired_export_import_pair():
    """`export`/`import` have been a retired, read-only-alias surface for a while
    (`plugins/saga/scripts/outcome.py`: `export` aliases `discover`; `import` always refuses) — the
    skill's own frontmatter already lists the CURRENT thin-coordinator verbs as `discover`,
    `handoff`, `attach`. The command description should name what's actually live, not a pair that
    reads as capability the command no longer meaningfully has."""
    front = _split_frontmatter(_read(OUTCOME_CMD))
    description = front["description"].lower()

    for retired in ("export", "import"):
        assert retired not in description, f"description still lists the retired verb {retired!r}"
    for live in ("discover", "handoff", "attach"):
        assert live in description, f"description is missing the live verb {live!r}"


# ---------------------------------------------------------------------------
# 2b. The description check has to distinguish naming /orchestrate (the pointer) from
#     describing /outcome using /orchestrate's own pitch (a pitch dressed as a pointer)
# ---------------------------------------------------------------------------
#
# BANNED_ORCHESTRATION_VOCABULARY above is a fixed, curated list. It cannot include "orchestrat"
# itself — the rewritten description is REQUIRED to name `/orchestrate` — which means a rewrite
# that leads with "Orchestrate a whole outcome…" before pointing at `/orchestrate` passes every
# check above. So does one that swaps in unlisted synonyms ("Manages multi-vendor children…",
# "Drive the whole campaign…"). A fixed list can always be dodged by a word nobody added yet.
#
# The distinguishing property isn't a better word list — it's WHERE the words appear. A legitimate
# description has exactly one place that's allowed to sound like /orchestrate: the clause that
# points at it ("Deprecated in favor of /orchestrate, which…"). Everywhere else — the part
# describing what /outcome itself still does — should share none of /orchestrate's own distinctive
# pitch vocabulary, because if it did, there would be nothing left to tell the two commands apart.
#
# So this check derives that vocabulary FROM /orchestrate's OWN live description (never a
# hardcoded guess-list) and asserts the SELF-description half of /outcome's text — everything
# before the sentence that names /orchestrate — contains none of it. Self-updating: if a later
# unit changes /orchestrate's wording, the words this check watches for change with it, so the
# guard doesn't quietly go stale the way a fixed list would.

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "of",
        "in",
        "on",
        "at",
        "to",
        "from",
        "by",
        "with",
        "without",
        "for",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "this",
        "that",
        "these",
        "those",
        "its",
        "it",
        "own",
        "never",
        "then",
        "than",
        "up",
        "down",
        "out",
        "instead",
        "before",
        "after",
        "each",
        "every",
        "one",
        "other",
        "another",
        "which",
        "who",
        "what",
        "when",
        "where",
        "why",
        "how",
        "not",
        "no",
        "only",
        "also",
        "still",
        "just",
        "into",
        "through",
        "during",
        "between",
        "required",
        "requires",
        "require",
        "takes",
        "take",
        "taking",
    }
)

# Words legitimately shared by BOTH commands describing their OWN real properties, so they don't
# count as "borrowed pitch" even though they happen to also appear in /orchestrate's description:
# "outcome"/"outcomes" — the shared object each command acts on (it's literally /outcome's name);
# "durable" — both commands really do persist durably (a DAG spec vs. a register); "shape" — a
# neutral enough word not worth banning on its own.
_SHARED_DOMAIN_WORDS = frozenset({"outcome", "outcomes", "durable", "shape"})


def _content_words(text: str, min_len: int = 5) -> set[str]:
    """Lowercased words of at least `min_len` characters, stopwords excluded — the word-level unit
    both the pitch-vocabulary derivation and the self-description scan operate on."""
    words = re.findall(r"[a-zA-Z']+", text.lower())
    return {w for w in words if len(w) >= min_len and w not in _STOPWORDS}


def _split_at_orchestrate_pointer(description: str) -> tuple[str, str]:
    """Split a description at the start of the sentence containing its first `/orchestrate`
    mention. Returns (self_description, pointer) — everything up to and including the previous
    sentence's full stop is `self_description`; the sentence naming `/orchestrate` onward is
    `pointer`, exempt from the self-description check (it's describing the REPLACEMENT, not this
    command). A description that never mentions `/orchestrate` returns `(description, "")` — the
    whole text counts as self-description, which is correct: nothing here IS a pointer.

    This is a simplification, not a general-purpose parser: it assumes the pointer lives in its
    own sentence, which is true of the current two-sentence-shaped description. A future rewrite
    that folds a `/orchestrate` mention into the middle of a self-descriptive sentence would need
    this split reconsidered, not just re-run."""
    idx = description.find(REPLACEMENT_COMMAND)
    if idx == -1:
        return description, ""
    boundary = description.rfind(".", 0, idx)
    start = boundary + 1 if boundary != -1 else 0
    return description[:start], description[start:]


def _orchestrate_pitch_vocabulary() -> set[str]:
    """The content words distinctive to /orchestrate's OWN live description, read from the real
    file at call time (never a frozen snapshot) — this is what makes the check self-updating."""
    front = _split_frontmatter(_read(ORCHESTRATE_CMD))
    return _content_words(front["description"]) - _SHARED_DOMAIN_WORDS


def _self_description_pitch_hits(outcome_description: str) -> list[str]:
    """Every word in `outcome_description`'s self-description half that is also distinctively
    /orchestrate's own pitch vocabulary — the "borrowed pitch" signal, independent of the fixed
    BANNED_ORCHESTRATION_VOCABULARY stems."""
    self_description, _pointer = _split_at_orchestrate_pointer(outcome_description)
    return sorted(_content_words(self_description) & _orchestrate_pitch_vocabulary())


# Concrete adversarial rewrites — reconstructed from three the review process actually ran, minus
# the property that confounded them with a check unrelated to this one: each originally led with
# `start`, which the separate test_outcome_description_does_not_lead_with_start check now catches
# on its own, so a rewrite built that way no longer demonstrates that PITCH-checking is what's
# catching it. These use the real live verbs instead (discover/handoff/attach, no start, no
# export/import) so each is caught — if it is — only by _self_description_pitch_hits, nothing
# else. Each keeps the required /orchestrate pointer and the real DAG/leaf-saga/status-derived-on-
# read/live-verb properties, so only this section's check can tell them apart from the genuine
# description.
_ADVERSARIAL_REWRITES = (
    # Leads with the product verb the fixed stem list cannot ban (it's needed for the pointer).
    "Orchestrate a whole outcome as a durable DAG of leaf sagas — advance the ready frontier, "
    "attend a leaf, resume, graph, discover, handoff, attach. Status is derived on read. "
    "Deprecated in favor of /orchestrate.",
    # Borrows /orchestrate's own "multi-vendor children across Claude and Codex" framing —
    # describing a capability /outcome does not actually have.
    "A durable DAG of leaf sagas for one outcome — advance, attend, resume, graph, discover, "
    "handoff, attach. Manages multi-vendor children across Claude and Codex. Status is derived "
    "on read. Deprecated in favor of /orchestrate.",
    # Unlisted orchestration-flavoured synonyms plus /orchestrate's own "operator turn" phrase.
    "A durable DAG of leaf sagas for one outcome — advance, attend, resume, graph, discover, "
    "handoff, attach. Drive the whole campaign and run the work across agents without an "
    "operator turn. Status is derived on read. Deprecated in favor of /orchestrate.",
)

# A rewrite that beats every check in this file, including the pitch check above: no banned stem,
# no word from /orchestrate's OWN current pitch vocabulary, still names /orchestrate, still reads
# DAG/leaf saga/outcome/status-is-derived-on-read, doesn't lead with start. It is a real, current
# blind spot in every heuristic here — not a hypothetical one, and not closed by adding it as one
# more banned word (the next unlisted synonym would just open the same gap again). It is what
# `test_outcome_description_is_the_pinned_approved_text` exists to close: that test does not need
# to recognize prose, only byte-for-byte identity with the approved text, so this rewrite fails it
# on sight regardless of what any heuristic below does or doesn't catch.
_PITCH_CHECKER_BLIND_SPOT_REWRITE = (
    "Manage an outcome end to end as a durable DAG of leaf sagas — assign jobs among multiple "
    "agents, supervise parallel progress, recover failures, and finish automatically. Status is "
    "derived on read. Deprecated in favor of /orchestrate."
)


def test_outcome_self_description_shares_none_of_orchestrates_pitch_vocabulary():
    front = _split_frontmatter(_read(OUTCOME_CMD))

    hits = _self_description_pitch_hits(front["description"])

    assert hits == [], f"self-description borrows /orchestrate's own pitch vocabulary: {hits}"


def test_pitch_checker_catches_adversarial_rewrites_the_fixed_stem_list_misses():
    """Each of these passes `test_outcome_description_contains_none_of_the_banned_vocabulary`
    (zero fixed-stem hits), `test_outcome_description_names_orchestrate_as_the_replacement`,
    `test_outcome_description_still_describes_what_outcome_actually_does`, and
    `test_outcome_description_does_not_lead_with_start` — proving none of THOSE checks is what
    catches these. The pitch-vocabulary check must fail every one of them; if it didn't, nothing
    in this file would."""
    for rewrite in _ADVERSARIAL_REWRITES:
        assert _vocabulary_hits(rewrite) == [], (
            "test fixture assumption broken: rewrite should "
            "dodge the fixed stem list, or it isn't testing what this test claims"
        )
        assert "start" not in rewrite.lower(), (
            "test fixture assumption broken: rewrite should not be catchable by the separate "
            "start-absence check, or it isn't isolating what this test claims to isolate"
        )
        assert REPLACEMENT_COMMAND in rewrite
        hits = _self_description_pitch_hits(rewrite)
        assert hits, f"pitch checker failed to catch an adversarial rewrite: {rewrite!r}"


def test_pitch_checker_has_a_real_blind_spot_the_pinned_description_closes():
    """Not a regression the pitch checker is expected to catch — the opposite: an honesty check
    that documents a real, current miss, so the module docstring's claim about it is verified
    rather than asserted. This rewrite passes the fixed-stem check, doesn't lead with `start`, and
    shares none of /orchestrate's OWN current content words in its self-description half — the
    pitch checker has nothing to flag. `test_outcome_description_is_the_pinned_approved_text` is
    what actually rejects it: it isn't this exact-approved text, full stop."""
    assert _vocabulary_hits(_PITCH_CHECKER_BLIND_SPOT_REWRITE) == [], (
        "fixture assumption broken: this rewrite should dodge the fixed stem list too"
    )
    assert "start" not in _PITCH_CHECKER_BLIND_SPOT_REWRITE.lower()
    assert REPLACEMENT_COMMAND in _PITCH_CHECKER_BLIND_SPOT_REWRITE

    hits = _self_description_pitch_hits(_PITCH_CHECKER_BLIND_SPOT_REWRITE)

    assert hits == [], (
        "fixture assumption broken: expected this to be a documented MISS for the pitch checker "
        "— if it now has hits, the checker changed and this comment/test pair needs revisiting"
    )
    assert _PITCH_CHECKER_BLIND_SPOT_REWRITE != APPROVED_OUTCOME_DESCRIPTION


def test_outcome_command_body_is_unchanged():
    """This unit is a description/argument-hint rewrite, not a behaviour change: `/outcome` must
    keep working, invoked explicitly, exactly as it did before. The load path and the body
    invariant are a second, independent read on "nothing deleted" beyond the skill/script check
    below."""
    text = _read(OUTCOME_CMD)

    assert "Load `saga/skills/outcome/SKILL.md`" in text
    assert "**The coordinator routes, it never executes**" in text  # body invariant, untouched


def test_outcome_argument_hint_names_live_verbs_not_the_retired_export_import_pair():
    """`argument-hint` is autocomplete for someone who already knows to reach for `/outcome`
    directly, not the field a model matches intent against — it can and does still list `start`
    (see `test_outcome_description_does_not_lead_with_start`). It should not be the one place left
    still advertising `export`/`import` as reachable verbs once the description itself no longer
    names them — see `test_outcome_description_names_live_verbs_not_the_retired_export_import_pair`."""
    front = _split_frontmatter(_read(OUTCOME_CMD))
    hint = front["argument-hint"]

    for verb in (
        "start",
        "advance",
        "approve",
        "commit",
        "attend",
        "resume",
        "graph",
        "discover",
        "handoff",
        "attach",
    ):
        assert verb in hint, f"argument-hint dropped a real verb: {verb!r}"
    for retired in ("export", "import"):
        assert retired not in hint, f"argument-hint still advertises the retired verb {retired!r}"


# ---------------------------------------------------------------------------
# 3. `/outcome`'s skill: body and scripts untouched; frontmatter carries exactly one new key
# ---------------------------------------------------------------------------
#
# A command's `description:` is not the only field Claude matches a natural-language request
# against — a same-named SKILL has its own, independent `description:` frontmatter field, and
# `plugins/saga/skills/outcome/SKILL.md`'s carries the entire fixed banned-stem list (verified
# below): "Coordinate a whole outcome…", "dispatches the ready frontier to executors", "the
# coordinator routes". Rewriting that text would only replay the same word-substitution game
# section 2b exists to defeat — a future synonym the wordlist doesn't know about would still work.
#
# `disable-model-invocation: true` closes it structurally instead of lexically: it stops Claude
# from choosing this skill on its own initiative, for ANY phrasing, while `/outcome` — which loads
# the skill directly rather than through model-initiated selection — keeps working exactly as
# before. The skill's description, body, and every script it documents are otherwise untouched;
# the frontmatter gains exactly the one new key.


def test_outcome_skill_still_exists_and_is_named_outcome():
    front = _split_frontmatter(_read(OUTCOME_SKILL))

    assert front.get("name") == "outcome"


def test_outcome_skill_description_still_reads_as_general_orchestration():
    """Confirms the design choice, not a defect: Route 2 (disable-model-invocation) was chosen
    over Route 1 (rewriting this description) specifically so this text would NOT need touching.
    This is the same checker section 2 runs against the command description — if this ever starts
    returning `[]`, someone rewrote the skill description, which is a real change to justify and
    reconcile with this test, not an accidental drift to silently accept."""
    front = _split_frontmatter(_read(OUTCOME_SKILL))

    hits = _vocabulary_hits(front["description"])

    assert set(hits) == set(BANNED_ORCHESTRATION_VOCABULARY)


def test_outcome_skill_disables_model_invocation():
    """The mechanism that actually stops the collision — verified live, not assumed from the
    review that proposed it. `disable-model-invocation: true` is a real, documented Claude Code
    frontmatter key (supported on both `commands/*.md` and `skills/*/SKILL.md`) that suppresses
    the model's own initiative to invoke a skill while leaving explicit `/<skill>` invocation
    working; see the installed Claude Code's own changelog for both properties confirmed as fixed
    bugs well below the currently installed version."""
    front = _split_frontmatter(_read(OUTCOME_SKILL))

    assert front.get("disable-model-invocation") is True


def test_outcome_skill_disable_model_invocation_mutation_is_detected():
    """Deletion proof, in memory: a frontmatter block missing `disable-model-invocation` (or
    carrying it as a falsy/wrong value) must fail the same check the real file passes."""
    front = _split_frontmatter(_read(OUTCOME_SKILL))
    missing = dict(front)
    del missing["disable-model-invocation"]
    falsy = dict(front)
    falsy["disable-model-invocation"] = False

    assert front.get("disable-model-invocation") is True  # sanity: the real file passes
    assert missing.get("disable-model-invocation") is not True
    assert falsy.get("disable-model-invocation") is not True


def test_outcome_skill_body_states_the_manual_only_deprecation_boundary():
    """The frontmatter `description:` is deliberately untouched (the test above confirms it still
    reads as general orchestration) so a human reading the file's most prominent field never sees
    a deprecation boundary there — the body is where it has to live instead. This only reaches a
    reader once the skill is already loaded (explicit `/outcome`, or the command body's file-read),
    so stating it here doesn't reopen the synonym game `disable-model-invocation` exists to close
    structurally on the selection surface itself."""
    # Blockquote-marker-and-whitespace-normalized: this is hard-wrapped Markdown prose, not
    # structured data — the phrases below are logically contiguous even where an editor line-wraps
    # them inside a `>` blockquote, and a rewrap of the paragraph (a legitimate future edit) should
    # not itself break this check.
    raw = _read(OUTCOME_SKILL)
    body = " ".join(line.removeprefix(">").strip() for line in raw.splitlines())

    assert "Manual-only, already-decomposed surface" in body
    assert "does not select it on its own initiative" in body
    assert REPLACEMENT_COMMAND in body


def test_outcome_skill_frontmatter_has_no_other_new_keys():
    """Scope proof: this round is authorised to touch the skill's description and frontmatter
    only — not its body, not the scripts it documents. Frontmatter should carry exactly `name`,
    `description`, and the one new `disable-model-invocation` key; anything else would be an
    undisclosed, wider edit."""
    front = _split_frontmatter(_read(OUTCOME_SKILL))

    assert set(front.keys()) == {"name", "description", "disable-model-invocation"}


def test_outcome_documented_scripts_still_exist_and_are_valid_python():
    for script_name in OUTCOME_DOCUMENTED_SCRIPTS:
        path = SAGA_SCRIPTS_DIR / script_name
        assert path.exists(), f"{script_name} referenced by outcome's SKILL.md is missing"
        ast.parse(_read(path), filename=str(path))  # real parse, not just "the file has bytes"


def test_every_outcome_prefixed_script_still_exists_and_is_valid_python():
    """Glob rather than a hand-maintained list, so a script this unit did not touch (and has no
    reason to know the full name of) still gets a real parse check instead of silent coverage
    gaps. This only inspects files already present on disk — it cannot itself delete anything."""
    outcome_scripts = sorted(SAGA_SCRIPTS_DIR.glob("outcome*.py"))

    assert len(outcome_scripts) >= 15, (
        "far fewer outcome_*.py scripts than expected — the outcome engine may have been pruned"
    )
    for path in outcome_scripts:
        ast.parse(_read(path), filename=str(path))


# ---------------------------------------------------------------------------
# 4. The marketplace entries validate
# ---------------------------------------------------------------------------


def test_orchestrate_and_saga_marketplace_entries_are_in_release_surface_parity():
    """Reuses the repository's own tri-lock checker (plugin.json version == marketplace entry
    version == CHANGELOG top heading version) rather than re-deriving the comparison, and asserts
    neither plugin this unit touched is reported drifted. Deliberately does not hardcode either
    plugin's version number: two other units bump `plugins/orchestrate`'s release surfaces on their
    own branches, so a literal version string here would be reconciled-away noise rather than a
    real regression signal."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "check_release_surface_parity",
        ROOT / "scripts" / "check_release_surface_parity.py",
    )
    assert spec is not None and spec.loader is not None
    parity = importlib.util.module_from_spec(spec)
    sys.modules["check_release_surface_parity"] = parity
    spec.loader.exec_module(parity)

    drifted = parity.check_parity()

    assert "orchestrate" not in drifted
    assert "saga" not in drifted


def test_orchestrate_marketplace_entry_matches_its_plugin_json():
    import json

    plugin_json = json.loads(_read(ORCHESTRATE_PLUGIN_JSON))
    marketplace = json.loads(_read(MARKETPLACE))
    entry = next(p for p in marketplace["plugins"] if p["name"] == "orchestrate")

    assert entry["version"] == plugin_json["version"]
    assert entry["source"] == "./plugins/orchestrate"
    assert entry["description"] == plugin_json["description"]
