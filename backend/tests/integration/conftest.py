"""HTTP-level fixtures: a FastAPI TestClient against the seeded TEST_DATABASE_URL."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import seed as seed_service


@pytest.fixture
def client(db) -> Iterator[TestClient]:
    """Freshly seeded demo state (same as Reset demo). The lifespan is not run: tests own the schema."""
    seed_service.seed(db)
    db.commit()
    db.close()  # requests use their own sessions; never hold a transaction open (reset TRUNCATEs)
    yield TestClient(app)


@pytest.fixture
def opp_id(client: TestClient) -> int:
    opps = client.get("/api/opportunities", headers={"X-Demo-Role": "buyer"}).json()
    return next(o["id"] for o in opps if o["status"] == "published")
