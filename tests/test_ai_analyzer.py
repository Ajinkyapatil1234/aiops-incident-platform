
import json
from unittest.mock import Mock, patch

import pytest
from google.genai import errors

from app import ai_analyzer


@pytest.fixture
def incident():
    return {
        "incident_id": "analyzer-test-001",
        "service": "aiops-demo",
        "type": "APPLICATION_ERROR",
        "evidence": "HTTP 500",
    }


@pytest.fixture
def valid_response():
    return {
        "severity": "HIGH",
        "root_cause_hypothesis": "Possible application failure",
        "evidence": "HTTP 500",
        "recommended_action": "Inspect application logs",
    }


def make_client(response_text):
    client = Mock()
    response = Mock()
    response.text = response_text
    client.models.generate_content.return_value = response
    return client


def test_successful_analysis(monkeypatch, incident, valid_response):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    client = make_client(json.dumps(valid_response))

    with patch(
        "app.ai_analyzer.genai.Client",
        return_value=client,
    ):
        result = ai_analyzer.analyze_incident(incident)

    assert result["severity"] == "HIGH"
    assert result["automatic_remediation"] is False
    assert result["analysis_mode"] == "gemini"
    client.models.generate_content.assert_called_once()


def test_server_error_is_passed_to_router(monkeypatch, incident):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    client = Mock()
    server_error = errors.ServerError(
        503,
        {"error": {"message": "Service unavailable"}},
    )
    client.models.generate_content.side_effect = server_error

    with patch(
        "app.ai_analyzer.genai.Client",
        return_value=client,
    ):
        with pytest.raises(errors.ServerError):
            ai_analyzer.analyze_incident(incident)

    client.models.generate_content.assert_called_once()


def test_non_retryable_client_error(monkeypatch, incident):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    client = Mock()
    client.models.generate_content.side_effect = errors.ClientError(
        400,
        {"error": {"message": "Invalid request"}},
    )

    with patch(
        "app.ai_analyzer.genai.Client",
        return_value=client,
    ):
        with pytest.raises(errors.ClientError):
            ai_analyzer.analyze_incident(incident)

    client.models.generate_content.assert_called_once()


def test_invalid_severity_is_rejected(monkeypatch, incident):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    invalid_response = {
        "severity": "EXTREME",
        "root_cause_hypothesis": "Unknown",
        "evidence": "HTTP 500",
        "recommended_action": "Investigate",
    }

    client = make_client(json.dumps(invalid_response))

    with patch(
        "app.ai_analyzer.genai.Client",
        return_value=client,
    ):
        with pytest.raises(ValueError, match="invalid severity"):
            ai_analyzer.analyze_incident(incident)


def test_missing_api_key_is_rejected(monkeypatch, incident):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        ai_analyzer.analyze_incident(incident)


def test_automatic_remediation_is_always_disabled(
    monkeypatch, incident, valid_response
):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    valid_response["automatic_remediation"] = True
    client = make_client(json.dumps(valid_response))

    with patch(
        "app.ai_analyzer.genai.Client",
        return_value=client,
    ):
        result = ai_analyzer.analyze_incident(incident)

    assert result["automatic_remediation"] is False


def test_rate_limit_is_passed_to_worker(monkeypatch, incident):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    client = Mock()
    rate_limit_error = errors.ClientError(
        429,
        {"error": {"message": "Rate limit exceeded"}},
    )
    client.models.generate_content.side_effect = rate_limit_error

    with patch(
        "app.ai_analyzer.genai.Client",
        return_value=client,
    ):
        with pytest.raises(errors.ClientError):
            ai_analyzer.analyze_incident(incident)

    client.models.generate_content.assert_called_once()
