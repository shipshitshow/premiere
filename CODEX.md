# Codex Instructions

This repo is the Adobe Premiere MCP editor workspace.

Active code lives in `apps/premiere`. The old self-editing Python app is not
part of this repo anymore; use git history only if it needs to be recovered.

Codex should prefer these checks:

```bash
bun run premiere:check
bun run format:check
```

For live Premiere edits, verify proxy, UXP, active sequence, and timeline layout.
If MCP tools are unavailable in the session, say that plainly and do not pretend
the edit was applied.
