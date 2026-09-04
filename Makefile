.PHONY: setup story quiz guess-map styles example lint format

setup:
	uv sync --extra dev

story:
	uv run tiktoks story --slug $(SLUG)

quiz:
	uv run tiktoks geo-quiz --config quizzes/geo/world-countries-001/quiz.yaml

guess-map:
	uv run tiktoks guess-map --config quizzes/guess-map/nato-members/guess_map.yaml

styles:
	uv run python scripts/style_lab.py

example:
	uv run python stories/2026-ssa-name-comeback/fetch.py
	uv run python stories/2026-ssa-name-comeback/process.py
	uv run python stories/2026-ssa-name-comeback/render.py

lint:
	uv run ruff check .

format:
	uv run ruff format .
