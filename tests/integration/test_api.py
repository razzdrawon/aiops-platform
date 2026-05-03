"""
Integration tests for the API endpoints.

Requires a real PostgreSQL database (TEST_DATABASE_URL).
The LangGraph pipeline runs in offline/heuristic mode (no API keys needed)
because OPENAI_API_KEY and PINECONE_API_KEY are not set in CI.
"""
import pytest


class TestHealth:
    async def test_health_returns_ok(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestCreateIncident:
    async def test_create_incident_returns_200(self, client):
        response = await client.post(
            "/incident",
            json={"title": "High error rate on checkout", "signals": {"error_rate": 0.12}},
        )
        assert response.status_code == 200

    async def test_create_incident_returns_incident_id(self, client):
        response = await client.post(
            "/incident",
            json={"title": "Database connection timeout", "signals": {"db_cpu": 95}},
        )
        data = response.json()
        assert "incident_id" in data
        assert len(data["incident_id"]) == 36  # UUID format

    async def test_create_incident_returns_status(self, client):
        response = await client.post(
            "/incident",
            json={"title": "Latency spike on payments", "signals": {"p95_ms": 2000}},
        )
        data = response.json()
        assert data["status"] in {"resolved", "blocked", "failed"}

    async def test_create_incident_includes_graph(self, client):
        response = await client.post(
            "/incident",
            json={"title": "OOM killed on worker pod", "signals": {"oom": True}},
        )
        data = response.json()
        assert "graph" in data
        assert "detector" in data["graph"]
        assert "diagnosis" in data["graph"]

    async def test_title_too_short_returns_422(self, client):
        response = await client.post(
            "/incident",
            json={"title": "ab"},
        )
        assert response.status_code == 422


class TestListIncidents:
    async def test_list_incidents_returns_list(self, client):
        response = await client.get("/incidents")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_created_incident_appears_in_list(self, client):
        await client.post(
            "/incident",
            json={"title": "Deploy failure on staging", "signals": {"deploy_failed": True}},
        )
        response = await client.get("/incidents")
        assert len(response.json()) >= 1

    async def test_list_includes_expected_fields(self, client):
        await client.post(
            "/incident",
            json={"title": "High error rate on payments", "signals": {}},
        )
        incidents = (await client.get("/incidents")).json()
        assert len(incidents) >= 1
        first = incidents[0]
        assert "incident_id" in first
        assert "title" in first
        assert "status" in first
        assert "created_at" in first


class TestGetIncident:
    async def test_get_incident_by_id(self, client):
        create_resp = await client.post(
            "/incident",
            json={"title": "Latency spike detected", "signals": {"p95_ms": 1800}},
        )
        incident_id = create_resp.json()["incident_id"]
        response = await client.get(f"/incidents/{incident_id}")
        assert response.status_code == 200
        assert response.json()["incident_id"] == incident_id

    async def test_get_nonexistent_incident_returns_404(self, client):
        response = await client.get("/incidents/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


class TestMetricsSummary:
    async def test_metrics_summary_returns_expected_shape(self, client):
        response = await client.get("/metrics/summary")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "blocked_rate" in data
