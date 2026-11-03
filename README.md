# AIOps Incident Response Platform

An AI-powered incident detection and analysis platform built with **Python, Flask, Prometheus, Docker, Kubernetes, Gemini, and Groq**.

The platform monitors application health, detects incidents, maintains a persistent incident queue, and uses AI models to generate structured incident analysis and recommended actions.

**The goal:** Reduce manual effort during incident investigation while keeping remediation decisions under human control.

## Architecture

```text
              Application
                   |
                   v
          Health & Metrics Checks
                   |
                   v
           Incident Detector
                   |
                   v
          Persistent Incident Queue
                   |
                   v
             AI Worker
                   |
                   v
             Model Router
              /       \
             v         v
          Gemini      Groq
          Primary    Fallback
              \       /
               v     v
           Structured Analysis
                   |
                   v
          Analysis & Audit Logs
                   |
                   v
             Flask Dashboard
```

## Key Features

### 1. Incident Detection
- Application health monitoring.
- Prometheus metrics-based error detection.
- Detection of health-check failures and application errors.
- Incident evidence and timestamps recorded in JSONL format.

### 2. Persistent Incident Queue
- Stores incidents for asynchronous AI analysis.
- Tracks processing attempts.
- Supports retry handling and delayed retries.
- Records failed analysis jobs for auditing.

### 3. AI Model Routing and Fallback
The platform uses a model router to improve analysis availability.

**Primary provider: Google Gemini**
- Attempts analysis first.
- Retries once when analysis fails.

**Fallback provider: Groq**
- Invoked when Gemini fails after its retry.
- Generates structured incident analysis.

Both providers are expected to return a consistent analysis structure containing:
- Severity
- Root-cause hypothesis
- Evidence
- Recommended action
- Automatic remediation status

The router records which provider generated the result.

### 4. AI-Powered Incident Analysis
The AI worker processes queued incidents and stores analysis results.

Analysis includes:
- Incident severity classification.
- Evidence-based root-cause hypotheses.
- Recommended investigation or remediation steps.
- Provider identification.

**Safety:** Automatic remediation is disabled. The platform generates recommendations only and does not execute infrastructure or application changes.

### 5. Dashboard
A Flask-based web dashboard provides:
- Application health status.
- Incident statistics.
- Pending and failed analysis counts.
- Incident history.
- AI-generated analysis details.
- Prometheus metrics.
- Controlled error simulation.

The frontend uses HTML, CSS, and JavaScript.

### Dashboard Screenshots

#### Overview
![Dashboard Overview](screenshots/Screenshot%20(2201).png)

#### Incident Management
![Incident Management](screenshots/Screenshot%20(2212).png)

#### AI Incident Analysis
![AI Incident Analysis](screenshots/Screenshot%20(2213).png)

#### Metrics Dashboard
![Metrics Dashboard](screenshots/Screenshot%20(2214).png)

The application's Prometheus `/metrics` endpoint was also independently
validated using live Kubernetes application metrics. A separate Prometheus
server scraping and alerting setup was not part of this validation.

### 6. Observability
- Prometheus metrics integration.
- Application health endpoint.
- Error counter monitoring.
- Dashboard visibility into operational status.

## Technology Stack

| Category | Technologies |
|---|---|
| Backend | Python, Flask |
| AI | Google Gemini, Groq |
| Monitoring | Prometheus |
| Frontend | HTML, CSS, JavaScript |
| Containers | Docker |
| Orchestration | Kubernetes, Minikube |
| Testing | Pytest |
| Data storage | JSONL-based incident and analysis logs |
| Deployment | Gunicorn |

## Project Structure

```text
aiops-incident-platform/
│
├── app/
│   ├── main.py
│   ├── incident_detector.py
│   ├── incident_queue.py
│   ├── ai_worker.py
│   ├── ai_analyzer.py
│   ├── groq_analyzer.py
│   └── model_router.py
│
├── templates/
│   └── dashboard.html
│
├── static/
│   ├── css/
│   │   └── dashboard.css
│   └── js/
│       └── dashboard.js
│
├── tests/
│   ├── test_ai_analyzer.py
│   ├── test_ai_worker.py
│   ├── test_incident_detector.py
│   ├── test_incident_queue.py
│   ├── test_integration.py
│   ├── test_main.py
│   └── test_model_router.py
│
├── k8s/
│   ├── deployment.yaml
│   └── service.yaml
│
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── .dockerignore
└── .gitignore
```

## Local Setup

### Prerequisites
- Python 3.11
- pip
- Git
- Google Gemini API key
- Groq API key

### 1. Clone the repository

```bash
git clone https://github.com/Ajinkyapatil1234/aiops-incident-platform.git

cd aiops-incident-platform
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv

source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
```

Keep API keys private. The `.env` file is excluded from Git.

### 5. Start the Flask application

```bash
gunicorn --bind 0.0.0.0:8080 app.main:app
```

Open the dashboard at:

```text
http://127.0.0.1:8080/dashboard
```

## API Endpoints

| Endpoint | Purpose |
|---|---|
| `/` | Service information |
| `/health` | Application health check |
| `/metrics` | Prometheus metrics |
| `/simulate-error` | Trigger a controlled application error |
| `/dashboard` | Web dashboard |
| `/api/dashboard` | Dashboard data API |

## Docker

Build the application image:

```bash
docker build -t aiops-incident-platform:latest .
```

Run the container:

```bash
docker run --rm -p 8080:8080 \
  --env-file .env \
  aiops-incident-platform:latest
```

Open:

```text
http://127.0.0.1:8080/dashboard
```

## Kubernetes

Kubernetes deployment and service manifests are available in the `k8s/` directory.

```text
k8s/
├── deployment.yaml
└── service.yaml
```

These manifests provide the starting point for deploying the application to a Kubernetes cluster.

Configure provider credentials securely before deploying. Do not commit API keys or Kubernetes secrets containing credentials to Git.

## Running Tests

Run the complete test suite:

```bash
python -m pytest -v
```

The project has **34 passing tests** covering incident detection, queue management, AI analysis, model routing, worker behavior, and application endpoints.

## AI Fallback Validation

The model router was tested with a simulated Gemini failure followed by a real Groq API request.

Observed result:
- Gemini attempt 1: timeout.
- Gemini attempt 2: timeout.
- Router switched to Groq.
- Groq successfully generated structured analysis.
- `model_provider` returned `groq`.
- `automatic_remediation` remained `false`.

The live fallback path was verified successfully. Successful live Gemini analysis remains to be verified in the current environment.

## Security and Reliability

- API credentials are stored in environment variables.
- `.env` is excluded from version control and Docker build context.
- Incident and analysis records are maintained separately.
- Failed jobs are tracked for auditing.
- AI output is validated before being accepted.
- Automatic remediation is disabled.
- AI-generated recommendations require human review.

## Future Improvements

- Add persistent database storage.
- Improve dashboard filtering and incident search.
- Add notification integrations.
- Expand model-provider health monitoring.
- Add production-grade metrics and alerting.
- Introduce role-based access control.
- Improve deployment configuration and secret management.

## Author

**Ajinkya N. Patil**

Cloud & DevOps | Python | Kubernetes | Docker | AWS | Azure

GitHub: https://github.com/Ajinkyapatil1234

---

*This project is developed as a practical exploration of AIOps, incident management, observability, and AI-assisted SRE workflows.*
