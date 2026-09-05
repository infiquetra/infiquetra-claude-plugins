# Issue 912 repair round — Lane A evidence

Workspace: `/Users/jefcox/workspace/infiquetra/cp912-lane-a`. Baseline supplied by the
controller: `77c01c99`. Specification: approved repair plan U1 and KTD1–KTD10.

Every command below was executed in the Lane A workspace; stdout and stderr are
captured together without abridging. `EXIT` records the actual process status.
Focused E1/E2 runs override the repository's default all-plugin coverage report
with `-o addopts=`; the required coverage run is recorded separately. The two owned
test modules stub repository metadata so their envelope/CLI tests run without Git.
Temporary backups live in `.pytest_cache/lane-a-proofs/`; restoration uses `cp`
followed by `cmp -s`. The original module was backed up before any production edit.

No plugin installation, marketplace refresh, full gate, or Git command is part of
this lane. The controller owns integration and release surfaces. Journal changes
are drafted in `lane-A-journal-draft.md` for the serial fold required by KTD6.

## Disposition and proof index

The final required scoped suite passed **313 tests**. The two-module coverage run
passed **155 tests** and measured `handoff_envelope.py` at **82%** (360 statements,
66 missing); all **17 extracted parser / re-anchor helpers have zero missing lines**.
All 42 functions satisfy the AST bar: at most 8 returns, at most 9 branch nodes
(the allowed ceiling is 12), and no nested definitions. Test-shape lint checked
301 modules, Ruff checked the tree, 517 files passed the format check, and mypy
reported no issues in 346 source files. These are scoped checks, not a full gate.

| Finding | Lane A disposition | One-line proof; exact command/output appears below |
|---|---|---|
| SEC-1 | Closed | Both `plan-ready` source and symlink E1 reds contain the forbidden live `/issue --prepare` command; both spellings refuse after repair. |
| TEST-1 | Closed | Replacing the undeclaring-twin refusal with `pass` yields `requirements-ready` and fails the new test; restore is byte-identical. |
| TEST-2 | Closed | The inline mutation publishes `brainstorms/x.md` instead of `FORCED-BY-TEST`; the normalization bypass yields `unknown:unreadable` instead of `pending-confirmation`. |
| AU-2 | Closed | Nested and sequence diagnostics fail their cause assertions before repair; same-source diagnostics have cardinality 1 before and 3 after repair. |
| AM-3 | Runtime repair proved; literal check exception | AST reports exactly one re-anchor call and two containment calls, all in `resolve_source`; the spy mutation fails. The prescribed raw grep also counts the definition, so returns 2, not 1. |
| AM-4 | Closed | `original absolute file is read` grep is 0; resolver prose enumerates twin-read and refusal outcomes. |
| AM-5 | Closed | `allow_bullet` is gone, the unreachable scan/zero-index arms are removed, and all extracted helpers report `missing_lines=[]`. |
| AM-6 | Closed | The pasted AST run validates every function against 8 returns / 12 branches / 0 nested definitions. |
| AM-10 | Closed | Blank maturity fails the pre-fix diagnostic assertion and passes afterward; `should not occur` grep is 0. |
| API-4 | Closed by cycle-8 test, mutation-confirmed | Removing the original marker-less `absolute = False` assignment leaks `plan-ready` and fails the existing test; no dedicated replacement test was added. |
| API-11 | Closed | The stale `redundant with suggested_command` grep is 0; both fields use bounded text and the truncation test passes. |
| AU-11 | Closed | `pending-confirmation` is absent from the pre-fix remediation and present after repair; the routable vocabulary is unchanged. |
| CORR-6 | Closed | The 9,946-byte fixture routes as `requirements-ready` before repair and becomes `unknown:unterminated:`; the diagnostic now names 8192 bytes. |
| CORR-7 | Closed | The early-dashes fixture routes as `requirements-ready` before repair and becomes `unknown:carrier:`; a valid dash-prefixed YAML key also has a red/green pin. |
| SEC-3 | Closed | The 4,000-level YAML fixture raises `RecursionError` in the red transcript and returns a carrier sentinel after repair. |
| SEC-5 | Closed | All four pre-fix source probes fail the exact six-token assertion; all pass after quoting, with single-line escaped/bounded refusal diagnostics. |
| SEC-8 | Closed to the specified acceptance | The 400-character component raises `OSError: File name too long` before repair and returns a string afterward; all file predicates use the guarded helper. |
| SEC-7 | Closed | Removing twin containment leaks `plan-ready`; restoring original absolute reads makes the spelling pair disagree. Both mutations fail their strengthened tests. |
| TEST-10 | Closed | `mkdtemp` grep is 0 and the rewritten refusal test's AST signature is exactly `['tmp_path']`. |
| CORR-5 | Closed | Reverting clarification to deferred-context alone changes `True` to `False` and fails the new test; `parse_issue.py` restores to its original bytes. |
| AU-3 | Test half closed | A top-level flow mapping returns `requirements-ready` under `docs/ideation/`, whose fallback would be `idea-ready`; no mutation required by the plan. |
| SEC-9 | Test half closed | Returning author-written `unknown:` values verbatim fails both forgery cases; restored code wraps them in `unknown:unrecognized:`. |

### Plan check exceptions, limits, and stop items

1. **AM-3's literal grep requirement cannot be met as written.** The exact command
   returns `2`: one definition and one call. The analogous containment grep returns
   `3`: one definition and two calls. The AST proof supplies the intended counts and
   proves every call is inside `resolve_source`. The controller must accept this
   mechanical correction; Lane A has not edited the read-only plan or disguised the
   function definition to make a textual count green. This is the sole remaining
   literal finding-acceptance exception; there is no unresolved runtime repair.
2. **The prescribed test-shape command is incomplete.** Its verbatim run exits 2
   because `paths` is required. The actual CI command at
   `.github/workflows/ci.yml:204`,
   `uv run python scripts/lint_test_shape.py tests plugins --prod-module server`,
   passes. Both runs are pasted below.
3. **No-Git verification changes invocation, not test selection.** Three tests in
   the immutable `test_saga_plugin.py` call envelope Git metadata directly. The
   recorded `uv run python -c ...` wrapper runs the exact five scoped modules,
   stubs only the two known read-only metadata requests, and installs an audit hook
   that raises before an actual Git process can start. Both scoped runs report six
   requests stubbed. The two owned test modules isolate their own metadata calls.
   No Git command, including a status command, was executed.
4. **KTD8's single-line check applies to diagnostics.** A runnable command uses
   `shlex.quote` and retains the exact source bytes, including an embedded newline
   inside one quoted argument; this is necessary for the mandated six-token
   `shlex.split` equality. The newline probe's refusing declaration and every other
   refusing diagnostic contain escaped controls. The published source remains the
   actual path, as required by the resolver contract.
5. **SEC-8's named test asserts a string, not a particular sentinel.** The specified
   guarded predicate returns false on a stat error, so an in-root path with an
   overlong component follows the existing missing-file path rule. No new sentinel
   cause was introduced. Its E1 proof is the reproduced exception followed by a
   successful string return, matching U1 item 17's explicit assertion.
6. The first E1 run used pytest's inherited global temporary directory and emitted
   cleanup permission warnings for older unrelated pytest garbage. Its full output
   is preserved. Subsequent runs explicitly use this lane's private
   `.pytest_cache/lane-a-proofs/pytest` base directory.

No listed stop-and-surface event required a policy decision: no byte-identity
restore failed, no immutable test or other lane file needed editing, and no sixth
sentinel was introduced. API-4's preflight watch was resolved by its exact mutation.
Version collision and release/integration checks remain with the controller.

### Lane B cross-check and changed files

The resolver docstring and journal draft implement KTD9's containment truth: a
source outside the declared root is never read; a contained marker-directory twin
may supply its declaration; otherwise refusal is independent of declaration,
existence, and spelling. A twin declaring nothing is refused. Resolved symlink
containment applies to both source spellings. The draft supplies complete learning
and decision entries for the KTD6 fold.

Affected prose remains Lane B's responsibility: Saga's handoff skill,
`references/saga-spec.md`, the unreleased 0.156.0 changelog entry, and the
`913-maturity-unknown-sentinel` decision. Lane A has not amended those files or any
release/version surface. The envelope schema stays 1.1 and the five sentinel causes
and maturity vocabulary are unchanged.

Persistent changed files (all owned):

- `plugins/saga/scripts/handoff_envelope.py`
- `tests/test_handoff_envelope_maturity.py`
- `tests/test_handoff_envelope.py`
- `docs/evidence/issue-912/lane-A-evidence.md`
- `docs/evidence/issue-912/lane-A-journal-draft.md`

`plugins/saga/scripts/parse_issue.py` was temporarily mutated for CORR-5 and restored;
it has no final byte changes. Standard generated caches, coverage output, test
fixtures, and the mandated backup files are excluded from the source custody
inventory. The SHA-256 inventory captured before editing and compared afterward
covers 2,261 original source files; the only additions are the two owned notes.

## E1: tests against the untouched production module

### E1 red — all prescribed behavior defects

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short -k 'out_of_root_declaring_file_is_refused_in_both_spellings or in_root_symlink_to_out_of_root_is_refused or reanchored_missing_twin_is_refused or carrier_diagnostic_names_the_actual_cause or carrier_diagnostics_are_pairwise_distinct or blank_maturity_diagnostic_says_blank_not_unrecognized or unrecognized_remediation_names_pending_confirmation or maturity_past_the_read_window_fails_closed or closing_delimiter_past_the_read_window_names_the_window or early_dashes_inside_quoted_value_fail_closed or deeply_nested_yaml_fails_closed_without_traceback or suggested_command_is_shell_safe_and_single_line or overlong_path_component_returns_a_sentinel_not_oserror'
FFFFF.FFFFFFFFFFFF                                                       [100%]
=================================== FAILURES ===================================
___________________ test_reanchored_missing_twin_is_refused ____________________
tests/test_handoff_envelope_maturity.py:535: in test_reanchored_missing_twin_is_refused
    assert maturity.startswith("unknown:out-of-root:")
E   AssertionError: assert False
E    +  where False = <built-in method startswith of str object at 0x10be28930>('unknown:out-of-root:')
E    +    where <built-in method startswith of str object at 0x10be28930> = 'pending-confirmation'.startswith
_________ test_out_of_root_declaring_file_is_refused_in_both_spellings _________
tests/test_handoff_envelope_maturity.py:915: in test_out_of_root_declaring_file_is_refused_in_both_spellings
    assert "/issue --prepare" not in envelope["suggested_command"]
E   AssertionError: assert '/issue --prepare' not in '/issue --pr...y plan-ready'
E     
E     '/issue --prepare' is contained here:
E       /issue --prepare --from /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/pytest-17151/test_out_of_root_declaring_fil0/elsewhere/docs/brainstorms/x.md --maturity plan-ready
E     ? ++++++++++++++++
________________ test_in_root_symlink_to_out_of_root_is_refused ________________
tests/test_handoff_envelope_maturity.py:929: in test_in_root_symlink_to_out_of_root_is_refused
    assert "/issue --prepare" not in envelope["suggested_command"]
E   AssertionError: assert '/issue --prepare' not in '/issue --pr...y plan-ready'
E     
E     '/issue --prepare' is contained here:
E       /issue --prepare --from /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/pytest-17151/test_in_root_symlink_to_out_of0/root/docs/plans/link.md --maturity plan-ready
E     ? ++++++++++++++++
_ test_carrier_diagnostic_names_the_actual_cause[---\nmeta:\n  maturity: requirements-ready\n---\n-nested] _
tests/test_handoff_envelope_maturity.py:1006: in test_carrier_diagnostic_names_the_actual_cause
    assert cause in diagnostic.lower()
E   assert 'nested' in "frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited yaml block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"
E    +  where "frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited yaml block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key" = <built-in method lower of str object at 0xa6d36e300>()
E    +    where <built-in method lower of str object at 0xa6d36e300> = "Frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited YAML block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key".lower
_ test_carrier_diagnostic_names_the_actual_cause[---\nkeys:\n- maturity: requirements-ready\n---\n-sequence item] _
tests/test_handoff_envelope_maturity.py:1006: in test_carrier_diagnostic_names_the_actual_cause
    assert cause in diagnostic.lower()
E   assert 'sequence item' in "frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited yaml block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"
E    +  where "frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited yaml block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key" = <built-in method lower of str object at 0xa6d36de00>()
E    +    where <built-in method lower of str object at 0xa6d36de00> = "Frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited YAML block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key".lower
________________ test_carrier_diagnostics_are_pairwise_distinct ________________
tests/test_handoff_envelope_maturity.py:1020: in test_carrier_diagnostics_are_pairwise_distinct
    assert len(set(diagnostics)) == 3
E   assert 1 == 3
E    +  where 1 = len({"Frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declar...ted YAML block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"})
E    +    where {"Frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declar...ted YAML block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"} = set(["Frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declar...ted YAML block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"])
__________ test_blank_maturity_diagnostic_says_blank_not_unrecognized __________
tests/test_handoff_envelope_maturity.py:1026: in test_blank_maturity_diagnostic_says_blank_not_unrecognized
    assert "blank" in envelope["suggested_command"].lower()
E   assert 'blank' in "unrecognized maturity '(empty)' for docs/brainstorms/t-requirements.md — no durable route; fix frontmatter to one of idea-ready, requirements-ready, plan-ready, resume-ready, deferred-context"
E    +  where "unrecognized maturity '(empty)' for docs/brainstorms/t-requirements.md — no durable route; fix frontmatter to one of idea-ready, requirements-ready, plan-ready, resume-ready, deferred-context" = <built-in method lower of str object at 0x10b67a330>()
E    +    where <built-in method lower of str object at 0x10b67a330> = "Unrecognized maturity '(empty)' for docs/brainstorms/t-requirements.md — no durable route; fix frontmatter to one of idea-ready, requirements-ready, plan-ready, resume-ready, deferred-context".lower
___________ test_unrecognized_remediation_names_pending_confirmation ___________
tests/test_handoff_envelope_maturity.py:1033: in test_unrecognized_remediation_names_pending_confirmation
    assert "pending-confirmation" in envelope["suggested_command"]
E   assert 'pending-confirmation' in "Unrecognized maturity 'pending confirmation' for docs/brainstorms/t-requirements.md — no durable route; fix frontmatter to one of idea-ready, requirements-ready, plan-ready, resume-ready, deferred-context"
_______________ test_maturity_past_the_read_window_fails_closed ________________
tests/test_handoff_envelope_maturity.py:1041: in test_maturity_past_the_read_window_fails_closed
    assert got.startswith("unknown:unterminated:")
E   AssertionError: assert False
E    +  where False = <built-in method startswith of str object at 0x10bf025f0>('unknown:unterminated:')
E    +    where <built-in method startswith of str object at 0x10bf025f0> = 'requirements-ready'.startswith
_________ test_closing_delimiter_past_the_read_window_names_the_window _________
tests/test_handoff_envelope_maturity.py:1050: in test_closing_delimiter_past_the_read_window_names_the_window
    assert "8192" in envelope["suggested_command"]
E   assert '8192' in "Unterminated frontmatter block for docs/brainstorms/t-requirements.md — maturity 'plan-ready' declared but closing --- missing; no durable route; fix frontmatter to close the block"
______________ test_early_dashes_inside_quoted_value_fail_closed _______________
tests/test_handoff_envelope_maturity.py:1056: in test_early_dashes_inside_quoted_value_fail_closed
    assert got.startswith("unknown:carrier:")
E   AssertionError: assert False
E    +  where False = <built-in method startswith of str object at 0x10bf025f0>('unknown:carrier:')
E    +    where <built-in method startswith of str object at 0x10bf025f0> = 'requirements-ready'.startswith
____________ test_deeply_nested_yaml_fails_closed_without_traceback ____________
tests/test_handoff_envelope_maturity.py:1063: in test_deeply_nested_yaml_fails_closed_without_traceback
    got = _infer(tmp_path, body)
          ^^^^^^^^^^^^^^^^^^^^^^
tests/test_handoff_envelope_maturity.py:706: in _infer
    return HE.infer_maturity(  # type: ignore[no-any-return]
plugins/saga/scripts/handoff_envelope.py:340: in infer_maturity
    declared = _read_frontmatter_maturity(candidate)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
plugins/saga/scripts/handoff_envelope.py:233: in _read_frontmatter_maturity
    parsed = yaml.load(frontmatter, Loader=_StrictMappingLoader)  # noqa: S506 # nosec B506
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/__init__.py:81: in load
    return loader.get_single_data()
           ^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/constructor.py:49: in get_single_data
    node = self.get_single_node()
           ^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:36: in get_single_node
    document = self.compose_document()
               ^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:55: in compose_document
    node = self.compose_node(None, None)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:84: in compose_node
    node = self.compose_mapping_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:133: in compose_mapping_node
    item_value = self.compose_node(node, item_key)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:111: in compose_sequence_node
    node.value.append(self.compose_node(node, index))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:82: in compose_node
    node = self.compose_sequence_node(anchor)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/composer.py:110: in compose_sequence_node
    while not self.check_event(SequenceEndEvent):
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/parser.py:98: in check_event
    self.current_event = self.state()
                         ^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/parser.py:474: in parse_flow_sequence_first_entry
    return self.parse_flow_sequence_entry(first=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/parser.py:477: in parse_flow_sequence_entry
    if not self.check_token(FlowSequenceEndToken):
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/scanner.py:116: in check_token
    self.fetch_more_tokens()
.venv/lib/python3.12/site-packages/yaml/scanner.py:195: in fetch_more_tokens
    return self.fetch_flow_sequence_start()
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/yaml/scanner.py:425: in fetch_flow_sequence_start
    self.fetch_flow_collection_start(FlowSequenceStartToken)
.venv/lib/python3.12/site-packages/yaml/scanner.py:433: in fetch_flow_collection_start
    self.save_possible_simple_key()
.venv/lib/python3.12/site-packages/yaml/scanner.py:306: in save_possible_simple_key
    self.remove_possible_simple_key()
E   RecursionError: maximum recursion depth exceeded
_ test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md; rm -rf victim] _
tests/test_handoff_envelope_maturity.py:1081: in test_suggested_command_is_shell_safe_and_single_line
    assert shlex.split(envelope["suggested_command"]) == [
E   AssertionError: assert ['/issue', '-...', '-rf', ...] == ['/issue', '-... 'plan-ready']
E     
E     At index 3 diff: 'docs/plans/a.md;' != 'docs/plans/a.md; rm -rf victim'
E     Left contains 3 more items, first extra item: 'victim'
E     Use -v to get more diff
_ test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md --maturity resume-ready --target x] _
tests/test_handoff_envelope_maturity.py:1081: in test_suggested_command_is_shell_safe_and_single_line
    assert shlex.split(envelope["suggested_command"]) == [
E   AssertionError: assert ['/issue', '-...e-ready', ...] == ['/issue', '-... 'plan-ready']
E     
E     At index 3 diff: 'docs/plans/a.md' != 'docs/plans/a.md --maturity resume-ready --target x'
E     Left contains 4 more items, first extra item: '--target'
E     Use -v to get more diff
_ test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md --force] _
tests/test_handoff_envelope_maturity.py:1081: in test_suggested_command_is_shell_safe_and_single_line
    assert shlex.split(envelope["suggested_command"]) == [
E   AssertionError: assert ['/issue', '-...aturity', ...] == ['/issue', '-... 'plan-ready']
E     
E     At index 3 diff: 'docs/plans/a.md' != 'docs/plans/a.md --force'
E     Left contains one more item: 'plan-ready'
E     Use -v to get more diff
_ test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md\n/issue --prepare --from attacker] _
tests/test_handoff_envelope_maturity.py:1081: in test_suggested_command_is_shell_safe_and_single_line
    assert shlex.split(envelope["suggested_command"]) == [
E   AssertionError: assert ['/issue', '-...prepare', ...] == ['/issue', '-... 'plan-ready']
E     
E     At index 3 diff: 'docs/plans/a.md' != 'docs/plans/a.md\n/issue --prepare --from attacker'
E     Left contains 4 more items, first extra item: '--from'
E     Use -v to get more diff
_________ test_overlong_path_component_returns_a_sentinel_not_oserror __________
tests/test_handoff_envelope_maturity.py:1100: in test_overlong_path_component_returns_a_sentinel_not_oserror
    got = HE.infer_maturity(source, root=tmp_path)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
plugins/saga/scripts/handoff_envelope.py:339: in infer_maturity
    if candidate.is_file():
       ^^^^^^^^^^^^^^^^^^^
../../../.local/share/uv/python/cpython-3.12-macos-aarch64-none/lib/python3.12/pathlib.py:892: in is_file
    return S_ISREG(self.stat().st_mode)
                   ^^^^^^^^^^^
../../../.local/share/uv/python/cpython-3.12-macos-aarch64-none/lib/python3.12/pathlib.py:840: in stat
    return os.stat(self, follow_symlinks=follow_symlinks)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   OSError: [Errno 63] File name too long: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/pytest-17151/test_overlong_path_component_r0/docs/plans/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.md'
=========================== short test summary info ============================
FAILED tests/test_handoff_envelope_maturity.py::test_reanchored_missing_twin_is_refused
FAILED tests/test_handoff_envelope_maturity.py::test_out_of_root_declaring_file_is_refused_in_both_spellings
FAILED tests/test_handoff_envelope_maturity.py::test_in_root_symlink_to_out_of_root_is_refused
FAILED tests/test_handoff_envelope_maturity.py::test_carrier_diagnostic_names_the_actual_cause[---\nmeta:\n  maturity: requirements-ready\n---\n-nested]
FAILED tests/test_handoff_envelope_maturity.py::test_carrier_diagnostic_names_the_actual_cause[---\nkeys:\n- maturity: requirements-ready\n---\n-sequence item]
FAILED tests/test_handoff_envelope_maturity.py::test_carrier_diagnostics_are_pairwise_distinct
FAILED tests/test_handoff_envelope_maturity.py::test_blank_maturity_diagnostic_says_blank_not_unrecognized
FAILED tests/test_handoff_envelope_maturity.py::test_unrecognized_remediation_names_pending_confirmation
FAILED tests/test_handoff_envelope_maturity.py::test_maturity_past_the_read_window_fails_closed
FAILED tests/test_handoff_envelope_maturity.py::test_closing_delimiter_past_the_read_window_names_the_window
FAILED tests/test_handoff_envelope_maturity.py::test_early_dashes_inside_quoted_value_fail_closed
FAILED tests/test_handoff_envelope_maturity.py::test_deeply_nested_yaml_fails_closed_without_traceback
FAILED tests/test_handoff_envelope_maturity.py::test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md; rm -rf victim]
FAILED tests/test_handoff_envelope_maturity.py::test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md --maturity resume-ready --target x]
FAILED tests/test_handoff_envelope_maturity.py::test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md --force]
FAILED tests/test_handoff_envelope_maturity.py::test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md\n/issue --prepare --from attacker]
FAILED tests/test_handoff_envelope_maturity.py::test_overlong_path_component_returns_a_sentinel_not_oserror
17 failed, 1 passed, 68 deselected in 1.64s
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/_pytest/pathlib.py:103: PytestWarning: (rm_rf) unknown function <built-in function scandir> when removing /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve0/repo/.orchestrate/land-r1:
<class 'PermissionError'>: [Errno 1] Operation not permitted: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve0/repo/.orchestrate/land-r1'
  warnings.warn(
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/_pytest/pathlib.py:96: PytestWarning: (rm_rf) error removing /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve0/repo/.orchestrate/land-r1
<class 'OSError'>: [Errno 66] Directory not empty: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve0/repo/.orchestrate/land-r1'
  warnings.warn(
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/_pytest/pathlib.py:96: PytestWarning: (rm_rf) error removing /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve0/repo/.orchestrate
<class 'OSError'>: [Errno 66] Directory not empty: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve0/repo/.orchestrate'
  warnings.warn(
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/_pytest/pathlib.py:96: PytestWarning: (rm_rf) error removing /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve0/repo
<class 'OSError'>: [Errno 66] Directory not empty: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve0/repo'
  warnings.warn(
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/_pytest/pathlib.py:96: PytestWarning: (rm_rf) error removing /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve0
<class 'OSError'>: [Errno 66] Directory not empty: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve0'
  warnings.warn(
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/_pytest/pathlib.py:103: PytestWarning: (rm_rf) unknown function <built-in function scandir> when removing /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve1/repo/.orchestrate/land-r1:
<class 'PermissionError'>: [Errno 1] Operation not permitted: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve1/repo/.orchestrate/land-r1'
  warnings.warn(
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/_pytest/pathlib.py:96: PytestWarning: (rm_rf) error removing /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve1/repo/.orchestrate/land-r1
<class 'OSError'>: [Errno 66] Directory not empty: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve1/repo/.orchestrate/land-r1'
  warnings.warn(
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/_pytest/pathlib.py:96: PytestWarning: (rm_rf) error removing /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve1/repo/.orchestrate
<class 'OSError'>: [Errno 66] Directory not empty: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve1/repo/.orchestrate'
  warnings.warn(
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/_pytest/pathlib.py:96: PytestWarning: (rm_rf) error removing /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve1/repo
<class 'OSError'>: [Errno 66] Directory not empty: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve1/repo'
  warnings.warn(
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/_pytest/pathlib.py:96: PytestWarning: (rm_rf) error removing /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve1
<class 'OSError'>: [Errno 66] Directory not empty: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877/test_real_removal_failure_neve1'
  warnings.warn(
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/_pytest/pathlib.py:96: PytestWarning: (rm_rf) error removing /private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877
<class 'OSError'>: [Errno 66] Directory not empty: '/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/garbage-23902051-b80e-478d-9b38-1df652fc5877'
  warnings.warn(
EXIT 1
```

### API-4 E2 green — existing cycle-8 pin

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_marker_less_out_of_root_declaration_is_never_read
.                                                                        [100%]
1 passed, 85 deselected in 0.11s
EXIT 0
```

### API-4 backup

```text
$ cp plugins/saga/scripts/handoff_envelope.py .pytest_cache/lane-a-proofs/handoff_envelope.py.bak
EXIT 0
```

### API-4 named mutation — remove marker-less absolute reset

```text
$ uv run python -c 'from pathlib import Path; p=Path('"'"'plugins/saga/scripts/handoff_envelope.py'"'"'); s=p.read_text(); assert s.count('"'"'            absolute = False'"'"') == 1; p.write_text(s.replace('"'"'            absolute = False'"'"', '"'"'            pass'"'"'))'
EXIT 0
```

### API-4 E2 red — absolute plan-ready declaration leaks

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_marker_less_out_of_root_declaration_is_never_read
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_marker_less_out_of_root_declaration_is_never_read ____________
tests/test_handoff_envelope_maturity.py:902: in test_marker_less_out_of_root_declaration_is_never_read
    assert got != "plan-ready", "a marker-less out-of-root file must not be read"
E   AssertionError: a marker-less out-of-root file must not be read
E   assert 'plan-ready' != 'plan-ready'
=========================== short test summary info ============================
FAILED tests/test_handoff_envelope_maturity.py::test_marker_less_out_of_root_declaration_is_never_read
1 failed, 85 deselected in 0.14s
EXIT 1
```

### Restore backup

```text
$ cp .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

### Verify byte identity

```text
$ cmp -s .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

```text
RESTORED-BYTE-IDENTICAL
```

### API-4 E2 green after restore

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_marker_less_out_of_root_declaration_is_never_read
.                                                                        [100%]
1 passed, 85 deselected in 0.11s
EXIT 0
```

### E1 green — repaired behavior defects

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k 'out_of_root_declaring_file_is_refused_in_both_spellings or in_root_symlink_to_out_of_root_is_refused or reanchored_missing_twin_is_refused or carrier_diagnostic_names_the_actual_cause or carrier_diagnostics_are_pairwise_distinct or blank_maturity_diagnostic_says_blank_not_unrecognized or unrecognized_remediation_names_pending_confirmation or maturity_past_the_read_window_fails_closed or closing_delimiter_past_the_read_window_names_the_window or early_dashes_inside_quoted_value_fail_closed or deeply_nested_yaml_fails_closed_without_traceback or suggested_command_is_shell_safe_and_single_line or overlong_path_component_returns_a_sentinel_not_oserror'
..................                                                       [100%]
18 passed, 68 deselected in 0.69s
EXIT 0
```

### Envelope module regression run

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py tests/test_handoff_envelope.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest
........................................................................ [ 50%]
.......................................................................  [100%]
143 passed in 1.16s
EXIT 0
```

### TEST-1 twin without a declaration E2 green

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_reanchored_twin_declaring_nothing_is_refused
.                                                                        [100%]
1 passed, 85 deselected in 0.16s
EXIT 0
```

### TEST-1 twin without a declaration backup

```text
$ cp plugins/saga/scripts/handoff_envelope.py .pytest_cache/lane-a-proofs/handoff_envelope.py.bak
EXIT 0
```

### TEST-1 twin without a declaration mutation

```text
$ uv run python -c 'from pathlib import Path; p=Path('"'"'plugins/saga/scripts/handoff_envelope.py'"'"'); s=p.read_text(); old='"'"'            # A twin that declares nothing cannot authorize the original source.\n            return f"unknown:out-of-root:{resolved.published}"'"'"'; new='"'"'            # A twin that declares nothing cannot authorize the original source.\n            pass'"'"'; assert s.count(old) == 1, s.count(old); p.write_text(s.replace(old, new))'
EXIT 0
```

### TEST-1 twin without a declaration E2 red

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_reanchored_twin_declaring_nothing_is_refused
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_reanchored_twin_declaring_nothing_is_refused _______________
tests/test_handoff_envelope_maturity.py:940: in test_reanchored_twin_declaring_nothing_is_refused
    assert HE.infer_maturity(source, root).startswith("unknown:out-of-root:")
E   AssertionError: assert False
E    +  where False = <built-in method startswith of str object at 0x107e9e270>('unknown:out-of-root:')
E    +    where <built-in method startswith of str object at 0x107e9e270> = 'requirements-ready'.startswith
E    +      where 'requirements-ready' = <function infer_maturity at 0x107a28cc0>('/Users/jefcox/workspace/infiquetra/cp912-lane-a/.pytest_cache/lane-a-proofs/pytest/test_reanchored_twin_declaring0/elsewhere/docs/brainstorms/x.md', PosixPath('/Users/jefcox/workspace/infiquetra/cp912-lane-a/.pytest_cache/lane-a-proofs/pytest/test_reanchored_twin_declaring0/root'))
E    +        where <function infer_maturity at 0x107a28cc0> = HE.infer_maturity
=========================== short test summary info ============================
FAILED tests/test_handoff_envelope_maturity.py::test_reanchored_twin_declaring_nothing_is_refused
1 failed, 85 deselected in 0.13s
EXIT 1
```

### Restore backup

```text
$ cp .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

### Verify byte identity

```text
$ cmp -s .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

```text
RESTORED-BYTE-IDENTICAL
```

### TEST-1 twin without a declaration E2 green restored

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_reanchored_twin_declaring_nothing_is_refused
.                                                                        [100%]
1 passed, 85 deselected in 0.11s
EXIT 0
```

### TEST-2 divergent inline re-anchor E2 green

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_resolve_source_is_the_single_owner
.                                                                        [100%]
1 passed, 85 deselected in 0.11s
EXIT 0
```

### TEST-2 divergent inline re-anchor backup

```text
$ cp plugins/saga/scripts/handoff_envelope.py .pytest_cache/lane-a-proofs/handoff_envelope.py.bak
EXIT 0
```

### TEST-2 divergent inline re-anchor mutation

```text
$ uv run python -c 'from pathlib import Path; p=Path('"'"'plugins/saga/scripts/handoff_envelope.py'"'"'); s=p.read_text(); old='"'"'    resolved = resolve_source(selected_source, root)\n'"'"'; new='"'"'    resolved = resolve_source(selected_source, root)\n    if Path(selected_source).is_absolute():\n        parts = Path(selected_source).parts\n        for marker in MARKER_DIRS:\n            if marker in parts:\n                inline = "/".join(parts[parts.index(marker):])\n                if (root / inline).is_file():\n                    resolved = ResolvedSource(root / inline, inline, True, False)\n                    break\n'"'"'; assert s.count(old) == 1, s.count(old); p.write_text(s.replace(old, new))'
EXIT 0
```

### TEST-2 divergent inline re-anchor E2 red

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_resolve_source_is_the_single_owner
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_resolve_source_is_the_single_owner ____________________
tests/test_handoff_envelope_maturity.py:960: in test_resolve_source_is_the_single_owner
    assert envelope["source"] == "FORCED-BY-TEST"
E   AssertionError: assert 'brainstorms/x.md' == 'FORCED-BY-TEST'
E     
E     - FORCED-BY-TEST
E     + brainstorms/x.md
=========================== short test summary info ============================
FAILED tests/test_handoff_envelope_maturity.py::test_resolve_source_is_the_single_owner
1 failed, 85 deselected in 0.13s
EXIT 1
```

### Restore backup

```text
$ cp .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

### Verify byte identity

```text
$ cmp -s .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

```text
RESTORED-BYTE-IDENTICAL
```

### TEST-2 divergent inline re-anchor E2 green restored

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_resolve_source_is_the_single_owner
.                                                                        [100%]
1 passed, 85 deselected in 0.11s
EXIT 0
```

### TEST-2 envelope bypasses backslash normalization E2 green

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_infer_and_envelope_agree_on_every_out_of_root_shape
....                                                                     [100%]
4 passed, 82 deselected in 0.12s
EXIT 0
```

### TEST-2 envelope bypasses backslash normalization backup

```text
$ cp plugins/saga/scripts/handoff_envelope.py .pytest_cache/lane-a-proofs/handoff_envelope.py.bak
EXIT 0
```

### TEST-2 envelope bypasses backslash normalization mutation

```text
$ uv run python -c 'from pathlib import Path; p=Path('"'"'plugins/saga/scripts/handoff_envelope.py'"'"'); s=p.read_text(); old='"'"'    resolved = resolve_source(selected_source, root)\n'"'"'; new='"'"'    resolved = resolve_source(selected_source, root)\n    if "\\\\" in selected_source:\n        resolved = ResolvedSource(root / selected_source, selected_source, False, False)\n'"'"'; assert s.count(old) == 1, s.count(old); p.write_text(s.replace(old, new))'
EXIT 0
```

### TEST-2 envelope bypasses backslash normalization E2 red

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_infer_and_envelope_agree_on_every_out_of_root_shape
..F.                                                                     [100%]
=================================== FAILURES ===================================
_____ test_infer_and_envelope_agree_on_every_out_of_root_shape[backslash] ______
tests/test_handoff_envelope_maturity.py:988: in test_infer_and_envelope_agree_on_every_out_of_root_shape
    assert envelope["handoff_maturity"] == expected
E   AssertionError: assert 'unknown:unreadable' == 'pending-confirmation'
E     
E     - pending-confirmation
E     + unknown:unreadable
=========================== short test summary info ============================
FAILED tests/test_handoff_envelope_maturity.py::test_infer_and_envelope_agree_on_every_out_of_root_shape[backslash]
1 failed, 3 passed, 82 deselected in 0.14s
EXIT 1
```

### Restore backup

```text
$ cp .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

### Verify byte identity

```text
$ cmp -s .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

```text
RESTORED-BYTE-IDENTICAL
```

### TEST-2 envelope bypasses backslash normalization E2 green restored

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_infer_and_envelope_agree_on_every_out_of_root_shape
....                                                                     [100%]
4 passed, 82 deselected in 0.12s
EXIT 0
```

### SEC-7 re-anchored containment E2 green

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_reanchored_candidate_escaping_root_is_refused
.                                                                        [100%]
1 passed, 85 deselected in 0.11s
EXIT 0
```

### SEC-7 re-anchored containment backup

```text
$ cp plugins/saga/scripts/handoff_envelope.py .pytest_cache/lane-a-proofs/handoff_envelope.py.bak
EXIT 0
```

### SEC-7 re-anchored containment mutation

```text
$ uv run python -c 'from pathlib import Path; p=Path('"'"'plugins/saga/scripts/handoff_envelope.py'"'"'); s=p.read_text(); old='"'"'        if _is_within(twin, base) and _is_file(twin):'"'"'; new='"'"'        if _is_file(twin):'"'"'; assert s.count(old) == 1, s.count(old); p.write_text(s.replace(old, new))'
EXIT 0
```

### SEC-7 re-anchored containment E2 red

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_reanchored_candidate_escaping_root_is_refused
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_reanchored_candidate_escaping_root_is_refused ______________
tests/test_handoff_envelope_maturity.py:854: in test_reanchored_candidate_escaping_root_is_refused
    assert result != "plan-ready", "an out-of-root declaration must not leak in"
E   AssertionError: an out-of-root declaration must not leak in
E   assert 'plan-ready' != 'plan-ready'
=========================== short test summary info ============================
FAILED tests/test_handoff_envelope_maturity.py::test_reanchored_candidate_escaping_root_is_refused
1 failed, 85 deselected in 0.14s
EXIT 1
```

### Restore backup

```text
$ cp .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

### Verify byte identity

```text
$ cmp -s .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

```text
RESTORED-BYTE-IDENTICAL
```

### SEC-7 re-anchored containment E2 green restored

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_reanchored_candidate_escaping_root_is_refused
.                                                                        [100%]
1 passed, 85 deselected in 0.12s
EXIT 0
```

### SEC-7 original absolute read E2 green

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_same_file_two_spellings_agree
.                                                                        [100%]
1 passed, 85 deselected in 0.12s
EXIT 0
```

### SEC-7 original absolute read backup

```text
$ cp plugins/saga/scripts/handoff_envelope.py .pytest_cache/lane-a-proofs/handoff_envelope.py.bak
EXIT 0
```

### SEC-7 original absolute read mutation

```text
$ uv run python -c 'from pathlib import Path; p=Path('"'"'plugins/saga/scripts/handoff_envelope.py'"'"'); s=p.read_text(); old='"'"'    return ResolvedSource(None, normalized, False, True)'"'"'; new='"'"'    if Path(normalized).is_absolute() and _is_file(candidate):\n        return ResolvedSource(candidate, normalized, False, False)\n    return ResolvedSource(None, normalized, False, True)'"'"'; assert s.count(old) == 1, s.count(old); p.write_text(s.replace(old, new))'
EXIT 0
```

### SEC-7 original absolute read E2 red

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_same_file_two_spellings_agree
F                                                                        [100%]
=================================== FAILURES ===================================
______________________ test_same_file_two_spellings_agree ______________________
tests/test_handoff_envelope_maturity.py:803: in test_same_file_two_spellings_agree
    assert absolute_outside.split(":", 2)[:2] == relative_outside.split(":", 2)[:2]
E   AssertionError: assert ['plan-ready'] == ['unknown', 'out-of-root']
E     
E     At index 0 diff: 'plan-ready' != 'unknown'
E     Right contains one more item: 'out-of-root'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED tests/test_handoff_envelope_maturity.py::test_same_file_two_spellings_agree
1 failed, 85 deselected in 0.14s
EXIT 1
```

### Restore backup

```text
$ cp .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

### Verify byte identity

```text
$ cmp -s .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

```text
RESTORED-BYTE-IDENTICAL
```

### SEC-7 original absolute read E2 green restored

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_same_file_two_spellings_agree
.                                                                        [100%]
1 passed, 85 deselected in 0.11s
EXIT 0
```

### SEC-9 reserved-prefix forgery E2 green

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_hand_written_unknown_prefix_is_wrapped_not_honoured
..                                                                       [100%]
2 passed, 84 deselected in 0.12s
EXIT 0
```

### SEC-9 reserved-prefix forgery backup

```text
$ cp plugins/saga/scripts/handoff_envelope.py .pytest_cache/lane-a-proofs/handoff_envelope.py.bak
EXIT 0
```

### SEC-9 reserved-prefix forgery mutation

```text
$ uv run python -c 'from pathlib import Path; p=Path('"'"'plugins/saga/scripts/handoff_envelope.py'"'"'); s=p.read_text(); old='"'"'    value = "" if raw is None else str(raw).strip()\n'"'"'; new='"'"'    value = "" if raw is None else str(raw).strip()\n    if value.startswith("unknown:"):\n        return value\n'"'"'; assert s.count(old) == 1, s.count(old); p.write_text(s.replace(old, new))'
EXIT 0
```

### SEC-9 reserved-prefix forgery E2 red

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_hand_written_unknown_prefix_is_wrapped_not_honoured
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_hand_written_unknown_prefix_is_wrapped_not_honoured[unknown:out-of-root:x] _
tests/test_handoff_envelope_maturity.py:1134: in test_hand_written_unknown_prefix_is_wrapped_not_honoured
    assert _infer(tmp_path, f'---\nmaturity: "{value}"\n---\n') == (f"unknown:unrecognized:{value}")
E   AssertionError: assert 'unknown:out-of-root:x' == 'unknown:unre...out-of-root:x'
E     
E     - unknown:unrecognized:unknown:out-of-root:x
E     + unknown:out-of-root:x
__ test_hand_written_unknown_prefix_is_wrapped_not_honoured[unknown:carrier:] __
tests/test_handoff_envelope_maturity.py:1134: in test_hand_written_unknown_prefix_is_wrapped_not_honoured
    assert _infer(tmp_path, f'---\nmaturity: "{value}"\n---\n') == (f"unknown:unrecognized:{value}")
E   AssertionError: assert 'unknown:carrier:' == 'unknown:unre...nown:carrier:'
E     
E     - unknown:unrecognized:unknown:carrier:
E     + unknown:carrier:
=========================== short test summary info ============================
FAILED tests/test_handoff_envelope_maturity.py::test_hand_written_unknown_prefix_is_wrapped_not_honoured[unknown:out-of-root:x]
FAILED tests/test_handoff_envelope_maturity.py::test_hand_written_unknown_prefix_is_wrapped_not_honoured[unknown:carrier:]
2 failed, 84 deselected in 0.15s
EXIT 1
```

### Restore backup

```text
$ cp .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

### Verify byte identity

```text
$ cmp -s .pytest_cache/lane-a-proofs/handoff_envelope.py.bak plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

```text
RESTORED-BYTE-IDENTICAL
```

### SEC-9 reserved-prefix forgery E2 green restored

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_hand_written_unknown_prefix_is_wrapped_not_honoured
..                                                                       [100%]
2 passed, 84 deselected in 0.12s
EXIT 0
```

### CORR-5 garbled handoff clarification E2 green

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_unrecognized_handoff_section_requires_clarification
.                                                                        [100%]
1 passed, 85 deselected in 0.11s
EXIT 0
```

### CORR-5 garbled handoff clarification backup

```text
$ cp plugins/saga/scripts/parse_issue.py .pytest_cache/lane-a-proofs/parse_issue.py.bak
EXIT 0
```

### CORR-5 garbled handoff clarification mutation

```text
$ uv run python -c 'from pathlib import Path; p=Path('"'"'plugins/saga/scripts/parse_issue.py'"'"'); s=p.read_text(); old='"'"'"requires_clarification": maturity == "deferred-context" or unrecognized_declaration,'"'"'; new='"'"'"requires_clarification": maturity == "deferred-context",'"'"'; assert s.count(old) == 1, s.count(old); p.write_text(s.replace(old, new))'
EXIT 0
```

### CORR-5 garbled handoff clarification E2 red

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_unrecognized_handoff_section_requires_clarification
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_unrecognized_handoff_section_requires_clarification ___________
tests/test_handoff_envelope_maturity.py:1119: in test_unrecognized_handoff_section_requires_clarification
    assert got["requires_clarification"] is True
E   assert False is True
=========================== short test summary info ============================
FAILED tests/test_handoff_envelope_maturity.py::test_unrecognized_handoff_section_requires_clarification
1 failed, 85 deselected in 0.14s
EXIT 1
```

### Restore backup

```text
$ cp .pytest_cache/lane-a-proofs/parse_issue.py.bak plugins/saga/scripts/parse_issue.py
EXIT 0
```

### Verify byte identity

```text
$ cmp -s .pytest_cache/lane-a-proofs/parse_issue.py.bak plugins/saga/scripts/parse_issue.py
EXIT 0
```

```text
RESTORED-BYTE-IDENTICAL
```

### CORR-5 garbled handoff clarification E2 green restored

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_unrecognized_handoff_section_requires_clarification
.                                                                        [100%]
1 passed, 85 deselected in 0.12s
EXIT 0
```

### AU-3 top-level flow mapping documentation pin

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k test_top_level_flow_mapping_declares
.                                                                        [100%]
1 passed, 85 deselected in 0.12s
EXIT 0
```

### AM-6 AST counts and acceptance bar

```text
$ uv run python -c 'import ast
tree = ast.parse(open("plugins/saga/scripts/handoff_envelope.py").read())
failures = []
for f in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
    returns = sum(isinstance(n, ast.Return) for n in ast.walk(f))
    branches = sum(isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.BoolOp)) for n in ast.walk(f))
    nested = sum(isinstance(n, ast.FunctionDef) for n in ast.walk(f)) - 1
    print(f"{f.name}: returns={returns} branches={branches} nested_defs={nested}")
    if returns > 8 or branches > 12 or nested:
        failures.append(f.name)
assert not failures, failures
print("AM-6: all functions meet the 8-return / 12-branch / zero-nested-def bar")
'
_no_duplicate_keys: returns=1 branches=2 nested_defs=0
_extract_declared_maturity_value: returns=2 branches=1 nested_defs=0
_scanned_maturity_line: returns=2 branches=2 nested_defs=0
_carrier: returns=1 branches=1 nested_defs=0
_recover_utf16: returns=2 branches=4 nested_defs=0
_recover_text: returns=3 branches=5 nested_defs=0
_decode_window: returns=3 branches=2 nested_defs=0
_read_window: returns=2 branches=2 nested_defs=0
_split_frontmatter: returns=3 branches=2 nested_defs=0
_nested_maturity_detail: returns=2 branches=5 nested_defs=0
_has_nested_maturity: returns=1 branches=0 nested_defs=0
_parse_frontmatter: returns=2 branches=1 nested_defs=0
_classify_declared_value: returns=2 branches=2 nested_defs=0
_classify_frontmatter: returns=4 branches=5 nested_defs=0
_read_frontmatter_maturity: returns=5 branches=6 nested_defs=0
carrier_detail: returns=4 branches=4 nested_defs=0
_unterminated_detail: returns=2 branches=2 nested_defs=0
_is_file: returns=2 branches=1 nested_defs=0
_is_within: returns=2 branches=1 nested_defs=0
_reanchor_to_marker: returns=2 branches=2 nested_defs=0
resolve_source: returns=3 branches=6 nested_defs=0
_path_maturity: returns=5 branches=7 nested_defs=0
_resolved_maturity: returns=4 branches=4 nested_defs=0
infer_maturity: returns=1 branches=0 nested_defs=0
infer_lifecycle_phase: returns=6 branches=6 nested_defs=0
read_state: returns=3 branches=2 nested_defs=0
_state_source: returns=2 branches=4 nested_defs=0
_source_candidates: returns=1 branches=9 nested_defs=0
discover_active_source: returns=3 branches=2 nested_defs=0
_git_output: returns=1 branches=0 nested_defs=0
current_git_state: returns=1 branches=0 nested_defs=0
_escape_controls: returns=1 branches=0 nested_defs=0
_display_source: returns=1 branches=0 nested_defs=0
_bounded_maturity: returns=2 branches=1 nested_defs=0
_diagnostic_source: returns=1 branches=1 nested_defs=0
_maturity_remediation: returns=1 branches=0 nested_defs=0
_maturity_diagnostic: returns=8 branches=7 nested_defs=0
_suggested_command: returns=2 branches=3 nested_defs=0
build_handoff_envelope: returns=1 branches=3 nested_defs=0
build_deploy_handoff_envelope: returns=1 branches=1 nested_defs=0
parse_args: returns=1 branches=0 nested_defs=0
main: returns=1 branches=0 nested_defs=0
AM-6: all functions meet the 8-return / 12-branch / zero-nested-def bar
EXIT 0
```

### AM-5 initial coverage measurement

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py tests/test_handoff_envelope.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest --cov=plugins/saga/scripts --cov-report=term-missing --cov-report=json:.pytest_cache/lane-a-proofs/coverage.json
........................................................................ [ 50%]
.......................................................................  [100%]
================================ tests coverage ================================
______________ coverage: platform darwin, python 3.12.11-final-0 _______________

Name                                                  Stmts   Miss  Cover   Missing
-----------------------------------------------------------------------------------
plugins/saga/scripts/adjustment_envelope.py             257    257     0%   44-536
plugins/saga/scripts/board_progression.py               280    280     0%   19-860
plugins/saga/scripts/bridge_signatures.py                68     68     0%   4-116
plugins/saga/scripts/capability_elo.py                  146    146     0%   20-270
plugins/saga/scripts/ceremony_hazards.py                 84     84     0%   34-372
plugins/saga/scripts/chaperone_economics.py             258    258     0%   4-562
plugins/saga/scripts/check_engine_registry.py            48     48     0%   4-81
plugins/saga/scripts/closure_gate.py                    120    120     0%   59-306
plugins/saga/scripts/completeness_gate.py               159    159     0%   7-275
plugins/saga/scripts/concurrency_governor.py            168    168     0%   9-343
plugins/saga/scripts/delegation_audit_query.py           26     26     0%   15-76
plugins/saga/scripts/deploy_handoff.py                  244     10    96%   181, 184, 237-238, 417, 420-421, 423, 459, 484
plugins/saga/scripts/detect_deploy_strategy.py           74     74     0%   4-120
plugins/saga/scripts/discover_sessions.py                53     53     0%   26-112
plugins/saga/scripts/discover_subissues.py               53     53     0%   4-168
plugins/saga/scripts/dispatch_settlement.py             951    951     0%   9-2062
plugins/saga/scripts/effort_ledger.py                   127    127     0%   24-259
plugins/saga/scripts/engine_benchmark.py                210    210     0%   16-399
plugins/saga/scripts/engine_bridge_http.py               90     90     0%   23-202
plugins/saga/scripts/engine_calibration.py              160    160     0%   31-347
plugins/saga/scripts/engine_dispatch.py                 886    886     0%   4-2328
plugins/saga/scripts/engine_onboarding.py               277    277     0%   4-472
plugins/saga/scripts/engine_overlay.py                  121    121     0%   4-178
plugins/saga/scripts/engine_promotion.py                112    112     0%   4-206
plugins/saga/scripts/engine_recommend.py                134    134     0%   4-292
plugins/saga/scripts/engine_registry.py                 481    481     0%   4-838
plugins/saga/scripts/engine_registry_cli.py             168    168     0%   4-317
plugins/saga/scripts/engine_registry_conformance.py      89     89     0%   4-182
plugins/saga/scripts/engine_resolver.py                 400    400     0%   4-980
plugins/saga/scripts/engine_stale_report.py             107    107     0%   24-217
plugins/saga/scripts/envelope_token.py                  320    320     0%   64-821
plugins/saga/scripts/evidence_ledger.py                 277    277     0%   43-700
plugins/saga/scripts/execution_spec.py                 1132   1132     0%   39-3096
plugins/saga/scripts/extract_session_skeleton.py        145    145     0%   26-250
plugins/saga/scripts/find_inflight_work.py               27     27     0%   16-63
plugins/saga/scripts/fleet_commons_shim.py               99     99     0%   25-169
plugins/saga/scripts/fleet_doctor.py                    854    854     0%   22-1782
plugins/saga/scripts/gate_divergence_reader.py          102    102     0%   37-234
plugins/saga/scripts/handoff_envelope.py                360     72    80%   161-162, 245, 253, 284-285, 333, 362, 364, 370-377, 381-387, 391-410, 414-421, 425-426, 430-432, 536, 538, 556, 604, 618-626, 630-641
plugins/saga/scripts/intent_envelope.py                 131    131     0%   34-256
plugins/saga/scripts/issue_progress.py                   81     81     0%   4-207
plugins/saga/scripts/journal_triggers.py                 15     15     0%   4-24
plugins/saga/scripts/lifecycle_review.py                227    227     0%   44-420
plugins/saga/scripts/lifecycle_state.py                 175    175     0%   4-661
plugins/saga/scripts/lint_gate_absence_contract.py      243    243     0%   46-453
plugins/saga/scripts/liveness_events.py                 502    502     0%   9-1085
plugins/saga/scripts/load_saga_context.py                18     18     0%   18-61
plugins/saga/scripts/manifest_reader.py                 124    124     0%   44-326
plugins/saga/scripts/manifest_store.py                  215    215     0%   38-434
plugins/saga/scripts/merge_watcher.py                   192    192     0%   36-549
plugins/saga/scripts/outcome.py                         985    985     0%   32-2838
plugins/saga/scripts/outcome_board_sync.py               97     97     0%   19-355
plugins/saga/scripts/outcome_compat.py                  521    521     0%   36-1536
plugins/saga/scripts/outcome_costs.py                   118    118     0%   27-259
plugins/saga/scripts/outcome_decompose.py               174    174     0%   32-419
plugins/saga/scripts/outcome_dispatcher.py              227    227     0%   29-769
plugins/saga/scripts/outcome_edges.py                    85     85     0%   14-139
plugins/saga/scripts/outcome_gate_transport.py           63     63     0%   31-187
plugins/saga/scripts/outcome_github.py                  193    193     0%   18-360
plugins/saga/scripts/outcome_intent.py                  229    229     0%   64-690
plugins/saga/scripts/outcome_liveness.py                 97     97     0%   21-223
plugins/saga/scripts/outcome_merge.py                   176    176     0%   54-522
plugins/saga/scripts/outcome_orchestrator.py            126    126     0%   27-362
plugins/saga/scripts/outcome_projection.py               41     41     0%   24-128
plugins/saga/scripts/outcome_reconcile.py               158    158     0%   30-444
plugins/saga/scripts/outcome_report.py                  145    145     0%   26-353
plugins/saga/scripts/outcome_spec.py                    322    322     0%   31-835
plugins/saga/scripts/outcome_store.py                   408    408     0%   38-870
plugins/saga/scripts/outcome_worktrees.py               281    281     0%   37-725
plugins/saga/scripts/override_rate_reader.py            133    133     0%   34-349
plugins/saga/scripts/parse_issue.py                      76     29    62%   36, 61-65, 91-107, 125-127, 131-137
plugins/saga/scripts/plan_artifact_conformance.py        92     92     0%   23-191
plugins/saga/scripts/plan_pre_answers.py                131    131     0%   51-404
plugins/saga/scripts/promote_scan.py                    297    297     0%   37-607
plugins/saga/scripts/provenance_manifest.py             292    292     0%   33-650
plugins/saga/scripts/provider_control_chart.py          106    106     0%   21-206
plugins/saga/scripts/pulse.py                           249    249     0%   35-656
plugins/saga/scripts/qa_health_score.py                  36     36     0%   30-119
plugins/saga/scripts/reconcile.py                       485    485     0%   9-956
plugins/saga/scripts/reconcile_controller.py            183    183     0%   50-631
plugins/saga/scripts/render_docs_visuals.py             201    201     0%   4-458
plugins/saga/scripts/reversibility_certificate.py       117    117     0%   29-540
plugins/saga/scripts/review_consensus.py               1223   1223     0%   83-2728
plugins/saga/scripts/run_ledger.py                      209    209     0%   26-416
plugins/saga/scripts/saga.py                            728    266    63%   52-53, 100, 139, 344-345, 357, 368, 383-384, 390, 409, 435, 440, 444-445, 453, 459, 473, 475-479, 481, 486-487, 502, 523, 543, 567-568, 571, 670, 712-715, 750-772, 811, 813, 838, 840, 842, 855-856, 860-861, 876-878, 919-930, 953-954, 996, 1036-1040, 1045-1048, 1053-1077, 1087-1126, 1142, 1156-1167, 1177-1180, 1185-1188, 1195-1231, 1236-1260, 1276-1302, 1332-1348, 1374-1383, 1392-1414, 1429, 1436, 1491, 1541-1548, 1701-1769, 1773-1836
plugins/saga/scripts/saga_spore.py                      235    235     0%   28-478
plugins/saga/scripts/scaffold_checkpoint.py              37     37     0%   20-104
plugins/saga/scripts/second_opinion.py                 1024   1024     0%   4-2076
plugins/saga/scripts/ship_ceremony.py                   468    468     0%   52-1710
plugins/saga/scripts/ship_receipt.py                    123    123     0%   24-287
plugins/saga/scripts/ship_teardown.py                   468    468     0%   29-999
plugins/saga/scripts/ship_undo.py                       201    201     0%   52-656
plugins/saga/scripts/spec_table.py                      172    172     0%   24-317
plugins/saga/scripts/spend_authority.py                  46     46     0%   19-115
plugins/saga/scripts/spend_estimate.py                  146    146     0%   33-372
plugins/saga/scripts/spend_receipt.py                    78     78     0%   27-173
plugins/saga/scripts/spend_retro.py                     152    152     0%   24-339
plugins/saga/scripts/status_card.py                     427    427     0%   18-960
plugins/saga/scripts/team_emitter.py                    149    149     0%   27-403
plugins/saga/scripts/team_teardown.py                   508    508     0%   22-1455
plugins/saga/scripts/tier_defaults.py                   102    102     0%   14-190
plugins/saga/scripts/tier_efficacy.py                    87     87     0%   19-196
plugins/saga/scripts/tier_session.py                     89     89     0%   12-142
-----------------------------------------------------------------------------------
TOTAL                                                 25106  24075     4%
Coverage JSON written to file .pytest_cache/lane-a-proofs/coverage.json
143 passed in 5.13s
EXIT 0
```

### AM-5 initial helper coverage — identify missing error-path pins

```text
$ uv run python -c 'import ast
import json
from pathlib import Path

path = "plugins/saga/scripts/handoff_envelope.py"
tree = ast.parse(Path(path).read_text())
report = json.loads(Path(".pytest_cache/lane-a-proofs/coverage.json").read_text())
missing = set(report["files"][path]["missing_lines"])
helpers = set(["_extract_declared_maturity_value","_scanned_maturity_line","_carrier","_recover_utf16","_recover_text","_decode_window","_read_window","_split_frontmatter","_nested_maturity_detail","_has_nested_maturity","_parse_frontmatter","_classify_declared_value","_classify_frontmatter","_read_frontmatter_maturity","carrier_detail","_unterminated_detail","_reanchor_to_marker"])
failures = {}
for function in (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in helpers):
    uncovered = sorted(missing.intersection(range(function.lineno, function.end_lineno + 1)))
    print(f"{function.name}: missing_lines={uncovered}")
    if uncovered:
        failures[function.name] = uncovered
assert not failures, failures
print("AM-5: zero missing lines in every extracted parser and re-anchor helper")
'
Traceback (most recent call last):
  File "<string>", line 16, in <module>
AssertionError: {'_read_window': [161, 162], '_read_frontmatter_maturity': [245], 'carrier_detail': [253]}
_extract_declared_maturity_value: missing_lines=[]
_scanned_maturity_line: missing_lines=[]
_carrier: missing_lines=[]
_recover_utf16: missing_lines=[]
_recover_text: missing_lines=[]
_decode_window: missing_lines=[]
_read_window: missing_lines=[161, 162]
_split_frontmatter: missing_lines=[]
_nested_maturity_detail: missing_lines=[]
_has_nested_maturity: missing_lines=[]
_parse_frontmatter: missing_lines=[]
_classify_declared_value: missing_lines=[]
_classify_frontmatter: missing_lines=[]
_read_frontmatter_maturity: missing_lines=[245]
carrier_detail: missing_lines=[253]
_unterminated_detail: missing_lines=[]
_reanchor_to_marker: missing_lines=[]
EXIT 1
```

### Format owned Python files

```text
$ uv run ruff format plugins/saga/scripts/handoff_envelope.py tests/test_handoff_envelope_maturity.py tests/test_handoff_envelope.py
3 files left unchanged
EXIT 0
```

### Required scoped suite — Git metadata stubbed

```text
$ uv run python -c 'import os
import subprocess
import sys
import pytest

real_run = subprocess.run
stubbed_metadata = []
allowed_metadata = {("git", "branch", "--show-current"), ("git", "rev-parse", "--short", "HEAD")}

def metadata_only(argv, *args, **kwargs):
    if isinstance(argv, (list, tuple)) and argv and os.path.basename(str(argv[0])) == "git":
        assert tuple(argv) in allowed_metadata, f"Unexpected prohibited Git request: {argv!r}"
        stubbed_metadata.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 1, "", "")
    return real_run(argv, *args, **kwargs)

def audit(event, args):
    if event == "subprocess.Popen" and os.path.basename(os.fsdecode(args[0])) == "git":
        raise RuntimeError("No-Git dispatch: attempted actual Git execution")

sys.addaudithook(audit)
subprocess.run = metadata_only
try:
    result = pytest.main(sys.argv[1:])
finally:
    print(f"NO-GIT: {len(stubbed_metadata)} metadata requests stubbed; no Git process executed")
sys.exit(result)
' tests/test_handoff_envelope_maturity.py tests/test_handoff_envelope.py tests/test_saga_plugin.py tests/test_saga_saga.py tests/test_saga_docs_coverage.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest
........................................................................ [ 23%]
........................................................................ [ 46%]
........................................................................ [ 69%]
........................................................................ [ 92%]
.........................                                                [100%]
313 passed in 2.92s
NO-GIT: 6 metadata requests stubbed; no Git process executed
EXIT 0
```

### Required test-shape lint

```text
$ uv run python scripts/lint_test_shape.py
usage: lint_test_shape.py [-h] [--prod-module PROD_MODULE]
                          [--allowlist ALLOWLIST] [--advisory]
                          paths [paths ...]
lint_test_shape.py: error: the following arguments are required: paths
EXIT 2
```

### Required test-shape lint — repository CI invocation supplies missing paths

```text
$ uv run python scripts/lint_test_shape.py tests plugins --prod-module server
lint_test_shape: OK — 301 module(s) checked, no fake-only suites
EXIT 0
```

### Required Ruff lint

```text
$ uv run ruff check .
All checks passed!
EXIT 0
```

### Required Ruff format check

```text
$ uv run ruff format --check .
517 files already formatted
EXIT 0
```

### Required mypy — single process

```text
$ uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
tests/test_unifi_protect_client.py:247: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_unifi_protect_client.py:284: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_unifi_protect_client.py:308: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_unifi_network_client.py:289: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_unifi_network_client.py:328: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_unifi_network_client.py:352: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_outcome_command.py:68: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
Success: no issues found in 346 source files
EXIT 0
```

### E1 final module backup

```text
$ cp plugins/saga/scripts/handoff_envelope.py .pytest_cache/lane-a-proofs/handoff_envelope.py.fixed
EXIT 0
```

### E1 restore pre-fix source captured before edits

```text
$ cp .pytest_cache/lane-a-proofs/handoff_envelope.py.pre plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

### E1 repeat on pre-fix source — restoration proof and delimiter pin

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k 'out_of_root_declaring_file_is_refused_in_both_spellings or in_root_symlink_to_out_of_root_is_refused or reanchored_missing_twin_is_refused or carrier_diagnostic_names_the_actual_cause or carrier_diagnostics_are_pairwise_distinct or blank_maturity_diagnostic_says_blank_not_unrecognized or unrecognized_remediation_names_pending_confirmation or maturity_past_the_read_window_fails_closed or closing_delimiter_past_the_read_window_names_the_window or early_dashes_inside_quoted_value_fail_closed or deeply_nested_yaml_fails_closed_without_traceback or suggested_command_is_shell_safe_and_single_line or overlong_path_component_returns_a_sentinel_not_oserror or test_dash_prefixed_yaml_key_does_not_close_frontmatter' --tb=line
FFFFF.FFFFFFFFFFFFF                                                      [100%]
=================================== FAILURES ===================================
E   AssertionError: assert False
     +  where False = <built-in method startswith of str object at 0x109fcbf30>('unknown:out-of-root:')
     +    where <built-in method startswith of str object at 0x109fcbf30> = 'pending-confirmation'.startswith
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:535: AssertionError: assert False
E   AssertionError: assert '/issue --prepare' not in '/issue --pr...y plan-ready'
      
      '/issue --prepare' is contained here:
        /issue --prepare --from /Users/jefcox/workspace/infiquetra/cp912-lane-a/.pytest_cache/lane-a-proofs/pytest/test_out_of_root_declaring_fil0/elsewhere/docs/brainstorms/x.md --maturity plan-ready
      ? ++++++++++++++++
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:915: AssertionError: assert '/issue --prepare' not in '/issue --pr...y plan-ready'
E   AssertionError: assert '/issue --prepare' not in '/issue --pr...y plan-ready'
      
      '/issue --prepare' is contained here:
        /issue --prepare --from /Users/jefcox/workspace/infiquetra/cp912-lane-a/.pytest_cache/lane-a-proofs/pytest/test_in_root_symlink_to_out_of0/root/docs/plans/link.md --maturity plan-ready
      ? ++++++++++++++++
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:929: AssertionError: assert '/issue --prepare' not in '/issue --pr...y plan-ready'
E   assert 'nested' in "frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited yaml block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"
     +  where "frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited yaml block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key" = <built-in method lower of str object at 0xca5a11b80>()
     +    where <built-in method lower of str object at 0xca5a11b80> = "Frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited YAML block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key".lower
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1009: assert 'nested' in "frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited yaml block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"
E   assert 'sequence item' in "frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited yaml block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"
     +  where "frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited yaml block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key" = <built-in method lower of str object at 0xca5a11e00>()
     +    where <built-in method lower of str object at 0xca5a11e00> = "Frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited YAML block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key".lower
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1009: assert 'sequence item' in "frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declare...ited yaml block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"
E   assert 1 == 3
     +  where 1 = len({"Frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declar...ted YAML block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"})
     +    where {"Frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declar...ted YAML block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"} = set(["Frontmatter carrier missing delimiters for docs/brainstorms/t-requirements.md — maturity 'requirements-ready' declar...ted YAML block; no durable route; fix frontmatter to be delimited by literal --- lines with a top-level maturity: key"])
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1023: assert 1 == 3
E   assert 'blank' in "unrecognized maturity '(empty)' for docs/brainstorms/t-requirements.md — no durable route; fix frontmatter to one of idea-ready, requirements-ready, plan-ready, resume-ready, deferred-context"
     +  where "unrecognized maturity '(empty)' for docs/brainstorms/t-requirements.md — no durable route; fix frontmatter to one of idea-ready, requirements-ready, plan-ready, resume-ready, deferred-context" = <built-in method lower of str object at 0x109792330>()
     +    where <built-in method lower of str object at 0x109792330> = "Unrecognized maturity '(empty)' for docs/brainstorms/t-requirements.md — no durable route; fix frontmatter to one of idea-ready, requirements-ready, plan-ready, resume-ready, deferred-context".lower
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1029: assert 'blank' in "unrecognized maturity '(empty)' for docs/brainstorms/t-requirements.md — no durable route; fix frontmatter to one of idea-ready, requirements-ready, plan-ready, resume-ready, deferred-context"
E   assert 'pending-confirmation' in "Unrecognized maturity 'pending confirmation' for docs/brainstorms/t-requirements.md — no durable route; fix frontmatter to one of idea-ready, requirements-ready, plan-ready, resume-ready, deferred-context"
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1036: assert 'pending-confirmation' in "Unrecognized maturity 'pending confirmation' for docs/brainstorms/t-requirements.md — no durable route; fix frontmatter to one of idea-ready, requirements-ready, plan-ready, resume-ready, deferred-context"
E   AssertionError: assert False
     +  where False = <built-in method startswith of str object at 0x10a0a05f0>('unknown:unterminated:')
     +    where <built-in method startswith of str object at 0x10a0a05f0> = 'requirements-ready'.startswith
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1044: AssertionError: assert False
E   assert '8192' in "Unterminated frontmatter block for docs/brainstorms/t-requirements.md — maturity 'plan-ready' declared but closing --- missing; no durable route; fix frontmatter to close the block"
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1053: assert '8192' in "Unterminated frontmatter block for docs/brainstorms/t-requirements.md — maturity 'plan-ready' declared but closing --- missing; no durable route; fix frontmatter to close the block"
E   AssertionError: assert False
     +  where False = <built-in method startswith of str object at 0x10a0a05f0>('unknown:carrier:')
     +    where <built-in method startswith of str object at 0x10a0a05f0> = 'requirements-ready'.startswith
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1059: AssertionError: assert False
E   RecursionError: maximum recursion depth exceeded
/Users/jefcox/workspace/infiquetra/cp912-lane-a/.venv/lib/python3.12/site-packages/yaml/scanner.py:306: RecursionError: maximum recursion depth exceeded
E   AssertionError: assert ['/issue', '-...', '-rf', ...] == ['/issue', '-... 'plan-ready']
      
      At index 3 diff: 'docs/plans/a.md;' != 'docs/plans/a.md; rm -rf victim'
      Left contains 3 more items, first extra item: 'victim'
      Use -v to get more diff
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1084: AssertionError: assert ['/issue', '-...', '-rf', ...] == ['/issue', '-... 'plan-ready']
E   AssertionError: assert ['/issue', '-...e-ready', ...] == ['/issue', '-... 'plan-ready']
      
      At index 3 diff: 'docs/plans/a.md' != 'docs/plans/a.md --maturity resume-ready --target x'
      Left contains 4 more items, first extra item: '--target'
      Use -v to get more diff
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1084: AssertionError: assert ['/issue', '-...e-ready', ...] == ['/issue', '-... 'plan-ready']
E   AssertionError: assert ['/issue', '-...aturity', ...] == ['/issue', '-... 'plan-ready']
      
      At index 3 diff: 'docs/plans/a.md' != 'docs/plans/a.md --force'
      Left contains one more item: 'plan-ready'
      Use -v to get more diff
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1084: AssertionError: assert ['/issue', '-...aturity', ...] == ['/issue', '-... 'plan-ready']
E   AssertionError: assert ['/issue', '-...prepare', ...] == ['/issue', '-... 'plan-ready']
      
      At index 3 diff: 'docs/plans/a.md' != 'docs/plans/a.md\n/issue --prepare --from attacker'
      Left contains 4 more items, first extra item: '--from'
      Use -v to get more diff
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1084: AssertionError: assert ['/issue', '-...prepare', ...] == ['/issue', '-... 'plan-ready']
E   OSError: [Errno 63] File name too long: '/Users/jefcox/workspace/infiquetra/cp912-lane-a/.pytest_cache/lane-a-proofs/pytest/test_overlong_path_component_r0/docs/plans/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.md'
/Users/jefcox/.local/share/uv/python/cpython-3.12-macos-aarch64-none/lib/python3.12/pathlib.py:840: OSError: [Errno 63] File name too long: '/Users/jefcox/workspace/infiquetra/cp912-lane-a/.pytest_cache/lane-a-proofs/pytest/test_overlong_path_component_r0/docs/plans/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.md'
E   AssertionError: assert 'requirements-ready' == 'pending-confirmation'
      
      - pending-confirmation
      + requirements-ready
/Users/jefcox/workspace/infiquetra/cp912-lane-a/tests/test_handoff_envelope_maturity.py:1159: AssertionError: assert 'requirements-ready' == 'pending-confirmation'
=========================== short test summary info ============================
FAILED tests/test_handoff_envelope_maturity.py::test_reanchored_missing_twin_is_refused
FAILED tests/test_handoff_envelope_maturity.py::test_out_of_root_declaring_file_is_refused_in_both_spellings
FAILED tests/test_handoff_envelope_maturity.py::test_in_root_symlink_to_out_of_root_is_refused
FAILED tests/test_handoff_envelope_maturity.py::test_carrier_diagnostic_names_the_actual_cause[---\nmeta:\n  maturity: requirements-ready\n---\n-nested]
FAILED tests/test_handoff_envelope_maturity.py::test_carrier_diagnostic_names_the_actual_cause[---\nkeys:\n- maturity: requirements-ready\n---\n-sequence item]
FAILED tests/test_handoff_envelope_maturity.py::test_carrier_diagnostics_are_pairwise_distinct
FAILED tests/test_handoff_envelope_maturity.py::test_blank_maturity_diagnostic_says_blank_not_unrecognized
FAILED tests/test_handoff_envelope_maturity.py::test_unrecognized_remediation_names_pending_confirmation
FAILED tests/test_handoff_envelope_maturity.py::test_maturity_past_the_read_window_fails_closed
FAILED tests/test_handoff_envelope_maturity.py::test_closing_delimiter_past_the_read_window_names_the_window
FAILED tests/test_handoff_envelope_maturity.py::test_early_dashes_inside_quoted_value_fail_closed
FAILED tests/test_handoff_envelope_maturity.py::test_deeply_nested_yaml_fails_closed_without_traceback
FAILED tests/test_handoff_envelope_maturity.py::test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md; rm -rf victim]
FAILED tests/test_handoff_envelope_maturity.py::test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md --maturity resume-ready --target x]
FAILED tests/test_handoff_envelope_maturity.py::test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md --force]
FAILED tests/test_handoff_envelope_maturity.py::test_suggested_command_is_shell_safe_and_single_line[docs/plans/a.md\n/issue --prepare --from attacker]
FAILED tests/test_handoff_envelope_maturity.py::test_overlong_path_component_returns_a_sentinel_not_oserror
FAILED tests/test_handoff_envelope_maturity.py::test_dash_prefixed_yaml_key_does_not_close_frontmatter
18 failed, 1 passed, 79 deselected in 0.85s
EXIT 1
```

### Restore backup

```text
$ cp .pytest_cache/lane-a-proofs/handoff_envelope.py.fixed plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

### Verify byte identity

```text
$ cmp -s .pytest_cache/lane-a-proofs/handoff_envelope.py.fixed plugins/saga/scripts/handoff_envelope.py
EXIT 0
```

```text
RESTORED-BYTE-IDENTICAL
```

### E1 green after byte-identical fixed-module restore

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest -k 'out_of_root_declaring_file_is_refused_in_both_spellings or in_root_symlink_to_out_of_root_is_refused or reanchored_missing_twin_is_refused or carrier_diagnostic_names_the_actual_cause or carrier_diagnostics_are_pairwise_distinct or blank_maturity_diagnostic_says_blank_not_unrecognized or unrecognized_remediation_names_pending_confirmation or maturity_past_the_read_window_fails_closed or closing_delimiter_past_the_read_window_names_the_window or early_dashes_inside_quoted_value_fail_closed or deeply_nested_yaml_fails_closed_without_traceback or suggested_command_is_shell_safe_and_single_line or overlong_path_component_returns_a_sentinel_not_oserror or test_dash_prefixed_yaml_key_does_not_close_frontmatter'
...................                                                      [100%]
19 passed, 79 deselected in 0.70s
EXIT 0
```

### AM-5 final scoped coverage

```text
$ uv run pytest tests/test_handoff_envelope_maturity.py tests/test_handoff_envelope.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest --cov=plugins/saga/scripts --cov-report=term-missing --cov-report=json:.pytest_cache/lane-a-proofs/coverage.json
........................................................................ [ 46%]
........................................................................ [ 92%]
...........                                                              [100%]
================================ tests coverage ================================
______________ coverage: platform darwin, python 3.12.11-final-0 _______________

Name                                                  Stmts   Miss  Cover   Missing
-----------------------------------------------------------------------------------
plugins/saga/scripts/adjustment_envelope.py             257    257     0%   44-536
plugins/saga/scripts/board_progression.py               280    280     0%   19-860
plugins/saga/scripts/bridge_signatures.py                68     68     0%   4-116
plugins/saga/scripts/capability_elo.py                  146    146     0%   20-270
plugins/saga/scripts/ceremony_hazards.py                 84     84     0%   34-372
plugins/saga/scripts/chaperone_economics.py             258    258     0%   4-562
plugins/saga/scripts/check_engine_registry.py            48     48     0%   4-81
plugins/saga/scripts/closure_gate.py                    120    120     0%   59-306
plugins/saga/scripts/completeness_gate.py               159    159     0%   7-275
plugins/saga/scripts/concurrency_governor.py            168    168     0%   9-343
plugins/saga/scripts/delegation_audit_query.py           26     26     0%   15-76
plugins/saga/scripts/deploy_handoff.py                  244     10    96%   181, 184, 237-238, 417, 420-421, 423, 459, 484
plugins/saga/scripts/detect_deploy_strategy.py           74     74     0%   4-120
plugins/saga/scripts/discover_sessions.py                53     53     0%   26-112
plugins/saga/scripts/discover_subissues.py               53     53     0%   4-168
plugins/saga/scripts/dispatch_settlement.py             951    951     0%   9-2062
plugins/saga/scripts/effort_ledger.py                   127    127     0%   24-259
plugins/saga/scripts/engine_benchmark.py                210    210     0%   16-399
plugins/saga/scripts/engine_bridge_http.py               90     90     0%   23-202
plugins/saga/scripts/engine_calibration.py              160    160     0%   31-347
plugins/saga/scripts/engine_dispatch.py                 886    886     0%   4-2328
plugins/saga/scripts/engine_onboarding.py               277    277     0%   4-472
plugins/saga/scripts/engine_overlay.py                  121    121     0%   4-178
plugins/saga/scripts/engine_promotion.py                112    112     0%   4-206
plugins/saga/scripts/engine_recommend.py                134    134     0%   4-292
plugins/saga/scripts/engine_registry.py                 481    481     0%   4-838
plugins/saga/scripts/engine_registry_cli.py             168    168     0%   4-317
plugins/saga/scripts/engine_registry_conformance.py      89     89     0%   4-182
plugins/saga/scripts/engine_resolver.py                 400    400     0%   4-980
plugins/saga/scripts/engine_stale_report.py             107    107     0%   24-217
plugins/saga/scripts/envelope_token.py                  320    320     0%   64-821
plugins/saga/scripts/evidence_ledger.py                 277    277     0%   43-700
plugins/saga/scripts/execution_spec.py                 1132   1132     0%   39-3096
plugins/saga/scripts/extract_session_skeleton.py        145    145     0%   26-250
plugins/saga/scripts/find_inflight_work.py               27     27     0%   16-63
plugins/saga/scripts/fleet_commons_shim.py               99     99     0%   25-169
plugins/saga/scripts/fleet_doctor.py                    854    854     0%   22-1782
plugins/saga/scripts/gate_divergence_reader.py          102    102     0%   37-234
plugins/saga/scripts/handoff_envelope.py                360     66    82%   333, 362, 364, 370-377, 381-387, 391-410, 414-421, 425-426, 430-432, 536, 538, 556, 604, 618-626, 630-641
plugins/saga/scripts/intent_envelope.py                 131    131     0%   34-256
plugins/saga/scripts/issue_progress.py                   81     81     0%   4-207
plugins/saga/scripts/journal_triggers.py                 15     15     0%   4-24
plugins/saga/scripts/lifecycle_review.py                227    227     0%   44-420
plugins/saga/scripts/lifecycle_state.py                 175    175     0%   4-661
plugins/saga/scripts/lint_gate_absence_contract.py      243    243     0%   46-453
plugins/saga/scripts/liveness_events.py                 502    502     0%   9-1085
plugins/saga/scripts/load_saga_context.py                18     18     0%   18-61
plugins/saga/scripts/manifest_reader.py                 124    124     0%   44-326
plugins/saga/scripts/manifest_store.py                  215    215     0%   38-434
plugins/saga/scripts/merge_watcher.py                   192    192     0%   36-549
plugins/saga/scripts/outcome.py                         985    985     0%   32-2838
plugins/saga/scripts/outcome_board_sync.py               97     97     0%   19-355
plugins/saga/scripts/outcome_compat.py                  521    521     0%   36-1536
plugins/saga/scripts/outcome_costs.py                   118    118     0%   27-259
plugins/saga/scripts/outcome_decompose.py               174    174     0%   32-419
plugins/saga/scripts/outcome_dispatcher.py              227    227     0%   29-769
plugins/saga/scripts/outcome_edges.py                    85     85     0%   14-139
plugins/saga/scripts/outcome_gate_transport.py           63     63     0%   31-187
plugins/saga/scripts/outcome_github.py                  193    193     0%   18-360
plugins/saga/scripts/outcome_intent.py                  229    229     0%   64-690
plugins/saga/scripts/outcome_liveness.py                 97     97     0%   21-223
plugins/saga/scripts/outcome_merge.py                   176    176     0%   54-522
plugins/saga/scripts/outcome_orchestrator.py            126    126     0%   27-362
plugins/saga/scripts/outcome_projection.py               41     41     0%   24-128
plugins/saga/scripts/outcome_reconcile.py               158    158     0%   30-444
plugins/saga/scripts/outcome_report.py                  145    145     0%   26-353
plugins/saga/scripts/outcome_spec.py                    322    322     0%   31-835
plugins/saga/scripts/outcome_store.py                   408    408     0%   38-870
plugins/saga/scripts/outcome_worktrees.py               281    281     0%   37-725
plugins/saga/scripts/override_rate_reader.py            133    133     0%   34-349
plugins/saga/scripts/parse_issue.py                      76     29    62%   36, 61-65, 91-107, 125-127, 131-137
plugins/saga/scripts/plan_artifact_conformance.py        92     92     0%   23-191
plugins/saga/scripts/plan_pre_answers.py                131    131     0%   51-404
plugins/saga/scripts/promote_scan.py                    297    297     0%   37-607
plugins/saga/scripts/provenance_manifest.py             292    292     0%   33-650
plugins/saga/scripts/provider_control_chart.py          106    106     0%   21-206
plugins/saga/scripts/pulse.py                           249    249     0%   35-656
plugins/saga/scripts/qa_health_score.py                  36     36     0%   30-119
plugins/saga/scripts/reconcile.py                       485    485     0%   9-956
plugins/saga/scripts/reconcile_controller.py            183    183     0%   50-631
plugins/saga/scripts/render_docs_visuals.py             201    201     0%   4-458
plugins/saga/scripts/reversibility_certificate.py       117    117     0%   29-540
plugins/saga/scripts/review_consensus.py               1223   1223     0%   83-2728
plugins/saga/scripts/run_ledger.py                      209    209     0%   26-416
plugins/saga/scripts/saga.py                            728    266    63%   52-53, 100, 139, 344-345, 357, 368, 383-384, 390, 409, 435, 440, 444-445, 453, 459, 473, 475-479, 481, 486-487, 502, 523, 543, 567-568, 571, 670, 712-715, 750-772, 811, 813, 838, 840, 842, 855-856, 860-861, 876-878, 919-930, 953-954, 996, 1036-1040, 1045-1048, 1053-1077, 1087-1126, 1142, 1156-1167, 1177-1180, 1185-1188, 1195-1231, 1236-1260, 1276-1302, 1332-1348, 1374-1383, 1392-1414, 1429, 1436, 1491, 1541-1548, 1701-1769, 1773-1836
plugins/saga/scripts/saga_spore.py                      235    235     0%   28-478
plugins/saga/scripts/scaffold_checkpoint.py              37     37     0%   20-104
plugins/saga/scripts/second_opinion.py                 1024   1024     0%   4-2076
plugins/saga/scripts/ship_ceremony.py                   468    468     0%   52-1710
plugins/saga/scripts/ship_receipt.py                    123    123     0%   24-287
plugins/saga/scripts/ship_teardown.py                   468    468     0%   29-999
plugins/saga/scripts/ship_undo.py                       201    201     0%   52-656
plugins/saga/scripts/spec_table.py                      172    172     0%   24-317
plugins/saga/scripts/spend_authority.py                  46     46     0%   19-115
plugins/saga/scripts/spend_estimate.py                  146    146     0%   33-372
plugins/saga/scripts/spend_receipt.py                    78     78     0%   27-173
plugins/saga/scripts/spend_retro.py                     152    152     0%   24-339
plugins/saga/scripts/status_card.py                     427    427     0%   18-960
plugins/saga/scripts/team_emitter.py                    149    149     0%   27-403
plugins/saga/scripts/team_teardown.py                   508    508     0%   22-1455
plugins/saga/scripts/tier_defaults.py                   102    102     0%   14-190
plugins/saga/scripts/tier_efficacy.py                    87     87     0%   19-196
plugins/saga/scripts/tier_session.py                     89     89     0%   12-142
-----------------------------------------------------------------------------------
TOTAL                                                 25106  24069     4%
Coverage JSON written to file .pytest_cache/lane-a-proofs/coverage.json
155 passed in 5.23s
EXIT 0
```

### AM-5 extracted helper coverage acceptance

```text
$ uv run python -c 'import ast
import json
from pathlib import Path

path = "plugins/saga/scripts/handoff_envelope.py"
tree = ast.parse(Path(path).read_text())
report = json.loads(Path(".pytest_cache/lane-a-proofs/coverage.json").read_text())
missing = set(report["files"][path]["missing_lines"])
helpers = set(["_extract_declared_maturity_value","_scanned_maturity_line","_carrier","_recover_utf16","_recover_text","_decode_window","_read_window","_split_frontmatter","_nested_maturity_detail","_has_nested_maturity","_parse_frontmatter","_classify_declared_value","_classify_frontmatter","_read_frontmatter_maturity","carrier_detail","_unterminated_detail","_reanchor_to_marker"])
failures = {}
for function in (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in helpers):
    uncovered = sorted(missing.intersection(range(function.lineno, function.end_lineno + 1)))
    print(f"{function.name}: missing_lines={uncovered}")
    if uncovered:
        failures[function.name] = uncovered
assert not failures, failures
print("AM-5: zero missing lines in every extracted parser and re-anchor helper")
'
_extract_declared_maturity_value: missing_lines=[]
_scanned_maturity_line: missing_lines=[]
_carrier: missing_lines=[]
_recover_utf16: missing_lines=[]
_recover_text: missing_lines=[]
_decode_window: missing_lines=[]
_read_window: missing_lines=[]
_split_frontmatter: missing_lines=[]
_nested_maturity_detail: missing_lines=[]
_has_nested_maturity: missing_lines=[]
_parse_frontmatter: missing_lines=[]
_classify_declared_value: missing_lines=[]
_classify_frontmatter: missing_lines=[]
_read_frontmatter_maturity: missing_lines=[]
carrier_detail: missing_lines=[]
_unterminated_detail: missing_lines=[]
_reanchor_to_marker: missing_lines=[]
AM-5: zero missing lines in every extracted parser and re-anchor helper
EXIT 0
```

### AM-6 final AST counts

```text
$ uv run python -c 'import ast
tree = ast.parse(open("plugins/saga/scripts/handoff_envelope.py").read())
failures = []
for f in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
    returns = sum(isinstance(n, ast.Return) for n in ast.walk(f))
    branches = sum(isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.BoolOp)) for n in ast.walk(f))
    nested = sum(isinstance(n, ast.FunctionDef) for n in ast.walk(f)) - 1
    print(f"{f.name}: returns={returns} branches={branches} nested_defs={nested}")
    if returns > 8 or branches > 12 or nested:
        failures.append(f.name)
assert not failures, failures
print("AM-6: all functions meet the 8-return / 12-branch / zero-nested-def bar")
'
_no_duplicate_keys: returns=1 branches=2 nested_defs=0
_extract_declared_maturity_value: returns=2 branches=1 nested_defs=0
_scanned_maturity_line: returns=2 branches=2 nested_defs=0
_carrier: returns=1 branches=1 nested_defs=0
_recover_utf16: returns=2 branches=4 nested_defs=0
_recover_text: returns=3 branches=5 nested_defs=0
_decode_window: returns=3 branches=2 nested_defs=0
_read_window: returns=2 branches=2 nested_defs=0
_split_frontmatter: returns=3 branches=2 nested_defs=0
_nested_maturity_detail: returns=2 branches=5 nested_defs=0
_has_nested_maturity: returns=1 branches=0 nested_defs=0
_parse_frontmatter: returns=2 branches=1 nested_defs=0
_classify_declared_value: returns=2 branches=2 nested_defs=0
_classify_frontmatter: returns=4 branches=5 nested_defs=0
_read_frontmatter_maturity: returns=5 branches=6 nested_defs=0
carrier_detail: returns=4 branches=4 nested_defs=0
_unterminated_detail: returns=2 branches=2 nested_defs=0
_is_file: returns=2 branches=1 nested_defs=0
_is_within: returns=2 branches=1 nested_defs=0
_reanchor_to_marker: returns=2 branches=2 nested_defs=0
resolve_source: returns=3 branches=6 nested_defs=0
_path_maturity: returns=5 branches=7 nested_defs=0
_resolved_maturity: returns=4 branches=4 nested_defs=0
infer_maturity: returns=1 branches=0 nested_defs=0
infer_lifecycle_phase: returns=6 branches=6 nested_defs=0
read_state: returns=3 branches=2 nested_defs=0
_state_source: returns=2 branches=4 nested_defs=0
_source_candidates: returns=1 branches=9 nested_defs=0
discover_active_source: returns=3 branches=2 nested_defs=0
_git_output: returns=1 branches=0 nested_defs=0
current_git_state: returns=1 branches=0 nested_defs=0
_escape_controls: returns=1 branches=0 nested_defs=0
_display_source: returns=1 branches=0 nested_defs=0
_bounded_maturity: returns=2 branches=1 nested_defs=0
_diagnostic_source: returns=1 branches=1 nested_defs=0
_maturity_remediation: returns=1 branches=0 nested_defs=0
_maturity_diagnostic: returns=8 branches=7 nested_defs=0
_suggested_command: returns=2 branches=3 nested_defs=0
build_handoff_envelope: returns=1 branches=3 nested_defs=0
build_deploy_handoff_envelope: returns=1 branches=1 nested_defs=0
parse_args: returns=1 branches=0 nested_defs=0
main: returns=1 branches=0 nested_defs=0
AM-6: all functions meet the 8-return / 12-branch / zero-nested-def bar
EXIT 0
```

### AM-3 literal planned grep — counts definition plus call

```text
$ grep -c '_reanchor_to_marker(' plugins/saga/scripts/handoff_envelope.py
2
EXIT 0
```

### AM-3 literal containment grep — counts definition plus calls

```text
$ grep -c '_is_within(' plugins/saga/scripts/handoff_envelope.py
3
EXIT 0
```

### AM-3 and TEST-10 AST ownership/signature proof

```text
$ uv run python -c 'import ast
from pathlib import Path
path = Path("plugins/saga/scripts/handoff_envelope.py")
tree = ast.parse(path.read_text())
for symbol, expected in (("_reanchor_to_marker", 1), ("_is_within", 2)):
    owners = {}
    definitions = sum(isinstance(node, ast.FunctionDef) and node.name == symbol for node in tree.body)
    for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)):
        calls = sum(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == symbol for node in ast.walk(function))
        if calls:
            owners[function.name] = calls
    print(f"{symbol}: definitions={definitions}; call_owners={owners}")
    assert owners == {"resolve_source": expected}, owners
test_tree = ast.parse(Path("tests/test_handoff_envelope_maturity.py").read_text())
function = next(node for node in test_tree.body if isinstance(node, ast.FunctionDef) and node.name == "test_reanchored_missing_twin_is_refused")
print(f"{function.name}: parameters={[arg.arg for arg in function.args.args]}")
assert [arg.arg for arg in function.args.args] == ["tmp_path"]
'
_reanchor_to_marker: definitions=1; call_owners={'resolve_source': 1}
_is_within: definitions=1; call_owners={'resolve_source': 2}
test_reanchored_missing_twin_is_refused: parameters=['tmp_path']
EXIT 0
```

### AM-4 stale-branch/comment grep

```text
$ grep -c 'original absolute file is read' plugins/saga/scripts/handoff_envelope.py
0
EXIT 1
```

### AM-5 stale-branch/comment grep

```text
$ grep -c allow_bullet plugins/saga/scripts/handoff_envelope.py
0
EXIT 1
```

### AM-10 stale-branch/comment grep

```text
$ grep -c 'should not occur' plugins/saga/scripts/handoff_envelope.py
0
EXIT 1
```

### API-11 stale-branch/comment grep

```text
$ grep -c 'redundant with suggested_command' plugins/saga/scripts/handoff_envelope.py
0
EXIT 1
```

### TEST-10 stale-branch/comment grep

```text
$ grep -c mkdtemp tests/test_handoff_envelope_maturity.py
0
EXIT 1
```

### CORR-5 final parse_issue original-byte identity

```text
$ cmp -s .pytest_cache/lane-a-proofs/parse_issue.py.pre plugins/saga/scripts/parse_issue.py
EXIT 0
```

### Final required scoped suite — Git metadata stubbed

```text
$ uv run python -c 'import os
import subprocess
import sys
import pytest

real_run = subprocess.run
stubbed_metadata = []
allowed_metadata = {("git", "branch", "--show-current"), ("git", "rev-parse", "--short", "HEAD")}

def metadata_only(argv, *args, **kwargs):
    if isinstance(argv, (list, tuple)) and argv and os.path.basename(str(argv[0])) == "git":
        assert tuple(argv) in allowed_metadata, f"Unexpected prohibited Git request: {argv!r}"
        stubbed_metadata.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 1, "", "")
    return real_run(argv, *args, **kwargs)

def audit(event, args):
    if event == "subprocess.Popen" and os.path.basename(os.fsdecode(args[0])) == "git":
        raise RuntimeError("No-Git dispatch: attempted actual Git execution")

sys.addaudithook(audit)
subprocess.run = metadata_only
try:
    result = pytest.main(sys.argv[1:])
finally:
    print(f"NO-GIT: {len(stubbed_metadata)} metadata requests stubbed; no Git process executed")
sys.exit(result)
' tests/test_handoff_envelope_maturity.py tests/test_handoff_envelope.py tests/test_saga_plugin.py tests/test_saga_saga.py tests/test_saga_docs_coverage.py -o addopts= -q --tb=short --basetemp=.pytest_cache/lane-a-proofs/pytest
........................................................................ [ 23%]
........................................................................ [ 46%]
........................................................................ [ 69%]
........................................................................ [ 92%]
.........................                                                [100%]
313 passed in 2.82s
NO-GIT: 6 metadata requests stubbed; no Git process executed
EXIT 0
```

### Final required Ruff lint

```text
$ uv run ruff check .
All checks passed!
EXIT 0
```

### Final required Ruff format check

```text
$ uv run ruff format --check .
517 files already formatted
EXIT 0
```

### Final required mypy — single process

```text
$ uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
tests/test_unifi_protect_client.py:247: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_unifi_protect_client.py:284: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_unifi_protect_client.py:308: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_unifi_network_client.py:289: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_unifi_network_client.py:328: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_unifi_network_client.py:352: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
tests/test_outcome_command.py:68: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
Success: no issues found in 346 source files
EXIT 0
```

### Custody inventory comparison (no Git)

The following is the actual output of the functions orchestration SHA-256 comparison
against the inventory captured before the first edit. Runtime caches and coverage
files are excluded; every other source path is compared, including deletions.

```json
{
  "baseline_count": 2261,
  "current_count": 2263,
  "changed": [
    "docs/evidence/issue-912/lane-A-evidence.md",
    "docs/evidence/issue-912/lane-A-journal-draft.md",
    "plugins/saga/scripts/handoff_envelope.py",
    "tests/test_handoff_envelope.py",
    "tests/test_handoff_envelope_maturity.py"
  ],
  "unexpected": [],
  "parse_issue_unchanged": true
}
```
