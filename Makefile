.PHONY: install test lint run docker-up docker-down

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check src tests evals

run:
	uvicorn db_agent.api:app --reload

docker-up:
	docker compose up --build

docker-down:
	docker compose down
