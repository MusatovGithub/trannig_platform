up-db:
	docker compose up -d

clear-db:
	docker compose down -v

down-db:
	docker compose down

migrate:
	python manage.py migrate

shell:
	python manage.py shell

test:
	python manage.py test -v1

run:
	python manage.py runserver

run-celery:
	celery -A config worker -l info --pool=solo

makemigrations:
	python manage.py makemigrations

createsuperuser:
	python manage.py createsuperuser

fill-db:
	python manage.py loaddata gender_fixtures.json
	python manage.py loaddata week_fixtures.json
	python manage.py loaddata permissions_fixtures.json
	python manage.py loaddata sport_categories_fixtures.json
	python manage.py loaddata type_representatives.json

lint:
	uv run ruff format .
	uv run ruff check --fix

fill-prod-db:
	docker exec -it django bash -c "python manage.py loaddata gender_fixtures.json; python manage.py loaddata week_fixtures.json; python manage.py loaddata sport_categories_fixtures.json; python manage.py loaddata permissions_fixtures.json; python manage.py loaddata type_representatives.json;"

start-prod:
	docker compose -f docker-compose.prod.yaml up -d --build

stop-prod:
	docker compose -f docker-compose.prod.yaml down

rebuild-prod:
	docker compose -f docker-compose.prod.yaml down
	docker compose -f docker-compose.prod.yaml up -d --build

start-production:
	docker compose -f docker-compose.production.yaml up -d --build

.PHONY: up-db clear-db down-db migrate run run-celery makemigrations createsuperuser fill-db fill-prod-db
