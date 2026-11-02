
import json
import os

from google import genai

MODEL_NAME = "gemini-3.8-flash"


def analyze_incident(incident):
    """
    Analyze an incident with Gemini.
    The model router handles retries and provider fallback.
    Returns validated structured recommendations only.
    Does not perform automatic remediation.
    """
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    client = genai.Client(
        api_key=api_key,
        http_options={"timeout": 60000},
    )

    prompt = f"""
You are an SRE assistant analyzing a software incident.

Analyze the following incident evidence:
{json.dumps(incident, indent=2)}

Return ONLY a valid JSON object with these fields:
- severity: one of LOW, MEDIUM, HIGH, CRITICAL
- root_cause_hypothesis: a concise, evidence-based hypothesis
- evidence: relevant evidence from the incident
- recommended_action: safe investigation or remediation recommendation
- automatic_remediation: always false

Do not claim a root cause is confirmed unless the evidence proves it.
Do not execute commands or perform any changes.
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
        },
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response")

    try:
        result = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini returned invalid JSON") from exc

    if not isinstance(result, dict):
        raise ValueError("Gemini response must be a JSON object")

    required_fields = {
        "severity",
        "root_cause_hypothesis",
        "evidence",
        "recommended_action",
    }

    missing_fields = required_fields - result.keys()

    if missing_fields:
        raise ValueError(
            f"Gemini response missing fields: {missing_fields}"
        )

    allowed_severities = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    if result.get("severity") not in allowed_severities:
        raise ValueError("Gemini returned an invalid severity")

    result["automatic_remediation"] = False
    result["analysis_mode"] = "gemini"

    return result
