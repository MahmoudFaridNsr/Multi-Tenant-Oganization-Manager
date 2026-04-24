import uuid


async def test_register_and_login(client):
    email = f"user-{uuid.uuid4()}@example.com"
    register = await client.post(
        "/auth/register",
        json={"email": email, "password": "StrongPassword123", "full_name": "John Doe"},
    )
    assert register.status_code == 201, register.text
    user_id = uuid.UUID(register.json()["user_id"])
    assert user_id

    login = await client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPassword123"},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
