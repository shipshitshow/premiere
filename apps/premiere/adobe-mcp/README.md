# Adobe Premiere MCP

MCP server for controlling Adobe Premiere Pro through the UXP plugin in this
repo. Not a multi-app Adobe server.

## Components

- `adobe_mcp/premiere/` — MCP server and tools
- `adobe_mcp/shared/` — proxy/socket utilities
- `proxy-server/` — Socket.IO bridge on `localhost:3001`
- `uxp-plugins/premiere/` — plugin loaded by UXP Developer Tools

Legacy ExtendScript under `../scripts/legacy-extendscript/` is **quarantined
and unused**. Do not wire it back in.

## Install

From the repo root:

```bash
cd apps/premiere/adobe-mcp
pip install -e .
```

Proxy dependencies (from `proxy-server/`):

```bash
cd apps/premiere/adobe-mcp/proxy-server
bun install
```

(`package-lock.json` is still committed for npm compatibility; prefer Bun.)

Load the plugin from `apps/premiere/adobe-mcp/uxp-plugins/premiere`.

## Run

```bash
bun run premiere:proxy     # from repo root
```

MCP command: `./.venv/bin/adobe-premiere` (`PROXY_URL=http://localhost:3001`).
Console script `adobe-proxy` also exists; prefer `bun run premiere:proxy`.

## Contract

Preflight → dry-run → Extract → verify. Canonical rules:
`apps/premiere/skills/premiere-mcp-ops/SKILL.md`.
Operator runbook: `PREMIERE_MCP_WORKFLOW.md`.
