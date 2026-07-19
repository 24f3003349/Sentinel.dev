.PHONY: run-demo test lint dashboard

run-demo:
	python run_sentinel_demo.py

test:
	python -m pytest

lint:
	python -m ruff check .

dashboard:
	cd dashboard && npm install && npm run dev
