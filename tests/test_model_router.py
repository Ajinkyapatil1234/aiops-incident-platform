
from unittest.mock import patch

import pytest

from app import model_router


@pytest.fixture
def incident():
    return {
        "incident_id": "router-test-001",
        "service": "aiops-demo",
        "type": "APPLICATION_ERROR",
        "evidence": "HTTP 500",
    }


@pytest.fixture
def gemini_result():
    return {
        "severity": "HIGH",
        "root_cause_hypothesis": "Possible application failure",
        "evidence": "HTTP 500",
        "recommended_action": "Inspect application logs",
        "automatic_remediation": False,
        "analysis_mode": "gemini",
    }


@pytest.fixture
def groq_result():
    return {
        "severity": "MEDIUM",
        "root_cause_hypothesis": "Possible deployment issue",
        "evidence": "HTTP 500",
        "recommended_action": "Review recent deployments",
        "automatic_remediation": False,
        "analysis_mode": "groq",
    }


def test_gemini_success_skips_groq(
    incident, gemini_result
):
    with (
        patch(
            "app.model_router.analyze_with_gemini",
            return_value=gemini_result.copy(),
        ) as mock_gemini,
        patch(
            "app.model_router.analyze_with_groq",
        ) as mock_groq,
    ):
        result = model_router.analyze_incident(incident)

    assert result["model_provider"] == "gemini"
    assert result["severity"] == "HIGH"
    mock_gemini.assert_called_once_with(incident)
    mock_groq.assert_not_called()


def test_gemini_failure_retries_then_uses_groq(
    incident, groq_result
):
    with (
        patch(
            "app.model_router.analyze_with_gemini",
            side_effect=RuntimeError("Gemini unavailable"),
        ) as mock_gemini,
        patch(
            "app.model_router.analyze_with_groq",
            return_value=groq_result.copy(),
        ) as mock_groq,
        patch("app.model_router.time.sleep") as mock_sleep,
    ):
        result = model_router.analyze_incident(incident)

    assert mock_gemini.call_count == 2
    mock_groq.assert_called_once_with(incident)
    mock_sleep.assert_called_once_with(
        model_router.RETRY_DELAY
    )
    assert result["model_provider"] == "groq"
    assert result["severity"] == "MEDIUM"


def test_groq_failure_is_propagated(incident):
    with (
        patch(
            "app.model_router.analyze_with_gemini",
            side_effect=RuntimeError("Gemini unavailable"),
        ),
        patch(
            "app.model_router.analyze_with_groq",
            side_effect=RuntimeError("Groq unavailable"),
        ) as mock_groq,
        patch("app.model_router.time.sleep"),
    ):
        with pytest.raises(
            RuntimeError,
            match="Groq unavailable",
        ):
            model_router.analyze_incident(incident)

    mock_groq.assert_called_once_with(incident)
