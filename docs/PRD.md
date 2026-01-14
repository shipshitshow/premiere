# Premiere - Automated Video Processing & YouTube Upload Tool

## Product Requirements Document (PRD)

### Overview

Premiere is an automated video processing pipeline that takes raw video footage, enhances it, and uploads it to YouTube with AI-generated metadata. Built for content creators who want to streamline their publishing workflow.

### Problem Statement

Content creators spend hours on repetitive video editing tasks:
- Manually cutting silence and dead air
- Cleaning up video quality issues
- Improving audio levels and clarity
- Adding background music
- Writing titles, descriptions, and creating thumbnails
- Uploading to YouTube

This tool automates the entire workflow, reducing hours of work to minutes.

### Target Users

- Solo content creators
- Small YouTube channels
- Vibe coders documenting their work
- Anyone who records raw footage and wants quick publishing

---

## Core Features

### 1. Silence Detection & Removal
- **Input**: Raw video file (MP4, MOV, MKV, AVI, WEBM)
- **Process**: Detect audio segments below threshold (configurable dB level)
- **Output**: Video with silent sections removed, maintaining natural pacing
- **Options**:
  - Silence threshold (default: -40dB)
  - Minimum silence duration to cut (default: 0.5s)
  - Padding around cuts (default: 0.1s)

### 2. Video Cleanup
- **Process**:
  - Stabilization (remove shakiness)
  - Color correction/normalization
  - Resolution optimization
  - Frame rate normalization
- **Output**: Cleaned, professional-looking video
- **Options**:
  - Target resolution (1080p, 4K)
  - Target frame rate (30fps, 60fps)
  - Stabilization strength

### 3. Audio Enhancement
- **Process**:
  - Noise reduction (remove background hiss, hum)
  - Volume normalization (LUFS targeting for YouTube)
  - Compression/limiting for consistent levels
  - De-essing (reduce harsh S sounds)
  - EQ optimization for voice clarity
- **Output**: Broadcast-quality audio
- **Options**:
  - Target LUFS (-14 for YouTube)
  - Noise reduction aggressiveness
  - Voice enhancement level

### 4. Background Music
- **Process**:
  - Select appropriate royalty-free music from library
  - Auto-ducking (lower music during speech)
  - Fade in/out at video start/end
  - Match music energy to content
- **Output**: Video with background music that doesn't overpower speech
- **Options**:
  - Music genre/mood
  - Volume level relative to speech
  - Enable/disable auto-ducking

### 5. AI Metadata Generation
- **Process**:
  - Transcribe video content
  - Generate SEO-optimized title (multiple options)
  - Generate description with timestamps
  - Extract key moments for thumbnail candidates
  - Generate thumbnail with text overlay
- **Output**:
  - 3-5 title suggestions
  - Full description with chapters
  - Thumbnail image (1280x720)
- **Options**:
  - Target keywords
  - Tone (professional, casual, clickbait)
  - Include hashtags

### 6. YouTube Upload
- **Process**:
  - Authenticate with YouTube API
  - Upload video with generated metadata
  - Set as private (default) or scheduled
  - Add to playlist (optional)
- **Output**: Video uploaded to YouTube, ready for review
- **Options**:
  - Privacy status (private, unlisted, public)
  - Schedule time
  - Target playlist
  - Category
  - Tags

---

## Technical Requirements

### Dependencies
- **FFmpeg**: Core video/audio processing
- **Python 3.11+**: Main runtime
- **Libraries**:
  - `moviepy` or `ffmpeg-python`: Video manipulation
  - `pydub` or `pedalboard`: Audio processing
  - `whisper` or `faster-whisper`: Transcription
  - `openai` or `anthropic`: AI metadata generation
  - `google-api-python-client`: YouTube upload
  - `Pillow`: Thumbnail generation

### System Requirements
- macOS (primary), Linux (secondary)
- 8GB+ RAM for video processing
- GPU optional but recommended for transcription

### Configuration
- YAML-based config file
- Environment variables for API keys
- Per-project overrides supported

---

## Architecture

```
premiere/
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── pipeline.py          # Orchestration
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── silence.py       # Silence detection/removal
│   │   ├── video.py         # Video cleanup
│   │   ├── audio.py         # Audio enhancement
│   │   └── music.py         # Background music
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── metadata.py      # Title/description generation
│   │   └── thumbnail.py     # Thumbnail generation
│   ├── uploaders/
│   │   ├── __init__.py
│   │   └── youtube.py       # YouTube upload
│   └── utils/
│       ├── __init__.py
│       ├── config.py        # Configuration management
│       ├── ffmpeg.py        # FFmpeg wrapper
│       └── logger.py        # Logging
├── tests/
├── config/
│   └── default.yaml
├── music/                   # Royalty-free music library
├── pyproject.toml
└── README.md
```

---

## CLI Interface

```bash
# Full pipeline
premiere process video.mp4 --output processed.mp4 --upload

# Individual steps
premiere cut-silence video.mp4 --threshold -35
premiere enhance-audio video.mp4
premiere add-music video.mp4 --genre chill
premiere generate-metadata video.mp4
premiere upload video.mp4 --private

# Configuration
premiere config set youtube.channel_id UC123...
premiere config set ai.provider anthropic
```

---

## Success Metrics

- Process 1-hour raw video in under 10 minutes
- 90%+ accuracy on silence detection
- Audio passes YouTube loudness standards
- Generated titles achieve comparable CTR to manual titles
- Zero manual intervention required for basic workflow

---

## Constraints

- No cloud processing (all local for privacy)
- Royalty-free music only (no DMCA risk)
- YouTube API quotas (10,000 units/day default)
- Single video processing (no batch initially)

---

## Future Considerations (Out of Scope for v1)

- Batch processing multiple videos
- Multi-platform upload (TikTok, Instagram)
- Custom music generation with AI
- Automatic chapter detection
- A/B title testing integration
- Analytics dashboard
