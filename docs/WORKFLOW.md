# Premiere Workflow Guide

Complete guide for processing videos from source to YouTube upload.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              VIDEO WORKFLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   SOURCE                PROCESS              REVIEW              PUBLISH    │
│   ──────                ───────              ──────              ───────    │
│                                                                             │
│   ┌─────────┐          ┌─────────┐         ┌─────────┐        ┌─────────┐  │
│   │YouTube  │    ┌────▶│Cut      │───┐     │Preview  │   ┌───▶│YouTube  │  │
│   │URL      │────┤     │Silence  │   │     │Video    │   │    │Private  │  │
│   └─────────┘    │     └─────────┘   │     └─────────┘   │    └─────────┘  │
│                  │                   │           │       │                  │
│   ┌─────────┐    │     ┌─────────┐   │     ┌─────────┐   │    ┌─────────┐  │
│   │Local    │────┤     │Enhance  │───┼────▶│Edit     │───┼───▶│Shorts   │  │
│   │File     │    │     │Audio    │   │     │Metadata │   │    │TikTok   │  │
│   └─────────┘    │     └─────────┘   │     └─────────┘   │    └─────────┘  │
│                  │                   │           │       │                  │
│   ┌─────────┐    │     ┌─────────┐   │     ┌─────────┐   │                  │
│   │Screen   │────┘     │Generate │───┘     │Approve/ │───┘                  │
│   │Record   │          │Clips    │         │Reject   │                      │
│   └─────────┘          └─────────┘         └─────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Get Your Video

### Option A: Download from YouTube

Use this to repurpose existing content, create reaction videos, or re-edit your own uploads.

```bash
# Basic download
premiere download "https://youtube.com/watch?v=VIDEO_ID"

# Download with specific quality
premiere download "https://youtube.com/watch?v=VIDEO_ID" --quality 1080

# Download and immediately process
premiere download "https://youtube.com/watch?v=VIDEO_ID" --process

# Download to specific folder
premiere download "https://youtube.com/watch?v=VIDEO_ID" --output ./videos/
```

**Supported URL formats:**
- `https://youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://youtube.com/shorts/VIDEO_ID`

### Option B: Use Local File

For screen recordings, camera footage, or files already on your machine.

```bash
# Add to job queue
premiere add-job ./my-recording.mp4

# Or process directly
premiere process ./my-recording.mp4 --clips
```

**Supported formats:** MP4, MOV, MKV, AVI, WEBM

### Option C: Via the UI

```bash
# Start the UI
premiere ui
```

Then in the sidebar:
1. Select "YouTube" or "Local File"
2. Paste URL or upload file
3. Click "Add from YouTube" / "Add Local File"

---

## Step 2: Process the Video

### Automatic Processing (Recommended)

```bash
# Process with full pipeline + viral clips
premiere process video.mp4 --clips

# Skip certain steps if needed
premiere process video.mp4 --skip-silence --clips
premiere process video.mp4 --skip-video --clips
premiere process video.mp4 --skip-audio --clips
```

### What Processing Does

| Step | What Happens |
|------|--------------|
| **Cut Silence** | Detects audio below -40dB, removes dead air |
| **Enhance Video** | Stabilization, color correction, scaling to 1080p |
| **Enhance Audio** | Noise reduction, normalize to -14 LUFS (YouTube standard) |
| **Transcribe** | Whisper extracts text with timestamps |
| **Generate Clips** | Claude CLI finds viral moments, extracts 9:16 shorts |
| **Generate Metadata** | Claude CLI creates titles, description, tags |
| **Generate Thumbnail** | Selects best frame, adds text overlay |

### Using the Job Queue

For batch processing or background work:

```bash
# Add multiple jobs
premiere add-job "https://youtube.com/watch?v=VIDEO1"
premiere add-job "https://youtube.com/watch?v=VIDEO2"
premiere add-job ./local-video.mp4

# Check queue
premiere jobs

# Process all pending jobs
premiere worker

# Or process just one
premiere worker --once
```

---

## Step 3: Review in UI

```bash
premiere ui
```

### Dashboard View

Shows all jobs with status indicators:
- ⏳ Pending - Waiting to be processed
- ⚙️ Processing - Currently being processed
- 👀 Review - Ready for your review
- ✅ Approved - Approved, waiting for upload
- 🎉 Completed - Uploaded to YouTube
- ❌ Failed - Error occurred

### Review a Video

1. Click on a job in the sidebar
2. **Watch the preview** - Full processed video player
3. **Edit metadata:**
   - Select from AI-generated titles or write custom
   - Edit description
   - Add/remove tags
4. **Review clips:**
   - Watch each viral clip
   - Select which to upload
5. **Check transcript:**
   - Read full transcript
   - Download as markdown

### Approve or Reject

- **Approve**: Moves to upload queue
- **Reject**: Marks as failed, won't upload
- **Reprocess**: Start processing again

---

## Step 4: Upload to YouTube

### From the UI

1. Videos with ✅ status are ready
2. Click "Upload Approved" in sidebar
3. Videos upload as **private** by default

### From CLI

```bash
# Upload a single processed video
premiere upload ./video_processed.mp4 --title "My Video" --privacy private

# Run worker to upload all approved
premiere worker
```

### Privacy Options

- `private` - Only you can see (default)
- `unlisted` - Anyone with link can see
- `public` - Published to your channel

---

## Complete Examples

### Example 1: Quick Repurpose

Download a video, process it, review, and upload:

```bash
# Download and process in one command
premiere download "https://youtube.com/watch?v=abc123" --process

# Open UI to review
premiere ui

# In UI: Review → Approve → Upload
```

### Example 2: Batch Processing

Process multiple videos overnight:

```bash
# Add all videos to queue
premiere add-job "https://youtube.com/watch?v=video1"
premiere add-job "https://youtube.com/watch?v=video2"
premiere add-job ./recording1.mp4
premiere add-job ./recording2.mp4

# Start worker (runs until stopped)
premiere worker

# Next day: open UI to review all
premiere ui
```

### Example 3: Just Generate Clips

Only extract viral clips from a long video:

```bash
# Generate 5 clips, 15-60 seconds each
premiere generate-clips ./long-video.mp4 --max 5

# Output in ./long-video_clips/
# - clip_01_120s.mp4 (vertical 9:16)
# - clip_02_340s.mp4
# - manifest.json (titles, captions, hashtags)
```

### Example 4: Manual Step-by-Step

Full control over each step:

```bash
# 1. Download
premiere download "https://youtube.com/watch?v=abc123" -o ./project/

# 2. Cut silence only
premiere cut-silence ./project/video.mp4

# 3. Enhance audio
premiere enhance-audio ./project/video_no_silence.mp4

# 4. Get transcript
premiere transcribe ./project/video_no_silence_enhanced_audio.mp4 -f md

# 5. Generate metadata
premiere generate-metadata ./project/video_no_silence_enhanced_audio.mp4

# 6. Create thumbnail
premiere thumbnail ./project/video_no_silence_enhanced_audio.mp4 -t "My Title"

# 7. Upload
premiere upload ./project/video_no_silence_enhanced_audio.mp4 --privacy private
```

---

## Output Files

After processing, you'll have:

```
video_processed.mp4          # Main video (silence removed, enhanced)
video_transcript.md          # Full transcript with timestamps
video_thumbnail.jpg          # Generated thumbnail (1280x720)
video_clips/                 # Viral clips folder
├── clip_01_120s.mp4        # Vertical 1080x1920
├── clip_02_340s.mp4
├── clip_03_520s.mp4
└── manifest.json           # Metadata for each clip
```

### Manifest Format

```json
{
  "clips": [
    {
      "file": "clip_01_120s.mp4",
      "start": 120.5,
      "end": 165.2,
      "duration": 44.7,
      "title": "The moment everything changed",
      "caption": "This is the part nobody expected 🔥",
      "hashtags": ["#viral", "#shorts", "#mindblown"],
      "transcript": "And that's when I realized..."
    }
  ]
}
```

---

## Troubleshooting

### Video won't download

```bash
# Update yt-dlp
brew upgrade yt-dlp

# Or with pip
pip install -U yt-dlp
```

### Processing fails

Check FFmpeg is installed:
```bash
ffmpeg -version
```

### Claude CLI errors

Make sure you're authenticated:
```bash
claude --version
claude "test"
```

### YouTube upload fails

1. Check credentials exist: `~/.premiere/client_secrets.json`
2. Re-authenticate: `premiere setup`
3. Check API quota at [Google Cloud Console](https://console.cloud.google.com/)

---

## Tips

1. **Start with private uploads** - Always upload as private first, then manually publish after final review on YouTube

2. **Use clips for Shorts** - The generated clips are already 9:16 vertical, perfect for YouTube Shorts

3. **Edit metadata in UI** - The AI generates good options, but personalize before upload

4. **Check audio levels** - Processing normalizes to -14 LUFS, YouTube's recommended loudness

5. **Batch overnight** - Add all jobs, run worker, review in morning
