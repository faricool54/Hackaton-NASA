# One-liners for everyone (humans and agents). Windows without make: see README.
PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: help setup setup-py setup-science setup-web demo schema validate api web test test-py test-web lint check

help:
	@echo "make setup      -> venv + pipeline/backend + frontend deps"
	@echo "make demo       -> regenerate synthetic demo data (data/demo)"
	@echo "make api        -> backend on http://localhost:8000 (docs at /docs)"
	@echo "make web        -> frontend on http://localhost:5173"
	@echo "make check      -> everything CI runs (run before every push)"

setup: setup-py setup-web

setup-py:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -U pip
	$(BIN)/pip install -e "pipeline[dev]" -e "backend[dev]"

# Heavy libs for real-data work (WS1/WS2/WS3): scipy, photutils, reproject, astroquery, pyvo
setup-science:
	$(BIN)/pip install -e "pipeline[dev,science]"

setup-web:
	cd frontend && npm ci

demo:
	$(BIN)/errante demo --out data/demo

schema:
	$(BIN)/errante schema

validate:
	$(BIN)/errante validate --dir data/demo
	@if [ -f data/products/manifest.json ]; then $(BIN)/errante validate --dir data/products; fi

api:
	cd backend && ../$(BIN)/uvicorn errante_api.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test: test-py test-web

test-py:
	$(BIN)/pytest -q pipeline/tests backend/tests

test-web:
	cd frontend && npm test

lint:
	$(BIN)/ruff check pipeline backend
	$(BIN)/ruff format --check pipeline backend

check: lint test
	$(BIN)/errante schema --check
	cd frontend && npm run build
