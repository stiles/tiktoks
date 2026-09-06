.PHONY: setup story quiz quiz-status guess-map catalog catalog-list crosswalk styles example rebuild test lint format check

setup:
	uv sync --extra dev

story:
	uv run tiktoks story --slug $(SLUG)

# Build the next batch from the country pool and render it.
quiz:
	uv run tiktoks quiz next --tier $(TIER) --count $(or $(COUNT),3)

quiz-status:
	uv run tiktoks quiz status --validate

guess-map:
	uv run tiktoks guess-map --config content/guess-map-csv-example/guess_map.yaml

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
	uv run python content/stories/2026-ssa-name-comeback/fetch.py
	uv run python content/stories/2026-ssa-name-comeback/process.py
	uv run python content/stories/2026-ssa-name-comeback/render.py

# Re-render every batch and catalog entry from content/.
rebuild:
	@for d in posts/geo-quiz/*/; do uv run tiktoks geo-quiz --config $$d/quiz.yaml >/dev/null; done
	@uv run tiktoks catalog --all >/dev/null
	@echo "rebuilt posts/ from content/"

test:
	uv run pytest -q

lint:
	uv run ruff check .

format:
	uv run ruff format .

check: lint test
