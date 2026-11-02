import json
import os

from groq import Groq

MODEL_NAME = "openai/gpt-oss-20b"

ALLOWED_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def analyze_incident(incident):
    """
    Analyze an incident using Groq.
    Returns the same structured output as Gemini.
    Does not perform automatic remediation.
    """

    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    client = Groq(api_key=api_key, timeout=30.0)

    prompt = f"""
You are an SRE assistant analyzing a software incident.

Analyze the following incident evidence:

{json.dumps(incident, indent=2)}

Return ONLY a valid JSON object with these fields:
- severity: LOW, MEDIUM, HIGH, or CRITICAL
- root_cause_hypothesis: concise evidence-based hypothesis
- evidence: relevant incident evidence
- recommended_action: safe investigation recommendation
- automatic_remediation: always false

Do not claim an unconfirmed root cause.
Do not execute commands or perform changes.
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "You are a careful SRE incident analysis assistant. Return valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("Groq returned an empty response")

    result = json.loads(content)

    if not isinstance(result, dict):
        raise ValueError("Groq response must be a JSON object")

    required_fields = {
        "severity",
        "root_cause_hypothesis",
        "evidence",
        "recommended_action",
    }

    missing_fields = required_fields - result.keys()

    if missing_fields:
        raise ValueError(f"Groq response missing fields: {missing_fields}")

    if result["severity"] not in ALLOWED_SEVERITIES:
        raise ValueError("Groq returned an invalid severity")

    result["automatic_remediation"] = False
    result["analysis_mode"] = "groq"

    return result
