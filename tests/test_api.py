import pytest
from fastapi.testclient import TestClient

from illustration_engine.api import create_app

VALID_BODY = {
    "issue_age": 40,
    "face_amount": 500_000,
    "annual_premium": 6_000,
    "projection_years": 25,
    "crediting": {
        "kind": "indexed",
        "current_rate": 0.07,
        "cap": 0.09,
        "floor": 0.0,
        "guaranteed_rate": 0.0,
    },
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health_and_readiness(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_version_reports_build_metadata(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_SHA", "abc1234")
    body = client.get("/version").json()
    assert body["git_sha"] == "abc1234"
    assert body["version"]


def test_illustration_returns_three_scenarios(client: TestClient) -> None:
    response = client.post("/v1/illustrations", json=VALID_BODY)
    assert response.status_code == 200
    body = response.json()
    assert set(body["scenarios"]) == {"guaranteed", "midpoint", "current"}
    current = body["scenarios"]["current"]
    assert current["credited_rate"] == pytest.approx(0.07)
    assert len(current["rows"]) == 25
    assert body["assumptions"]["premium_load"] == 0.06
    assert "synthetic" in body["notice"].lower()
    assert response.headers["x-request-id"]


def test_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/healthz", headers={"x-request-id": "trace-123"})
    assert response.headers["x-request-id"] == "trace-123"


def test_validation_errors_return_422(client: TestClient) -> None:
    too_young = {**VALID_BODY, "issue_age": 10}
    assert client.post("/v1/illustrations", json=too_young).status_code == 422
    extra_field = {**VALID_BODY, "agent_name": "nope"}
    assert client.post("/v1/illustrations", json=extra_field).status_code == 422
    assert client.post("/v1/illustrations", json={}).status_code == 422


def test_assumptions_endpoint_exposes_synthetic_tables(client: TestClient) -> None:
    body = client.get("/v1/assumptions").json()
    assert body["product"]["current_coi_factor"] == 0.6
    assert body["corridor_factor"]["25"] == 2.5
    assert body["mortality_per_thousand"]["35"] < body["mortality_per_thousand"]["65"]


def test_metrics_are_exposed_in_prometheus_format(client: TestClient) -> None:
    client.post("/v1/illustrations", json=VALID_BODY)
    client.get("/healthz")
    text = client.get("/metrics").text
    assert 'http_requests_total{method="POST",route="/v1/illustrations",status="200"}' in text
    assert 'illustrations_total{crediting_kind="indexed"}' in text
    assert "http_request_duration_seconds_bucket" in text


def test_unhandled_errors_are_converted_to_500(monkeypatch: pytest.MonkeyPatch) -> None:
    import illustration_engine.api as api_module

    def boom(_request: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(api_module, "illustrate", boom)
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post("/v1/illustrations", json=VALID_BODY)
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error"}
