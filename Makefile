.PHONY: install lint typecheck test security run docker-build docker-run tf-fmt tf-validate

PY ?= python
IMAGE ?= illustration-engine:local

install:
	$(PY) -m pip install -e ".[dev]"

lint:
	ruff format --check .
	ruff check .

typecheck:
	mypy

test:
	pytest

security:
	bandit -q -r src -c pyproject.toml
	pip-audit --skip-editable

run:
	uvicorn illustration_engine.api:app --reload --port 8080

docker-build:
	docker build --build-arg GIT_SHA=$$(git rev-parse --short HEAD) --build-arg BUILD_TIME=$$(date -u +%FT%TZ) -t $(IMAGE) .

docker-run:
	docker run --rm -p 8080:8080 $(IMAGE)

tf-fmt:
	terraform -chdir=infra/bootstrap fmt -check -recursive
	terraform -chdir=infra/live fmt -check -recursive

tf-validate:
	terraform -chdir=infra/live init -backend=false -input=false
	terraform -chdir=infra/live validate
