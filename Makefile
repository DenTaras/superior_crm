.PHONY: dev test build run stop logs shell

dev:
	uvicorn main:app --reload

test:
	python -m pytest tests/ -q

build:
	docker build -t superior-crm .

run:
	docker run -d --name superior-crm --network host \
		--env-file .env \
		superior-crm sh -c 'uvicorn main:app --host 0.0.0.0 --port 8000'

stop:
	docker stop superior-crm 2>/dev/null; docker rm superior-crm 2>/dev/null || true

logs:
	docker logs -f superior-crm

shell:
	docker exec -it superior-crm bash

rebuild: stop build run