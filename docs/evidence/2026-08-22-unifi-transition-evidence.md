# UniFi transition evidence, and the release that is not yet activated

Unit U9 of the UniFi and portable Fleet Core portability pilot, Run B, in
`infiquetra-claude-plugins`.

## Activation addendum, 2026-08-22

**Added after the fact, and additive only.** Nothing below this section was edited. Every
finding, count, digest, and conclusion in the original document stands exactly as U9 wrote
it, including the sections that report the release as not activated — those were true when
written and are the record of the state this evidence was taken in.

What changed afterwards is the second gate condition. The deployed-profile receipt arrived,
naming the runtime path and a deployed SHA-256 digest of
`7b42dc2220707f47f41c1d9fd66c6949c3b99c4526cb90898cb0c8422882cb2a`. That equals the private
input digest recorded below, so the test this document set for itself — "if that digest
equals ..., the pre-activation evidence above was taken against exactly the bytes Run C
deployed ... and activation may proceed" — is met on its own terms rather than waived. The
release was then activated as version `2.0.0`, dated 2026-08-22, across all three surfaces.

The post-activation requirement is **not** discharged by that activation. Of the four items
the original document lists as outstanding, two are now provable from the released bytes and
two are not:

| Outstanding item | Status | Why |
| --- | --- | --- |
| Tri-lock parity across the three release surfaces | Proved from the released bytes | `scripts/check_release_surface_parity.py`, run against the activation commit |
| Generated marketplace file matches its generator | Proved from the released bytes | `scripts/sync_marketplace.py --check` |
| Installed version and digest readback | **Still outstanding** | Requires a marketplace refresh and a fresh client session, which this repository cannot perform on its own bytes |
| Three profile states re-proved against the installed release | **Still outstanding** | Same reason, and the original document is right that a running client can hold a cached earlier version |

The two outstanding items remain the controller's to run after
`/plugin marketplace update` and a new session. A source tree cannot settle what an installed
client is holding, which is the point the original document already made and which activation
does not change.

## What this document is for

Units U6 and U7 corrected the `unifi` plugin's documentation and moved one operator's lab
topology out of the `unifi-network-ops` agent definition into a site profile the agent
reads at runtime. Both were authored and deliberately left unreleased. Releasing them
removes site knowledge the installed agent currently carries in its own text, so the
plugin's own rule applies: a component being deployed is not the same as a behavior being
verified end to end. This unit proves the replacement context path works **before**
anything is switched on.

The evidence is the deliverable. The release is merely what the evidence unlocks.

## Release activation status: NOT ACTIVATED

The three release surfaces are byte-unchanged by this unit:

- `plugins/unifi/.claude-plugin/plugin.json` — version `1.2.1`
- the `unifi` entry in `.claude-plugin/marketplace.json` — version `1.2.1`
- `plugins/unifi/CHANGELOG.md` — top dated heading `[1.2.1] - 2026-08-08`, with the U6 and
  U7 work still under `[Unreleased]`

Activation requires two conditions. One is met; one is not.

| Condition | Status | Basis |
| --- | --- | --- |
| This unit's own safety evidence passes | Met | 50 fields compared, 50 passed, 0 failed, recorded below |
| Run C's deployed-profile receipt supplied, naming the runtime path and the deployed digest | **Not met** | No receipt was released to this run |

The second condition is not a formality. The run topology joins three repositories by
named receipts rather than by ambient access, precisely so that one run cannot conclude
another run finished by looking around for traces of it. Run C's site-profile work exists
on unmerged branches in the `home-lab` repository and has not landed on that repository's
default branch, so Run C has not released its receipt. A deployed profile is also readable
on this machine, but reaching for it directly is the ambient access the topology rule
forbids, and it is the same shortcut that already produced one silent failure in this
pilot: Run C's own follow-up commit records that its first attempt reported success while
the runtime path resolved to no profile at all. A receipt is how that class of error gets
caught. Discovering the file independently reproduces the mistake the repair was written
for.

So the release is not activated, and the capability gap is not closed by an unproven
premise.

## Method

The pre-activation load is taken from the **staged path** — this worktree's corrected
bytes — rather than from the installed release, because the installed release cannot
demonstrate the replacement path at all.

```
plugins/unifi/skills/unifi-network/scripts/site_profile_loader.py
```

| Property | Value |
| --- | --- |
| Staged tree revision | `010372d16078e7c5462a11b199f822ca0111a188` |
| Staged loader digest, SHA-256 | `f074306bc88c239c1c82681231a4372c0737fdc50d86857277085084d90a5312` |
| Installed release version | `1.2.1` |
| Loader present in the installed release | no |

That last row is the gap stated plainly. Version 1.2.1 predates U7, so the installed agent
still carries the topology in its own prose and carries no loader at all. Nothing about the
replacement path can be observed from the installed bytes, which is why the staged load is
the only pre-activation proof available and why a post-activation readback in a fresh
client session is separately required.

The comparison basis for the first state is the set of facts the pre-relocation agent
definition embedded, taken from the parity test that already carries them
(`tests/test_unifi_site_profile_loader.py`, `PRIOR_AGENT_FACTS`) so this comparison cannot
drift from the assertion the repository enforces.

### Wording differs from fact, and the difference is recorded

That parity test carries two forms for every prior agent fact: the literal string this
repository's own relocation record uses, and a regular expression that discriminates the
fact wherever it is written. The deployed profile is a separate, independent authoring of
the same site, so a fact can be present in different words. Three facts matched on the
regular expression rather than the literal:

- the agent virtual machine range, written as a span rather than a hyphenated pair
- the service virtual machine range, the same difference
- the camera recorder, written as the abbreviation rather than the expanded phrase

Each is the same fact in different words, and each row below records which form matched
rather than reporting a bare pass. No fact was absent.

## Pre-activation evidence


#### State: profile deployed

Expectation: site context equivalent to what the agent previously embedded, compared fact by fact.

Fields compared: 31. Passed: 31. Failed: 0.

| Compared field | Result | Matched form |
| --- | --- | --- |
| controller address | pass | literal |
| controller model | pass | literal |
| controller operating system | pass | literal |
| main LAN subnet | pass | literal |
| main LAN vlan | pass | literal |
| main LAN trust | pass | literal |
| management subnet | pass | literal |
| management vlan | pass | literal |
| management role | pass | literal |
| iot subnet | pass | literal |
| iot vlan | pass | literal |
| iot isolation | pass | literal |
| guest subnet | pass | literal |
| guest vlan | pass | literal |
| guest internet-only | pass | literal |
| proxmox master address | pass | literal |
| proxmox master hostname | pass | literal |
| agent virtual machine range | pass | equivalent-phrasing |
| service virtual machine range | pass | equivalent-phrasing |
| camera count | pass | literal |
| camera series | pass | literal |
| camera recorder | pass | equivalent-phrasing |
| wireless standard | pass | literal |
| deployed profile validates against the contract | pass | not applicable |
| resolution mode | pass | not applicable |
| resolution source | pass | not applicable |
| contract schema version | pass | not applicable |
| site identifier present | pass | not applicable |
| named subjects non-empty | pass | not applicable |
| intended policies non-empty | pass | not applicable |
| operational constraints non-empty | pass | not applicable |


#### State: profile absent

Expectation: explicit unknowns reported, no intent inferred.

Fields compared: 13. Passed: 13. Failed: 0.

| Compared field | Result | Matched form |
| --- | --- | --- |
| resolution mode | pass | not applicable |
| profile path reported absent | pass | not applicable |
| named subjects empty | pass | not applicable |
| discovery-only limits stated | pass | not applicable |
| intent field reported unknown: trust_role | pass | not applicable |
| intent field reported unknown: criticality | pass | not applicable |
| intent field reported unknown: ownership | pass | not applicable |
| intent field reported unknown: intended_policies | pass | not applicable |
| query returns the explicit unknown: trust_role | pass | not applicable |
| query returns the explicit unknown: criticality | pass | not applicable |
| query returns the explicit unknown: ownership | pass | not applicable |
| query returns the explicit unknown: intended_policies | pass | not applicable |
| operational constraints unknown | pass | not applicable |


#### State: profile present but unreadable

Expectation: loud failure, never a silent fall back to no-profile mode.

Fields compared: 6. Passed: 6. Failed: 0.

| Compared field | Result | Matched form |
| --- | --- | --- |
| unreadable profile raises rather than falls back | pass | not applicable |
| raised error names the unreadable condition | pass | not applicable |
| unparseable profile raises rather than falls back | pass | not applicable |
| unparseable error names the unreadable condition | pass | not applicable |
| configured path that no longer exists is reported | pass | not applicable |
| missing-path error names the not-found condition | pass | not applicable |

## Public evidence record

The record follows the public evidence schema: compared field names, comparison counts,
per-field pass or fail, a digest of the private input and a digest of the result, and
commands whose site-identifying arguments are redacted. It carries no address, no
hostname, no hardware address, and no camera name. The schema itself and its validating
test are Run A's to land in `infiquetra-agent-plugins`, at `schemas/public-evidence.schema.json`
and `tests/test_public_evidence_schema.py`; this repository does not carry a second copy,
because a schema with two writable sources is not a contract.

```json
{
  "commands": [
    "python3 <staged>/skills/unifi-network/scripts/site_profile_loader.py --summary",
    "python3 <staged>/skills/unifi-network/scripts/site_profile_loader.py --config-path <redacted>"
  ],
  "compared_field_count": 50,
  "failed": 0,
  "loaded_from": "staged path",
  "passed": 50,
  "private_input_digest": "7b42dc2220707f47f41c1d9fd66c6949c3b99c4526cb90898cb0c8422882cb2a",
  "result_digest": "6f46ac1bc3a19a5912c34ffaea0c7124dd0e5b015776059821efc9679ebfa783",
  "sanitization": {
    "categories_asserted": [
      "address",
      "cidr",
      "hardware address",
      "hostname",
      "subject identifier",
      "site identifier"
    ],
    "violations": 0
  },
  "stage": "pre-activation",
  "states": [
    {
      "compared_field_count": 31,
      "expectation": "site context equivalent to what the agent previously embedded, compared fact by fact",
      "failed": 0,
      "passed": 31,
      "state": "profile deployed"
    },
    {
      "compared_field_count": 13,
      "expectation": "explicit unknowns reported, no intent inferred",
      "failed": 0,
      "passed": 13,
      "state": "profile absent"
    },
    {
      "compared_field_count": 6,
      "expectation": "loud failure, never a silent fall back to no-profile mode",
      "failed": 0,
      "passed": 6,
      "state": "profile present but unreadable"
    }
  ]
}
```

### Sanitization

Four categories are asserted by pattern search against the rendered record, plus the
deployed profile's own site and subject identifiers: address, network prefix, hardware
address, hostname, subject identifier, site identifier. Violations found: 0.

Words the repository's own public parity vocabulary already uses for network tiers are
excluded from the identifier check. They name a tier every site has, not this one.

### The private receipt

The private input is the deployed site profile. It stays outside this repository and is
referenced only by digest.

| Item | Value |
| --- | --- |
| Private input digest, SHA-256 | `7b42dc2220707f47f41c1d9fd66c6949c3b99c4526cb90898cb0c8422882cb2a` |
| Result digest, SHA-256 | `6f46ac1bc3a19a5912c34ffaea0c7124dd0e5b015776059821efc9679ebfa783` |

The result digest is computed over the record's own content with the digest field excluded,
because a digest is never computed over bytes that contain it.

## Post-activation evidence: NOT PERFORMED

Required and outstanding, in a **fresh** client session, because a running client can hold
a cached earlier version and source-tree evidence cannot settle the question:

1. Installed version and digest readback matching the released bytes.
2. All three profile states re-proved against the installed release.
3. The tri-lock parity gate passing, with the plugin manifest version, the marketplace
   entry version, and the changelog's top dated heading equal.
4. The generated marketplace file matching its generator's output.

None of these can run before activation, and activation is blocked on the missing receipt.

## Rollback, defined before it is needed

- **Trigger** — any post-activation fresh-session failure of the three profile states, or a
  tri-lock or readback mismatch.
- **Reachable prior version** — `1.2.1`, released 2026-08-08, the version currently
  installed.
- **Action** — release the prior version by the same coordinated three-surface bump,
  refresh the marketplace, and repeat the fresh-session proof against the restored version.

A rollback that is not re-proved has not been verified.

## Reproducing the pre-activation evidence

Run from a checkout of this branch, on a machine where the operator profile is deployed.
No network call, no credential read, and no controller contact is made at any point.

```
# State 1 - profile deployed
python3 plugins/unifi/skills/unifi-network/scripts/site_profile_loader.py --summary

# State 2 - profile absent
env -u UNIFI_SITE_PROFILE XDG_CONFIG_HOME="$(mktemp -d)" \
  python3 plugins/unifi/skills/unifi-network/scripts/site_profile_loader.py --summary

# State 3 - profile present but unreadable
#   point a configuration file at an unreadable, an unparseable, and a missing profile in
#   turn, and confirm each raises rather than returning discovery-only mode
python3 plugins/unifi/skills/unifi-network/scripts/site_profile_loader.py \
  --config-path <redacted>
```

The fact-by-fact comparison harness is a working file rather than a repository artifact:
it reads a machine-local deployed profile that continuous integration does not have, so it
cannot become a repository test. The repository's own loader tests cover the same three
states against fixtures.

## What the controller needs to carry

Run C's deployed-profile receipt, naming:

- the runtime path the profile is deployed to, and
- the deployed profile's SHA-256 digest.

If that digest equals `7b42dc2220707f47f41c1d9fd66c6949c3b99c4526cb90898cb0c8422882cb2a`,
the pre-activation evidence above was taken against exactly the bytes Run C deployed, the
first gate condition is already satisfied against the right input, and activation may
proceed. If it differs, the evidence above must be re-taken against the deployed bytes
before activation.
