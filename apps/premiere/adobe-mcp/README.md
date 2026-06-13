# Adobe Premiere MCP

This package exposes one thing: an MCP server for controlling Adobe Premiere Pro
through the Premiere UXP plugin in this repo.

It is intentionally not a multi-app Adobe server. Non-Premiere app
modules, plugins, icon assets, generic launch menus, and legacy pipeline helpers
have been removed so agents stay on the live Premiere editing workflow.

## Components

- `adobe_mcp/premiere/` - Premiere MCP server and additional UXP-backed tools.
- `adobe_mcp/shared/` - Shared proxy/socket utilities.
- `proxy-server/` - Socket.IO bridge on `localhost:3001`.
- `uxp-plugins/premiere/` - Premiere UXP plugin loaded by UXP Developer Tools.
- `../scripts/` - Premiere ExtendScript helpers, used only when explicitly needed.

## Install

From the repo root:

```bash
cd apps/premiere/adobe-mcp
pip install -e .
```

Install proxy dependencies:

```bash
cd apps/premiere/adobe-mcp/proxy-server
npm install
```

Load the Premiere plugin in Adobe UXP Developer Tools from:

```text
apps/premiere/adobe-mcp/uxp-plugins/premiere
```

## Run

Start the proxy from the repo root:

```bash
bun run premiere:proxy
```

The MCP command configured at the repo root is:

```text
./.venv/bin/adobe-premiere
```

## Tool Surface

The core server handles project/sequence inspection, media import, timeline
editing, markers, trim, clip removal, keyboard-backed actions, and
`remove_silence_segments`.

The additional Premiere tools expose UXP-backed export, transcripts, keyframes,
effect lookup/application, transition lookup/application, work area selection,
subsequence creation, clip handles, sequence selection, and MOGRT insertion.

## Workflow Contract

- Edit the active Premiere sequence.
- Prefer `remove_silence_segments` for transcript removal ranges.
- Verify the timeline layout after tool calls.
- Stop on focus, connection, sequence identity, or verification uncertainty.
- Do not create rendered replacements, alternate timelines, or parallel edit
  outputs unless explicitly requested.

See `PREMIERE_MCP_WORKFLOW.md` and
`.agents/memory/premiere-workflow.md` for the repo-level workflow rules.
