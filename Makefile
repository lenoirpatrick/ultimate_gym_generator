.PHONY: help install css css-watch run test lint format check migrate superuser exercises docker-build docker-up docker-down

PYTHON ?= python
CSS_IN  := assets/css/input.css
CSS_OUT := core/static/core/css/app.css

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dépendances de développement
	$(PYTHON) -m pip install -r requirements/dev.txt

css: ## Compile la feuille de style
	tailwindcss -i $(CSS_IN) -o $(CSS_OUT) --minify

css-watch: ## Recompile la feuille de style à chaque modification
	tailwindcss -i $(CSS_IN) -o $(CSS_OUT) --watch

run: ## Lance le serveur de développement (port 5907 par défaut, DJANGO_PORT sinon)
	$(PYTHON) manage.py runserver

migrate: ## Applique les migrations
	$(PYTHON) manage.py migrate

superuser: ## Crée un compte administrateur
	$(PYTHON) manage.py createsuperuser

exercises: ## Charge le catalogue d'exercices en base
	$(PYTHON) manage.py load_exercises

test: ## Exécute la suite de tests avec la couverture
	$(PYTHON) -m pytest --cov --cov-report=term-missing --cov-report=xml

lint: ## Vérifie le style et la qualité du code
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format: ## Reformate le code
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

check: ## Contrôle la configuration de déploiement
	$(PYTHON) manage.py check --deploy

docker-build: ## Construit l'image
	docker build -t plenoir/ultimate-gym-generator:latest .

docker-up: ## Démarre la pile complète
	docker compose up -d --build

docker-down: ## Arrête la pile (les volumes sont conservés)
	docker compose down
