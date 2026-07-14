# Boundary-crossing test convention

_Issue #458 · facet T11-F4-7_

## Why

> A round-trip test only proves the round-trip if the consumer reads from the boundary it claims to
> validate.

That is the generalizable rule from `docs/engineering-journal/LEARNINGS.md`
`{#test-shape-masks-dead-wiring-291}`. The saga Layer-2 `artifact_pointers` test was green while the
consumer leg dereferenced the producer's **in-memory** value instead of the value read back from the
**persisted** tick — so the test never actually crossed the persistence boundary it claimed to
validate, and a dead-wiring bug shipped and had to be fixed under adversarial review.

## The convention

A round-trip / persistence test must re-read its asserted value **from the boundary** (disk, a tick,
a persisted row), never from an in-memory variable the producer already holds. The shared helper
`assert_reads_from_boundary` (in `tests/conftest.py`, exposed as a fixture) makes that explicit:

```python
def test_boundary_crossing_roundtrip(saga, tmp_path, monkeypatch, assert_reads_from_boundary):
    _stub_no_git(saga, monkeypatch)
    result = saga.save(tmp_path, _make_saga(saga, summary="persisted-value"), now=FIXED_NOW)
    envelope_path = Path(result["envelope_path"])

    assert_reads_from_boundary(
        lambda: saga.restore(tmp_path, "issue-42").summary,  # reader RE-READS from disk
        "persisted-value",                                   # expected
        boundary=envelope_path,                              # the on-disk artifact that must exist
        description="saga.summary",
    )
```

The helper enforces two invariants **before** comparing values:

1. the `boundary` artifact (a path, or iterable of paths) **exists**, and
2. it is **non-empty**.

Only then does it call `reader()` and compare to `expected`. Consequences:

- A test that reads an **in-memory** variable can't masquerade as a round-trip — the reader must
  re-read from the boundary.
- **Stubbing out the persistence write** (e.g. `monkeypatch` the envelope `write_text`) makes the
  boundary-existence assertion fail, which is the proof the assertion truly reads from disk. This is
  the negative case the acceptance criterion checks.

## Worked example (v1)

`tests/test_saga_saga.py::test_boundary_crossing_roundtrip` (plus the converted
`test_restore_round_trips_including_extra`) drive `saga.save` → `saga.restore`, asserting the summary
re-read from the persisted tick equals what was saved, with the tick file as the declared boundary.

## Scope

v1 converts **one** existing round-trip test as the worked example and convention proof. Converting
every round-trip test is out of scope (issue #458 non-goals) — apply the helper when a new
persistence round-trip needs to prove it crosses the boundary.
