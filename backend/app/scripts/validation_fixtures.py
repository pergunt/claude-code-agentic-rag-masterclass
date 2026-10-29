"""Fixtures for the validation suite: dedicated users, wiped and re-seeded on every run.

Usage (services must be running; API base from VALIDATION_API_URL, default http://localhost:8000):
    cd backend && venv/bin/python -m app.scripts.validation_fixtures setup
Prints JSON {"api", "supabase_url", "anon_key", "a": {...}, "b": {...}} where each user has
email, token, id and doc_id. Only public config values and test tokens are printed.
All data goes through the backend API (user JWT), so Storage is cleaned up too. No service-role use.
"""

import json
import os
import sys
import time
from pathlib import Path

import httpx

from app.config import get_settings
from app.db import create_anon_client
from app.scripts.dev_tokens import DEV_TEST_PASSWORD, sign_in

VAL_A = "rag-test-val-a@example.com"
VAL_B = "rag-test-val-b@example.com"
# Sign-in/sign-out flows only: signing out revokes the user's sessions server-side, which would
# invalidate the tokens the other tests hold for A and B.
VAL_C = "rag-test-val-c@example.com"
# Promoted to admin out of band (profiles.is_admin has no write policy); no seeded docs.
VAL_ADMIN = "rag-test-val-admin@example.com"

# backend/app/scripts/validation_fixtures.py -> repo root is parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_A = REPO_ROOT / "test-data/ingestion/velmora-station.md"
SEED_B = REPO_ROOT / "test-data/ingestion/b-recipes.md"

INGEST_TIMEOUT_SECONDS = 60


def api_url() -> str:
    return os.environ.get("VALIDATION_API_URL", "http://localhost:8000").rstrip("/")


def ensure_user(email: str) -> tuple[str, str]:
    """Return (access_token, user_id), signing the user up first if sign-in fails."""
    try:
        return sign_in(email)
    except Exception:
        # Email confirmation is disabled in the dev project, so sign-up logs in instantly.
        create_anon_client().auth.sign_up({"email": email, "password": DEV_TEST_PASSWORD})
        return sign_in(email)


def _client(token: str) -> httpx.Client:
    return httpx.Client(base_url=api_url(), headers={"Authorization": f"Bearer {token}"}, timeout=60)


def reset_user(token: str) -> None:
    """Delete all of the user's threads, then documents, through the backend API."""
    with _client(token) as client:
        for collection in ("threads", "documents"):
            res = client.get(f"/api/{collection}")
            res.raise_for_status()
            for row in res.json():
                deleted = client.delete(f"/api/{collection}/{row['id']}")
                if deleted.status_code not in (204, 404):
                    deleted.raise_for_status()


def seed(token: str, path: Path) -> dict:
    """Upload a file and wait until ingestion completes. Raises on `failed` or timeout."""
    with _client(token) as client:
        with path.open("rb") as f:
            res = client.post("/api/documents", files={"file": (path.name, f, "text/markdown")})
        res.raise_for_status()
        doc = res.json()
        deadline = time.monotonic() + INGEST_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            doc = client.get(f"/api/documents/{doc['id']}").json()
            if doc["status"] == "completed":
                return doc
            if doc["status"] == "failed":
                raise RuntimeError(f"seeding {path.name} failed: {doc.get('error')}")
            time.sleep(1)
    raise TimeoutError(f"seeding {path.name} did not complete in {INGEST_TIMEOUT_SECONDS}s")


def reset_admin_settings(token: str) -> None:
    """Clear every runtime-settings override (a failed earlier run may have left one behind)."""
    fields = ("llm_base_url", "llm_model", "llm_api_key", "embedding_base_url", "embedding_model", "embedding_api_key")
    with _client(token) as client:
        res = client.put("/api/admin/settings", json={name: None for name in fields})
    if res.status_code == 403:  # val-admin isn't promoted yet; nothing to reset
        print("validation_fixtures: val-admin is not promoted to admin yet, skipped settings reset", file=sys.stderr)
    else:
        res.raise_for_status()


def setup() -> dict:
    """Ensure both users exist, wipe their data, seed A and B, and return the env dict."""
    settings = get_settings()
    result = {"api": api_url(), "supabase_url": settings.supabase_url, "anon_key": settings.supabase_anon_key}
    for key, email, path in (("a", VAL_A, SEED_A), ("b", VAL_B, SEED_B)):
        token, user_id = ensure_user(email)
        reset_user(token)
        doc = seed(token, path)
        result[key] = {"email": email, "token": token, "id": user_id, "doc_id": doc["id"]}
    token, user_id = ensure_user(VAL_ADMIN)
    reset_user(token)
    result["admin"] = {"email": VAL_ADMIN, "token": token, "id": user_id}
    reset_admin_settings(token)
    token, user_id = ensure_user(VAL_C)
    reset_user(token)
    result["c"] = {"email": VAL_C, "id": user_id}  # no token: tests sign in through the UI
    return result


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] != "setup":
        print("usage: python -m app.scripts.validation_fixtures setup", file=sys.stderr)
        sys.exit(2)
    try:
        print(json.dumps(setup()))
    except Exception as exc:
        print(f"validation_fixtures: setup failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
