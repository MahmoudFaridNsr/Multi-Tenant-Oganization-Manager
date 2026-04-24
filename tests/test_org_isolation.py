import uuid


async def _register_and_login(client, email: str) -> str:
    await client.post(
        "/auth/register",
        json={"email": email, "password": "StrongPassword123", "full_name": email.split("@")[0]},
    )
    resp = await client.post("/auth/login", json={"email": email, "password": "StrongPassword123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_org_isolation_membership_required(client):
    token = await _register_and_login(client, f"user-{uuid.uuid4()}@example.com")

    org1 = await client.post(
        "/organization",
        headers={"Authorization": f"Bearer {token}"},
        json={"org_name": "Org 1"},
    )
    assert org1.status_code == 201, org1.text
    org1_id = org1.json()["org_id"]

    org2 = await client.post(
        "/organization",
        headers={"Authorization": f"Bearer {token}"},
        json={"org_name": "Org 2"},
    )
    assert org2.status_code == 201, org2.text
    org2_id = org2.json()["org_id"]

    other_user_token = await _register_and_login(client, f"other-{uuid.uuid4()}@example.com")

    forbidden = await client.get(
        f"/organizations/{org1_id}/item",
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    assert forbidden.status_code == 403

    admin_only = await client.get(
        f"/organizations/{org2_id}/users",
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    assert admin_only.status_code == 403
