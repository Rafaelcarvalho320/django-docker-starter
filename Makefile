# Every target exports a development secret key, because the settings module
# deliberately refuses to boot without one. `?=` so a real environment wins.
export DJANGO_SECRET_KEY ?= dev-only-never-used-to-serve-anything-real-0123456789
export DJANGO_DEBUG ?= true

PY := python

.DEFAULT_GOAL := help

.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install:  ## Install dependencies and the pre-commit hooks
	$(PY) -m pip install -r requirements-dev.txt
	pre-commit install

.PHONY: run
run:  ## Start the development server
	$(PY) manage.py runserver

.PHONY: migrate
migrate:  ## Apply migrations
	$(PY) manage.py migrate

.PHONY: migrations
migrations:  ## Create migrations for model changes
	$(PY) manage.py makemigrations

.PHONY: test
test:  ## Run the test suite
	pytest

.PHONY: cov
cov:  ## Run the suite with a coverage report
	pytest --cov --cov-report=term-missing

.PHONY: lint
lint:  ## Lint and check formatting
	ruff check .
	ruff format --check .

.PHONY: fmt
fmt:  ## Fix what can be fixed automatically
	ruff check --fix .
	ruff format .

.PHONY: types
types:  ## Type check
	mypy

.PHONY: check
check:  ## Everything CI runs, in the same order
	ruff check .
	ruff format --check .
	mypy
	DJANGO_DEBUG=false $(PY) manage.py check --deploy --fail-level WARNING
	$(PY) manage.py makemigrations --check --dry-run
	pytest

.PHONY: up
up:  ## Start the stack with Docker
	docker compose up --build

.PHONY: down
down:  ## Stop the stack and remove volumes
	docker compose down -v

.PHONY: shell
shell:  ## Django shell
	$(PY) manage.py shell

.PHONY: secret
secret:  ## Generate a secret key
	@$(PY) -c "import secrets; print(secrets.token_urlsafe(50))"
