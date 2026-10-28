"""Fixtures for live tests (need running services + Supabase). Run with `pytest -m live`."""

import httpx
import pytest

from app.scripts import validation_fixtures


def pytest_collection_modifyitems(items):
    """Mark every test under tests/live/ as `live` (deselected by default via pytest.ini)."""
    for item in items:
        if "tests/live/" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.live)


@pytest.fixture(scope="session")
def env() -> dict:
    """Setup dict from validation_fixtures.setup(): keys `api`, `supabase_url`, `anon_key`,
    `a` and `b` (each a dict with `email`, `token`, `id`, `doc_id`). Use dict access."""
    api = validation_fixtures.api_url()
    try:
        httpx.get(f"{api}/health", timeout=5).raise_for_status()
    except httpx.HTTPError as exc:
        pytest.fail(f"services not running ({exc}); use scripts/validate.sh", pytrace=False)
    return validation_fixtures.setup()


def _api_client(env: dict, user: str):
    with httpx.Client(
        base_url=env["api"], headers={"Authorization": f"Bearer {env[user]['token']}"}, timeout=60
    ) as client:
        yield client


@pytest.fixture(scope="session")
def a(env):
    """httpx.Client for the backend API as val-a."""
    yield from _api_client(env, "a")


@pytest.fixture(scope="session")
def b(env):
    """httpx.Client for the backend API as val-b."""
    yield from _api_client(env, "b")


@pytest.fixture(scope="session")
def anon_rest(env):
    """httpx.Client for Supabase with only the anon `apikey` header (no user JWT)."""
    with httpx.Client(base_url=env["supabase_url"], headers={"apikey": env["anon_key"]}, timeout=60) as client:
        yield client


@pytest.fixture
def new_thread():
    """Factory `new_thread(client) -> thread_id`; created threads are deleted at teardown."""
    created: list[tuple[httpx.Client, str]] = []

    def make(client: httpx.Client) -> str:
        res = client.post("/api/threads", json={})
        res.raise_for_status()
        thread_id = res.json()["id"]
        created.append((client, thread_id))
        return thread_id

    yield make
    for client, thread_id in created:
        client.delete(f"/api/threads/{thread_id}")  # 404 if the test already deleted it
