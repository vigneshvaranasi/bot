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
