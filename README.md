# Premiere Hybrid Editing System

A unified system for video editing combining:
- **Python App** - Automated "run once and done" processing
- **Adobe MCP** - Claude-controlled manual editing in Premiere Pro
- **ExtendScripts** - Adobe automation inside Premiere

## Project Structure

```
premiere/
├── app/                          # Python video processor
│   ├── src/premiere/
│   │   ├── processors/           # Silence, audio, video processors
│   │   ├── generators/           # Clips, metadata, thumbnails
│   │   ├── uploaders/            # YouTube upload
│   │   └── utils/                # FFmpeg, Claude CLI wrappers
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
│
├── mcp/                          # MCP servers for Claude Code
│   ├── premiere-mcp/             # Control Python app via MCP
│   │   ├── server.py
│   │   └── tools/
│   └── adobe-mcp/                # Control Adobe Premiere Pro
│
└── scripts/                      # ExtendScript for Adobe automation
    ├── import-media.jsx
    ├── create-sequence.jsx
    ├── apply-cuts.jsx
    ├── add-markers.jsx
    ├── export-sequence.jsx
    └── batch-operations.jsx
```

## Two Workflows

### Workflow A: Automated Processing (Python App)

Use when you want to process a video and be done with it.

```bash
# Process video through full pipeline
cd app && premiere process ~/Videos/livestream.mp4

# Or with specific options
premiere process video.mp4 --clips --max-clips 5 --upload
```

Via Claude Code with MCP:
```
"Process my livestream and find viral clips"
→ premiere_process + premiere_detect_clips
```

### Workflow B: Creative Editing (Adobe MCP)

Use when you need manual control, preview, or creative decisions.

```
"Open this in Premiere and show me the timeline"
→ adobe_create_project + adobe_import_media

"Cut at 5:32 and add a transition"
→ Claude sends commands to Premiere
→ You see changes live
```

## Setup

### 1. Python App

```bash
cd app
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Verify installation
premiere --version
premiere info ~/Videos/test.mp4
```

### 2. premiere-mcp (MCP Server)

```bash
cd mcp/premiere-mcp
pip install -e .
```

Add to Claude Code settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "premiere": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "server"],
      "cwd": "~/www/VincentShipsIt/premiere/mcp/premiere-mcp"
    }
  }
}
```

### 3. adobe-mcp (Optional)

See [mcp/adobe-mcp/README.md](mcp/adobe-mcp/README.md) for setup instructions.

## MCP Tools

### premiere (Python App)

| Tool | Purpose |
|------|---------|
| `premiere_info` | Get video file information |
| `premiere_download` | Download from YouTube |
| `premiere_detect_segments` | Analyze silence/speech |
| `premiere_detect_clips` | Find viral moments with AI |
| `premiere_process` | Run automated pipeline |
| `premiere_cut_silence` | Remove silence from video |
| `premiere_enhance_audio` | Improve audio quality |
| `premiere_transcribe` | Transcribe audio to text |
| `premiere_export` | Export processed video |
| `premiere_export_clips` | Export multiple clips |

### adobe-premiere (Premiere Pro)

| Tool | Purpose |
|------|---------|
| `adobe_create_project` | Create new Premiere project |
| `adobe_import_media` | Import files into project |
| `adobe_create_sequence` | Create timeline |
| `adobe_insert_clip` | Add clip to timeline |
| `adobe_apply_effect` | Apply video/audio effect |
| `adobe_add_marker` | Add marker at timestamp |
| `adobe_export` | Export sequence |

## ExtendScripts

Scripts in `scripts/` can be called by adobe-mcp or run directly in Premiere:

- **import-media.jsx** - Import files into project bins
- **create-sequence.jsx** - Create sequences from presets
- **apply-cuts.jsx** - Remove silence segments from timeline
- **add-markers.jsx** - Add markers for clips, chapters
- **export-sequence.jsx** - Queue exports to Media Encoder
- **batch-operations.jsx** - Combined workflows

## Example Workflows

### Quick Automated Edit

```bash
# Download and process in one go
premiere download "https://youtube.com/..." --process

# Process local file with clips
premiere process video.mp4 --clips --max-clips 5
```

### Via Claude Code

```
"Download my livestream from [URL] and remove silence"
"What clips did it find? Export 1, 3, and 5"
"Open the processed video in Premiere for fine-tuning"
```

### Fine-Tuning in Premiere

```
"Add a crossfade at 10:32"
"Mark chapters at 0:00, 5:23, 12:45"
"Export just the intro section (0:00-2:30)"
```

## Dependencies

- Python 3.11+
- FFmpeg
- OpenAI Whisper (for transcription)
- yt-dlp (for downloads)
- Adobe Premiere Pro (for adobe-mcp workflow)
