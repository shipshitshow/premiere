# Premiere App

Adobe Premiere Pro editing through MCP and a Premiere UXP plugin. This is the
only app in the repo.

## Paths

- `adobe-mcp/` — MCP server, Socket.IO proxy, UXP plugin
- `scripts/legacy-extendscript/` — quarantined `.jsx`, not wired in
- `skills/` — transcript planning + live MCP ops

## Commands

From the repo root:

```bash
bun run premiere:proxy     # Socket.IO proxy
bun run premiere:status    # proxy + plugin connection
bun run premiere:check     # Python compile
bun run premiere:lint      # ruff
bun run premiere:test      # plan/layout/verify unit tests
```

## Workflow

See `apps/premiere/skills/premiere-mcp-ops/SKILL.md` (canonical cut contract)
and the root `README.md` (setup).
