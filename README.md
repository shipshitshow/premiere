# Adobe Premiere Editor

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Premiere MCP Check](https://github.com/shipshitshow/premiere/actions/workflows/ci.yml/badge.svg)](https://github.com/shipshitshow/premiere/actions/workflows/ci.yml)

Transcript-driven editing for the **live Adobe Premiere Pro timeline**. Weekly
production uses native computer use, with repository skills documenting project
preservation, editorial planning, audio, color, captions and delivery. The repo
also contains an MCP server + Socket.IO proxy + Premiere UXP plugin for explicitly
requested bridge operation. Verify every edit for source selection, A/V sync and
program continuity before trusting it.

Built and used by the [**Ship Sh!t Show**](https://www.youtube.com/@shipshitshow)
to cut technical livestreams down to publishable videos.

> The active Premiere sequence is the source of truth. This is **not** a
> standalone editor, a generated replacement timeline, or an FFmpeg render
> pipeline. It drives the real Premiere UI and then reads the result back to
> confirm what actually happened.

## Weekly editing through computer use

**Current editing preference (2026-09-09): operate installed Premiere through
computer use, without the Adobe MCP bridge.** The MCP implementation and its
route-specific documentation below remain available for bridge development or
an explicit MCP request; they are not prerequisites for native editing.

- [Weekly edit skill](apps/premiere/skills/premiere-weekly-edit/SKILL.md): project
  naming, locked full livestream, transcript planning, native edits, sound and light.
- [Shorts and delivery skill](apps/premiere/skills/premiere-shorts-delivery/SKILL.md):
  speaker framing, vertical and 16:9 versions, corrected visible captions and folders.
- [Native panel operation](apps/premiere/skills/premiere-weekly-edit/references/native-control.md):
  focus, selection, dialogs and the recovery lessons from the actual session.
- [260908 edit record](apps/premiere/skills/premiere-weekly-edit/references/260908-edit-record.md):
  actual cuts, effects, caption choices, preservation checks and remaining review.

The repository skills are the maintained source. To install them in Codex, copy
both skill directories to `~/.codex/skills/` without overwriting unrelated skills.
Re-sync these two installed copies whenever their repository instructions change.
Media, Premiere projects and exports remain in the dated production folders.

## Why this exists

Cutting a 3-hour livestream by transcript is easy to get subtly wrong: a cut that
leaves video and audio off by a single frame, a gap that breaks "back to back," or
a tool that reports success while the timeline never changed. Those failures are
invisible until you scrub the export.

So the point of this repo is not tool count — it is the **verification layer**.
The MCP cut path frame-snaps every range, cuts with Premiere's native
**Extract** (which closes the gap in the same A/V-synced operation), and then
re-reads the sequence to prove the edit landed correctly.

## What the MCP implementation does

- Exposes an `adobe-premiere` MCP server to MCP-capable agents (Claude Code, etc.)
- Connects that server to Premiere through a local Socket.IO proxy (`localhost:3001`)
- Loads a Premiere UXP plugin that runs commands inside Premiere Pro
- Edits the **active sequence** in the live Premiere UI
- Verifies every transcript cut and reports the real state, not just a success flag

## MCP workflow: preflight → plan → cut → verify

`remove_silence_segments` is the only safe cut primitive, and it is wrapped in
a check-first flow so nothing executes sight-unseen:

0. **Preflight** — `premiere_preflight()` verifies the whole chain in one
   read-only call: proxy up, UXP plugin connected, project open, active
   sequence, frame ticks readable, Premiere frontmost. Broken links fail fast
   with `nextSteps` instead of hanging until the timeout.
1. **Plan (dry run)** — `remove_silence_segments(..., dry_run=True)` validates
   every range (types, order, bounds, overlaps), frame-snaps, and returns the
   exact `plannedCuts` and `expectedRemovedSeconds` **without touching the
   timeline**. Approve the plan, then execute with `dry_run=False`.
2. **Confirms focus** — makes the target sequence active and refuses to cut if it
   cannot confirm it (the Extract keystroke lands on whatever timeline is focused).
3. **Frame-snaps** the range so video and audio cut on the exact same frame.
4. **Extracts** the range with Premiere's native ripple-delete, which closes the
   gap in the same A/V-synced op — the normal "regroup," done natively per cut.
   Each Extract is confirmed against the live layout before the next; a
   keystroke is only retried when the timeline provably did not change.
5. **Verifies** the result and returns it.

If Premiere/UXP cannot provide frame ticks, `frame_snap=True` cannot actually
snap the range before Extract. In that specific state, Extract can remove the
right material but leave tiny native gaps. The only documented recovery is
Premiere's own **Sequence > Close Gap** command (`W` in this workspace), now
automated as `close_gap_recovery(sequence_id)`: one pass at a time,
`verify_sequence_layout` after every pass, refusing on oversized gaps or A/V
misalignments, hard-stopping if clip content changes. Keep the edit only when
it reports `clean: true` (`packed: true`, `videoAudioInSync: true`,
`gapCount: 0`, `warnings: []`); otherwise undo to the previous clean baseline
and stop.

### Verification contract

After a cut, read the top-level flags:

| Flag | Meaning |
|------|---------|
| `verified` | The right amount was removed, no new gap appeared, and every cut lands on the same frame for video and audio. |
| `packed` | The program bed is back to back — zero gaps on program lanes (including a leading gap). Overlay lanes (b-roll, titles, stingers) are reported separately and do not fail this. |
| `avSynced` | Video and audio cut at the same timecode everywhere (frame-accurate). |
| `nextSteps` | Plain instructions for the user when something needs attention. |

Treat `verified: false` / `null` as **not confirmed**. The A/V check tolerates
only sub-frame rounding (half a frame) — a full one-frame drift is reported as a
misalignment and fails `verified`/`avSynced`. The full contract (unsafe tools,
program vs overlay lanes, Close Gap constraints) is
`apps/premiere/skills/premiere-mcp-ops/SKILL.md`. Standalone helpers:

- `premiere_preflight` — one-call health check of the proxy/plugin/project chain.
- `verify_sequence_layout` — per-lane gaps, `avMisalignments`, end-skew, warnings.
- `get_sequence_frame_image` — returns the frame at a timestamp as an inline image
  (read-only) so you can *see* a cut junction, on top of the numbers.
- `close_gap_recovery` — the bounded, verified Close Gap recovery (the only
  allowed gap fix).

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
bun install
```

Enable **UXP Developer Mode** in Premiere (Settings > Development), then load
the Premiere UXP plugin in Adobe UXP Developer Tools from
`apps/premiere/adobe-mcp/uxp-plugins/premiere`, and start the proxy from the
repo root:

```bash
bun run premiere:proxy     # start the Socket.IO proxy on :3001
bun run premiere:status    # check proxy + connected plugin clients
```

The MCP server command (already wired into `.mcp.json` / `.claude` / `.codex`) is
`./.venv/bin/adobe-premiere`, with `PROXY_URL=http://localhost:3001`. If it fails
with `ModuleNotFoundError`, re-run `.venv/bin/pip install -e apps/premiere/adobe-mcp`
(the editable install goes stale if the workspace path changes). Once everything
is up, `premiere_preflight()` from the agent session confirms the whole chain.

## MCP safety rules

- Edit the active Premiere sequence, then verify it — success flags are untrusted
  until the clip layout actually changes.
- Use `remove_silence_segments` for transcript cuts, always dry-run first. Do
  **not** use split/trim/delete fallbacks or `set_clip_position` to close gaps —
  they desync linked audio/video. (They exist in the server, inherited from
  upstream, but all 13 carry an `UNSAFE` docstring prefix and are not part of
  the cut workflow; the canonical list is in
  `apps/premiere/skills/premiere-mcp-ops/SKILL.md`.)
- The only allowed gap recovery is `close_gap_recovery` (the documented native
  Premiere Close Gap flow above), and only after verification proves the gaps
  are tiny Extract-created gaps in the requested active sequence.
- Do not create replacement timelines, rendered proxy edits, or alternate
  assemblies unless explicitly asked.
- Stop on uncertain focus, wrong sequence, proxy disconnect, or failed verification.

## Checks

```bash
bun run premiere:check     # Python compile check
bun run premiere:lint      # ruff (repo policy from pyproject.toml)
bun run premiere:test      # plan/layout/verify unit tests
bun run format:check       # Biome formatting
```

Live editing behavior requires Premiere Pro, the proxy server, and the UXP plugin
to be running.

## Credits

The MCP server, proxy, and UXP plugin architecture originate in **Mike
Chambers'** open-source [`adb-mcp`](https://github.com/mikechambers/adb-mcp)
(MIT); the vendored package layout here follows the
[`adobe-mcp`](https://github.com/matrayu/adobe-mcp) packaging of that project.
This repo focuses it on Premiere only and adds the hardened, verification-first
transcript-cut workflow (dry-run planning, preflight, per-cut confirmation, and
the bounded Close Gap recovery). As of mid-2026 Adobe ships no first-party
Premiere Pro MCP server.

## License

[MIT](LICENSE). Bundled components retain their own notices
(`apps/premiere/adobe-mcp/LICENSE` — MIT; the UXP plugin — Apache 2.0).
