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
bun run premiere:check
bun run format:check
```

For Python syntax across the active MCP workspace:

```bash
python3 -m compileall -q apps/premiere/adobe-mcp/adobe_mcp
```

## Premiere Workflow Safety

- The live Premiere sequence is the source of truth.
- Use `remove_silence_segments` for transcript-based removal ranges. It extracts
  (ripple-deletes) each range so the gap closes in the same A/V-synced op, then
  verifies the layout.
- Verify timeline changes after each cut batch; treat a `verified: false`/`null`
  result as not confirmed.
- Stop if the active sequence, Premiere focus, proxy state, or UXP connection is
  uncertain.
- Do not create rendered replacements, proxy edits, or alternate sequences unless
  the user explicitly asks for that.

## Git

- Keep commits scoped to one workflow change.
- Do not commit local media, proxy logs, process ids, virtual environments, or
  generated cache files.
- Use GitHub issues for larger work. Do not create local `.agents/TASKS` or
  `.agents/PRDS` entries.
