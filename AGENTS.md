# Agent Instructions

This repo is an Adobe Premiere MCP editor workspace. The active product is
`apps/premiere`.

## Read First

1. `README.md`
2. `.agents/memory/premiere-workflow.md`
3. `apps/premiere/skills/premiere-mcp-ops/SKILL.md`

## Active Paths

- `apps/premiere/adobe-mcp/` - Adobe MCP server, proxy, and UXP plugin workspace.
- `apps/premiere/scripts/legacy-extendscript/` - Quarantined legacy `.jsx`, not
  wired into anything. Use the MCP tools instead.
- `apps/premiere/skills/` - Repo-local workflow skills.

## Workflow Rules

- The live Premiere Pro timeline is the source of truth.
- Use `remove_silence_segments` for transcript-based removal ranges. It cuts with
  Premiere's Extract (ripple-delete), which normally closes the gap in the same
  A/V-synced op, then verifies the layout and returns a `verified` flag.
- Verify real sequence changes after every cut batch. Treat `verified: false` or
  `verified: null` as NOT confirmed — re-inspect with `verify_sequence_layout`.
- If Premiere/UXP returns no frame ticks and Extract leaves only tiny native
  gaps, use the documented native Close Gap recovery (`W`) one pass at a time,
  verifying after every pass. Keep the cut only when packed and A/V sync both
  verify clean; otherwise undo to the previous clean baseline and stop.
- Stop on uncertain focus, wrong sequence, failed verification, or unsafe fallback.
- Do not create alternate sequences, rendered assemblies, or proxy edits unless
  the user explicitly asks for them.

## Checks

```bash
bun run premiere:check
bun run format:check
```
