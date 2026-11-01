# Windows/Git Bash layout: the venv python lives in .venv/Scripts.
PY ?= .venv/Scripts/python
Q ?=
LANG ?= en

.PHONY: venv install up down ingest test test-unit test-integration test-chaos eval chaos-query

venv:
	python -m venv .venv

install:
	$(PY) -m pip install -r requirements-dev.txt

up:
	docker compose up -d

down:
	docker compose down

ingest:
	$(PY) scripts/ingest.py --source data/raw

# Default run: everything that needs no live services and no paid API.
test:
	$(PY) -m pytest -m "not integration and not live and not slow"

test-unit:
	$(PY) -m pytest -m unit

test-integration:
	$(PY) -m pytest -m integration

test-chaos:
	$(PY) -m pytest -m chaos

eval:
	$(PY) scripts/evaluate_retrieval.py

# Filled in during Phase 4 (scripts/chaos.py does not exist yet).
chaos-query:
	$(PY) scripts/chaos.py query --q "$(Q)" --lang $(LANG)
