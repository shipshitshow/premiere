# Adobe MCP For Premiere

This is the active MCP workspace for controlling Adobe Premiere Pro from this
repo. The upstream package still contains support files for other Adobe apps,
but this repo's workflow is Premiere-first.

## Components

- `adobe_mcp/premiere/` - Premiere MCP server.
- `adobe_mcp/shared/` - Shared proxy/socket utilities.
- `proxy-server/` - WebSocket bridge on `localhost:3001`.
- `uxp-plugins/premiere/` - Premiere UXP plugin.
- `../scripts/` - ExtendScripts used by the Premiere workflow.

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

## Workflow Contract

- Edit the active Premiere sequence.
- Use `remove_silence_segments` for transcript removal ranges.
- Verify the timeline layout after tool calls.
- Stop on focus, connection, sequence identity, or verification uncertainty.
- Do not create rendered replacements or alternate timelines unless explicitly
  requested.

See `PREMIERE_PIPELINE_SETUP.md` and `.agents/memory/premiere-workflow.md` for
the repo-level workflow rules.
