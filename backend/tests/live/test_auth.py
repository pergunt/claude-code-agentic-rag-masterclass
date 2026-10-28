def test_AUTH_01_health(env):
    import httpx

    res = httpx.get(f"{env['api']}/health", timeout=10)
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_AUTH_02_api_auth(env, a):
    import httpx

    api = env["api"]
    assert httpx.get(f"{api}/api/me", timeout=10).status_code == 401
    bad = httpx.get(f"{api}/api/me", headers={"Authorization": "Bearer garbage.token.value"}, timeout=10)
    assert bad.status_code == 401
    ok = a.get("/api/me")
    assert ok.status_code == 200
    body = ok.json()
    assert body["id"] == env["a"]["id"]
    assert body["email"] == env["a"]["email"]
