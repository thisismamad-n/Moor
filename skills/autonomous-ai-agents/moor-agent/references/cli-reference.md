# Moor CLI Reference

Live sources when anything looks stale: `moor --help`, `moor <command> --help`,
https://hermes-agent.nousresearch.com/docs/reference/cli-commands

### Global Flags

```
moor [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
moor chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
moor setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
moor model                Interactive model/provider picker
moor fallback [add|remove|list]  Fallback provider chain
moor config [show|edit|get|set|unset|path|env-path|check|migrate]
moor login / logout       OAuth sign-in / clear stored auth
moor doctor [--fix]       Check dependencies and config
moor status [--all]       Component status
```

### Tools & Skills

```
moor tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

moor skills list|browse|search QUERY|inspect ID
moor skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
moor skills config        Enable/disable skills per platform
moor skills check|update|uninstall|publish PATH
moor skills tap add REPO  Add a GitHub repo as a skill source
moor bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
moor mcp add NAME (--url or --command) | remove | list | test NAME
moor mcp catalog | install NAME     Curated catalog install
moor mcp configure NAME             Toggle tool selection
moor mcp serve                      Run Moor as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
moor gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `moor photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
moor sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
moor cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
moor webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
moor profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
moor profile rename A B | alias NAME | export NAME | import FILE
```

### Credentials & Pools

```
moor auth                 Interactive credential manager
moor auth add [PROVIDER]  Add OAuth or API-key credential (moor, openai-codex, qwen-oauth, …)
moor auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
moor desktop / gui        Native desktop app
moor dashboard            Web admin panel + embedded chat (--stop / --status)
moor proxy                OpenAI-compatible local proxy backed by an OAuth provider
moor portal               Quick setup / sign in via Moor Portal
moor kanban <verb>        Multi-agent work-queue board
moor project              Named multi-folder workspaces
moor skin list|use|set    Switch/tweak skins (see references/themes.md)
moor pets <verb>          Pet mascots (see references/petdex.md)
moor memory setup|status|off|reset   Memory provider
moor secrets bitwarden|onepassword   External secret stores
moor moa                  Mixture-of-Agents slots
moor hooks / security / backup / import / checkpoints / console
moor logs [-f] [errors]   View agent/error logs
moor send                 One-off message through a gateway platform
moor pairing / plugins / insights / journey / computer-use
moor acp                  ACP server (IDE integration)
moor completion bash|zsh|fish
moor update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `moor photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `moor config edit` · [Configuration docs](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) |
| Tools / toolsets | `moor tools list` · [Tools reference](https://hermes-agent.nousresearch.com/docs/reference/tools-reference) |
| Skills catalog | `moor skills browse` · [Skills catalog](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `moor model` · [Providers guide](https://hermes-agent.nousresearch.com/docs/integrations/providers) |
| Env variables | `moor config env-path` · [Env vars reference](https://hermes-agent.nousresearch.com/docs/reference/environment-variables) |
| Gateway logs | `~/.moor/logs/gateway.log` (or `moor logs`) |
| Sessions | `moor sessions browse` (reads state.db) |
