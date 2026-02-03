# Premiere

Automated video processing pipeline with YouTube upload, viral clip generation, and review UI. Transform raw footage into polished, upload-ready content.

## Complete Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PREMIERE WORKFLOW                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. INGEST           2. PROCESS          3. REVIEW       4. UPLOAD  │
│  ┌──────────┐       ┌────────────┐      ┌──────────┐    ┌────────┐ │
│  │ YouTube  │──────▶│ Cut        │─────▶│ Streamlit│───▶│YouTube │ │
│  │ Download │       │ Silence    │      │ UI       │    │Upload  │ │
│  │ (yt-dlp) │       │ Enhance    │      │ Preview  │    │Private │ │
│  └──────────┘       │ Transcribe │      │ Edit     │    └────────┘ │
│       or            │ Clips      │      │ Approve  │               │
│  ┌──────────┐       │ Metadata   │      └──────────┘               │
│  │ Local    │       └────────────┘                                 │
│  │ File     │                                                      │
│  └──────────┘                                                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Features

- **YouTube Download**: Download videos with yt-dlp
- **Silence Removal**: Cut dead air automatically
- **Video Enhancement**: Stabilization, color correction
- **Audio Enhancement**: Noise reduction, -14 LUFS normalization
- **Transcription**: Whisper-powered with timestamps
- **Viral Clips**: AI detects best moments for Shorts (9:16)
- **AI Metadata**: Claude CLI generates titles, descriptions, tags
- **Thumbnail Generation**: Smart frame selection with text
- **Review UI**: Streamlit interface for preview and approval
- **YouTube Upload**: Private upload with full metadata

## Installation

```bash
# Python 3.11+ required
pip install -e .

# System dependencies
brew install ffmpeg yt-dlp

# Claude CLI for AI features
npm install -g @anthropic-ai/claude-code
```

## Quick Start

### Option 1: Full UI Workflow

```bash
# 1. Start the review UI
premiere ui

# 2. Add videos via sidebar (YouTube URL or upload)
# 3. Click "Process Pending" to process
# 4. Review output, edit metadata, select clips
# 5. Click "Approve" then "Upload Approved"
```

### Option 2: CLI Workflow

```bash
# Download and process
premiere download "https://youtube.com/watch?v=..." --process

# Or add to job queue
premiere add-job "https://youtube.com/watch?v=..."
premiere add-job ./local-video.mp4

# Process jobs
premiere worker --once

# List jobs
premiere jobs

# Launch UI for review
premiere ui
```

### Option 3: Direct Processing

```bash
# Full pipeline with clips
premiere process video.mp4 --clips --upload

# Individual steps
premiere transcribe video.mp4 --format md
premiere generate-clips video.mp4 --max 5
premiere generate-metadata video.mp4
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `ui` | Launch Streamlit review interface |
| `download` | Download video from YouTube |
| `add-job` | Add video to processing queue |
| `jobs` | List all jobs and their status |
| `worker` | Run background processor |
| `process` | Full pipeline (silence, enhance, metadata) |
| `transcribe` | Extract transcript (md, txt, json, srt) |
| `generate-clips` | Find viral moments and extract shorts |
| `generate-metadata` | AI titles/description via Claude CLI |
| `cut-silence` | Remove silent segments |
| `enhance-audio` | Noise reduction, normalization |
| `enhance-video` | Stabilization, color correction |
| `thumbnail` | Generate thumbnail with text overlay |
| `upload` | Upload to YouTube |
| `setup` | Configure YouTube API credentials |

## Review UI

The Streamlit UI provides:

- **Dashboard**: Overview of all jobs and their status
- **Video Preview**: Watch processed video before approval
- **Metadata Editor**: Edit titles, description, tags
- **Clips Gallery**: Preview and select viral clips
- **Transcript Viewer**: Read and download transcript
- **One-click Approval**: Approve and queue for upload

```bash
premiere ui --port 8501
```

## Job Status Flow

```
PENDING → DOWNLOADING → PROCESSING → REVIEW → APPROVED → UPLOADING → COMPLETED
                                        ↓                      ↓
                                      FAILED ←─────────────────┘
```

## Viral Clips

Clips are extracted as vertical 9:16 videos ready for Shorts/TikTok:

```bash
premiere generate-clips video.mp4 --max 5 --min-duration 15 --max-duration 60
```

Each clip includes:
- Vertical 1080x1920 MP4
- AI-generated title and caption
- Hashtags for discovery
- Transcript text

## Configuration

Edit `config/default.yaml`:

```yaml
silence:
  threshold_db: -40
  min_duration: 0.5

audio:
  target_lufs: -14
  noise_reduction: true

ai:
  transcription_model: "base"
  title_count: 5
  tone: "professional"

youtube:
  privacy: "private"
  category: "22"
```

## Output Structure

```
~/.premiere/
├── jobs/
│   └── jobs.json           # Job queue
└── output/
    └── {job_id}/
        ├── source.mp4      # Downloaded video
        ├── source_processed.mp4
        ├── source_transcript.md
        ├── source_thumbnail.jpg
        └── source_clips/
            ├── clip_01_120s.mp4
            ├── clip_02_340s.mp4
            └── manifest.json
```

## Requirements

- Python 3.11+
- FFmpeg with libx264
- yt-dlp (for YouTube download)
- Claude CLI (for AI features)
- Google OAuth credentials (for upload)

## YouTube API Setup

1. [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → Enable YouTube Data API v3
3. Create OAuth 2.0 credentials (Desktop app)
4. Download JSON → `~/.premiere/client_secrets.json`
5. Run `premiere setup`
