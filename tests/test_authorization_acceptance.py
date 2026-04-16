def _register_admin(client):
    r = client.post(
        "/auth/register-admin",
        headers={"X-Bootstrap-Key": "test-bootstrap"},
        json={"username": "admin1", "email": "admin1@example.com", "password": "verysecret123"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["role"] == "admin"
    return data


def _register_user(client, username: str, email: str):
    r = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": "verysecret123"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["role"] == "user"
    return data


def _token(client, username: str, password: str = "verysecret123") -> str:
    r = client.post(
        "/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_user_cannot_read_other_player(client):
    admin = _register_admin(client)
    user = _register_user(client, "user1", "user1@example.com")

    user_token = _token(client, "user1")

    r = client.get(f"/players/{admin['id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 403, r.text

    r = client.get(f"/players/{user['id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "user1"


def test_user_list_players_returns_only_self(client):
    _register_admin(client)
    user = _register_user(client, "user1", "user1@example.com")
    _register_user(client, "user2", "user2@example.com")

    user_token = _token(client, "user1")

    r = client.get("/players", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == user["id"]


def test_admin_can_read_all_players_and_delete(client):
    admin = _register_admin(client)
    user1 = _register_user(client, "user1", "user1@example.com")
    _register_user(client, "user2", "user2@example.com")

    admin_token = _token(client, "admin1")

    r = client.get("/players", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    usernames = {p["username"] for p in r.json()}
    assert {"admin1", "user1", "user2"} <= usernames

    r = client.delete(f"/players/{user1['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 204, r.text

    r = client.get(f"/players/{user1['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 404, r.text


def test_user_cannot_delete_anyone(client):
    _register_admin(client)
    user1 = _register_user(client, "user1", "user1@example.com")
    user2 = _register_user(client, "user2", "user2@example.com")

    user_token = _token(client, "user1")

    r = client.delete(f"/players/{user2['id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 403, r.text

    r = client.delete(f"/players/{user1['id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 403, r.text


def test_openapi_contains_auth_paths(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    assert "/auth/register" in paths
    assert "/auth/token" in paths
    assert "/auth/register-admin" in paths

