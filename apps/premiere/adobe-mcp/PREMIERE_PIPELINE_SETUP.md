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
- ExtendScripts: `apps/premiere/scripts`

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
SCRIPTS_DIR: ./apps/premiere/scripts
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
4. Apply transcript removal ranges with `remove_silence_segments`.
5. Inspect the sequence after each batch.
6. Stop if the tool reports success but the clip layout is unchanged.

## Safety Rules

- The live Premiere sequence is the source of truth.
- Use removal ranges in source timeline seconds.
- Do not create alternate sequences or rendered replacement files unless the user
  explicitly asks for that.
- Do not use split/delete/trim fallback APIs for linked timeline cuts.
- Do not use `set_clip_position` to close gaps.
- Report exact verified state before continuing after a partial failure.

## Headless Checks

From the repo root:

```bash
bun run premiere:check
python3 -m compileall -q apps/premiere/adobe-mcp/adobe_mcp
```

Live editing checks require Premiere Pro, the proxy, and the UXP plugin.
