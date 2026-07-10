async def _create(client, headers, name, **extra):
    resp = await client.post(
        "/api/v1/projects", json={"name": name, **extra}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_project(client, member_headers, member_user):
    body = await _create(client, member_headers, "Alpha", description="First")
    assert body["status"] == "active"
    assert body["owner_id"] == member_user["id"]


async def test_duplicate_name_for_same_owner_conflicts(client, member_headers):
    await _create(client, member_headers, "Alpha")
    resp = await client.post(
        "/api/v1/projects", json={"name": "Alpha"}, headers=member_headers
    )
    assert resp.status_code == 409


async def test_same_name_allowed_for_different_owners(client, member_headers, other_headers):
    await _create(client, member_headers, "Alpha")
    await _create(client, other_headers, "Alpha")


async def test_other_users_project_is_forbidden(client, other_headers, project):
    resp = await client.get(f"/api/v1/projects/{project['id']}", headers=other_headers)
    assert resp.status_code == 403


async def test_admin_can_read_any_project(client, admin_headers, project):
    resp = await client.get(f"/api/v1/projects/{project['id']}", headers=admin_headers)
    assert resp.status_code == 200


async def test_list_is_scoped_to_owner(client, member_headers, other_headers):
    await _create(client, member_headers, "Mine")
    await _create(client, other_headers, "Theirs")
    resp = await client.get("/api/v1/projects", headers=member_headers)
    assert [p["name"] for p in resp.json()["items"]] == ["Mine"]


async def test_search_and_sort(client, member_headers):
    for name in ("Backend rewrite", "Frontend polish", "Backend docs"):
        await _create(client, member_headers, name)
    resp = await client.get(
        "/api/v1/projects",
        params={"search": "backend", "sort_by": "name", "sort_dir": "asc"},
        headers=member_headers,
    )
    assert [p["name"] for p in resp.json()["items"]] == ["Backend docs", "Backend rewrite"]


async def test_filter_by_status(client, member_headers):
    await _create(client, member_headers, "Live")
    await _create(client, member_headers, "Old", status="archived")
    resp = await client.get(
        "/api/v1/projects", params={"status": "archived"}, headers=member_headers
    )
    assert [p["name"] for p in resp.json()["items"]] == ["Old"]


async def test_update_project(client, member_headers, project):
    resp = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"description": "Updated", "status": "archived"},
        headers=member_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"
    assert resp.json()["description"] == "Updated"


async def test_soft_delete_and_restore(client, member_headers, project):
    pid = project["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}", headers=member_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/projects/{pid}", headers=member_headers)
    assert resp.status_code == 404

    resp = await client.post(f"/api/v1/projects/{pid}/restore", headers=member_headers)
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/projects/{pid}", headers=member_headers)
    assert resp.status_code == 200


async def test_restore_of_live_project_conflicts(client, member_headers, project):
    resp = await client.post(
        f"/api/v1/projects/{project['id']}/restore", headers=member_headers
    )
    assert resp.status_code == 409


async def test_empty_name_is_422(client, member_headers):
    resp = await client.post(
        "/api/v1/projects", json={"name": "   "}, headers=member_headers
    )
    assert resp.status_code == 422
