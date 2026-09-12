# Member Callout

Design and requirements: [DESIGN.md](DESIGN.md).

Run it: `docker compose up -d --build` (Docker + Compose). Builds, migrates, seeds two locals, starts two
backend instances behind nginx, a Celery worker, and the frontend. Screen: http://localhost:3000.
API via the load balancer: http://localhost:8080/api/v1 (instances directly at :8001 and :8002).

Logins: `leader@local27.example` / `leadership123`, `member@local27.example` / `member123` (Local 27),
`leader@local84.example` / `leadership123`, `member@local84.example` / `member123` (Local 84).

Member read/acknowledge:
```bash
curl -X POST http://localhost:8080/api/v1/announcements/<id>/read/ -H "Authorization: Token <member token>"
curl -X POST http://localhost:8080/api/v1/announcements/<id>/acknowledge/ -H "Authorization: Token <member token>"
```

Rule 1, a Local 27 login cannot read Local 84's data:
```bash
curl -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/v1/announcements/<Local 27 id>/ \
  -H "Authorization: Token <Local 84 leader token>"   # 404
```

Rule 2, a retried send does not double deliver. Automated: `docker compose run --rm web1 pytest -q core/tests/test_rule2_idempotency.py`.
By hand, same `Idempotency-Key` twice through the load balancer:
```bash
curl -X POST http://localhost:8080/api/v1/announcements/ -H "Authorization: Token <token>" \
  -H "Idempotency-Key: k1" -H "Content-Type: application/json" -d '{"title":"x","body":"y"}'
# repeat: same id comes back, 200 not 201, recipient count does not double
```

Re-seed anytime: `docker compose run --rm web1 python manage.py seed_demo_data` (safe to re-run).

## TEST ACCOUNTS

Ids below are deterministic (`uuid5` off a fixed namespace in `seed_demo_data`), so they are the same on any fresh `docker compose up`.

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
