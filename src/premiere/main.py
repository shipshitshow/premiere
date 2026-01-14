"""Premiere CLI - Video processing pipeline."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from premiere import __version__
from premiere.pipeline import Pipeline, PipelineStep
from premiere.utils.config import get_config, load_config, set_config
from premiere.utils.logger import setup_logger


app = typer.Typer(
    name="premiere",
    help="Automated video processing pipeline with YouTube upload",
    add_completion=False,
)

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"[bold]Premiere[/bold] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Enable verbose output"),
    ] = False,
    config: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", help="Path to config file"),
    ] = None,
):
    """Premiere - Automated video processing pipeline."""
    level = "DEBUG" if verbose else "INFO"
    setup_logger(level=level)

    if config:
        set_config(load_config(config))


@app.command()
def process(
    video: Annotated[Path, typer.Argument(help="Input video file")],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output video path"),
    ] = None,
    upload: Annotated[
        bool,
        typer.Option("--upload", "-u", help="Upload to YouTube"),
    ] = False,
    clips: Annotated[
        bool,
        typer.Option("--clips", help="Generate viral clips for shorts"),
    ] = False,
    max_clips: Annotated[
        int,
        typer.Option("--max-clips", help="Max number of clips to generate"),
    ] = 5,
    skip_silence: Annotated[
        bool,
        typer.Option("--skip-silence", help="Skip silence removal"),
    ] = False,
    skip_video: Annotated[
        bool,
        typer.Option("--skip-video", help="Skip video enhancement"),
    ] = False,
    skip_audio: Annotated[
        bool,
        typer.Option("--skip-audio", help="Skip audio enhancement"),
    ] = False,
):
    """Process video through the full pipeline."""
    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    # Determine steps to run
    steps = [s for s in PipelineStep if s != PipelineStep.GENERATE_CLIPS]
    if skip_silence:
        steps.remove(PipelineStep.CUT_SILENCE)
    if skip_video:
        steps.remove(PipelineStep.ENHANCE_VIDEO)
    if skip_audio:
        steps.remove(PipelineStep.ENHANCE_AUDIO)

    console.print(Panel(f"[bold]Processing:[/bold] {video.name}"))

    pipeline = Pipeline(steps=steps)
    result = pipeline.run(video, output, upload=upload, generate_clips=clips, max_clips=max_clips)

    # Display results
    if result.errors:
        console.print("\n[yellow]Warnings:[/yellow]")
        for error in result.errors:
            console.print(f"  • {error}")

    if result.output_path:
        console.print(f"\n[green]✓[/green] Output: {result.output_path}")

    if result.transcript_path:
        console.print(f"[green]✓[/green] Transcript: {result.transcript_path}")

    if result.clips:
        console.print(f"\n[bold]Generated {len(result.clips)} Clips:[/bold]")
        for clip in result.clips:
            console.print(f"  • {clip.path.name} ({clip.end - clip.start:.1f}s)")
        if result.clips_dir:
            console.print(f"  → Clips directory: {result.clips_dir}")

    if result.metadata:
        console.print("\n[bold]Generated Titles:[/bold]")
        for i, title in enumerate(result.metadata.titles[:3], 1):
            console.print(f"  {i}. {title}")

    if result.upload_result:
        console.print(f"\n[green]✓[/green] Uploaded: {result.upload_result['url']}")


@app.command()
def transcribe(
    video: Annotated[Path, typer.Argument(help="Input video file")],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output transcript path"),
    ] = None,
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format (md, txt, json, srt)"),
    ] = "md",
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Whisper model size"),
    ] = "base",
):
    """Transcribe video audio to text."""
    from premiere.generators.transcription import generate_srt, save_transcript, transcribe_video

    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    console.print(f"Transcribing {video.name} with whisper-{model}...")
    transcript = transcribe_video(video, model)

    # Determine output path
    ext = "srt" if format == "srt" else format
    output = output or video.parent / f"{video.stem}_transcript.{ext}"

    if format == "srt":
        generate_srt(transcript, output)
    else:
        save_transcript(transcript, output, format)

    console.print(f"\n[green]✓[/green] Transcript: {output}")
    console.print(f"  Language: {transcript.language}")
    console.print(f"  Segments: {len(transcript.segments)}")
    console.print(f"  Characters: {len(transcript.full_text)}")


@app.command("generate-clips")
def generate_clips_cmd(
    video: Annotated[Path, typer.Argument(help="Input video file")],
    output_dir: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output directory for clips"),
    ] = None,
    max_clips: Annotated[
        int,
        typer.Option("--max", "-n", help="Maximum number of clips"),
    ] = 5,
    min_duration: Annotated[
        int,
        typer.Option("--min-duration", help="Minimum clip duration (seconds)"),
    ] = 15,
    max_duration: Annotated[
        int,
        typer.Option("--max-duration", help="Maximum clip duration (seconds)"),
    ] = 60,
    horizontal: Annotated[
        bool,
        typer.Option("--horizontal", help="Keep horizontal format (default: vertical 9:16)"),
    ] = False,
):
    """Generate viral short clips from video."""
    from premiere.generators.clips import detect_viral_moments, extract_clips, save_clips_manifest
    from premiere.generators.transcription import transcribe_video
    from premiere.utils.ffmpeg import probe

    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    output_dir = output_dir or video.parent / f"{video.stem}_clips"

    console.print(f"Analyzing {video.name} for viral moments...")

    # Get video info
    info = probe(video)

    # Transcribe
    console.print("Transcribing video...")
    transcript = transcribe_video(video)

    # Detect viral moments using Claude CLI
    console.print("Detecting viral moments with AI...")
    candidates = detect_viral_moments(
        transcript,
        info.duration,
        max_clips=max_clips,
        min_duration=min_duration,
        max_duration=max_duration,
    )

    if not candidates:
        console.print("[yellow]No viral moments detected[/yellow]")
        raise typer.Exit(0)

    console.print(f"\nFound {len(candidates)} viral moments:")
    for i, clip in enumerate(candidates, 1):
        console.print(f"  {i}. [{clip.start:.0f}s-{clip.end:.0f}s] Score: {clip.score}/10")
        if clip.hook:
            console.print(f"     Hook: \"{clip.hook[:50]}...\"" if len(clip.hook) > 50 else f"     Hook: \"{clip.hook}\"")

    # Extract clips
    console.print(f"\nExtracting clips to {output_dir}...")
    clips = extract_clips(
        video,
        candidates,
        output_dir,
        transcript,
        vertical=not horizontal,
    )

    # Save manifest
    save_clips_manifest(clips, output_dir / "manifest.json")

    console.print(f"\n[green]✓[/green] Generated {len(clips)} clips:")
    for clip in clips:
        console.print(f"  • {clip.path.name}")
    console.print(f"\n  Manifest: {output_dir / 'manifest.json'}")


@app.command("cut-silence")
def cut_silence_cmd(
    video: Annotated[Path, typer.Argument(help="Input video file")],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output video path"),
    ] = None,
    threshold: Annotated[
        float,
        typer.Option("--threshold", "-t", help="Silence threshold in dB"),
    ] = -40,
    min_duration: Annotated[
        float,
        typer.Option("--min-duration", "-d", help="Minimum silence duration"),
    ] = 0.5,
):
    """Remove silence from video."""
    from premiere.processors.silence import cut_silence

    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    output = output or video.parent / f"{video.stem}_no_silence.mp4"

    console.print(f"Cutting silence from {video.name}...")
    cut_silence(video, output, threshold, min_duration)
    console.print(f"[green]✓[/green] Output: {output}")


@app.command("enhance-audio")
def enhance_audio_cmd(
    video: Annotated[Path, typer.Argument(help="Input video file")],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output video path"),
    ] = None,
):
    """Enhance audio quality."""
    from premiere.processors.audio import enhance_audio

    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    output = output or video.parent / f"{video.stem}_enhanced_audio.mp4"

    console.print(f"Enhancing audio in {video.name}...")
    enhance_audio(video, output)
    console.print(f"[green]✓[/green] Output: {output}")


@app.command("enhance-video")
def enhance_video_cmd(
    video: Annotated[Path, typer.Argument(help="Input video file")],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output video path"),
    ] = None,
    resolution: Annotated[
        str,
        typer.Option("--resolution", "-r", help="Target resolution"),
    ] = "1080p",
):
    """Enhance video quality."""
    from premiere.processors.video import enhance_video
    from premiere.utils.config import VideoConfig

    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    output = output or video.parent / f"{video.stem}_enhanced_video.mp4"
    config = VideoConfig(target_resolution=resolution)

    console.print(f"Enhancing video {video.name}...")
    enhance_video(video, output, config)
    console.print(f"[green]✓[/green] Output: {output}")


@app.command("add-music")
def add_music_cmd(
    video: Annotated[Path, typer.Argument(help="Input video file")],
    music: Annotated[
        Optional[Path],
        typer.Option("--music", "-m", help="Music file (auto-select if not provided)"),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output video path"),
    ] = None,
    volume: Annotated[
        float,
        typer.Option("--volume", "-v", help="Music volume in dB"),
    ] = -20,
):
    """Add background music to video."""
    from premiere.processors.music import add_background_music
    from premiere.utils.config import MusicConfig

    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    output = output or video.parent / f"{video.stem}_with_music.mp4"
    config = MusicConfig(enabled=True, volume_db=volume)

    console.print(f"Adding music to {video.name}...")
    add_background_music(video, output, music, config)
    console.print(f"[green]✓[/green] Output: {output}")


@app.command("generate-metadata")
def generate_metadata_cmd(
    video: Annotated[Path, typer.Argument(help="Input video file")],
    transcript: Annotated[
        Optional[Path],
        typer.Option("--transcript", "-t", help="Use existing transcript file"),
    ] = None,
):
    """Generate YouTube metadata (title, description, tags) using Claude CLI."""
    from premiere.generators.metadata import generate_metadata
    from premiere.generators.transcription import Transcript, transcribe_video

    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    if transcript and transcript.exists():
        console.print(f"Using existing transcript: {transcript}")
        # For now, transcribe anyway - could parse transcript file in future
        console.print("Transcribing video...")
        trans = transcribe_video(video)
    else:
        console.print(f"Transcribing {video.name}...")
        trans = transcribe_video(video)

    console.print("Generating metadata with Claude CLI...")
    metadata = generate_metadata(trans, video, use_claude_cli=True)

    console.print("\n[bold]Title Options:[/bold]")
    for i, title in enumerate(metadata.titles, 1):
        console.print(f"  {i}. {title}")

    console.print("\n[bold]Description:[/bold]")
    desc = metadata.description
    console.print(desc[:500] + "..." if len(desc) > 500 else desc)

    console.print(f"\n[bold]Tags:[/bold] {', '.join(metadata.tags[:10])}")

    if metadata.hashtags:
        console.print(f"\n[bold]Hashtags:[/bold] {' '.join(metadata.hashtags)}")


@app.command("thumbnail")
def thumbnail_cmd(
    video: Annotated[Path, typer.Argument(help="Input video file")],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output thumbnail path"),
    ] = None,
    title: Annotated[
        Optional[str],
        typer.Option("--title", "-t", help="Title text overlay"),
    ] = None,
):
    """Generate thumbnail from video."""
    from premiere.generators.thumbnail import generate_thumbnail

    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    output = output or video.parent / f"{video.stem}_thumbnail.jpg"

    console.print(f"Generating thumbnail for {video.name}...")
    generate_thumbnail(video, output, title)
    console.print(f"[green]✓[/green] Output: {output}")


@app.command()
def upload(
    video: Annotated[Path, typer.Argument(help="Input video file")],
    title: Annotated[
        Optional[str],
        typer.Option("--title", "-t", help="Video title"),
    ] = None,
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="Video description"),
    ] = None,
    thumbnail: Annotated[
        Optional[Path],
        typer.Option("--thumbnail", help="Thumbnail image"),
    ] = None,
    privacy: Annotated[
        str,
        typer.Option("--privacy", "-p", help="Privacy status"),
    ] = "private",
):
    """Upload video to YouTube."""
    from premiere.generators.metadata import VideoMetadata
    from premiere.uploaders.youtube import upload_video
    from premiere.utils.config import YouTubeConfig

    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    # Create metadata
    metadata = VideoMetadata(
        titles=[title or video.stem],
        description=description or "",
        tags=[],
        chapters=[],
    )

    config = YouTubeConfig(privacy=privacy)

    console.print(f"Uploading {video.name} to YouTube...")
    result = upload_video(video, metadata, thumbnail, config)

    console.print(f"\n[green]✓[/green] Uploaded: {result['url']}")
    console.print(f"  Status: {result['status']}")


@app.command()
def setup():
    """Set up YouTube API credentials."""
    from premiere.uploaders.youtube import setup_credentials

    setup_credentials()


@app.command()
def info(
    video: Annotated[Path, typer.Argument(help="Input video file")],
):
    """Show video file information."""
    from premiere.utils.ffmpeg import probe

    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    video_info = probe(video)

    table = Table(title=f"Video Info: {video.name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Duration", f"{video_info.duration:.2f}s")
    table.add_row("Resolution", f"{video_info.width}x{video_info.height}")
    table.add_row("Frame Rate", f"{video_info.fps:.2f} fps")
    table.add_row("Video Codec", video_info.video_codec)
    table.add_row("Audio Codec", video_info.audio_codec or "N/A")
    table.add_row("File Size", f"{video_info.file_size / 1024 / 1024:.2f} MB")
    table.add_row("Bitrate", f"{video_info.bitrate / 1000:.0f} kbps")

    console.print(table)


@app.command()
def ui(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to run UI on"),
    ] = 8501,
):
    """Launch the Streamlit review UI."""
    import subprocess
    import sys

    ui_path = Path(__file__).parent / "ui.py"

    console.print(f"[bold]Starting Premiere UI[/bold] on http://localhost:{port}")
    console.print("Press Ctrl+C to stop\n")

    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(ui_path),
        "--server.port", str(port),
        "--server.headless", "true",
    ])


@app.command()
def download(
    url: Annotated[str, typer.Argument(help="YouTube video URL")],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output directory"),
    ] = None,
    quality: Annotated[
        str,
        typer.Option("--quality", "-q", help="Video quality (best, 1080, 720, 480)"),
    ] = "best",
    process_now: Annotated[
        bool,
        typer.Option("--process", "-p", help="Process video after download"),
    ] = False,
):
    """Download video from YouTube."""
    from premiere.downloaders.youtube_dl import download_video, get_video_info

    output = output or Path.cwd()

    console.print(f"Fetching video info...")
    info = get_video_info(url)

    console.print(f"\n[bold]{info.title}[/bold]")
    console.print(f"  Channel: {info.channel}")
    console.print(f"  Duration: {info.duration // 60}:{info.duration % 60:02d}")

    console.print(f"\nDownloading ({quality} quality)...")
    video_path = download_video(url, output, quality=quality)

    console.print(f"[green]✓[/green] Downloaded: {video_path}")

    if process_now:
        console.print("\nProcessing video...")
        pipeline = Pipeline()
        result = pipeline.run(video_path, generate_clips=True)

        if result.output_path:
            console.print(f"[green]✓[/green] Processed: {result.output_path}")


@app.command()
def jobs(
    status: Annotated[
        Optional[str],
        typer.Option("--status", "-s", help="Filter by status"),
    ] = None,
):
    """List processing jobs."""
    from premiere.jobs import JobStatus, get_queue

    queue = get_queue()
    job_list = queue.list_jobs()

    if status:
        try:
            filter_status = JobStatus(status.lower())
            job_list = [j for j in job_list if j.status == filter_status]
        except ValueError:
            console.print(f"[red]Invalid status:[/red] {status}")
            raise typer.Exit(1)

    if not job_list:
        console.print("No jobs found.")
        return

    table = Table(title="Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Status")
    table.add_column("Title")
    table.add_column("Created")

    status_colors = {
        "pending": "yellow",
        "downloading": "blue",
        "processing": "blue",
        "review": "magenta",
        "approved": "green",
        "uploading": "blue",
        "completed": "green",
        "failed": "red",
    }

    for job in job_list:
        color = status_colors.get(job.status.value, "white")
        table.add_row(
            job.id,
            f"[{color}]{job.status.value}[/{color}]",
            (job.title[:40] + "...") if len(job.title) > 40 else job.title,
            job.created_at[:16],
        )

    console.print(table)


@app.command("add-job")
def add_job(
    source: Annotated[str, typer.Argument(help="YouTube URL or local file path")],
):
    """Add a new job to the queue."""
    from premiere.jobs import get_queue

    queue = get_queue()

    if source.startswith("http"):
        job = queue.create_job(source_type="youtube", source_url=source)
        console.print(f"[green]✓[/green] Added YouTube job: {job.id}")
    else:
        path = Path(source)
        if not path.exists():
            console.print(f"[red]Error:[/red] File not found: {source}")
            raise typer.Exit(1)
        job = queue.create_job(source_type="local", source_path=str(path), title=path.stem)
        console.print(f"[green]✓[/green] Added local job: {job.id}")

    console.print(f"  Run 'premiere ui' to review, or 'premiere worker' to process.")


@app.command()
def worker(
    once: Annotated[
        bool,
        typer.Option("--once", help="Process one job and exit"),
    ] = False,
):
    """Run the background worker to process jobs."""
    from premiere.worker import Worker as JobWorker

    w = JobWorker()

    if once:
        console.print("Processing one pending job...")
        processed = w.process_pending(limit=1)
        if processed:
            console.print(f"[green]✓[/green] Processed job: {processed[0].id}")
        else:
            console.print("No pending jobs.")
    else:
        console.print("[bold]Starting worker...[/bold]")
        console.print("Press Ctrl+C to stop\n")

        import time
        try:
            while True:
                processed = w.process_pending(limit=1)
                uploaded = w.upload_approved(limit=1)

                if not processed and not uploaded:
                    time.sleep(5)  # Wait before checking again
        except KeyboardInterrupt:
            console.print("\nWorker stopped.")


if __name__ == "__main__":
    app()
