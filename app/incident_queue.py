
import json
from datetime import datetime, timezone
from pathlib import Path

QUEUE_FILE = Path("incident_queue.jsonl")
FAILED_FILE = Path("incident_analysis_failed.jsonl")


def enqueue_incident(incident):
    """Persist an incident for background AI analysis."""
    job = {
        "incident": incident,
        "attempts": 0,
    }

    with QUEUE_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(job) + "\n")
        file.flush()

    print(
        f"Incident queued for AI analysis: "
        f"{incident['incident_id']}",
        flush=True,
    )


def load_jobs():
    """Read queued jobs from disk."""
    if not QUEUE_FILE.exists():
        return []

    jobs = []

    with QUEUE_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                jobs.append(json.loads(line))

    return jobs


def save_jobs(jobs):
    """Persist remaining jobs using an atomic file replacement."""
    temporary_file = QUEUE_FILE.with_suffix(".tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        for job in jobs:
            file.write(json.dumps(job) + "\n")
        file.flush()

    temporary_file.replace(QUEUE_FILE)


def record_failed_job(job, error):
    """Persist a job that exhausted its worker attempts."""
    record = {
        "incident_id": job["incident"]["incident_id"],
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "attempts": job["attempts"],
        "error": str(error),
        "incident": job["incident"],
    }

    with FAILED_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")
        file.flush()
