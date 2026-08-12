# Codex Instructions

This repo is the Adobe Premiere MCP editor workspace.

Active code lives in `apps/premiere`. The old self-editing Python app is not
part of this repo anymore; use git history only if it needs to be recovered.

Codex should prefer these checks:

```bash
bun run premiere:check
bun run premiere:lint
bun run premiere:test
bun run format:check
```

For live Premiere edits follow the contract in `AGENTS.md` and
`apps/premiere/skills/premiere-mcp-ops/SKILL.md`: run `premiere_preflight()`
first, plan with `remove_silence_segments(..., dry_run=True)` and get user
approval before executing, and use `close_gap_recovery` as the only gap fix.
If MCP tools are unavailable in the session, say that plainly and do not pretend
the edit was applied.
