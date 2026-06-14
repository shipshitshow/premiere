# Adobe Premiere MCP Editor

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Premiere MCP Check](https://github.com/shipshitshow/premiere/actions/workflows/ci.yml/badge.svg)](https://github.com/shipshitshow/premiere/actions/workflows/ci.yml)

Transcript-driven editing for the **live Adobe Premiere Pro timeline**, through a
local MCP server + Socket.IO proxy + Premiere UXP plugin. An MCP-capable agent
removes dead filler from a sequence and **every cut is verified** for A/V sync,
missing frames, and back-to-back packing before it is trusted.

Built and used by the [**Ship Sh!t Show**](https://www.youtube.com/@shipshitshow)
to cut technical livestreams down to publishable videos.

> The active Premiere sequence is the source of truth. This is **not** a
> standalone editor, a generated replacement timeline, or an FFmpeg render
> pipeline. It drives the real Premiere UI and then reads the result back to
> confirm what actually happened.

## Why this exists

Cutting a 3-hour livestream by transcript is easy to get subtly wrong: a cut that
leaves video and audio off by a single frame, a gap that breaks "back to back," or
a tool that reports success while the timeline never changed. Those failures are
invisible until you scrub the export.

So the point of this repo is not tool count — it is the **verification layer**.
The one supported cut path frame-snaps every range, cuts with Premiere's native
**Extract** (which closes the gap in the same A/V-synced operation), and then
re-reads the sequence to prove the edit landed correctly.

## What it does

- Exposes an `adobe-premiere` MCP server to MCP-capable agents (Claude Code, etc.)
- Connects that server to Premiere through a local Socket.IO proxy (`localhost:3001`)
- Loads a Premiere UXP plugin that runs commands inside Premiere Pro
- Edits the **active sequence** in the live Premiere UI
- Verifies every transcript cut and reports the real state, not just a success flag

## The supported workflow: `remove_silence_segments`

This is the only safe cut primitive. Give it the active sequence id and removal
ranges (in source-timeline seconds); for each range it:

1. **Confirms focus** — makes the target sequence active and refuses to cut if it
   cannot confirm it (the Extract keystroke lands on whatever timeline is focused).
2. **Frame-snaps** the range so video and audio cut on the exact same frame.
3. **Extracts** the range with Premiere's native ripple-delete, which closes the
   gap in the same A/V-synced op — the "regroup," done natively per cut.
4. **Verifies** the result and returns it.

### Verification contract

After a cut, read the top-level flags:

| Flag | Meaning |
|------|---------|
| `verified` | The right amount was removed, no new gap appeared, and every cut lands on the same frame for video and audio. |
| `packed` | The whole sequence is back to back — zero gaps on any lane (including a leading gap). |
| `avSynced` | Video and audio cut at the same timecode everywhere (frame-accurate). |
| `nextSteps` | Plain instructions for the user when something needs attention. |

Treat `verified: false` / `null` as **not confirmed**. The A/V check tolerates
only sub-frame rounding (half a frame) — a full one-frame drift is reported as a
misalignment and fails `verified`/`avSynced`. Standalone helpers:

- `verify_sequence_layout` — per-lane gaps, `avMisalignments`, end-skew, warnings.
- `get_sequence_frame_image` — returns the frame at a timestamp as an inline image
  (read-only) so you can *see* a cut junction, on top of the numbers.

> Never trust an MCP success response on its own. Re-read the layout.

## Layout

```text
apps/premiere/
├── adobe-mcp/              # Premiere MCP server, proxy, and UXP plugin
│   ├── adobe_mcp/premiere/ # MCP server + tools (server.py, tools.py)
│   ├── proxy-server/       # Socket.IO proxy (localhost:3001)
│   └── uxp-plugins/premiere/ # UXP plugin executed inside Premiere
├── scripts/                # legacy-extendscript/ — quarantined .jsx, reference only
└── skills/                 # Repo-local editing workflow instructions

.agents/                    # Durable agent context and memory
.claude/  .codex/  .mcp.json # MCP client configs (point at ./.venv/bin/adobe-premiere)
```

Only Premiere lives under `apps/premiere`. Photoshop, Illustrator, InDesign, and
the old self-editing Python app were removed; git history is the archive.

## Setup

Requires Adobe Premiere Pro with UXP support (25.6+), Python, and Bun.

```bash
# 1. Install the MCP package into the repo virtual environment
cd apps/premiere/adobe-mcp
pip install -e .

# 2. Install proxy dependencies
cd proxy-server
npm install
```

Load the Premiere UXP plugin in Adobe UXP Developer Tools from
`apps/premiere/adobe-mcp/uxp-plugins/premiere`, then start the proxy from the
repo root:

```bash
bun run premiere:proxy
```

The MCP server command (already wired into `.mcp.json` / `.claude` / `.codex`) is
`./.venv/bin/adobe-premiere`, with `PROXY_URL=http://localhost:3001`.

## Safety rules

- Edit the active Premiere sequence, then verify it — success flags are untrusted
  until the clip layout actually changes.
- Use `remove_silence_segments` for transcript cuts. Do **not** use
  split/trim/delete fallbacks or `set_clip_position` to close gaps — they desync
  linked audio/video. (They exist in the server, inherited from upstream, but
  carry an `UNSAFE` docstring and are not part of the cut workflow.)
- Do not create replacement timelines, rendered proxy edits, or alternate
  assemblies unless explicitly asked.
- Stop on uncertain focus, wrong sequence, proxy disconnect, or failed verification.

## Checks

```bash
bun run premiere:check     # Python syntax / repo hygiene
bun run format:check       # Biome formatting
```

Live editing behavior requires Premiere Pro, the proxy server, and the UXP plugin
to be running.

## Credits

Derived from the open-source [`adobe-mcp`](https://github.com/mikechambers/adb-mcp)
project by **Mike Chambers** (MIT). The MCP server, proxy, and UXP plugin
architecture come from that project; this repo focuses it on Premiere and adds the
hardened, verification-first transcript-cut workflow.

## License

[MIT](LICENSE). Bundled components retain their own notices
(`apps/premiere/adobe-mcp/LICENSE` — MIT; the UXP plugin — Apache 2.0).
