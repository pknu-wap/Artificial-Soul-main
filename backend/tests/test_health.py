import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


async def test_health_does_not_check_infrastructure(infrastructure_client):
    client, engine, connection, qdrant = infrastructure_client
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    engine.connect.assert_not_called()
    connection.execute.assert_not_awaited()
    qdrant.get_collections.assert_not_awaited()
    qdrant.collection_exists.assert_not_awaited()
    qdrant.create_collection.assert_not_awaited()
    qdrant.upsert.assert_not_awaited()


async def test_health_with_real_clients_without_infrastructure(settings):
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("postgres_fails", "qdrant_fails"),
    [(False, False), (True, False), (False, True), (True, True)],
)
async def test_readiness_reports_each_service(
    infrastructure_client, postgres_fails, qdrant_fails, caplog
):
    client, _, connection, qdrant = infrastructure_client
    sensitive_error = "postgresql://private:private-password@secret-host/db"
    if postgres_fails:
        connection.execute.side_effect = ConnectionError(sensitive_error)
    if qdrant_fails:
        qdrant.get_collections.side_effect = ConnectionError(sensitive_error)

    response = await client.get("/health/ready")
    failed = postgres_fails or qdrant_fails

    assert response.status_code == (503 if failed else 200)
    assert response.json() == {
        "status": "not_ready" if failed else "ready",
        "postgres": "error" if postgres_fails else "ok",
        "qdrant": "error" if qdrant_fails else "ok",
    }
    # Failure of either check must not skip the other check.
    connection.execute.assert_awaited_once()
    qdrant.get_collections.assert_awaited_once()
    assert sensitive_error not in response.text
    assert sensitive_error not in caplog.text


@pytest.mark.parametrize("slow_service", ["postgres", "qdrant", "both"])
async def test_readiness_times_out(infrastructure_client, slow_service):
    client, _, connection, qdrant = infrastructure_client

    async def wait_forever(*args, **kwargs):
        await asyncio.Event().wait()

    if slow_service in ("postgres", "both"):
        connection.execute.side_effect = wait_forever
    if slow_service in ("qdrant", "both"):
        qdrant.get_collections.side_effect = wait_forever

    response = await asyncio.wait_for(client.get("/health/ready"), timeout=1)

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "postgres": "error" if slow_service in ("postgres", "both") else "ok",
        "qdrant": "error" if slow_service in ("qdrant", "both") else "ok",
    }


async def test_swagger_and_openapi(infrastructure_client):
    client, _, _, _ = infrastructure_client
    docs = await client.get("/docs")
    schema = await client.get("/openapi.json")

    assert docs.status_code == 200
    assert "swagger-ui" in docs.text
    assert schema.status_code == 200
    assert schema.json()["info"] == {
        "title": "Artificial Soul API",
        "version": "0.1.0",
    }
    assert set(schema.json()["paths"]) == {"/health", "/health/ready"}
