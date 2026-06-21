SHELL := /bin/sh
.DEFAULT_GOAL := help

PYTHON ?= python3
VENV ?= .venv
CONFIG ?= ./config.yaml
PIP_ARGS ?=

.PHONY: help setup run test lint check deb clean distclean

help:
	@echo "Команды:"
	@echo "  setup      создать окружение и установить зависимости"
	@echo "  run        запустить службу с CONFIG=./config.yaml"
	@echo "  test       запустить тесты"
	@echo "  lint       проверить код с помощью Ruff"
	@echo "  check      выполнить все проверки"
	@echo "  deb        собрать пакет Debian в dist/"
	@echo "  clean      удалить кэш и результаты сборки"
	@echo "  distclean  выполнить clean и удалить окружение"

$(VENV)/.installed: pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install $(PIP_ARGS) -e '.[dev]'
	@touch $@

setup: $(VENV)/.installed

run: setup
	$(VENV)/bin/python -m irrigationd.main --config $(CONFIG)

test: setup
	$(VENV)/bin/python -m pytest -q

lint: setup
	$(VENV)/bin/python -m ruff check irrigationd tests

check: lint test
	$(VENV)/bin/python -m compileall -q irrigationd tests

deb:
	PYTHON=$(PYTHON) PIP_ARGS='$(PIP_ARGS)' ./packaging/build-deb.sh

clean:
	rm -rf .build .pytest_cache .ruff_cache build dist
	find irrigationd tests -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -maxdepth 1 -type d -name '*.egg-info' -prune -exec rm -rf {} +

distclean: clean
	rm -rf $(VENV)
