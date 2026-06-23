.PHONY: dev test build run stop logs shell

dev:
	uvicorn main:app --reload

test:
	python -m pytest tests/ -q

build:
	docker build -t superior-crm .

run:
	docker run -d -p 8000:8000 --env-file .env \
		-v "$(CURDIR)/superior.db:/app/superior.db" \
		--name superior-crm superior-crm

stop:
	docker stop superior-crm 2>/dev/null; docker rm superior-crm 2>/dev/null || true

logs:
	docker logs -f superior-crm

shell:
	docker exec -it superior-crm bash

rebuild: stop build run
