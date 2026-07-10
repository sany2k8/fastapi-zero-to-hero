from tests.conftest import MEMBER, register


async def test_register_returns_201_without_password(client):
    body = await register(client, MEMBER)
    assert body["email"] == MEMBER["email"]
    assert body["role"] == "member"
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_duplicate_email_conflicts(client, member_user):
    resp = await client.post("/api/v1/auth/register", json=MEMBER)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_register_weak_password_rejected(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "full_name": "X", "password": "lettersonly"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert any("password" in d["loc"] for d in body["error"]["details"])


async def test_register_email_normalized_and_name_stripped(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "MiXeD@Example.com", "full_name": "  Padded Name  ", "password": "abc12345"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "mixed@example.com"
    assert resp.json()["full_name"] == "Padded Name"


async def test_login_wrong_password_is_401(client, member_user):
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": MEMBER["email"], "password": "wrong-pass1"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_protected_route_without_token_is_401(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


async def test_garbage_token_is_401(client):
    resp = await client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert resp.status_code == 401


async def test_refresh_rotates_tokens(client, member_user):
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": MEMBER["email"], "password": MEMBER["password"]},
    )
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    new_access = resp.json()["access_token"]

    me = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {new_access}"}
    )
    assert me.status_code == 200


async def test_access_token_rejected_as_refresh_token(client, member_headers):
    access_token = member_headers["Authorization"].removeprefix("Bearer ")
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401
