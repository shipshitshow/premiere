# Premiere Parallel Editing Pipeline Setup

This document describes how to set up and use the parallel editing workflow that creates both FFmpeg and Adobe Premiere versions of edited videos.

## Architecture

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

## Prerequisites

1. **Python 3.10+** with pip
2. **Node.js 18+** with npm (for proxy server)
3. **Adobe Premiere Pro 25.3+**
4. **Adobe UXP Developer Tools** (from Creative Cloud)

## Installation Steps

### Step 1: Clone and Install adobe-premiere-mcp

```bash
cd /Users/decod3rslabs/www/premiere/mcp
rm -rf adobe-premiere-mcp
git clone https://github.com/david-t-martel/adobe-mcp.git adobe-premiere-mcp
cd adobe-premiere-mcp
pip3 install -e .
```

### Step 2: Install Proxy Server Dependencies

```bash
cd proxy-server
npm install
cd ..
```

### Step 3: Install UXP Plugin in Premiere Pro

1. Open **Adobe UXP Developer Tools** (install from Creative Cloud if needed)
2. Click **"Add Plugin"**
3. Navigate to `mcp/adobe-premiere-mcp/uxp-plugins/premiere/`
4. Select `manifest.json`
5. Click **"Load"** to activate the plugin
6. Open **Premiere Pro** - the plugin should connect automatically

### Step 4: Verify Setup

1. Start the proxy server:
   ```bash
   cd /Users/decod3rslabs/www/premiere/mcp/adobe-premiere-mcp/proxy-server
   node proxy.js
   ```

2. Check the UXP Developer Tools - the plugin should show "Connected"

3. Test a basic command (with Premiere Pro open):
   ```bash
   # From another terminal
   adobe-premiere
   ```

## Claude Code Configuration

The `.claude/settings.json` has been updated with:

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

## Available Tools

### Python Pipeline (premiere MCP)
- `premiere_get_video_info` - Get video metadata
- `premiere_detect_segments` - Detect silence/speech segments
- `premiere_cut_silence` - FFmpeg-based silence removal

### Adobe Pipeline (adobe-premiere MCP)
- `adobe_premiere_import_and_setup` - Create project and import video
- `adobe_premiere_apply_python_cuts` - Apply segments.json cuts to timeline
- `adobe_premiere_export` - Export edited sequence
- `adobe_premiere_full_workflow` - Complete pipeline in one call
- `adobe_premiere_get_segment_stats` - Preview cut statistics
- `adobe_premiere_compare_outputs` - Compare FFmpeg vs Premiere outputs

### Low-Level Adobe Tools
- `create_project` - Create new Premiere project
- `import_media` - Import media files
- `create_sequence_from_media` - Create timeline sequence
- `save_project` - Save current project
- And more (see adobe-premiere-mcp README)

## Workflow Usage

### Option 1: Separate Steps

```
# Step 1: Detect silence (creates segments.json)
Use premiere_detect_segments on video.mp4

# Step 2: FFmpeg version
Use premiere_cut_silence with the segments

# Step 3: Premiere version
Use adobe_premiere_full_workflow with video.mp4 and segments.json
```

### Option 2: Full Workflow

```
# Run both pipelines
1. premiere_detect_segments → segments.json
2. premiere_cut_silence → output_ffmpeg.mp4
3. adobe_premiere_full_workflow → output_premiere.mp4
```

### Option 3: Preview Before Processing

```
# Check what cuts will be made
Use adobe_premiere_get_segment_stats on segments.json

# Then decide which pipeline to use
```

## Comparison Workflow

After processing the same video through both pipelines:

```
# Compare the outputs
Use adobe_premiere_compare_outputs with:
  - ffmpeg_output_path: path/to/output_ffmpeg.mp4
  - premiere_output_path: path/to/output_premiere.mp4
```

## Files Reference

### Bridge Modules (new)
- `mcp/adobe-premiere-mcp/bridge.py` - Converts segments.json to Premiere format
- `mcp/adobe-premiere-mcp/jsx_runner.py` - Executes commands via proxy
- `mcp/adobe-premiere-mcp/premiere_tools.py` - High-level MCP tools

### ExtendScript Files (existing)
- `scripts/apply-cuts.jsx` - Timeline cut operations
- `scripts/batch-operations.jsx` - Full workflow operations

### UXP Plugin
- `mcp/adobe-premiere-mcp/uxp-plugins/premiere/` - Premiere Pro plugin

## Troubleshooting

### Plugin won't connect
1. Ensure proxy server is running (`node proxy.js`)
2. Check proxy is on port 3001
3. Reload plugin in UXP Developer Tools

### Commands timeout
1. Increase timeout: `PROXY_TIMEOUT=30 adobe-premiere`
2. Check Premiere Pro is responsive
3. Verify plugin shows "Connected" in UXP tools

### Import fails
1. Check file path is absolute
2. Verify file exists and is readable
3. Check Premiere supports the file format

### Cuts not applied
Note: The cut application feature requires additional UXP plugin implementation.
Currently, cuts are prepared but the actual timeline editing needs the UXP
`applyCuts` action to be added to `uxp-plugins/premiere/commands/index.js`.

## Future Enhancements

1. **UXP applyCuts Implementation** - Add native cut application to UXP plugin
2. **AME Export Integration** - Full sequence export via Adobe Media Encoder
3. **Real-time Preview** - Preview cuts before applying
4. **Batch Processing** - Process multiple videos in sequence
