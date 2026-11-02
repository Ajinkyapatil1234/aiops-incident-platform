from app.main import app, ERROR_COUNT


def test_home_endpoint():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert response.json["service"] == "aiops-demo"


def test_health_endpoint_healthy(monkeypatch):
    monkeypatch.delenv("SIMULATE_FAILURE", raising=False)

    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json["status"] == "healthy"


def test_health_endpoint_simulated_failure(monkeypatch):
    monkeypatch.setenv("SIMULATE_FAILURE", "1")

    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 500
    assert response.json["status"] == "unhealthy"


def test_simulate_error_increments_counter():
    client = app.test_client()

    previous_count = ERROR_COUNT._value.get()

    response = client.get("/simulate-error")

    current_count = ERROR_COUNT._value.get()

    assert response.status_code == 500
    assert response.json["status"] == "error"
    assert current_count == previous_count + 1


def test_metrics_endpoint():
    client = app.test_client()

    response = client.get("/metrics")

    assert response.status_code == 200
    assert b"aiops_http_errors_total" in response.data
    assert b"aiops_http_requests_total" in response.data
