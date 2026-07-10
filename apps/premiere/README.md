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
bun run premiere:proxy     # start the Socket.IO proxy
bun run premiere:status    # proxy + plugin connection status
bun run premiere:check     # Python compile check
bun run premiere:lint      # ruff
```

## Workflow

Use the live Premiere timeline. Start with `premiere_preflight()` (one read-only
health check of proxy/plugin/project/sequence). Plan with
`remove_silence_segments(..., dry_run=True)` — it returns the exact cut plan
without touching the timeline — then execute after approval. Each removed range
uses Premiere's Extract (ripple-delete), so it normally closes its own gap in
the same A/V-synced operation; the tool confirms every Extract against the live
layout and returns a `verified` flag. Inspect the sequence after each batch (or
call `verify_sequence_layout`) and stop if the active sequence or clip layout
cannot be verified — treat `verified: false`/`null` as not confirmed.

If `frame_snap=True` cannot snap because Premiere/UXP reports no frame ticks and
Extract leaves only tiny native gaps, run `close_gap_recovery(sequence_id)` —
the automated, bounded native Close Gap recovery (one pass at a time, verified
after every pass). Do not use `set_clip_position`, split, trim, delete,
alternate sequences, or rendered proxy edits as recovery paths.
