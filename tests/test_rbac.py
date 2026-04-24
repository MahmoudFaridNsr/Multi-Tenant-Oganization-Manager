import uuid


async def _register(client, email: str) -> None:
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": "StrongPassword123", "full_name": email.split("@")[0]},
    )
    assert resp.status_code in {201, 409}, resp.text


async def _login(client, email: str) -> str:
    resp = await client.post("/auth/login", json={"email": email, "password": "StrongPassword123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_admin_vs_member_permissions(client):
    admin_email = f"admin-{uuid.uuid4()}@example.com"
    member_email = f"member-{uuid.uuid4()}@example.com"

    await _register(client, admin_email)
    await _register(client, member_email)

    admin_token = await _login(client, admin_email)
    create_org = await client.post(
        "/organization",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"org_name": "Electro Pi"},
    )
    assert create_org.status_code == 201, create_org.text
    org_id = create_org.json()["org_id"]

    invite = await client.post(
        f"/organization/{org_id}/user",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": member_email, "role": "member"},
    )
    assert invite.status_code == 201, invite.text

    member_token = await _login(client, member_email)

    list_users = await client.get(
        f"/organizations/{org_id}/users",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert list_users.status_code == 403

    create_item = await client.post(
        f"/organizations/{org_id}/item",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"item_details": {"k": "v"}},
    )
    assert create_item.status_code == 201, create_item.text

    list_items = await client.get(
        f"/organizations/{org_id}/item",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert list_items.status_code == 200, list_items.text
    assert len(list_items.json()["items"]) == 1
