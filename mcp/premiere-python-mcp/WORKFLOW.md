# Premiere Python MCP Video Editing Workflow

## Quick Start Checklist

1. **Start proxy server**: `cd ../adobe-premiere-mcp/proxy-server && node proxy.js`
2. **Connect UXP plugin**: Open UXP Developer Tools in Premiere, click Connect
3. **Verify connection**: Run `get_project_info` — should return active sequence
4. **Premiere must be in focus** when cuts are executed (AppleScript sends keystrokes)

## Cutting Segments from a Livestream

### Step 1: Read the transcript

Load the JSON transcript file (e.g. `assets/260324 - livestream.json`).
Structure: `{ language, segments: [{ start, duration, words: [{ text, start }] }], speakers }`

Extract text with timestamps to understand the content.

### Step 2: Plan the video

From the transcript, identify segments to KEEP based on the video topic.
Create a timeline plan with source timestamps for each section.

Example (10-min video):
```
| Section              | Source Start | Source End |
|----------------------|-------------|-----------|
| Hook                 | 3:04 (184s) | 3:37 (217s) |
| What Are Channels    | 4:25 (265s) | 5:20 (320s) |
| Setup & How It Works | 5:47 (347s) | 6:58 (418s) |
| ...                  | ...         | ...       |
```

### Step 3: Invert to get removal segments

Convert KEEP segments into REMOVE segments (the gaps between keeps + head/tail).

```
Remove: 0-184, 217-265, 320-347, 418-489, ...
```

### Step 4: Cut using remove_silence_segments

**THIS IS THE ONLY TOOL THAT WORKS FOR CUTTING. DO NOT USE:**
- `split_video_clip` / `split_audio_clip` — desyncs video and audio
- `remove_linked_clip_range` — audio doesn't follow video ripple
- `batch_split_clips` — fails entirely
- `cut_at_playhead` — AppleScript timeout issues

**Use `remove_silence_segments`:**
```json
{
  "sequence_id": "<active-sequence-id>",
  "silence_segments": [
    {"start": 0, "end": 184},
    {"start": 217, "end": 265},
    {"start": 320, "end": 347}
  ]
}
```

- Processes end-to-start automatically
- Uses Premiere's native Extract command (';' key via AppleScript)
- Keeps video + audio perfectly in sync
- **Premiere MUST be the front/active window** when this runs

### Step 5: Handle partial failures

If the MCP connection drops mid-operation:
1. Restart proxy server if needed: `lsof -i :3001` to check, then `node proxy.js`
2. Reconnect UXP plugin in Premiere
3. Run `get_full_project_data` to see which clips exist
4. Count how many segments were already cut
5. Re-run `remove_silence_segments` with only the remaining segments

### Step 6: User closes gaps

After all cuts, the timeline has the correct segments with gaps between them.
The user manually closes gaps in Premiere (ripple delete gaps or drag clips together).

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Could not connect to premiere command proxy server` | Start proxy: `cd ../adobe-premiere-mcp/proxy-server && node proxy.js` |
| `Connection closed` / MCP tools disappear | Proxy crashed or session dropped — restart proxy, reconnect UXP, restart Claude Code session |
| `remove_silence_segments` reports success but nothing changes | Premiere was not in focus — bring Premiere to front and retry |
| AppleScript timeout | Check Accessibility permissions: Claude, osascript, terminal app all need access |
| Video/audio out of sync | Wrong tool was used — undo everything, use only `remove_silence_segments` |

## Project Structure

```
premiere/mcp/
├── adobe-premiere-mcp/
│   ├── proxy-server/proxy.js    # WebSocket bridge (port 3001)
│   ├── uxp-plugins/premiere/    # UXP plugin for Premiere
│   └── adobe_mcp/premiere/      # MCP server (Python)
└── premiere-python-mcp/
    ├── server.py                # Video processing MCP server
    └── tools/                   # FFmpeg-based tools
```
