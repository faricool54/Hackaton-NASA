# Thin wrapper for people who have `make` (macOS/Linux). The real tasks live in
# scripts/dev.py, which works the same on Windows:  py scripts/dev.py <task>
PY ?= $(shell command -v python3 >/dev/null 2>&1 && echo python3 || echo python)

TASKS := setup setup-py setup-web setup-science doctor demo schema validate api web test test-py test-web lint fmt owners check
.PHONY: help $(TASKS)

help:
	@$(PY) scripts/dev.py

$(TASKS):
	@$(PY) scripts/dev.py $@
