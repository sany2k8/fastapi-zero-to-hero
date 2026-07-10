async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"


async def test_live(client):
    resp = await client.get("/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


async def test_ready_checks_database(client):
    resp = await client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "database": "ok"}


async def test_metrics_reports_requests(client):
    await client.get("/health")
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "uptime_seconds" in body
    assert any(route.startswith("GET /health") for route in body["routes"])


async def test_request_id_and_timing_headers(client):
    resp = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["x-request-id"] == "abc-123"
    assert float(resp.headers["x-process-time-ms"]) >= 0
