# Premiere MCP Workflow

This workspace is for editing the active Adobe Premiere Pro timeline through
Adobe MCP. It does not maintain a parallel FFmpeg edit path.

## Architecture

```text
Agent / MCP client
        |
        v
adobe-premiere MCP server
        |
        v
proxy server on localhost:3001
        |
        v
Premiere UXP plugin
        |
        v
active Premiere Pro sequence
```

## Active Paths

- MCP workspace: `apps/premiere/adobe-mcp`
- Proxy server: `apps/premiere/adobe-mcp/proxy-server`
- Premiere UXP plugin: `apps/premiere/adobe-mcp/uxp-plugins/premiere`
- Legacy ExtendScripts (quarantined, unused): `apps/premiere/scripts/legacy-extendscript`

## Setup

Install the MCP package into the repo virtual environment:

```bash
cd apps/premiere/adobe-mcp
pip install -e .
```

Install proxy dependencies:

```bash
cd apps/premiere/adobe-mcp/proxy-server
npm install
```

Load the Premiere UXP plugin from:

```text
apps/premiere/adobe-mcp/uxp-plugins/premiere
```

Start the proxy from the repo root:

```bash
bun run premiere:proxy
```

## MCP Configuration

The repo-level MCP configs point at:

```text
command: ./.venv/bin/adobe-premiere
PROXY_URL: http://localhost:3001
PROXY_TIMEOUT: 120
```

Relevant files:

- `.mcp.json` — the MCP server definition (Claude Code reads project servers
  from here)
- `.claude/settings.json` — enables the `.mcp.json` server and raises the
  client-side MCP tool timeout above `PROXY_TIMEOUT`
- `.codex/config.toml` — same server for Codex, with `tool_timeout_sec = 180`

If `./.venv/bin/adobe-premiere` fails with `ModuleNotFoundError`, the venv's
editable install is stale (it happened after the workspace moved) — re-run
`.venv/bin/pip install -e apps/premiere/adobe-mcp` from the repo root.

## Operator Runbook (start everything)

1. Start the proxy: `bun run premiere:proxy` (repo root). Check it any time with
   `bun run premiere:status` — the JSON shows connected clients per app.
2. Open Premiere with the target project. Load the UXP plugin once via Adobe UXP
   Developer Tools (`uxp-plugins/premiere`; requires UXP Developer Mode enabled
   in Premiere); afterwards open the "Premiere MCP Agent" panel and click
   **Connect** (or tick "connect on launch").
3. Make the target sequence active (double-click it in the Project panel).
4. From the agent session, run `premiere_preflight()` — it verifies the whole
   chain (proxy, plugin, project, active sequence, frame ticks, focus) and
   returns `nextSteps` for anything broken. `ready: true` means go.
5. A dead proxy or disconnected plugin now fails fast with a clear error instead
   of hanging for the full timeout.

## Cut Workflow

1. Run `premiere_preflight()` (replaces manually checking proxy/plugin/sequence).
2. Plan: `remove_silence_segments(sequence_id, segments, dry_run=True)` — nothing
   is cut; it validates every range, frame-snaps, merges overlaps, and returns
   `plannedCuts` + `expectedRemovedSeconds`. Get user approval on the plan.
3. Execute: re-run with `dry_run=False`. Before cutting it makes the target
   sequence active and confirms it — if it cannot confirm the target is the
   focused Timeline, it refuses (the Extract keystroke would hit the wrong
   sequence) and returns `nextSteps`. Each range is then removed with Premiere's
   **Extract** (ripple-delete), which normally closes its gap in the same
   A/V-synced op — this is the "regroup" step, done natively per cut. Each
   Extract is confirmed against the live layout before the next one; a keystroke
   is only retried when a successful layout read shows the timeline did not
   change (an unreadable layout stops the batch).
4. Read the top-level flags: `verified`, `packed` (fully back to back), `avSynced`
   (every cut frame-aligned across video and audio), and `nextSteps`. The
   `verification` block reports expected vs actual removed time (measured on clip
   content), `newGapsIntroduced`, `residualGaps`, and `avMisalignments` (each cut
   where V/A diverge by ≥1 frame). Treat `verified: false`/`null` as NOT confirmed.
5. Re-inspect with `verify_sequence_layout` if anything is uncertain — it returns
   the same `packed` / `avMisalignments` / `videoAudioInSync` / `warnings`. For a
   visual check, `get_sequence_frame_image(sequence_id, seconds)` returns the frame
   at a timestamp as an inline image (read-only) so you can see a cut junction.
6. Stop if the tool reports success but the clip layout is unchanged. If a
   residual gap / A/V misalignment is reported, use only the documented native
   Close Gap recovery when its constraints are met; otherwise hand the user the
   `nextSteps` and stop.

### Native Close Gap recovery

Use this only when Premiere/UXP reports no frame ticks (`frameRateValue: null`,
`ticksPerFrame: null`, plus a `frameRateError` saying why) and Extract has
actually changed the requested active sequence but left tiny native gaps. The
`close_gap_recovery(sequence_id)` tool automates the bounded loop: Premiere's
**Sequence > Close Gap** shortcut (`W` in this workspace) one pass at a time,
`verify_sequence_layout` after every press, refusing on oversized gaps or A/V
misalignments, and hard-stopping if clip content changes. Keep the edit only
when it reports `clean: true` (`packed: true`, `videoAudioInSync: true`,
`gapCount: 0`, `warnings: []`). If those flags do not verify after bounded
passes, undo back to the previous clean baseline (its `nextSteps` say how many
undos) and stop. Never use `set_clip_position`, split, trim, delete, alternate
sequences, or rendered assemblies to recover a transcript cut.

### End-to-end transcript edit (the supported path)

1. Plan removal ranges from the transcript (planning skill), dry-run them
   (`remove_silence_segments(..., dry_run=True)`), and get user approval on the
   returned plan.
2. Call `remove_silence_segments(sequence_id, segments)` — it cuts, regroups via
   Extract, frame-snaps, and verifies in one call.
3. Confirm `verified: true` and zero residual gaps. If only the documented tiny
   Extract-gap case occurs, run `close_gap_recovery(sequence_id)` and confirm
   `clean: true`; otherwise report the real state and stop.
4. The user finishes the edit manually (color, audio polish, b-roll). Optional
   helpers: `premiere_apply_lumetri_correction`, `premiere_clean_audio_pipeline`.

The Lumetri "Auto" button, adjustment-layer creation, and "Enhance Speech" have
no UXP API and stay manual.

## Safety Rules

- The live Premiere sequence is the source of truth.
- Use removal ranges in source timeline seconds.
- Do not create alternate sequences or rendered replacement files unless the user
  explicitly asks for that.
- Do not use split/delete/trim fallback APIs for linked timeline cuts.
- Do not use `set_clip_position` to close gaps.
- Do not use Close Gap as a generic repair tool; use it only under the documented
  native recovery constraints and verify after every pass.
- Report exact verified state before continuing after a partial failure.

## Applying Plugin / Server Changes

New UXP commands (e.g. `getSequenceLayout`, `addEffectWithParams`) and new MCP
tools only take effect after you reload the moving parts:

1. Reload the UXP plugin in Premiere (UXP Developer Tool → Reload, or toggle the
   panel) so `uxp-plugins/premiere/commands/index.js` is re-read.
2. Restart the MCP server / client so `server.py`, `tools.py`, and
   `command_runner.py` are re-imported.
3. The proxy on `localhost:3001` can keep running; reconnect the plugin if needed.

## Headless Checks

From the repo root:

```bash
bun run premiere:check    # Python compile check
bun run premiere:lint     # ruff, repo policy from pyproject.toml
bun run format:check      # biome formatting
node --check apps/premiere/adobe-mcp/proxy-server/proxy.js
```

Live editing checks require Premiere Pro, the proxy, and the UXP plugin.
