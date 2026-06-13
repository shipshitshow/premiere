# Agent Instructions

This repo is an Adobe Premiere MCP editor workspace. The active product is
`apps/premiere`.

## Read First

1. `README.md`
2. `.agents/memory/premiere-workflow.md`
3. `apps/premiere/skills/premiere-mcp-ops/SKILL.md`

## Active Paths

- `apps/premiere/adobe-mcp/` - Adobe MCP server, proxy, and UXP plugin workspace.
- `apps/premiere/scripts/` - ExtendScripts executed in Premiere.
- `apps/premiere/skills/` - Repo-local workflow skills.

## Workflow Rules

- The live Premiere Pro timeline is the source of truth.
- Prefer `remove_silence_segments` for transcript-based removal ranges.
- Verify real sequence changes after every cut batch.
- Stop on uncertain focus, wrong sequence, failed verification, or unsafe fallback.
- Do not create alternate sequences, rendered assemblies, or proxy edits unless
  the user explicitly asks for them.

## Checks

```bash
bun run premiere:check
bun run format:check
```
