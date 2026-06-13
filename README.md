# Adobe Premiere MCP Editor

This repo is for editing inside Adobe Premiere Pro through a local MCP server,
proxy, and Premiere UXP plugin. The source of truth is the open Premiere
project and the active Premiere sequence.

This is not a standalone video editor, not a generated replacement timeline,
and not a Python/FFmpeg rendering pipeline. The old self-editing app has been
removed from the working tree; git history is the archive.

## What This Repo Does

- exposes an `adobe-premiere` MCP server to MCP-capable agents
- connects that server to Premiere through a local Socket.IO proxy
- loads a Premiere UXP plugin that executes commands inside Premiere Pro
- edits the active sequence in the Premiere UI
- keeps repo-local workflow rules for transcript-driven cuts and safe recovery

The default transcript/cut workflow is `remove_silence_segments`: set in/out
points on the active sequence, use Premiere's native Extract command, then
verify the sequence layout changed.

## Current Adobe Status

Checked on June 13, 2026:

- Adobe has official MCP work, but the public first-party MCP servers I found
  are for products like Adobe Express Developer docs, Adobe Target, AEM, App
  Builder, and design/dev resources. I did not find an official Adobe Premiere
  Pro editing MCP server.
- Premiere itself has moved forward: Adobe says UXP is officially available in
  Premiere Pro 25.6, and the Premiere UXP API now covers projects, sequences,
  tracks, clips, markers, project items, and application settings.
- Adobe's official Premiere UXP samples now cover import/export, encoder,
  transcripts, effects, transitions, keyframes, markers, source monitor, and
  project conversion formats. That means our least-hacky path is to keep
  expanding direct UXP-backed MCP commands, not revive a separate editor app.
- Premiere Pro 26.2 adds UXP Hybrid Plugins, which may be useful later for
  native media analysis or high-performance operations, but it is not needed
  for normal timeline editing.

Sources:
[Adobe Express Developer MCP](https://developer.adobe.com/express/add-ons/docs/guides/getting-started/local-development/mcp-server),
[Adobe Target MCP](https://experienceleague.adobe.com/en/docs/target/using/integrate/mcp/target-mcp-get-started),
[Premiere UXP API](https://developer.adobe.com/premiere-pro/uxp/),
[Premiere UXP Changelog](https://developer.adobe.com/premiere-pro/uxp/changelog/),
[Premiere UXP Samples](https://github.com/AdobeDocs/uxp-premiere-pro-samples),
[UXP Hybrid Plugins for Premiere](https://blog.developer.adobe.com/en/publish/2026/04/uxp-hybrid-plugins-now-available-for-premiere).

## Layout

```text
apps/premiere/
├── adobe-mcp/              # Premiere MCP server, proxy, and UXP plugin
├── scripts/                # Premiere ExtendScript helpers kept for explicit use
└── skills/                 # Repo-local editing workflow instructions

.agents/                   # Durable agent context and memory
.claude/                   # Claude MCP config
.codex/                    # Codex MCP config
.mcp.json                  # MCP config for compatible clients
```

Only Premiere lives under `apps/premiere`. Photoshop, Illustrator, InDesign,
the legacy Python app, generic Windows launch menus, and unused icon assets have
been removed.

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

Load the Premiere UXP plugin in Adobe UXP Developer Tools from:

```text
apps/premiere/adobe-mcp/uxp-plugins/premiere
```

Start the proxy from the repo root:

```bash
bun run premiere:proxy
```

The MCP server command is:

```text
./.venv/bin/adobe-premiere
```

## MCP Commands

Core live-edit tools include project and sequence inspection, import, sequence
creation, trim, clip delete/duplicate/move, markers, effects, transitions,
keyframes, selection, transcript import/export, MOGRT insertion, export, and
keyboard-backed Premiere actions.

Use `remove_silence_segments` for transcript-based deletions. Avoid
`set_clip_position` for closing gaps, and do not use split/delete fallback tools
for linked audio/video cuts unless the user explicitly asks for recovery work.

## Safety Rules

- Edit the active Premiere sequence, then verify it.
- Treat MCP success responses as untrusted until the clip layout actually changes.
- Stop on uncertain focus, wrong sequence, proxy disconnect, or failed verification.
- Do not create replacement timelines, rendered proxy edits, or alternate Python
  assemblies unless explicitly asked.
- Keep this repo focused on Premiere MCP/UXP work only.

## Checks

Headless checks cover syntax and repo hygiene:

```bash
bun run premiere:check
bun run format:check
```

Live editing behavior still requires Premiere Pro, the proxy server, and the UXP
plugin to be running.
