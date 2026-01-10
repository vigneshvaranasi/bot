.PHONY: infra bootstrap dev be-dev fe-dev prod be-prod fe-prod stop help

help:
	@echo ""
	@echo "Infra:"
	@echo "  make infra        Start required services (DBs, Qdrant)"
	@echo ""
	@echo "One-time setup:"
	@echo "  make bootstrap    Run once after cloning"
	@echo ""
	@echo "Development:"
	@echo "  make dev          Start backend + frontend (dev)"
	@echo "  make be-dev       Start backend (dev)"
	@echo "  make fe-dev       Start frontend (dev)"
	@echo ""
	@echo "Production:"
	@echo "  make prod         Start backend + frontend (prod)"
	@echo "  make be-prod      Start backend (prod)"
	@echo "  make fe-prod      Start frontend (prod)"
	@echo ""

# --------------------
# Infra
# --------------------

infra:
	docker compose up -d

stop:
	docker compose down

# --------------------
# Bootstrap
# --------------------

bootstrap: infra
	uv sync
	cd src/api/db && alembic upgrade head
	python scripts/ingestion/main.py
	cd frontend && npm install

# --------------------
# Development
# --------------------

dev:
	make -j be-dev fe-dev

be-dev:
	uv run uvicorn src.api.main:app --reload

fe-dev:
	cd frontend && npm run dev

# --------------------
# Production
# --------------------

prod:
	make -j be-prod fe-prod

be-prod:
	uv run uvicorn src.api.main:app \
		--host 0.0.0.0 \
		--port 8000 \
		--log-level info

fe-prod:
	cd frontend && npm run build && serve -s dist -l 3000