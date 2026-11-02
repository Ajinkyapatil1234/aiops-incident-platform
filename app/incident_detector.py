import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.incident_queue import enqueue_incident

HEALTH_URL = "http://127.0.0.1:8083/health"
METRICS_URL = "http://127.0.0.1:8083/metrics"
CHECK_INTERVAL = 10

INCIDENT_FILE = Path("incidents.jsonl")
ANALYSIS_FILE = Path("incident_analyses.jsonl")

previous_error_count = None
application_was_healthy = True


def check_application():
    try:
        response = requests.get(HEALTH_URL, timeout=3)

        if response.status_code != 200:
            return {
                "healthy": False,
                "failure_type": "APPLICATION_FAILURE",
                "evidence": (
                    f"Health endpoint returned HTTP "
                    f"{response.status_code}"
                ),
            }

        return {
            "healthy": True,
            "failure_type": None,
            "evidence": response.json(),
        }

    except requests.Timeout as exc:
        return {
            "healthy": False,
            "failure_type": "MONITORING_TIMEOUT",
            "evidence": (
                f"Health check timed out; application health "
                f"could not be confirmed: {exc}"
            ),
        }

    except requests.ConnectionError as exc:
        return {
            "healthy": False,
            "failure_type": "MONITORING_CONNECTION_ERROR",
            "evidence": (
                f"Could not connect to the health endpoint; "
                f"application health could not be confirmed: {exc}"
            ),
        }

    except requests.RequestException as exc:
        return {
            "healthy": False,
            "failure_type": "MONITORING_ERROR",
            "evidence": str(exc),
        }

def get_error_count():
    response = requests.get(METRICS_URL, timeout=3)
    response.raise_for_status()

    for line in response.text.splitlines():
        if line.startswith("aiops_http_errors_total "):
            return float(line.split()[-1])

    return None



def record_incident(evidence, incident_type="HEALTH_CHECK_FAILURE"):
    incident = {
        "incident_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "aiops-demo",
        "type": incident_type,
        "evidence": evidence,
    }

    # Persist the incident before queuing AI analysis.
    with INCIDENT_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(incident) + "\n")

    print("INCIDENT DETECTED", flush=True)
    print(json.dumps(incident, indent=2), flush=True)

    try:
        enqueue_incident(incident)
    except OSError as exc:
        print(
            f"WARNING: Incident saved, but queueing AI analysis failed "
            f"for {incident['incident_id']}: {exc}",
            flush=True,
        )

    return incident

def main():
    global previous_error_count, application_was_healthy

    print("AIOps incident detector started.", flush=True)

    while True:
        result = check_application()

        # 1. Monitor application health.
        if result["healthy"]:
            print(
                f"Application healthy: {result['evidence']}",
                flush=True,
            )

            if not application_was_healthy:
                print("APPLICATION RECOVERED", flush=True)

            application_was_healthy = True

        elif result["failure_type"] == "APPLICATION_FAILURE":
            if application_was_healthy:
                record_incident(
                    result["evidence"],
                    incident_type="HEALTH_CHECK_FAILURE",
                )
                application_was_healthy = False
            else:
                print(
                    "Application remains unhealthy; "
                    "duplicate incident suppressed.",
                    flush=True,
                )

        else:
            print(
                f"MONITORING ISSUE "
                f"({result['failure_type']}): {result['evidence']}",
                flush=True,
            )

        # 2. Monitor Prometheus application-error counter.
        try:
            current_error_count = get_error_count()

            if current_error_count is not None:
                if previous_error_count is None:
                    previous_error_count = current_error_count

                elif current_error_count > previous_error_count:
                    record_incident(
                        "Simulated application error counter increased "
                        f"from {previous_error_count} to "
                        f"{current_error_count}",
                        incident_type="APPLICATION_ERROR",
                    )
                    previous_error_count = current_error_count

                elif current_error_count < previous_error_count:
                    # Handle a counter reset after an application restart.
                    previous_error_count = current_error_count

        except requests.RequestException as exc:
            print(f"Metrics check failed: {exc}", flush=True)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
