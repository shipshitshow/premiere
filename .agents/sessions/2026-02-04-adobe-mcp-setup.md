# Session: Adobe MCP Server Setup
**Date:** 2026-02-04
**Duration:** ~45 minutes
**Status:** Partially Complete - UXP Plugin Connection Issue

---

## Objective
Set up Adobe Premiere MCP server + scripts to create two parallel editing versions:
- **Version 1**: Python/FFmpeg (existing) - outputs processed MP4 directly
- **Version 2**: Adobe Premiere Pro via MCP - edits in Premiere timeline, exports from there

## What Was Accomplished

### 1. Cloned and Installed adobe-premiere-mcp Workspace
```bash
cd /Users/decod3rslabs/www/premiere/mcp
rm -rf adobe-premiere-mcp
git clone https://github.com/david-t-martel/adobe-mcp.git adobe-premiere-mcp
cd adobe-premiere-mcp && pip3 install -e .
```
- **Status:** ✅ Complete
- Python package installed successfully
- Command `adobe-premiere` is available at `/Library/Frameworks/Python.framework/Versions/3.13/bin/adobe-premiere`

### 2. Installed Proxy Server Dependencies
```bash
cd proxy-server && npm install
```
- **Status:** ✅ Complete
- Proxy server running on port 3001

### 3. Created Bridge Modules

#### `mcp/adobe-premiere-mcp/bridge.py`
Converts Python pipeline output to Premiere format:
- `segments_to_premiere_cuts()` - Extract silence segments for cutting
- `create_jsx_args()` - Format for apply-cuts.jsx
- `create_workflow_args()` - Format for batch-operations.jsx
- `get_segment_stats()` - Statistics about detected segments
- `validate_segments()` - Validate segment data integrity

#### `mcp/adobe-premiere-mcp/jsx_runner.py`
Execute commands via the proxy server:
- `JSXRunner` class for managing connections
- Convenience functions: `import_media()`, `create_sequence()`, `create_project()`, `save_project()`

#### `mcp/adobe-premiere-mcp/premiere_tools.py`
High-level MCP tools:
- `adobe_premiere_import_and_setup` - Create project + import + sequence
- `adobe_premiere_apply_python_cuts` - Apply segments.json cuts
- `adobe_premiere_export` - Export sequence
- `adobe_premiere_full_workflow` - Complete pipeline
- `adobe_premiere_get_segment_stats` - Preview cut statistics
- `adobe_premiere_compare_outputs` - Compare FFmpeg vs Premiere outputs

### 4. Updated Configuration

#### `.claude/settings.json`
```json
{
  "mcpServers": {
    "premiere": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "server"],
      "cwd": "./mcp/premiere-python-mcp"
    },
    "adobe-premiere": {
      "type": "stdio",
      "command": "adobe-premiere",
      "env": {
        "SCRIPTS_DIR": "/Users/decod3rslabs/www/premiere/scripts"
      }
    }
  }
}
```

### 5. Created Documentation
- `mcp/adobe-premiere-mcp/PREMIERE_PIPELINE_SETUP.md` - Full setup and usage guide

---

## Current Blocker

### UXP Developer Tools Cannot Connect to Premiere Pro

**Error Message:**
```
No applications are connected to the service. Make sure the target application is running and connected to the service.
```

**Environment:**
- Premiere Pro Version: 26.0.0 (2026)
- UXP Developer Tools: Installed and running
- Plugin manifest requires: minVersion 25.3.0 ✅

**Troubleshooting Performed:**
1. ✅ Verified proxy server running on port 3001
2. ✅ Verified Premiere Pro is running (process 35567)
3. ✅ Enabled CEP debug mode (`defaults write com.adobe.CSXS.11 PlayerDebugMode 1`)
4. ✅ Verified UXP Developer mode enabled (`/Library/Application Support/Adobe/UXP/Developer/settings.json`)
5. ✅ Checked macOS firewall (disabled)
6. ✅ Verified UXP Developer Tools listening on port 14001
7. ❌ Premiere Pro not connecting to UXP Developer Tools service

**Observations:**
- UXP logs in Premiere show UXP framework is working (home screen plugin runs)
- UXP Developer Tools only shows internal connections (to its own helper process)
- Premiere Pro is not establishing connection to UXP Developer Tools

**Likely Cause:**
Premiere Pro needs to be started AFTER UXP Developer Tools is already running for the connection to establish.

---

## Next Steps

### Immediate (To Resolve Connection)
1. Quit Premiere Pro completely
2. Quit UXP Developer Tools
3. Wait 5 seconds
4. Start UXP Developer Tools FIRST
5. Wait until fully loaded
6. Start Premiere Pro
7. Wait 20-30 seconds for connection

### If Connection Still Fails
1. Check if Premiere Pro 26.0 has different UXP connection mechanism
2. Try Window → Development menu in Premiere (if exists)
3. Consider alternative: CEP-based plugin instead of UXP
4. Check Adobe forums for Premiere 2026 + UXP Developer Tools compatibility

### After Connection Established
1. Load the plugin from `/Users/decod3rslabs/www/premiere/mcp/adobe-premiere-mcp/uxp-plugins/premiere/`
2. Verify plugin appears in Premiere's Window → Extensions menu
3. Test basic MCP commands (create project, import media)
4. Test full workflow with segments.json

---

## Files Created/Modified This Session

### Created
- `/Users/decod3rslabs/www/premiere/mcp/adobe-premiere-mcp/bridge.py`
- `/Users/decod3rslabs/www/premiere/mcp/adobe-premiere-mcp/jsx_runner.py`
- `/Users/decod3rslabs/www/premiere/mcp/adobe-premiere-mcp/premiere_tools.py`
- `/Users/decod3rslabs/www/premiere/mcp/adobe-premiere-mcp/PREMIERE_PIPELINE_SETUP.md`

### Modified
- `/Users/decod3rslabs/www/premiere/.claude/settings.json`
- `/Users/decod3rslabs/www/premiere/mcp/adobe-premiere-mcp/adobe_mcp/premiere/server.py`

### Cloned
- `/Users/decod3rslabs/www/premiere/mcp/adobe-premiere-mcp/` (from github.com/david-t-martel/adobe-mcp)

---

## Architecture Reference

```
Python Pipeline (Version 1)        Adobe Pipeline (Version 2)
────────────────────────────       ────────────────────────────
premiere_detect_segments           premiere_detect_segments
        │                                  │
        ▼                                  ▼
   segments.json ─────────────────► segments.json
        │                                  │
        ▼                                  ▼
premiere_cut_silence              adobe_premiere_full_workflow
(FFmpeg concat)                   (Premiere timeline edits)
        │                                  │
        ▼                                  ▼
   output_ffmpeg.mp4                output_premiere.mp4
```

## Connection Architecture

```
Claude Code
    │
    ▼ (stdio)
adobe-premiere MCP server (Python)
    │
    ▼ (WebSocket port 3001)
Proxy Server (Node.js)
    │
    ▼ (WebSocket)
UXP Plugin (inside Premiere Pro)
    │
    ▼ (UXP API)
Adobe Premiere Pro
```

---

## Commands Reference

```bash
# Start proxy server
cd /Users/decod3rslabs/www/premiere/mcp/adobe-premiere-mcp/proxy-server
node proxy.js

# Check proxy is running
lsof -i :3001

# Check Premiere is running
ps aux | grep -i premiere | grep -v grep

# Check UXP Developer Tools connections
lsof -i :14001
```
