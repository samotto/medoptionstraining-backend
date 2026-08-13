# Med Options Training Backend

FastAPI and PostgreSQL backend for the Med Options employee training portal.

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.seed
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The local database is `medoptionstraining`. API docs are available at
`http://127.0.0.1:8000/docs` and health at `http://127.0.0.1:8000/health`.

The seed creates the configured bootstrap Admin, reusable lookup values, and a
placeholder orientation course. Replace placeholder video URLs through the
Administration UI.

## Main resources

- `/auth`: registration, verification, login, logout, current user
- `/users`: Admin user management
- `/courses` and `/lessons`: training content
- `/courses/{course_id}/lessons`: ordered course content
- `/users/{user_id}/courses`: course assignment and progress
- `/admin/lookup-lists` and `/admin/audit`: reusable administration

Production runs migrations and idempotent seeding before Uvicorn using the
`Procfile`. Store all secrets and deployment values in Railway variables.
