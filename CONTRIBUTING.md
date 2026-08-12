# Contributing

This repo is an Adobe Premiere MCP editor workspace. Contributions should improve
the Premiere Pro MCP workflow under `apps/premiere`.

## Active Scope

Work here by default:

- `apps/premiere/adobe-mcp/`
- `apps/premiere/scripts/legacy-extendscript/` (quarantined `.jsx`, reference only)
- `apps/premiere/skills/`
- `.agents/`

## Development Checks

From the repo root:

```bash
bun run premiere:check     # Python compile check
bun run premiere:lint      # ruff (policy in pyproject.toml, enforced in CI)
bun run premiere:test      # plan/layout/verify unit tests
bun run format:check       # biome formatting (enforced in CI)
```

## Premiere Workflow Safety

Follow `apps/premiere/skills/premiere-mcp-ops/SKILL.md`. Short version: live
sequence is the source of truth; dry-run then Extract; treat `verified: false`
/`null` as not confirmed; do not invent fallback sequences or unsafe split/trim
APIs.

## Git

- Keep commits scoped to one workflow change.
- Do not commit local media, proxy logs, process ids, virtual environments, or
  generated cache files.
- Use GitHub issues for larger work. Do not create local `.agents/TASKS` or
  `.agents/PRDS` entries.
