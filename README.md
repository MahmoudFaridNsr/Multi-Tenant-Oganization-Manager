# Multi-Tenant Organization Manager (FastAPI + Async SQLAlchemy)

## Overview
This service is a secure, async, multi-tenant backend for managing organizations. Users can create organizations, invite members with roles (Admin/Member), create items inside organizations, and view audit logs. Admins can also ask a chatbot-style endpoint “what happened today?” which answers based on audit logs (with optional Gemini support).

## Tech Stack
- Python 3.11+
- FastAPI (ASGI)
- SQLAlchemy 2.0 (Async) + asyncpg
- PostgreSQL
- JWT authentication (python-jose)
- RBAC authorization (Admin/Member) + organization-scoped access control
- PostgreSQL Full-Text Search (tsvector/tsquery via SQLAlchemy `func`)
- HTTPX (Gemini API integration, optional)
- Pytest + pytest-asyncio

Dependencies: [pyproject.toml](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/pyproject.toml)

## Architecture
The project is organized by responsibility:
- **App bootstrap / lifecycle**: [main.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/main.py)
  - Uses FastAPI lifespan to initialize DB tables at startup (`create_all`) and dispose the engine on shutdown.
- **Configuration**: [settings.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/settings.py)
  - Loads configuration from environment variables via `pydantic-settings`.
- **Database**: [db.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/db.py)
  - Creates the async engine/sessionmaker and provides the per-request session dependency.
- **Domain model**: [models.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/models.py)
  - SQLAlchemy models and relationships.
- **Security**: [security.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/security.py)
  - Password hashing (PBKDF2-HMAC-SHA256) and JWT encode/decode.
- **Auth & RBAC dependencies**: [dependencies.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/dependencies.py)
  - Extracts the current user from JWT.
  - Ensures membership inside a given organization and enforces required role(s).
- **API routers**:
  - Auth: [auth.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/routers/auth.py)
  - Organizations: [organizations.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/routers/organizations.py)
  - Items: [items.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/routers/items.py)
  - Audit logs + Ask: [audit_logs.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/routers/audit_logs.py)
- **Seeder / dummy data**: [seed.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/seed.py)
  - Creates the database (if missing), creates tables, and inserts sample users/org/items/audit logs.

## Database Model
Core entities:
- **User**
  - `email` (unique), `full_name`, `password_hash`, `created_at`
- **Organization**
  - `org_name`, `created_at`
- **Membership**
  - Many-to-many between User and Organization with a `role`
  - Unique constraint on `(user_id, org_id)`
- **Role**
  - Enum: `admin` / `member`
- **Item**
  - Belongs to an organization (`org_id`) and the creator (`created_by_user_id`)
  - `item_details` stored as JSONB key/value payload
- **AuditLog**
  - Tracks actions per organization (`org_id`)
  - Records the actor (`actor_user_id`), action name, message, and JSONB metadata

Multi-tenancy & RBAC rules:
- A user can belong to multiple organizations.
- Any `/organizations/{org_id}/...` endpoint enforces that the user is a member of that org.
- Admin can see all org items; Member can only see items created by themselves.
- Admin-only capabilities:
  - Invite/add users to an organization
  - List/search users in an organization
  - View audit logs
  - Use the `/audit-logs/ask` endpoint

## Authentication (JWT)
Login endpoints:
- `POST /auth/login` (JSON body) — good for apps/scripts
- `POST /auth/token` (form-data) — compatible with Swagger “Authorize” (OAuth2 password flow)

Successful login returns:
```json
{ "access_token": "jwt", "token_type": "bearer" }
```

Protected endpoints require:
`Authorization: Bearer <token>`

## Authorization (RBAC)
RBAC enforcement is done via dependencies:
- `require_org_role(Role.admin)` for admin-only endpoints
- `require_org_role(Role.admin, Role.member)` for member/admin endpoints

Implementation: [dependencies.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/dependencies.py)

## API Endpoints
### Auth
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/token` (Swagger OAuth2)

### Organizations
- `POST /organization` (creates org + admin membership + audit log)
- `POST /organization/{org_id}/user` (Admin only)
- `GET /organizations/{org_id}/users?limit=&offset=` (Admin only)
- `GET /organizations/{org_id}/users/search?q=keyword` (Admin only, Full-Text Search)

### Items
- `POST /organizations/{org_id}/item` (Admin/Member)
- `GET /organizations/{org_id}/item?limit=&offset=` (Admin sees all; Member sees own)

### Audit Logs + Insights
- `GET /organizations/{org_id}/audit-logs` (Admin only)
- `POST /organizations/{org_id}/audit-logs/ask` (Admin only)
  - Body:
    ```json
    { "question": "what happened today?", "stream": false }
    ```
  - If `stream=true`, the endpoint streams the answer as plain text.

## Gemini Integration (Ask Endpoint)
The Ask endpoint optionally uses Gemini:
- If `gemini_api_key` is configured, the endpoint sends today’s audit logs + the admin’s question to Gemini and returns the model’s response.
- If Gemini is not configured or fails, it falls back to a simple local summary based on the logs.

Gemini implementation: [audit_logs.py](file:///c:/Users/Farid/Documents/Interview%20task/Project/Multi-Tenant-Oganization-Manager/app/routers/audit_logs.py#L51-L85)

## Running Locally
### 1) Database
Local PostgreSQL example:
- host: `localhost`
- port: `5432`
- user: `postgres`
- password: `123456`

Configure via `DATABASE_URL` (optional). Otherwise the default in `settings.py` is used.

### 2) Install dependencies
```bash
python -m pip install -e ".[test]"
```

### 3) Initialize DB + seed dummy data
```bash
python -m app.seed
```

Seeded accounts:
- admin: `admin@example.com` / `StrongPassword123`
- member: `member@example.com` / `StrongPassword123`

### 4) Start the server
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI:
`http://127.0.0.1:8000/docs`

## Windows PowerShell Notes
- In PowerShell, `curl` is often an alias for `Invoke-WebRequest`. Use `curl.exe` for real curl.
- Easiest way to call the API from PowerShell is `Invoke-RestMethod`.

Example login (PowerShell):
```powershell
$base = "http://127.0.0.1:8000"
$body = @{ email="admin@example.com"; password="StrongPassword123" } | ConvertTo-Json
(Invoke-RestMethod -Method Post -Uri "$base/auth/login" -ContentType "application/json" -Body $body).access_token
```

## Testing
```bash
python -m pytest -q
```

Coverage focus:
- Authentication
- RBAC enforcement
- Organization isolation

## Design Tradeoffs
- Uses `create_all` (no Alembic migrations) to keep local setup simple. Production systems should use migrations.
- Full-text search is implemented functionally using `to_tsvector`/`plainto_tsquery`. For production performance, add a GIN index.
- Password hashing uses PBKDF2 to avoid bcrypt compatibility issues on some environments. In production, Argon2/bcrypt are common alternatives depending on policy.

## Ai Tools i used to code

- I have used TraeAI Code editor to write some parts of the code { Like Tests , and Seed and project docs , this readme file , pyproject.toml}