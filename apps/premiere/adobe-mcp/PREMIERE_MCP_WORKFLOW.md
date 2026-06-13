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

- `.mcp.json`
- `.claude/settings.json`
- `.codex/config.toml`

## Cut Workflow

1. Confirm the proxy is running.
2. Confirm the Premiere UXP plugin is connected.
3. Confirm the correct Premiere sequence is active.
4. Apply transcript removal ranges with `remove_silence_segments`. Before cutting
   it makes the target sequence active and confirms it — if it cannot confirm the
   target is the focused Timeline, it refuses (the Extract keystroke would hit the
   wrong sequence) and returns `nextSteps`. Each range is then removed with
   Premiere's **Extract** (ripple-delete), which closes its gap in the same
   A/V-synced op — this is the "regroup" step, done natively per cut.
5. Read the top-level flags: `verified`, `packed` (fully back to back), `avSynced`
   (every cut frame-aligned across video and audio), and `nextSteps`. The
   `verification` block reports expected vs actual removed time (measured on clip
   content), `newGapsIntroduced`, `residualGaps`, and `avMisalignments` (each cut
   where V/A diverge by ≥1 frame). Treat `verified: false`/`null` as NOT confirmed.
6. Re-inspect with `verify_sequence_layout` if anything is uncertain — it returns
   the same `packed` / `avMisalignments` / `videoAudioInSync` / `warnings`.
7. Stop if the tool reports success but the clip layout is unchanged, or if any
   residual gap / A/V misalignment is reported. Hand the user the `nextSteps`.

### End-to-end transcript edit (the supported path)

1. Plan removal ranges from the transcript (planning skill) and get user approval.
2. Call `remove_silence_segments(sequence_id, segments)` — it cuts, regroups via
   Extract, frame-snaps, and verifies in one call.
3. Confirm `verified: true` and zero residual gaps; otherwise report the real
   state and stop.
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
bun run premiere:check
python3 -m compileall -q apps/premiere/adobe-mcp/adobe_mcp
```

Live editing checks require Premiere Pro, the proxy, and the UXP plugin.
