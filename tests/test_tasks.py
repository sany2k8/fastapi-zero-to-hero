from datetime import UTC, datetime, timedelta


async def test_create_task_defaults(client, member_headers, project):
    resp = await client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "New Task"},
        headers=member_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "todo"
    assert body["priority"] == "medium"


async def test_cannot_create_task_in_foreign_project(client, other_headers, project):
    resp = await client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Sneaky"},
        headers=other_headers,
    )
    assert resp.status_code == 403


async def test_past_due_date_is_422(client, member_headers, project):
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    resp = await client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Late", "due_date": past},
        headers=member_headers,
    )
    assert resp.status_code == 422


async def test_filter_by_status_and_priority(client, member_headers, project):
    for title, status_, priority in (
        ("A", "todo", "low"),
        ("B", "in_progress", "high"),
        ("C", "in_progress", "low"),
    ):
        await client.post(
            "/api/v1/tasks",
            json={
                "project_id": project["id"],
                "title": title,
                "status": status_,
                "priority": priority,
            },
            headers=member_headers,
        )
    resp = await client.get(
        "/api/v1/tasks",
        params={"status": "in_progress", "priority": "low"},
        headers=member_headers,
    )
    assert [t["title"] for t in resp.json()["items"]] == ["C"]


async def test_search_matches_description(client, member_headers, project):
    await client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Opaque", "description": "fix the login flow"},
        headers=member_headers,
    )
    resp = await client.get(
        "/api/v1/tasks", params={"search": "login"}, headers=member_headers
    )
    assert resp.json()["total"] == 1


async def test_sort_by_title_ascending(client, member_headers, project):
    for title in ("Charlie", "Alpha", "Bravo"):
        await client.post(
            "/api/v1/tasks",
            json={"project_id": project["id"], "title": title},
            headers=member_headers,
        )
    resp = await client.get(
        "/api/v1/tasks",
        params={"sort_by": "title", "sort_dir": "asc"},
        headers=member_headers,
    )
    assert [t["title"] for t in resp.json()["items"]] == ["Alpha", "Bravo", "Charlie"]


async def test_update_task_status(client, member_headers, task):
    resp = await client.patch(
        f"/api/v1/tasks/{task['id']}", json={"status": "done"}, headers=member_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


async def test_soft_delete_and_restore_task(client, member_headers, task):
    tid = task["id"]
    assert (await client.delete(f"/api/v1/tasks/{tid}", headers=member_headers)).status_code == 204
    assert (await client.get(f"/api/v1/tasks/{tid}", headers=member_headers)).status_code == 404
    assert (
        await client.post(f"/api/v1/tasks/{tid}/restore", headers=member_headers)
    ).status_code == 200
    assert (await client.get(f"/api/v1/tasks/{tid}", headers=member_headers)).status_code == 200


async def test_tasks_of_deleted_project_disappear_from_list(
    client, member_headers, project, task
):
    await client.delete(f"/api/v1/projects/{project['id']}", headers=member_headers)
    resp = await client.get("/api/v1/tasks", headers=member_headers)
    assert resp.json()["total"] == 0


# --- Attachments -------------------------------------------------------------


async def _upload(
    client, headers, task_id, filename="notes.txt", content=b"hello", ct="text/plain"
):
    return await client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        files={"file": (filename, content, ct)},
        headers=headers,
    )


async def test_upload_and_download_attachment(client, member_headers, task):
    resp = await _upload(client, member_headers, task["id"], content=b"file body")
    assert resp.status_code == 201, resp.text
    attachment = resp.json()
    assert attachment["filename"] == "notes.txt"
    assert attachment["size_bytes"] == len(b"file body")

    listing = await client.get(
        f"/api/v1/tasks/{task['id']}/attachments", headers=member_headers
    )
    assert len(listing.json()) == 1

    download = await client.get(
        f"/api/v1/tasks/{task['id']}/attachments/{attachment['id']}",
        headers=member_headers,
    )
    assert download.status_code == 200
    assert download.content == b"file body"


async def test_disallowed_content_type_is_400(client, member_headers, task):
    resp = await _upload(
        client, member_headers, task["id"], filename="app.exe", ct="application/x-msdownload"
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"


async def test_oversized_upload_is_413(client, member_headers, task):
    # Test env caps uploads at 10 kB (MAX_UPLOAD_SIZE_BYTES in conftest).
    resp = await _upload(client, member_headers, task["id"], content=b"x" * 20_000)
    assert resp.status_code == 413


async def test_delete_attachment(client, member_headers, task):
    attachment = (await _upload(client, member_headers, task["id"])).json()
    resp = await client.delete(
        f"/api/v1/tasks/{task['id']}/attachments/{attachment['id']}",
        headers=member_headers,
    )
    assert resp.status_code == 204
    listing = await client.get(
        f"/api/v1/tasks/{task['id']}/attachments", headers=member_headers
    )
    assert listing.json() == []


async def test_foreign_task_attachment_is_forbidden(client, other_headers, task):
    resp = await _upload(client, other_headers, task["id"])
    assert resp.status_code == 403
