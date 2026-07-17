.PHONY: install run test clean docker

install:
	pip install -r server/requirements.txt

run:
	uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload

test:
	python -m pytest tests/ -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache 2>/dev/null || true

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
