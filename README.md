# Adobe Premiere MCP Editor

This repo is the workspace for editing inside Adobe Premiere Pro through the
Adobe MCP bridge. The source of truth is the live Premiere timeline, not a
separate Python-rendered edit.

The old self-editing Python app has been removed from the working tree. Git
history is the archive.

## Active Workflow

Use this repo when the job is:

- inspect or modify the active Premiere Pro sequence
- run transcript-driven removal ranges against the Premiere timeline
- operate the Adobe MCP proxy and UXP bridge
- maintain JSX scripts used by Premiere automation
- document the safe Premiere editing workflow for agents

Do not create replacement timelines, rendered proxy edits, or alternate Python
assemblies unless the user explicitly asks for that recovery path.

## Layout

```text
apps/premiere/
├── adobe-mcp/              # Adobe MCP server, proxy, and UXP plugin workspace
├── scripts/                # ExtendScript files executed inside Premiere
└── skills/                 # Repo-local workflow instructions

.agents/                   # Durable agent context and session notes
.claude/                   # Claude MCP config
.codex/                    # Codex MCP config
.mcp.json                  # MCP config used by compatible clients
```

## Running The Premiere Bridge

Start the proxy:

```bash
bun run premiere:proxy
```

Then connect the Premiere UXP plugin from:

```text
apps/premiere/adobe-mcp/uxp-plugins/premiere
```

The MCP server command is configured as:

```text
./.venv/bin/adobe-premiere
```

The shared script directory is:

```text
apps/premiere/scripts
```

## Safety Rules

- Use `remove_silence_segments` for transcript-based deletion ranges.
- Verify timeline changes with project or sequence inspection after each cut batch.
- Treat MCP success responses as untrusted until the sequence layout actually changes.
- Do not use split/delete fallback tools that can desync linked audio and video.
- Do not use `set_clip_position` to close gaps; it can stretch clips.
- Stop if Premiere focus, keyboard automation, or sequence identity is uncertain.

## Checks

Headless checks cover syntax and repo hygiene only:

```bash
bun run premiere:check
bun run format:check
```

Live editing behavior still requires Premiere Pro, the proxy server, and the UXP
plugin to be running.
