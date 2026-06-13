# Premiere App

This is the only app in the repo: Adobe Premiere Pro editing through MCP and a
Premiere UXP plugin.

## Paths

- `adobe-mcp/` - Premiere MCP server, Socket.IO proxy, and UXP plugin.
- `scripts/` - Premiere ExtendScript helpers kept for explicit manual/tool use.
- `skills/` - Workflow instructions for transcript planning and live MCP edits.

## Commands

From the repo root:

```bash
bun run premiere:proxy
bun run premiere:check
```

## Workflow

Use the live Premiere timeline. Apply transcript removal ranges through
`remove_silence_segments`, inspect the sequence after each batch, and stop if
the active sequence or clip layout cannot be verified.
