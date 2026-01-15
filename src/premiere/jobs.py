"""Job queue system for video processing."""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from premiere.utils.logger import get_logger


class JobStatus(str, Enum):
    """Job processing status."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    REVIEW = "review"
    APPROVED = "approved"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Video processing job."""

    id: str
    status: JobStatus
    created_at: str
    updated_at: str

    # Source
    source_type: str  # "youtube" or "local"
    source_url: str | None = None
    source_path: str | None = None

    # Video info
    title: str = ""
    description: str = ""
    duration: int = 0
    channel: str = ""

    # Processing
    input_path: str | None = None
    output_path: str | None = None
    transcript_path: str | None = None
    thumbnail_path: str | None = None
    clips_dir: str | None = None

    # Generated metadata
    generated_titles: list[str] = field(default_factory=list)
    generated_description: str = ""
    generated_tags: list[str] = field(default_factory=list)

    # Selected metadata (for upload)
    selected_title: str = ""
    selected_description: str = ""
    selected_tags: list[str] = field(default_factory=list)

    # Clips
    clips: list[dict] = field(default_factory=list)
    selected_clips: list[str] = field(default_factory=list)

    # Upload
    youtube_video_id: str | None = None
    youtube_url: str | None = None

    # Errors
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        """Create from dictionary."""
        data["status"] = JobStatus(data["status"])
        return cls(**data)


class JobQueue:
    """Persistent job queue."""

    def __init__(self, storage_dir: Path):
        """Initialize job queue.

        Args:
            storage_dir: Directory for job storage.
        """
        self.storage_dir = storage_dir
        self.jobs_file = storage_dir / "jobs.json"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, Job] = {}
        self._load()

    def _load(self) -> None:
        """Load jobs from disk."""
        if self.jobs_file.exists():
            with open(self.jobs_file) as f:
                data = json.load(f)
                self._jobs = {
                    job_id: Job.from_dict(job_data)
                    for job_id, job_data in data.items()
                }

    def _save(self) -> None:
        """Save jobs to disk."""
        data = {job_id: job.to_dict() for job_id, job in self._jobs.items()}
        with open(self.jobs_file, "w") as f:
            json.dump(data, f, indent=2)

    def create_job(
        self,
        source_type: str,
        source_url: str | None = None,
        source_path: str | None = None,
        title: str = "",
    ) -> Job:
        """Create a new job.

        Args:
            source_type: "youtube" or "local".
            source_url: YouTube URL (if youtube).
            source_path: Local file path (if local).
            title: Video title.

        Returns:
            Created job.
        """
        job_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        job = Job(
            id=job_id,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
            source_type=source_type,
            source_url=source_url,
            source_path=source_path,
            title=title,
        )

        self._jobs[job_id] = job
        self._save()

        get_logger().info(f"Created job {job_id}: {title or source_url or source_path}")
        return job

    def get_job(self, job_id: str) -> Job | None:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def update_job(self, job: Job) -> None:
        """Update job."""
        job.updated_at = datetime.now().isoformat()
        self._jobs[job.id] = job
        self._save()

    def delete_job(self, job_id: str) -> bool:
        """Delete job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save()
            return True
        return False

    def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[Job]:
        """List jobs.

        Args:
            status: Filter by status.
            limit: Maximum jobs to return.

        Returns:
            List of jobs, newest first.
        """
        jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    def get_pending_jobs(self) -> list[Job]:
        """Get jobs ready for processing."""
        return self.list_jobs(status=JobStatus.PENDING)

    def get_review_jobs(self) -> list[Job]:
        """Get jobs ready for review."""
        return self.list_jobs(status=JobStatus.REVIEW)

    def get_approved_jobs(self) -> list[Job]:
        """Get jobs approved for upload."""
        return self.list_jobs(status=JobStatus.APPROVED)


# Default queue instance
_queue: JobQueue | None = None


def get_queue(storage_dir: Path | None = None) -> JobQueue:
    """Get the job queue instance.

    Args:
        storage_dir: Storage directory (default: workspace/.premiere/jobs).

    Returns:
        JobQueue instance.
    """
    global _queue
    if _queue is None:
        if storage_dir is None:
            # Check if we're in the premiere project (has pyproject.toml or src/premiere)
            workspace_jobs = Path.cwd() / ".premiere" / "jobs"
            is_project = (
                (Path.cwd() / "pyproject.toml").exists()
                or (Path.cwd() / "src" / "premiere").exists()
            )
            storage_dir = workspace_jobs if is_project else Path.home() / ".premiere" / "jobs"
        _queue = JobQueue(storage_dir)
    return _queue
