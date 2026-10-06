.PHONY: help up down logs build doctor ingest seed backend-run backend-test pi-run pi-doctor web-dev

help:
	@echo "Clausewise · Common commands"
	@echo "  make up             Start the full stack with docker compose"
	@echo "  make down           Stop docker compose"
	@echo "  make logs           Follow logs"
	@echo "  make doctor         Model connectivity self-check (Python)"
	@echo "  make ingest         Import sample documents from department_files"
	@echo "  make seed           Seed data (departments/glossary/calendar/rules)"
	@echo "  make backend-run    Run the backend locally"
	@echo "  make backend-test   Run backend unit tests"
	@echo "  make pi-run         Run the pi agent service locally"
	@echo "  make pi-doctor      pi framework self-check"
	@echo "  make web-dev        Run the frontend dev server locally"

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

doctor:
	docker compose exec backend python -m scripts.doctor

ingest:
	docker compose exec backend python -m scripts.ingest_department_files --base /app/department_files

seed:
	docker compose exec backend python -m scripts.seed_data

backend-install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

backend-run:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

backend-test:
	cd backend && . .venv/bin/activate && pytest

pi-install:
	cd services/pi-agent && npm install

pi-run:
	cd services/pi-agent && npm run dev

# pi doctor depends on devDependencies, unavailable in the container; run only locally after npm install
pi-doctor:
	cd services/pi-agent && npm run doctor

web-install:
	cd web && npm install

web-dev:
	cd web && BACKEND_URL=http://localhost:8000 npm run dev
