# Member Callout

Design and requirements are in [DESIGN.md](DESIGN.md). This is Part B, a running slice of that design: a Django REST API, a Next.js leadership screen, Postgres, Redis, and a Celery worker, with two backend instances behind nginx for the devops bonus.

## Run it

Requires Docker and Docker Compose.

```bash
docker compose up -d --build
```

This builds the backend and frontend images, waits for Postgres and Redis to be healthy, runs migrations, seeds two locals with their logins and one already sent announcement, then starts two backend instances behind nginx, a Celery worker, and the frontend.

- Leadership screen: http://localhost:3000
- API through the load balancer: http://localhost:8080/api/v1
- API, instance 1 directly: http://localhost:8001/api/v1
- API, instance 2 directly: http://localhost:8002/api/v1

Re-seed at any point with `docker compose run --rm web1 python manage.py seed_demo_data`. It is safe to run more than once, it looks up existing rows by email and by request id instead of duplicating them.

## Logins

| Local | Role | Email | Password |
|---|---|---|---|
| Local 27 | Leadership | leader@local27.example | leadership123 |
| Local 27 | Member | member@local27.example | member123 |
| Local 84 | Leadership | leader@local84.example | leadership123 |
| Local 84 | Member | member@local84.example | member123 |

```bash
curl -s -X POST http://localhost:8080/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "leader@local27.example", "password": "leadership123"}'
```

## Member read and acknowledge

```bash
TOKEN=<token from the member@local27.example login>
ANNOUNCEMENT=d33cd1f4-f31e-5419-9c8d-805238dacf85

curl -s -X POST http://localhost:8080/api/v1/announcements/$ANNOUNCEMENT/read/ \
  -H "Authorization: Token $TOKEN"
curl -s -X POST http://localhost:8080/api/v1/announcements/$ANNOUNCEMENT/acknowledge/ \
  -H "Authorization: Token $TOKEN"
```

## Rule 1, a Local 27 login cannot read Local 84's data

```bash
TOKEN27=<token from the leader@local27.example login>
curl -s -o /dev/null -w "%{http_code}\n" \
  http://localhost:8080/api/v1/announcements/d33cd1f4-f31e-5419-9c8d-805238dacf85/ \
  -H "Authorization: Token <token from the leader@local84.example login>"
# 404: the base viewset scopes every query to the caller's own local before this handler runs
```

## Rule 2, a retried send does not double deliver

Automated: `docker compose run --rm web1 pytest -q core/tests/test_rule2_idempotency.py`, covers both a retried request and a restarted worker directly.

By hand, sending the same `Idempotency-Key` twice against the load balancer, so either instance can take either request:

```bash
TOKEN=<token from a leadership login>
curl -s -X POST http://localhost:8080/api/v1/announcements/ \
  -H "Authorization: Token $TOKEN" -H "Idempotency-Key: retry-demo-1" -H "Content-Type: application/json" \
  -d '{"title": "Retry check", "body": "Same key, twice."}'
# run the exact same curl again: the same id comes back, 200 instead of 201 the second time,
# and the recipient row count for that id never doubles
```

## TEST ACCOUNTS

The two ids below are not from one particular run. `seed_demo_data` derives them with `uuid5` from a fixed namespace, so they come out the same on any fresh `docker compose up`, not just this one.

```json
{
  "logins": {
    "local_27": {
      "leadership": { "email": "leader@local27.example", "password": "leadership123" },
      "member": { "email": "member@local27.example", "password": "member123" }
    },
    "local_84": {
      "leadership": { "email": "leader@local84.example", "password": "leadership123" },
      "member": { "email": "member@local84.example", "password": "member123" }
    }
  },
  "existing_announcement_id_local_27": "d33cd1f4-f31e-5419-9c8d-805238dacf85",
  "member_id_local_84": "d55d7e10-e4c9-5a62-850a-0f25d4dae1cb",
  "endpoints": [
    { "method": "POST", "path": "/api/v1/auth/login/", "auth": "none" },
    { "method": "GET", "path": "/api/v1/announcements/", "auth": "Token, leadership only, scoped to caller's local" },
    { "method": "POST", "path": "/api/v1/announcements/", "auth": "Token, leadership only, optional Idempotency-Key header" },
    { "method": "GET", "path": "/api/v1/announcements/{id}/", "auth": "Token, leadership only, scoped to caller's local" },
    { "method": "POST", "path": "/api/v1/announcements/draft/", "auth": "Token, leadership only" },
    { "method": "POST", "path": "/api/v1/announcements/{id}/read/", "auth": "Token, any member with a recipient row for that announcement" },
    { "method": "POST", "path": "/api/v1/announcements/{id}/acknowledge/", "auth": "Token, any member with a recipient row for that announcement" }
  ]
}
```

## What's in here

- `DESIGN.md`, requirements and design, Part 0 and Part A.
- `backend/`, Django, DRF, Postgres, Celery, Redis.
- `frontend/`, the one Next.js leadership screen.
- `nginx/`, the load balancer config for the devops bonus.
- `docker-compose.yml`, the whole stack.
- AI conversation exports, at the repo root, one file per design session.
