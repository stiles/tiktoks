.PHONY: setup story quiz guess-map catalog catalog-list crosswalk styles example test lint format check

setup:
	uv sync --extra dev

story:
	uv run tiktoks story --slug $(SLUG)

quiz:
	uv run tiktoks geo-quiz --config quizzes/geo/world-countries-001/quiz.yaml

guess-map:
	uv run tiktoks guess-map --config quizzes/guess-map/nato-members-csv/guess_map.yaml

catalog:
	uv run tiktoks catalog --all

catalog-list:
	uv run tiktoks catalog --list

# Rerun when the boundary file changes. Everything joined by ISO code depends on it.
crosswalk:
	uv run python scripts/build_crosswalk.py

styles:
	uv run python scripts/style_lab.py

example:
	uv run python stories/2026-ssa-name-comeback/fetch.py
	uv run python stories/2026-ssa-name-comeback/process.py
	uv run python stories/2026-ssa-name-comeback/render.py

test:
	uv run pytest -q

lint:
	uv run ruff check .

format:
	uv run ruff format .

check: lint test
