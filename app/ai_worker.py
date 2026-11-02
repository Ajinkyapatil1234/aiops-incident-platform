
import json
import re
import time
import os
from datetime import datetime, timedelta, timezone

from app.model_router import analyze_incident
from app.incident_queue import (
    load_jobs,
    record_failed_job,
    save_jobs,
)

ANALYSIS_FILE = "incident_analyses.jsonl"

POLL_INTERVAL = 5
MAX_IDLE_WAIT = 60
MAX_WORKER_ATTEMPTS = 3
WORKER_RETRY_DELAY = 30
DEFAULT_QUOTA_RETRY_DELAY = 3600


def save_analysis(incident, analysis):
    incident_id = incident["incident_id"]

    # Prevent duplicate analysis records.
    if os.path.exists(ANALYSIS_FILE):
        with open(ANALYSIS_FILE, "r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue

                existing_record = json.loads(line)

                if existing_record.get("incident_id") == incident_id:
                    print(
                        f"Analysis already exists for {incident_id}. "
                        "Skipping duplicate.",
                        flush=True,
                    )
                    return False

    record = {
        "incident_id": incident_id,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "analysis": analysis,
    }

    with open(ANALYSIS_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")
        file.flush()

    provider = analysis.get(
        "model_provider",
        analysis.get("analysis_mode", "unknown"),
    ).upper()

    print(f"{provider} ANALYSIS SAVED", flush=True)
    print(json.dumps(record, indent=2), flush=True)

    return True


def is_quota_error(exc):
    code = getattr(exc, "code", None)
    message = str(exc).upper()

    return (
        code == 429
        or "RESOURCE_EXHAUSTED" in message
    )


def get_quota_retry_delay(exc):
    message = str(exc)

    # Prefer Google's structured RetryInfo duration.
    match = re.search(
        r"""retryDelay['"]?\s*:\s*['"](\d+)s""",
        message,
    )

    if match:
        return int(match.group(1))

    # Parse messages such as "retry in 16h45m8s".
    match = re.search(
        r"retry in\s+"
        r"(?:(\d+)h)?"
        r"(?:(\d+)m)?"
        r"(?:(\d+)s)?",
        message,
        re.IGNORECASE,
    )

    if match:
        hours, minutes, seconds = match.groups()

        delay = (
            int(hours or 0) * 3600
            + int(minutes or 0) * 60
            + int(seconds or 0)
        )

        if delay > 0:
            return delay

    return DEFAULT_QUOTA_RETRY_DELAY


def get_idle_wait(jobs):
    """Calculate when the next queued job becomes eligible."""
    now = datetime.now(timezone.utc)

    retry_times = [
        datetime.fromisoformat(job["available_at"])
        for job in jobs
        if job.get("available_at")
    ]

    if not retry_times:
        return POLL_INTERVAL

    next_retry = min(retry_times)
    remaining = (next_retry - now).total_seconds()

    if remaining <= 0:
        return POLL_INTERVAL

    return min(remaining, MAX_IDLE_WAIT)


def main():
    print("AIOps AI worker started.", flush=True)

    while True:
        jobs = load_jobs()

        if not jobs:
            time.sleep(POLL_INTERVAL)
            continue

        remaining_jobs = []
        processed_job = False
        now = datetime.now(timezone.utc)

        for index, job in enumerate(jobs):
            incident = job["incident"]

            available_at = job.get("available_at")

            if available_at:
                retry_time = datetime.fromisoformat(available_at)

                if retry_time > now:
                    remaining_jobs.append(job)
                    continue

            try:
                print(
                    f"Analyzing incident {incident['incident_id']}",
                    flush=True,
                )

                # Gemini primary -> Groq fallback.
                analysis = analyze_incident(incident)
                save_analysis(incident, analysis)

            except Exception as exc:
                print(
                    f"AI analysis failed for "
                    f"{incident['incident_id']}: {exc}",
                    flush=True,
                )

                if is_quota_error(exc):
                    delay = get_quota_retry_delay(exc)

                    job["available_at"] = (
                        datetime.now(timezone.utc)
                        + timedelta(seconds=delay)
                    ).isoformat()

                    remaining_jobs.append(job)

                    print(
                        f"Analysis quota exhausted. Incident deferred "
                        f"for {delay} seconds.",
                        flush=True,
                    )

                else:
                    job["attempts"] = job.get("attempts", 0) + 1

                    if job["attempts"] >= MAX_WORKER_ATTEMPTS:
                        record_failed_job(job, exc)

                        print(
                            f"Incident moved to failed-analysis log: "
                            f"{incident['incident_id']}",
                            flush=True,
                        )
                    else:
                        job["available_at"] = (
                            datetime.now(timezone.utc)
                            + timedelta(seconds=WORKER_RETRY_DELAY)
                        ).isoformat()

                        remaining_jobs.append(job)

            # Preserve all jobs that haven't been processed.
            remaining_jobs.extend(jobs[index + 1:])
            processed_job = True
            break

        save_jobs(remaining_jobs)

        if not processed_job:
            time.sleep(get_idle_wait(remaining_jobs))


if __name__ == "__main__":
    main()
