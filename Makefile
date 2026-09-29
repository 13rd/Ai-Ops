.PHONY: help install migrate seed run docker-up docker-down clean test sim sim-standalone \
        demo-up demo-seed demo-down demo-status demo-trigger demo-stop demo-run-ml \
        demo-bootstrap target-up target-down

help:
	@echo "Available commands:"
	@echo "  make install        - Install dependencies"
	@echo "  make migrate        - Run database migrations"
	@echo "  make seed           - Seed database with test data"
	@echo "  make run            - Run development server"
	@echo "  make docker-up      - Start all services with Docker"
	@echo "  make docker-down    - Stop all Docker services"
	@echo "  make clean          - Clean cache and temp files"
	@echo "  make test           - Run tests"
	@echo "  make sim            - Start server simulator (API mode)"
	@echo "  make sim-standalone - Generate metrics to file (standalone)"
	@echo "  make target-up      - Start standalone test stand (target + net-peer)"
	@echo "  make target-down    - Stop standalone test stand"
	@echo "  make demo-up        - Start full demo system"
	@echo "  make demo-bootstrap - Register stress-target in DB (after demo-up)"

install:
	uv sync

migrate:
	uv run alembic upgrade head

seed:
	uv run python scripts/seed_db.py

run:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f backend

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

test:
	uv run pytest

sim:
	uv run python -m data_gen.simulator --config data_gen/simulator/default_config.yml -v

sim-standalone:
	uv run python -m data_gen.simulator --standalone --output /tmp/simulator_metrics.jsonl --duration 3600 -v

# ── Demo environment ───────────────────────────────────────────────────────────
# Usage:
#   make demo-up
#   make demo-seed SERVER=prod-web
#   make demo-trigger TYPE=cpu_spike SERVER_ID=1
#   make demo-stop SERVER_ID=1
#   make demo-run-ml SERVER_ID=1

demo-up:
	docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d

# Register the stress-target in the DB (run after demo-up). Backend reaches it
# by compose service name stress-target:22.
demo-bootstrap:
	docker compose exec backend uv run python scripts/bootstrap_stress_target.py

demo-seed:
	docker compose exec backend uv run python scripts/demo_seed_target.py --server-name $(or $(SERVER),prod-web)

demo-down:
	docker compose -f docker-compose.yml -f docker-compose.demo.yml down

demo-status:
	@curl -sf -H "Authorization: Bearer $$(cat /tmp/demo_token 2>/dev/null)" \
	  http://localhost:8000/api/v1/demo/status | python3 -m json.tool

demo-trigger:
	@curl -sf -X POST \
	  -H "Authorization: Bearer $$(cat /tmp/demo_token 2>/dev/null)" \
	  "http://localhost:8000/api/v1/demo/trigger/$(or $(TYPE),cpu_spike)?server_id=$(or $(SERVER_ID),1)" \
	  | python3 -m json.tool

demo-stop:
	@curl -sf -X POST \
	  -H "Authorization: Bearer $$(cat /tmp/demo_token 2>/dev/null)" \
	  "http://localhost:8000/api/v1/demo/stop?server_id=$(or $(SERVER_ID),1)" \
	  | python3 -m json.tool

demo-run-ml:
	@curl -sf -X POST \
	  -H "Authorization: Bearer $$(cat /tmp/demo_token 2>/dev/null)" \
	  "http://localhost:8000/api/v1/demo/run-ml?server_id=$(or $(SERVER_ID),1)" \
	  | python3 -m json.tool

# ── Standalone test stand (no main system) ──────────────────────────────────────
# Usage:
#   make target-up
#   docker exec server-monitor-stress-target /usr/local/bin/demo_anomaly.sh cpu 120
#   make target-down
target-up:
	docker compose -f docker-compose.target.yml up -d --build

target-down:
	docker compose -f docker-compose.target.yml down
