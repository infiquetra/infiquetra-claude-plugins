# home-lab-ops

Claude Code plugin for managing the **olympus** Proxmox VE 9.1.1 cluster — a 6-node homelab running Ceph distributed storage, 8 OpenClaw AI agent VMs, and 4 service VMs, all automated with Ansible.

## Why This Plugin

The home-lab commit history shows a ~1:1 fix:feat ratio — half of all commits were fixing something that just got deployed. This plugin encodes the tribal knowledge that prevents that cycle:

- **Undocumented Proxmox/Ceph CLI behaviors** extracted from fix commits
- **Cascade update checklists** for hardware changes (prevents missing 1 of 8+ files)
- **Common mistakes catalog** from the actual fix history
- **Metric name registry** to prevent silent dashboard breakage
- **Vault workflows** to collapse 5 commits into 1

## Skills

| Skill | Trigger | Impact |
|-------|---------|--------|
| `ansible-preflight` | Before committing Ansible changes | Catches errors before they become fix commits |
| `proxmox-operations` | Any pvecm, qm, ceph, pveceph command | Correct PVE 9.x CLI syntax, no trial-and-error |
| `inventory-sync` | Hardware adds/removes/IP changes | Full checklist of every file that needs updating |
| `monitoring-guard` | Exporter updates, dashboard edits | Prevents silent metric/dashboard breakage |
| `vault-helper` | Adding/rotating secrets | Streamlines multi-commit vault workflows |

## Agent

**`homelab-sre`** — Cross-cutting SRE agent for cluster triage, change planning, and OpenClaw agent debugging. Combines knowledge from all 5 skills.

Invoke for:
- "My cluster is having issues"
- "I want to add/remove a node"
- "OpenClaw agents are crash-looping"
- "What's the safest way to..."
- "Plan upgrading Proxmox/Ceph"

## Cluster Reference

- **Proxmox nodes**: r420 (master, .7), r640-1 (.8), r640-2 (.9), r720xd (.10), r820 (.11), r640-3 (.12)
- **Ceph**: ceph-fast (SSD, R640s) + ceph-bulk (HDD, r420/r720xd/r820)
- **Agent VMs**: Zeus–Ares (VMIDs 100–107, IPs 10.220.1.50–57)
- **Service VMs**: RustDesk, Dell OME, PBS, Monitoring (VMIDs 200–203, IPs .60–.63)
- **Repo**: `namredips/home-lab` at `/Users/jefcox/workspace/infiquetra/home-lab`
