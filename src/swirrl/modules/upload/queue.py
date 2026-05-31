"""Upload queue management for persistent job tracking and retry logic.

Provides a JSONL-based queue system for managing upload jobs with
support for retries, status tracking, and batch processing.
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from swirrl.core.paths import get_config_dir
from swirrl.modules.upload.models import TorrentMetadata, UploadResult


@dataclass
class QueuedUpload:
    """Represents a queued upload job."""

    job_id: str
    torrent_path: str
    metadata: dict[str, Any]
    tracker_names: list[str]
    status: str  # "pending", "failed", "completed"
    created_at: str
    error_message: str = ""
    attempts: int = 0


class UploadQueue:
    """Persistent queue for upload jobs stored in JSONL format."""

    def __init__(self):
        self.queue_file = get_config_dir() / "upload_queue.jsonl"
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)

    def enqueue(
        self, torrent_path: Path, metadata: TorrentMetadata, tracker_names: list[str]
    ) -> str:
        """Add upload job to queue. Returns job_id."""
        job_id = str(uuid.uuid4())
        job = QueuedUpload(
            job_id=job_id,
            torrent_path=str(torrent_path),
            metadata=metadata.model_dump(),
            tracker_names=tracker_names,
            status="pending",
            created_at=datetime.now().isoformat(),
            attempts=0,
        )

        with open(self.queue_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(job)) + "\n")

        return job_id

    def _load_queue(self) -> list[QueuedUpload]:
        """Load all jobs from queue file."""
        if not self.queue_file.exists():
            return []

        jobs = []
        with open(self.queue_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    jobs.append(QueuedUpload(**json.loads(line)))
        return jobs

    def _save_queue(self, jobs: list[QueuedUpload]) -> None:
        """Save all jobs to queue file."""
        with open(self.queue_file, "w", encoding="utf-8") as f:
            for job in jobs:
                f.write(json.dumps(asdict(job)) + "\n")

    def list_pending(self) -> list[QueuedUpload]:
        """List all pending jobs."""
        return [j for j in self._load_queue() if j.status == "pending"]

    def list_failed(self) -> list[QueuedUpload]:
        """List all failed jobs."""
        return [j for j in self._load_queue() if j.status == "failed"]

    def retry_failed(self, service) -> dict[str, dict[str, UploadResult]]:
        """Retry all failed jobs. Returns results dict."""
        failed_jobs = self.list_failed()
        results = {}

        for job in failed_jobs:
            torrent_path = Path(job.torrent_path)
            if not torrent_path.exists():
                continue

            metadata = TorrentMetadata(**job.metadata)
            job_results = service.upload_to_multiple(torrent_path, metadata, job.tracker_names)

            # Update job status
            all_success = all(r.success for r in job_results.values())
            job.status = "completed" if all_success else "failed"
            job.attempts += 1
            if not all_success:
                job.error_message = "; ".join(
                    f"{t}: {r.message}" for t, r in job_results.items() if not r.success
                )

            results[job.job_id] = job_results

        # Save updated queue
        all_jobs = self._load_queue()
        self._save_queue(all_jobs)

        return results

    def process_all(self, service) -> dict[str, dict[str, UploadResult]]:
        """Process all pending jobs. Returns results dict."""
        pending_jobs = self.list_pending()
        results = {}

        for job in pending_jobs:
            torrent_path = Path(job.torrent_path)
            if not torrent_path.exists():
                job.status = "failed"
                job.error_message = "Torrent file not found"
                continue

            metadata = TorrentMetadata(**job.metadata)
            job_results = service.upload_to_multiple(torrent_path, metadata, job.tracker_names)

            # Update job status
            all_success = all(r.success for r in job_results.values())
            job.status = "completed" if all_success else "failed"
            job.attempts += 1
            if not all_success:
                job.error_message = "; ".join(
                    f"{t}: {r.message}" for t, r in job_results.items() if not r.success
                )

            results[job.job_id] = job_results

        # Save updated queue
        all_jobs = self._load_queue()
        self._save_queue(all_jobs)

        return results

    def clear(self) -> int:
        """Clear all completed jobs. Returns count of cleared jobs."""
        jobs = self._load_queue()
        completed = [j for j in jobs if j.status == "completed"]
        remaining = [j for j in jobs if j.status != "completed"]
        self._save_queue(remaining)
        return len(completed)
