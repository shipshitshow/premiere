# Premiere repo memory

This repo edits the **live Adobe Premiere Pro timeline** through Adobe MCP.
There is no parallel FFmpeg / self-editing Python app in the working tree.

## Start here

1. `README.md` — product + setup
2. `apps/premiere/skills/premiere-mcp-ops/SKILL.md` — **canonical live-cut contract**
3. `apps/premiere/adobe-mcp/PREMIERE_MCP_WORKFLOW.md` — operator runbook
4. `.agents/memory/premiere-workflow.md` — durable house facts (audio preset, known ranges)

## Rules

- Live sequence is the source of truth. Verify after every cut.
- Preflight → dry-run plan → user approval → Extract → verify.
- The only allowed gap recovery is `close_gap_recovery`, and only for tiny native Extract gaps.
- Do not create alternate sequences or rendered assemblies unless asked.
