# Support Bot

## Setup

### Docker

Start local services with Docker Compose:

```bash
docker-compose up -d
```

### Database

#### Initialization

```bash
cd src/api/db
alembic upgrade head
```

#### Migrations

If you make any changes to `src/api/db/models.py` to modify tables, do this:

```bash
cd src/api/db
alembic revision --autogenerate -m "describe changes"
alembic upgrade head
```

## Tests

Run all tests:
```bash
uv run pytest src/api/tests/
```

Run tests with verbose output and coverage report:
```bash
uv run pytest src/api/tests/ -v --tb=short --cov=src/api --cov-report=term-missing
```

