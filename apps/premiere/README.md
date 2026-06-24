# Premiere App

This is the only app in the repo: Adobe Premiere Pro editing through MCP and a
Premiere UXP plugin.

## Paths

- `adobe-mcp/` - Premiere MCP server, Socket.IO proxy, and UXP plugin.
- `scripts/legacy-extendscript/` - Quarantined legacy `.jsx`, not wired into the
  workflow. Use the MCP tools instead. See its README.
- `skills/` - Workflow instructions for transcript planning and live MCP edits.

## Commands

From the repo root:

```bash
bun run premiere:proxy
bun run premiere:check
```

## Workflow

Use the live Premiere timeline. Apply transcript removal ranges through
`remove_silence_segments`. It uses Premiere's Extract (ripple-delete), so each
removed range normally closes its own gap in the same A/V-synced operation; the
tool then re-reads the sequence and returns a `verified` flag. Inspect the
sequence after each batch (or call `verify_sequence_layout`) and stop if the
active sequence or clip layout cannot be verified — treat
`verified: false`/`null` as not confirmed.

If `frame_snap=True` cannot snap because Premiere/UXP reports no frame ticks and
Extract leaves only tiny native gaps, use the repo-documented native Close Gap
recovery (`W`) one pass at a time and verify after every pass. Do not use
`set_clip_position`, split, trim, delete, alternate sequences, or rendered proxy
edits as recovery paths.
