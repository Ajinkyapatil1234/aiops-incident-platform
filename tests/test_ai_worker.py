from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import ai_worker


def sample_incident():
    return {
        "incident_id": "worker-test-001",
        "service": "aiops-demo",
        "type": "APPLICATION_ERROR",
        "evidence": "HTTP 500",
    }


def run_worker_once(jobs, analysis_error=None):
    analysis = {
        "severity": "HIGH",
        "root_cause_hypothesis": "Simulated failure",
        "automatic_remediation": False,
    }

    with (
        patch("app.ai_worker.load_jobs", side_effect=[jobs, []]),
        patch(
            "app.ai_worker.analyze_incident",
            side_effect=analysis_error,
            return_value=analysis,
        ) as mock_analyze,
        patch("app.ai_worker.save_analysis") as mock_save,
        patch("app.ai_worker.save_jobs") as mock_save_jobs,
        patch("app.ai_worker.record_failed_job") as mock_failed,
        patch(
            "app.ai_worker.time.sleep",
            side_effect=KeyboardInterrupt,
        ),
    ):
        try:
            ai_worker.main()
        except KeyboardInterrupt:
            pass

    return {
        "remaining": mock_save_jobs.call_args.args[0],
        "analyze": mock_analyze,
        "save": mock_save,
        "failed": mock_failed,
    }


def test_successful_analysis():
    incident = sample_incident()

    result = run_worker_once([
        {"incident": incident, "attempts": 0}
    ])

    assert result["analyze"].call_count == 1
    assert result["save"].call_count == 1
    assert result["remaining"] == []
    assert result["failed"].called is False


def test_temporary_failure_requeues_job():
    incident = sample_incident()

    result = run_worker_once(
        [{"incident": incident, "attempts": 0}],
        analysis_error=RuntimeError("Temporary failure"),
    )

    job = result["remaining"][0]

    assert job["attempts"] == 1
    assert "available_at" in job
    assert result["failed"].called is False


def test_quota_error_defers_without_incrementing_attempts():
    incident = sample_incident()

    quota_error = Exception(
        "429 RESOURCE_EXHAUSTED. Please retry in 16h45m8s."
    )

    result = run_worker_once(
        [{"incident": incident, "attempts": 0}],
        analysis_error=quota_error,
    )

    job = result["remaining"][0]

    assert job["attempts"] == 0
    assert "available_at" in job
    assert result["failed"].called is False


def test_maximum_attempts_moves_job_to_failed_log():
    incident = sample_incident()

    result = run_worker_once(
        [{"incident": incident, "attempts": 2}],
        analysis_error=RuntimeError("Permanent failure"),
    )

    assert result["failed"].call_count == 1
    assert result["remaining"] == []


def test_future_job_is_preserved_without_analysis():
    incident = sample_incident()

    job = {
        "incident": incident,
        "attempts": 0,
        "available_at": (
            datetime.now(timezone.utc)
            + timedelta(hours=2)
        ).isoformat(),
    }

    result = run_worker_once([job])

    assert result["analyze"].called is False
    assert result["remaining"] == [job]


def test_idle_wait_is_capped_at_maximum():
    job = {
        "available_at": (
            datetime.now(timezone.utc)
            + timedelta(hours=16)
        ).isoformat()
    }

    assert ai_worker.get_idle_wait([job]) == ai_worker.MAX_IDLE_WAIT


def test_idle_wait_uses_nearest_retry():
    job = {
        "available_at": (
            datetime.now(timezone.utc)
            + timedelta(seconds=20)
        ).isoformat()
    }

    wait = ai_worker.get_idle_wait([job])

    assert 0 < wait <= 20


def test_empty_queue_uses_poll_interval():
    assert ai_worker.get_idle_wait([]) == ai_worker.POLL_INTERVAL


def test_save_analysis_prevents_duplicate_records(tmp_path, monkeypatch):
    import json
    from app import ai_worker

    analysis_file = tmp_path / "incident_analyses.jsonl"

    monkeypatch.setattr(
        ai_worker,
        "ANALYSIS_FILE",
        str(analysis_file),
    )

    incident = {
        "incident_id": "test-incident-123",
    }

    analysis = {
        "severity": "HIGH",
        "summary": "Test analysis",
        "automatic_remediation": False,
    }

    first_result = ai_worker.save_analysis(incident, analysis)
    second_result = ai_worker.save_analysis(incident, analysis)

    records = [
        json.loads(line)
        for line in analysis_file.read_text().splitlines()
    ]

    assert first_result is True
    assert second_result is False
    assert len(records) == 1
    assert records[0]["incident_id"] == "test-incident-123"
