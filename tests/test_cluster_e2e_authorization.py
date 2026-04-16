import os
import time
import uuid

import httpx
import pytest


pytestmark = pytest.mark.e2e


def _base_url() -> str:
    return os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")


def _bootstrap_key() -> str:
    key = os.getenv("BOOTSTRAP_ADMIN_KEY")
    if not key:
        raise RuntimeError("BOOTSTRAP_ADMIN_KEY env is required for e2e tests")
    return key


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register_admin(client: httpx.Client, username: str, email: str, password: str) -> dict:
    r = client.post(
        "/auth/register-admin",
        headers={"X-Bootstrap-Key": _bootstrap_key()},
        json={"username": username, "email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _register_user(client: httpx.Client, username: str, email: str, password: str) -> dict:
    r = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _token(client: httpx.Client, username: str, password: str) -> str:
    r = client.post(
        "/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _wait_health(client: httpx.Client, timeout_s: int = 20) -> None:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            r = client.get("/health")
            last = r
            if r.status_code == 200:
                return
        except httpx.HTTPError as e:
            last = e
        time.sleep(0.5)
    raise AssertionError(f"Service not healthy at {_base_url()}: {last}")


def test_e2e_authorization_user_vs_admin():
    password = "verysecret123"
    admin_u = _unique("admin")
    user_u = _unique("user")

    with httpx.Client(base_url=_base_url(), timeout=10.0) as client:
        _wait_health(client)

        admin = _register_admin(client, admin_u, f"{admin_u}@example.com", password)
        user = _register_user(client, user_u, f"{user_u}@example.com", password)

        admin_token = _token(client, admin_u, password)
        user_token = _token(client, user_u, password)

        # user cannot read admin
        r = client.get(f"/players/{admin['id']}", headers=_auth(user_token))
        assert r.status_code == 403, r.text

        # user can read self
        r = client.get(f"/players/{user['id']}", headers=_auth(user_token))
        assert r.status_code == 200, r.text
        assert r.json()["id"] == user["id"]

        # user list returns only self
        r = client.get("/players", headers=_auth(user_token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == user["id"]

        # admin list includes both
        r = client.get("/players", headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        ids = {p["id"] for p in r.json()}
        assert admin["id"] in ids and user["id"] in ids

        # user cannot delete anyone (including self)
        r = client.delete(f"/players/{user['id']}", headers=_auth(user_token))
        assert r.status_code == 403, r.text

        # admin can delete user
        r = client.delete(f"/players/{user['id']}", headers=_auth(admin_token))
        assert r.status_code == 204, r.text

