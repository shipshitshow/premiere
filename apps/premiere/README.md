# Premiere App

This is the active app in the repo: Adobe Premiere Pro editing through Adobe MCP.

## Paths

- `adobe-mcp/` - MCP server, proxy, and UXP plugin workspace.
- `scripts/` - ExtendScripts executed in Premiere.
- `skills/` - Workflow instructions for transcript planning and MCP operations.

## Commands

From the repo root:

```bash
bun run premiere:proxy
bun run premiere:check
```

## Workflow

Use the live Premiere timeline. Apply transcript removal ranges through
`remove_silence_segments`, then verify the sequence layout before continuing.
