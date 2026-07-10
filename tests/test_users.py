from tests.conftest import ADMIN, MEMBER, login_headers


async def test_read_me(client, member_headers):
    resp = await client.get("/api/v1/users/me", headers=member_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == MEMBER["email"]


async def test_update_my_profile(client, member_headers):
    resp = await client.patch(
        "/api/v1/users/me", json={"full_name": "Renamed"}, headers=member_headers
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Renamed"


async def test_change_password_then_login_with_new_one(client, member_headers):
    resp = await client.patch(
        "/api/v1/users/me", json={"password": "brandnew99"}, headers=member_headers
    )
    assert resp.status_code == 200
    assert await login_headers(client, {**MEMBER, "password": "brandnew99"})


async def test_member_cannot_list_users(client, member_headers):
    resp = await client.get("/api/v1/users", headers=member_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


async def test_admin_lists_users_with_pagination(client, admin_headers, member_user):
    resp = await client.get(
        "/api/v1/users", params={"page": 1, "page_size": 1}, headers=admin_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["pages"] == 2
    assert len(body["items"]) == 1


async def test_admin_filters_users_by_role(client, admin_headers, member_user):
    resp = await client.get(
        "/api/v1/users", params={"role": "admin"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert [u["email"] for u in resp.json()["items"]] == [ADMIN["email"]]


async def test_member_cannot_view_other_user(client, member_headers, admin_headers):
    admins = await client.get(
        "/api/v1/users", params={"role": "admin"}, headers=admin_headers
    )
    admin_id = admins.json()["items"][0]["id"]
    resp = await client.get(f"/api/v1/users/{admin_id}", headers=member_headers)
    assert resp.status_code == 403


async def test_admin_promotes_member(client, admin_headers, member_user):
    resp = await client.patch(
        f"/api/v1/users/{member_user['id']}", json={"role": "admin"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


async def test_deactivated_user_cannot_log_in(client, admin_headers, member_user):
    resp = await client.delete(
        f"/api/v1/users/{member_user['id']}", headers=admin_headers
    )
    assert resp.status_code == 204

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": MEMBER["email"], "password": MEMBER["password"]},
    )
    assert resp.status_code == 403


async def test_unknown_user_is_404(client, admin_headers):
    resp = await client.get(
        "/api/v1/users/00000000-0000-0000-0000-000000000000", headers=admin_headers
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
