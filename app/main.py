import json
import os
import time
from pathlib import Path

from flask import Flask, jsonify, Response, request, render_template
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

BASE_DIR = Path(__file__).resolve().parent.parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static")
)

REQUEST_COUNT = Counter(
    "aiops_http_requests_total",
    "Total HTTP requests",
    ["endpoint", "status"],
)

ERROR_COUNT = Counter(
    "aiops_http_errors_total",
    "Total simulated application errors",
)

START_TIME = time.time()

INCIDENT_FILE = Path("incidents.jsonl")
QUEUE_FILE = Path("incident_queue.jsonl")
ANALYSIS_FILE = Path("incident_analyses.jsonl")
FAILED_FILE = Path("incident_analysis_failed.jsonl")


@app.after_request
def record_request(response):
    REQUEST_COUNT.labels(
        endpoint=request.path,
        status=str(response.status_code),
    ).inc()
    return response


def read_jsonl(path):
    """Read JSONL records, ignoring malformed lines."""
    if not path.exists():
        return []

    records = []

    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue

                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    app.logger.warning(
                        "Skipping malformed JSONL record in %s", path
                    )
    except OSError:
        app.logger.exception("Unable to read %s", path)

    return records


def get_metric_total(metric_name):
    """Return the sum of all samples for a Prometheus counter."""
    total = 0.0

    for line in generate_latest().decode("utf-8").splitlines():
        if line.startswith("#") or not line:
            continue

        name = line.split("{", 1)[0].split(" ", 1)[0]

        if name == metric_name:
            try:
                total += float(line.rsplit(" ", 1)[-1])
            except ValueError:
                continue

    return total


@app.route("/")
def home():
    return jsonify({
        "service": "aiops-demo",
        "message": "AIOps Incident Response Platform is running",
    })


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/dashboard")
def dashboard_data():
    incidents = read_jsonl(INCIDENT_FILE)
    queue_jobs = read_jsonl(QUEUE_FILE)
    analyses = read_jsonl(ANALYSIS_FILE)
    failed_jobs = read_jsonl(FAILED_FILE)

    analysis_by_id = {
        record["incident_id"]: record
        for record in analyses
        if record.get("incident_id")
    }

    failed_by_id = {
        record["incident_id"]: record
        for record in failed_jobs
        if record.get("incident_id")
    }

    queue_by_id = {
        job.get("incident", {}).get("incident_id"): job
        for job in queue_jobs
        if job.get("incident", {}).get("incident_id")
    }

    dashboard_incidents = []

    for incident in incidents:
        incident_id = incident.get("incident_id")
        analysis_record = analysis_by_id.get(incident_id)
        failed_record = failed_by_id.get(incident_id)
        queue_record = queue_by_id.get(incident_id)

        if analysis_record:
            status = "ANALYZED"
        elif failed_record:
            status = "FAILED"
        elif queue_record:
            status = "PENDING"
        else:
            status = "NOT_QUEUED"

        dashboard_incidents.append({
            **incident,
            "incident_id": incident_id,
            "status": status,
            "analysis": (
                analysis_record.get("analysis")
                if analysis_record else None
            ),
            "analyzed_at": (
                analysis_record.get("analyzed_at")
                if analysis_record else None
            ),
            "attempts": (
                queue_record.get("attempts", 0)
                if queue_record else (
                    failed_record.get("attempts", 0)
                    if failed_record else 0
                )
            ),
        })

    dashboard_incidents.sort(
        key=lambda item: item.get("timestamp") or "",
        reverse=True,
    )

    try:
        health = {
            "status": (
                "unhealthy"
                if os.environ.get("SIMULATE_FAILURE") == "1"
                else "healthy"
            ),
            "uptime_seconds": round(time.time() - START_TIME, 2),
        }

        if health["status"] == "unhealthy":
            health["reason"] = "Simulated failure"

    except Exception:
        health = {
            "status": "unknown",
            "uptime_seconds": None,
        }

    analysis_count = len(analysis_by_id)

    return jsonify({
        "health": health,
        "summary": {
            "total_incidents": len(incidents),
            "pending_jobs": len(queue_jobs),
            "failed_jobs": len(failed_jobs),
            "analyzed_incidents": analysis_count,
            "ai_status": (
                "Analysis recorded"
                if analysis_count
                else "No analysis yet"
            ),
        },
        "metrics": {
            "error_count": get_metric_total(
                "aiops_http_errors_total"
            ),
            "request_count": get_metric_total(
                "aiops_http_requests_total"
            ),
        },
        "incidents": dashboard_incidents,
    })


@app.route("/health")
def health():
    if os.environ.get("SIMULATE_FAILURE") == "1":
        return jsonify({
            "status": "unhealthy",
            "reason": "Simulated failure",
        }), 500

    return jsonify({
        "status": "healthy",
        "uptime_seconds": round(time.time() - START_TIME, 2),
    })


@app.route("/simulate-error")
def simulate_error():
    ERROR_COUNT.inc()
    app.logger.error("Simulated application failure triggered")

    return jsonify({
        "status": "error",
        "message": "Controlled incident simulation",
    }), 500


@app.route("/metrics")
def metrics():
    return Response(
        generate_latest(),
        mimetype=CONTENT_TYPE_LATEST,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
