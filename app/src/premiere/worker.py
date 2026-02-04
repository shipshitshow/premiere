"""Background worker for processing jobs."""

from pathlib import Path

from premiere.downloaders.youtube_dl import download_video, get_video_info
from premiere.jobs import Job, JobQueue, JobStatus, get_queue
from premiere.pipeline import Pipeline
from premiere.utils.logger import get_logger


class Worker:
    """Processes jobs from the queue."""

    def __init__(
        self,
        queue: JobQueue | None = None,
        output_dir: Path | None = None,
    ):
        """Initialize worker.

        Args:
            queue: Job queue (uses default if not provided).
            output_dir: Output directory for processed files (default: workspace/output).
        """
        self.queue = queue or get_queue()
        # Default to workspace/output when in project directory, otherwise ~/.premiere/output
        if output_dir is None:
            # Check if we're in the premiere project (has pyproject.toml or src/premiere)
            workspace_output = Path.cwd() / "output"
            is_project = (
                (Path.cwd() / "pyproject.toml").exists()
                or (Path.cwd() / "src" / "premiere").exists()
            )
            self.output_dir = workspace_output if is_project else Path.home() / ".premiere" / "output"
        else:
            self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger()

    def process_job(self, job: Job, generate_clips: bool = True) -> Job:
        """Process a single job.

        Args:
            job: Job to process.
            generate_clips: Generate viral clips.

        Returns:
            Updated job.
        """
        self.logger.info(f"Processing job {job.id}: {job.title}")

        try:
            # Download if YouTube source
            if job.source_type == "youtube" and job.source_url:
                job.status = JobStatus.DOWNLOADING
                self.queue.update_job(job)

                # Get video info
                info = get_video_info(job.source_url)
                job.title = info.title
                job.description = info.description
                job.duration = info.duration
                job.channel = info.channel

                # Download video
                job_dir = self.output_dir / job.id
                job_dir.mkdir(exist_ok=True)

                video_path = download_video(
                    job.source_url,
                    job_dir,
                    filename="source",
                )
                job.input_path = str(video_path)

            elif job.source_type == "local" and job.source_path:
                job.input_path = job.source_path
                if not job.title:
                    job.title = Path(job.source_path).stem

            if not job.input_path:
                raise ValueError("No input video")

            # Process video
            job.status = JobStatus.PROCESSING
            self.queue.update_job(job)

            input_path = Path(job.input_path)
            job_dir = self.output_dir / job.id
            job_dir.mkdir(exist_ok=True)

            pipeline = Pipeline()
            result = pipeline.run(
                input_path,
                output_dir=job_dir,
                generate_clips=generate_clips,
                max_clips=5,
            )

            # Update job with results
            if result.output_path:
                job.output_path = str(result.output_path)

            if result.transcript_path:
                job.transcript_path = str(result.transcript_path)

            if result.clips_dir:
                job.clips_dir = str(result.clips_dir)
                job.clips = [
                    {
                        "path": str(c.path),
                        "title": c.title,
                        "caption": c.caption,
                        "hashtags": c.hashtags,
                        "start": c.start,
                        "end": c.end,
                    }
                    for c in result.clips
                ]

            if result.metadata:
                job.generated_titles = result.metadata.titles
                job.generated_description = result.metadata.description
                job.generated_tags = result.metadata.tags

                # Pre-select first title
                if result.metadata.titles:
                    job.selected_title = result.metadata.titles[0]
                job.selected_description = result.metadata.description
                job.selected_tags = result.metadata.tags

            # Mark for review
            job.status = JobStatus.REVIEW
            job.error = None
            self.queue.update_job(job)

            self.logger.info(f"Job {job.id} ready for review")

        except Exception as e:
            self.logger.error(f"Job {job.id} failed: {e}")
            job.status = JobStatus.FAILED
            job.error = str(e)
            self.queue.update_job(job)

        return job

    def process_pending(self, limit: int = 1) -> list[Job]:
        """Process pending jobs.

        Args:
            limit: Maximum jobs to process.

        Returns:
            List of processed jobs.
        """
        pending = self.queue.get_pending_jobs()[:limit]
        return [self.process_job(job) for job in pending]

    def upload_approved(self, limit: int = 1) -> list[Job]:
        """Upload approved jobs.

        Args:
            limit: Maximum jobs to upload.

        Returns:
            List of uploaded jobs.
        """
        from premiere.generators.metadata import VideoMetadata
        from premiere.uploaders.youtube import upload_video
        from premiere.utils.config import get_config

        approved = self.queue.get_approved_jobs()[:limit]
        uploaded = []

        for job in approved:
            try:
                job.status = JobStatus.UPLOADING
                self.queue.update_job(job)

                if not job.output_path:
                    raise ValueError("No output video to upload")

                # Create metadata from selected values
                metadata = VideoMetadata(
                    titles=[job.selected_title or job.title],
                    description=job.selected_description,
                    tags=job.selected_tags,
                    chapters=[],
                )

                # Upload
                thumbnail_path = Path(job.thumbnail_path) if job.thumbnail_path else None
                result = upload_video(
                    Path(job.output_path),
                    metadata,
                    thumbnail_path,
                    get_config().youtube,
                )

                job.youtube_video_id = result["video_id"]
                job.youtube_url = result["url"]
                job.status = JobStatus.COMPLETED
                job.error = None

                self.logger.info(f"Job {job.id} uploaded: {result['url']}")

            except Exception as e:
                self.logger.error(f"Upload failed for job {job.id}: {e}")
                job.status = JobStatus.FAILED
                job.error = str(e)

            self.queue.update_job(job)
            uploaded.append(job)

        return uploaded
