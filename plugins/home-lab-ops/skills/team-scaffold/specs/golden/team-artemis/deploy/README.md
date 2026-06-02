# Deploying Artemis (legacy single agent) independently

Deploys **only this team** from this repo, reusing the home-lab `hermes` role
via the per-team-deploy hooks (`hermes_team_profiles_filter` +
`hermes_souls_source`). It does **not** fork the role.

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
ansible-playbook \
  -i "$HOME/workspace/infiquetra/home-lab/ansible/inventory/hosts.yml" \
  --limit artemis.infiquetra.com \
  artemis.yml \
  --vault-password-file ~/.vault_pass.txt
```
Dry-run first with `--check --diff`. The play prints its profile scope and
asserts the souls source exists before acting.

## Not yet
- Per-team vault split (secrets still from home-lab `group_vars/all`).
- Native distribution install (deferred).
- Team-owned host_vars slice (uses home-lab's today).
