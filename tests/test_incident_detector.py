import json
from unittest.mock import Mock

import requests

from app import incident_detector


def test_check_application_healthy(monkeypatch):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"status": "healthy"}

    monkeypatch.setattr(
        incident_detector.requests,
        "get",
        lambda *args, **kwargs: response,
    )

    result = incident_detector.check_application()

    assert result["healthy"] is True
    assert result["evidence"] == {"status": "healthy"}


def test_check_application_http_failure(monkeypatch):
    response = Mock()
    response.status_code = 500

    monkeypatch.setattr(
        incident_detector.requests,
        "get",
        lambda *args, **kwargs: response,
    )

    result = incident_detector.check_application()

    assert result["healthy"] is False
    assert result["failure_type"] == "APPLICATION_FAILURE"
    assert "500" in result["evidence"]


def test_check_application_timeout(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise requests.Timeout("simulated timeout")

    monkeypatch.setattr(
        incident_detector.requests,
        "get",
        raise_timeout,
    )

    result = incident_detector.check_application()

    assert result["healthy"] is False
    assert result["failure_type"] == "MONITORING_TIMEOUT"


def test_record_incident_persists_and_queues(
    tmp_path, monkeypatch
):
    incident_file = tmp_path / "incidents.jsonl"

    monkeypatch.setattr(
        incident_detector,
        "INCIDENT_FILE",
        incident_file,
    )

    queued = []
    monkeypatch.setattr(
        incident_detector,
        "enqueue_incident",
        lambda incident: queued.append(incident),
    )

    evidence = {"status_code": 500}

    incident = incident_detector.record_incident(
        evidence,
        incident_type="APPLICATION_ERROR",
    )

    with incident_file.open(encoding="utf-8") as file:
        saved = json.loads(file.readline())

    assert saved == incident
    assert queued == [incident]
    assert incident["evidence"] == evidence
    assert incident["type"] == "APPLICATION_ERROR"
    assert incident["incident_id"]
    assert incident["timestamp"]
    assert incident["service"] == "aiops-demo"


def test_record_incident_queue_failure_keeps_incident(
    tmp_path, monkeypatch
):
    incident_file = tmp_path / "incidents.jsonl"

    monkeypatch.setattr(
        incident_detector,
        "INCIDENT_FILE",
        incident_file,
    )

    def fail_queue(incident):
        raise OSError("simulated disk error")

    monkeypatch.setattr(
        incident_detector,
        "enqueue_incident",
        fail_queue,
    )

    incident = incident_detector.record_incident(
        "simulated failure"
    )

    with incident_file.open(encoding="utf-8") as file:
        saved = json.loads(file.readline())

    assert saved["incident_id"] == incident["incident_id"]
    assert saved["evidence"] == "simulated failure"
