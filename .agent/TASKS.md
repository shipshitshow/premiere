# Premiere - Implementation Tasks

## Phase 1: Project Foundation

### Task 1.1: Project Setup
- [x] Create directory structure
- [x] Write PRD document
- [ ] Initialize pyproject.toml with dependencies
- [ ] Set up ruff for linting/formatting
- [ ] Create base configuration system
- [ ] Set up logging utility

### Task 1.2: FFmpeg Integration
- [ ] Create FFmpeg wrapper utility
- [ ] Implement probe function (get video metadata)
- [ ] Implement basic transcode function
- [ ] Add error handling for missing FFmpeg
- [ ] Write unit tests

---

## Phase 2: Core Processors

### Task 2.1: Silence Detection & Removal
- [ ] Implement audio extraction from video
- [ ] Implement silence detection algorithm
  - Use FFmpeg silencedetect filter
  - Parse output for silence timestamps
- [ ] Implement segment cutting logic
- [ ] Implement video reassembly
- [ ] Add configurable thresholds
- [ ] Write tests with sample audio

### Task 2.2: Video Cleanup
- [ ] Implement video stabilization (FFmpeg vidstabdetect/vidstabtransform)
- [ ] Implement color normalization
- [ ] Implement resolution scaling
- [ ] Implement frame rate conversion
- [ ] Create quality presets (fast, balanced, quality)
- [ ] Write tests

### Task 2.3: Audio Enhancement
- [ ] Implement noise reduction (FFmpeg afftdn or anlmdn)
- [ ] Implement volume normalization (loudnorm filter)
- [ ] Implement compression/limiting
- [ ] Implement de-essing
- [ ] Implement EQ for voice clarity
- [ ] Target -14 LUFS for YouTube
- [ ] Write tests

### Task 2.4: Background Music
- [ ] Create music library structure
- [ ] Source 5-10 royalty-free tracks
- [ ] Implement music selection logic
- [ ] Implement auto-ducking (sidechain compression)
- [ ] Implement fade in/out
- [ ] Implement music/speech mixing
- [ ] Write tests

---

## Phase 3: AI Generators

### Task 3.1: Transcription
- [ ] Integrate faster-whisper for transcription
- [ ] Implement timestamp extraction
- [ ] Generate SRT/VTT subtitles
- [ ] Create transcript text for metadata generation
- [ ] Write tests

### Task 3.2: Metadata Generation
- [ ] Create AI prompt templates for titles
- [ ] Create AI prompt templates for descriptions
- [ ] Implement Anthropic API integration
- [ ] Generate multiple title options
- [ ] Generate description with chapters
- [ ] Extract keywords/tags
- [ ] Write tests

### Task 3.3: Thumbnail Generation
- [ ] Implement key frame extraction
- [ ] Implement face/subject detection for best frame
- [ ] Create thumbnail templates
- [ ] Implement text overlay
- [ ] Generate 1280x720 output
- [ ] Write tests

---

## Phase 4: YouTube Integration

### Task 4.1: YouTube API Setup
- [ ] Create Google Cloud project
- [ ] Enable YouTube Data API v3
- [ ] Implement OAuth2 flow
- [ ] Store/refresh credentials securely
- [ ] Write tests with mocks

### Task 4.2: Upload Implementation
- [ ] Implement resumable upload
- [ ] Set video metadata (title, description, tags)
- [ ] Set privacy status (private default)
- [ ] Set category and playlist
- [ ] Implement thumbnail upload
- [ ] Handle rate limits/quotas
- [ ] Write tests

---

## Phase 5: Pipeline & CLI

### Task 5.1: Pipeline Orchestration
- [ ] Create Pipeline class
- [ ] Implement step chaining
- [ ] Add progress reporting
- [ ] Implement temp file management
- [ ] Add error recovery/cleanup
- [ ] Write integration tests

### Task 5.2: CLI Implementation
- [ ] Set up Click/Typer CLI framework
- [ ] Implement `process` command (full pipeline)
- [ ] Implement individual step commands
- [ ] Implement `config` command
- [ ] Add progress bars (rich)
- [ ] Add --dry-run option
- [ ] Write CLI tests

---

## Phase 6: Polish

### Task 6.1: Configuration
- [ ] Create default.yaml config template
- [ ] Implement config file loading
- [ ] Implement env var overrides
- [ ] Implement per-project config
- [ ] Document all config options

### Task 6.2: Documentation
- [ ] Write README with quick start
- [ ] Document CLI commands
- [ ] Document configuration options
- [ ] Add example workflows
- [ ] Create demo video

### Task 6.3: Testing & Validation
- [ ] Run full pipeline on test videos
- [ ] Verify YouTube upload works
- [ ] Check audio meets LUFS standards
- [ ] Validate metadata generation quality
- [ ] Performance benchmarking

---

## Dependencies to Install

```toml
[project]
dependencies = [
    "ffmpeg-python>=0.2.0",
    "faster-whisper>=1.0.0",
    "anthropic>=0.40.0",
    "google-api-python-client>=2.0.0",
    "google-auth-oauthlib>=1.0.0",
    "Pillow>=10.0.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "pyyaml>=6.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.8.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
]
```

---

## Notes

- All processing is local (no cloud)
- FFmpeg must be installed separately (`brew install ffmpeg`)
- YouTube API requires OAuth consent (one-time setup)
- Anthropic API key required for metadata generation
- GPU acceleration optional but recommended for whisper
