# Live herdr evidence, captured 2026-09-19 from the operator's running herdr server (client 0.9.0)

This session runs inside herdr (HERDR_ENV=1, pane w7C:p2P). Agent list at capture time, one row per live agent pane:

| Workspace | Agent kind | Status | Pane title |
|---|---|---|---|
| w70 | claude | idle | L7 Web App architecture contracts |
| w70 | claude | idle | L7 Web App Lead recovery handoff |
| w70 | claude | idle | L7 Web App plan review |
| w70 | claude | idle | L7 Web App product scope document |
| w70 | codex | idle | campps-web-app | main | gpt-5.6-sol |
| w70 | opencode | idle | OC | L7 Web App Issue Readiness Review |
| w7C | claude | working | Claude Code |
| w7C | claude | working | Typesafe-ai skill validation |
| w7C | codex | idle | team-mimir | main | gpt-6-astra |
| w7C | codex | working | home-lab | main | gpt-5.6-luna |
| w7W | cursor | idle | Project Lead Takeover |
| w81 | codex | idle | campps-web-app | l7-activity-leader-roster | gpt-5.6-luna |
| w81 | codex | idle | campps-web-app | l7-activity-leader-roster | gpt-5.6-luna |
| w81 | cursor | idle | L7 Test Author |
| w81 | cursor | idle | L7 Test Author |
| w81 | cursor | idle | L7 Test Author |
| w81 | grok | idle | L7 U2 WCAG remediations and routeless si… - grok |
| w81 | muse | idle | campps-web-app |
| w81 | muse | idle | campps-web-app |
| w82 | agy | idle | campps-web-app |
| w82 | claude | idle | Claude Code |
| w82 | codex | idle | campps-web-app | l7-activity-leader-roster | gpt-5.6-luna |
| w82 | codex | idle | campps-web-app | l7-activity-leader-roster | gpt-5.6-luna |
| w82 | muse | idle | Target 53 review verdict |
| w82 | opencode | idle | OpenCode |
| w87 | grok | idle | Complete issue 908 with saga, reviews, t… - grok |

Kinds in use:
- agy: 1
- claude: 7
- codex: 7
- cursor: 4
- grok: 2
- muse: 3
- opencode: 2

Named agents (herdr agent names follow the pane occupant): team-mimir-update, add-jev, lead, lead-glm, web-app-planner, i-rev, dev-1, dev-2, developer-five, test-author-one, test-author-two, test-author-three, expert, investigator, release-worker, functional-tester

Socket API capabilities (herdr docs v0.9.1, socket-api.mdx): create/list/focus/close workspaces, tabs, panes; start/prompt/wait-on/read agents; report custom agent state from hooks and plugins; subscribe to events (pane.agent_status_changed, pane.output_matched, worktree.created/opened/removed, workspace.*); install integrations. Plugins (plugins.mdx): TOML manifest with [[actions]], [[events]] (on = "worktree.created", command = [...]), startup hooks, panes, link handlers. Agent state (agents.mdx): Claude Code and Codex integrations are lifecycle-hook authorities for idle/working/blocked; 'herdr integration install claude'.
