# Agent Instructions

This repo contains the Adobe Premiere editor workspace and computer-use editing
skills. The active product is `apps/premiere`.

## Read First

1. `README.md`
2. `.agents/memory/MEMORY.md`
3. `apps/premiere/skills/premiere-weekly-edit/SKILL.md`
4. `apps/premiere/skills/premiere-shorts-delivery/SKILL.md` for shorts

## Active Paths

- `apps/premiere/adobe-mcp/` - Adobe MCP server, proxy, and UXP plugin workspace.
- `apps/premiere/scripts/legacy-extendscript/` - Quarantined legacy `.jsx`, not
  wired into anything. Do not use them for native editing.
- `apps/premiere/skills/` - Repo-local workflow skills.

## Workflow Rules

- Default editing route: **computer use in installed Premiere**, per Vincent's
  2026-09-09 instruction. Read `premiere-weekly-edit`, then
  `premiere-shorts-delivery` for shorts. Do not start or call the Adobe MCP bridge
  for this workflow. MCP implementation remains available for explicitly requested
  bridge work; its safety contract is scoped to that route.
- The live Premiere timeline is the source of truth. Read current project,
  sequence, frame rate, media links, selection and locks before mutations.
- Keep the full `livestream` intact with all A/V tracks locked. Edit only the
  designated edit sequence and requested short/orientation variants. Never clear
  the master or use broad Select All/Delete to create an empty sequence.
- Respect topic/plan review when requested; carry existing execution authorization
  forward. Verify intended source ranges, packed picture/audio, matching A/V
  boundaries and master preservation after each small cut batch.
- Use available computer-use controls under their tool instructions. Previously
  authorized native macOS automation is allowed within current permissions;
  never bypass tool restrictions with hidden APIs or external project rewrites.
- Stop dependent edits on wrong sequence, uncertain focus or failed verification.
  Re-observe and recover the last confirmed state before continuing.
- Review in Premiere precedes export when Vincent reserves that review. Do not
  export just to inspect the video. An explicit later export request is enough;
  publishing is a separate action.
- Do not create alternate sequences, rendered assemblies or proxy edits unless
  requested. Keep session-specific coordinates and temporary scripts out of
  reusable instructions.

## Checks

```bash
bun run premiere:check
bun run premiere:lint
bun run premiere:test
bun run format:check
```
