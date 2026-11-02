import json

import pytest

from app import ai_worker, incident_detector, incident_queue


def test_incident_to_ai_analysis_pipeline(tmp_path, monkeypatch):
    # Isolate all persistent files from real project data.
    monkeypatch.setattr(
        incident_detector, "INCIDENT_FILE",
        tmp_path / "incidents.jsonl",
    )
    monkeypatch.setattr(
        incident_queue, "QUEUE_FILE",
        tmp_path / "incident_queue.jsonl",
    )
    monkeypatch.setattr(
        ai_worker, "ANALYSIS_FILE",
        str(tmp_path / "incident_analyses.jsonl"),
    )

    # Mock Gemini: no external API request is made.
    expected_analysis = {
        "severity": "HIGH",
        "summary": "Application error counter increased.",
        "automatic_remediation": False,
    }

    monkeypatch.setattr(
        ai_worker,
        "analyze_incident",
        lambda incident: expected_analysis,
    )

    # 1. Detector creates and queues an incident.
    incident = incident_detector.record_incident(
        "Simulated application error counter increased from 1.0 to 2.0",
        incident_type="APPLICATION_ERROR",
    )

    # 2. Verify incident persistence.
    incident_records = (
        tmp_path / "incidents.jsonl"
    ).read_text(encoding="utf-8").splitlines()

    assert len(incident_records) == 1
    assert json.loads(incident_records[0])["incident_id"] == (
        incident["incident_id"]
    )

    # 3. Verify the real queue contains the incident.
    jobs = incident_queue.load_jobs()

    assert len(jobs) == 1
    assert jobs[0]["incident"]["incident_id"] == (
        incident["incident_id"]
    )
    assert jobs[0]["attempts"] == 0

    # 4. Run one real worker iteration.
    # Interrupt its sleep after the first iteration.
    monkeypatch.setattr(
        ai_worker.time,
        "sleep",
        lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    with pytest.raises(KeyboardInterrupt):
        ai_worker.main()

    # 5. Verify the worker removed the processed job.
    assert incident_queue.load_jobs() == []

    # 6. Verify the analysis was persisted.
    analysis_records = (
        tmp_path / "incident_analyses.jsonl"
    ).read_text(encoding="utf-8").splitlines()

    assert len(analysis_records) == 1

    saved_record = json.loads(analysis_records[0])

    assert saved_record["incident_id"] == incident["incident_id"]
    assert saved_record["analysis"] == expected_analysis
