"""Render a team's deploy harness (deploy/{<team>.yml,requirements.yml,README.md}).

Promoted verbatim from the one-off migration generator
(home-lab `/tmp/journal-partition/gen_harness.py`, 2026-05-31). The template
strings below are byte-identical to that generator's output — proven by the
golden test, which reproduces all 12 live team repos exactly. Do NOT reflow or
"clean up" these templates: any whitespace change breaks byte parity. In
particular keep `requirements.yml`'s ``src`` pointing at
``git+https://github.com/namredips/home-lab.git`` (personal account, not
``infiquetra``) — parity depends on it.

The only change from the migration script is the data source: instead of a
hardcoded ``TEAMS`` dict it takes a spec ``cfg`` dict (see ``spec.py``), so new
teams render from a ``team-spec.yaml`` rather than a code edit.
"""
from __future__ import annotations

REQUIREMENTS = """---
# Reuse the home-lab roles (native distribution packaging deferred; this Ansible
# path is the supported independent-deploy mechanism). See deploy/README.md for
# the roles-path setup (local checkout recommended).
roles:
  - name: hermes
    src: git+https://github.com/namredips/home-lab.git
    version: main
"""


def render_play(name: str, cfg: dict) -> str:
    """Render deploy/<team>.yml. ``name`` is the play filename (e.g. themis.yml)."""
    coresident = cfg.get("coresident")
    coresident_note = (
        f" Co-resident team on this host ({coresident}) is NOT in the filter "
        f"and is left untouched." if coresident else
        " Only this team's profiles are touched.")
    pin = ("    hermes_update: false  # runtime pinned (shared host)\n" if cfg["pin"] else "")
    roles = "\n".join(
        f"    - {{ role: {r}, tags: ['{t}'] }}" for r, t in cfg["roles"])
    return f"""---
# Deploy the {cfg['team']} — and ONLY this team — from this repo.
#
# Reuses the home-lab hermes role via the per-team-deploy hooks (2026-05-31):
#   hermes_team_profiles_filter : narrows the host's profiles to this team's
#     (derived from this repo's profiles/ dir) so co-resident teams are untouched.
#   hermes_souls_source         : SOULs sourced from this repo's profiles/<n>/SOUL.md.
#
# Usage (see deploy/README.md):
#   cd deploy && ansible-playbook -i <home-lab-inventory> \\
#     --limit {cfg['limit']} {name} --vault-password-file ~/.vault_pass.txt
#
# Native distribution packaging (`hermes profile install`) is DEFERRED.

- name: Deploy {cfg['team']} (profile-scoped)
  hosts: {cfg['hosts']}
  gather_facts: true
  vars:
    # realpath normalizes the .. so the control-node find() gets an absolute dir.
    # NOTE: ansible's fileglob lookup does NOT expand '..' — use find() instead.
    _team_repo_root: "{{{{ (playbook_dir + '/..') | realpath }}}}"
    hermes_souls_source: "{{{{ _team_repo_root }}}}/profiles"
    # profile-dir layout = source each SOUL from <repo>/profiles/<name>/SOUL.md
    # (the team repo is authoritative). Without this the role's SOUL tasks fall
    # back to home-lab's bundled files/souls/ (macOS ignored the source entirely).
    hermes_souls_layout: profile-dir
    # home-lab checkout (for the SHARED-INFRA vault: github-app PEMs, langfuse,
    # elevenlabs). Override -e homelab_root=/path if your checkout differs.
    homelab_root: "{{{{ lookup('ansible.builtin.env', 'HOME') }}}}/workspace/infiquetra/home-lab"
{pin}  vars_files:
    # This team's OWN secrets (post vault-split): Discord tokens etc.
    - "{{{{ _team_repo_root }}}}/ansible/inventory/group_vars/all/vault.yml"
    # Shared-infra secrets that live in home-lab (PEMs / langfuse / elevenlabs).
    - "{{{{ homelab_root }}}}/ansible/inventory/group_vars/all/vault_shared_infra.yml"
    # This team's hermes_team_profiles (Phase 8 Stage A — relocated FROM home-lab
    # host_vars so the harness is self-contained and home-lab can drop per-team
    # content). A play var, so it overrides any home-lab host_var of the same name
    # while that dual-write window lasts, and is the sole source after deletion.
    - "{{{{ _team_repo_root }}}}/deploy/team_profiles.yml"
  pre_tasks:
    - name: Enumerate this repo's profile dirs on the control node
      ansible.builtin.find:
        paths: "{{{{ _team_repo_root }}}}/profiles"
        file_type: directory
        recurse: false
      delegate_to: localhost
      run_once: true
      register: _team_profile_dirs

    - name: Derive the per-team filter from the profile dirs
      ansible.builtin.set_fact:
        hermes_team_profiles_filter: >-
          {{{{ _team_profile_dirs.files | map(attribute='path') | map('basename') | list | sort }}}}

    # HARD GATE: an empty filter would make the hermes role deploy ALL of the
    # host's profiles (incl. co-resident teams). Refuse, loudly, before any role runs.
    - name: Refuse to proceed on an empty filter (would deploy co-resident teams)
      ansible.builtin.assert:
        that:
          - hermes_team_profiles_filter | length > 0
        fail_msg: >-
          Derived an EMPTY profile filter from {{{{ _team_repo_root }}}}/profiles —
          refusing to deploy (an empty filter makes the hermes role deploy the
          host's entire profile set, including co-resident teams). Check the
          repo layout / playbook_dir.

    - name: Show profile-scope (and what it won't touch)
      ansible.builtin.debug:
        msg: >-
          Deploying {{{{ hermes_team_profiles_filter | length }}}} profiles
          ({{{{ hermes_team_profiles_filter | join(', ') }}}}).{coresident_note}
  roles:
{roles}
"""


README_TMPL = """# Deploying {team} independently

Deploys **only this team** from this repo, reusing the home-lab `hermes` role
via the per-team-deploy hooks (`hermes_team_profiles_filter` +
`hermes_souls_source`). It does **not** fork the role.{coresident_line}

> Native Hermes profile-distribution packaging is deferred; this Ansible path is
> the supported independent-deploy mechanism.

## Prereqs
1. Home-lab roles on the roles-path:
   ```bash
   export ANSIBLE_ROLES_PATH="$HOME/workspace/infiquetra/home-lab/ansible/roles"
   ```
   (or `ansible-galaxy install -r deploy/requirements.yml -p deploy/roles`)
2. Inventory + secrets from home-lab until the per-team vault split lands.
3. Vault password at `~/.vault_pass.txt`.

## Deploy
```bash
cd deploy
ansible-playbook \\
  -i "$HOME/workspace/infiquetra/home-lab/ansible/inventory/hosts.yml" \\
  --limit {limit} \\
  {play} \\
  --vault-password-file ~/.vault_pass.txt
```
Dry-run first with `--check --diff`. The play prints its profile scope and
asserts the souls source exists before acting.

## Not yet
- Per-team vault split (secrets still from home-lab `group_vars/all`).
- Native distribution install (deferred).
- Team-owned host_vars slice (uses home-lab's today).
"""


def render_readme(cfg: dict) -> str:
    coresident_line = (
        f"\n\n**Note:** this team shares its host with {cfg['coresident']}; "
        f"the filter ensures {cfg['coresident']} is never touched by this deploy."
        if cfg.get("coresident") else "")
    return README_TMPL.format(
        team=cfg["team"], limit=cfg["limit"], play=cfg["play"],
        coresident_line=coresident_line)


def render_harness(cfg: dict) -> dict[str, str]:
    """Return {filename: content} for the 3 generated deploy/ files."""
    return {
        cfg["play"]: render_play(cfg["play"], cfg),
        "requirements.yml": REQUIREMENTS,
        "README.md": render_readme(cfg),
    }
