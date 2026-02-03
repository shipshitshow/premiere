# Adobe MCP (Placeholder)

This directory is reserved for the Adobe MCP integration that controls Adobe Premiere Pro directly.

## Setup

The recommended approach is to use the existing [adobe-mcp](https://github.com/david-t-martel/adobe-mcp) project:

```bash
# Clone into this directory
cd ~/www/VincentShipsIt/premiere/mcp
rm -rf adobe-mcp
git clone https://github.com/david-t-martel/adobe-mcp.git adobe-mcp

# Install dependencies
cd adobe-mcp
pip install -e .
cd proxy-server && npm install
```

## Components

Adobe MCP consists of:

1. **Python MCP Server** - Communicates with Claude Code
2. **Node.js Proxy Server** - WebSocket bridge to Adobe
3. **UXP Plugin** - Runs inside Premiere Pro

## Configuration

After installation, add to your Claude Code settings:

```json
{
  "mcpServers": {
    "adobe-premiere": {
      "type": "stdio",
      "command": "adobe-premiere"
    }
  }
}
```

## Available Tools

| Tool | Purpose |
|------|---------|
| `adobe_create_project` | Create new Premiere project |
| `adobe_import_media` | Import files into project |
| `adobe_create_sequence` | Create timeline |
| `adobe_insert_clip` | Add clip to timeline |
| `adobe_apply_effect` | Apply video/audio effect |
| `adobe_add_marker` | Add marker at timestamp |
| `adobe_export` | Export sequence |
