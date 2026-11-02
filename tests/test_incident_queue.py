import json

from app import incident_queue


def sample_incident():
    return {
        "incident_id": "test-incident-001",
        "service": "aiops-demo",
        "type": "HTTP_ERROR",
        "evidence": {
            "status_code": 500,
            "error_count": 5,
        },
    }


def test_enqueue_incident(tmp_path, monkeypatch):
    queue_file = tmp_path / "incident_queue.jsonl"
    monkeypatch.setattr(incident_queue, "QUEUE_FILE", queue_file)

    incident = sample_incident()

    incident_queue.enqueue_incident(incident)

    jobs = incident_queue.load_jobs()

    assert len(jobs) == 1
    assert jobs[0]["incident"] == incident
    assert jobs[0]["attempts"] == 0


def test_load_jobs_when_queue_does_not_exist(tmp_path, monkeypatch):
    queue_file = tmp_path / "missing_queue.jsonl"
    monkeypatch.setattr(incident_queue, "QUEUE_FILE", queue_file)

    assert incident_queue.load_jobs() == []


def test_save_jobs_replaces_queue(tmp_path, monkeypatch):
    queue_file = tmp_path / "incident_queue.jsonl"
    monkeypatch.setattr(incident_queue, "QUEUE_FILE", queue_file)

    jobs = [
        {
            "incident": sample_incident(),
            "attempts": 1,
        }
    ]

    incident_queue.save_jobs(jobs)

    assert incident_queue.load_jobs() == jobs
    assert not queue_file.with_suffix(".tmp").exists()


def test_record_failed_job(tmp_path, monkeypatch):
    failed_file = tmp_path / "failed.jsonl"
    monkeypatch.setattr(incident_queue, "FAILED_FILE", failed_file)

    incident = sample_incident()
    job = {
        "incident": incident,
        "attempts": 3,
    }

    incident_queue.record_failed_job(job, RuntimeError("Simulated failure"))

    with failed_file.open(encoding="utf-8") as file:
        record = json.loads(file.readline())

    assert record["incident_id"] == incident["incident_id"]
    assert record["attempts"] == 3
    assert record["error"] == "Simulated failure"
    assert record["incident"] == incident
    assert "failed_at" in record
