.PHONY: setup story quiz quiz-silhouette quiz-progressive quiz-status area-quiz guess-map catalog catalog-list crosswalk styles example name-trends texas-top-names karen matthew rebuild test lint format check publish-status

setup:
	uv sync --extra dev

.PHONY: neighbors-quiz
neighbors-quiz:
	uv run tiktoks neighbors-quiz --config content/neighbors-quiz/$(or $(SLUG),neighbors-001)/quiz.yaml --theme $(or $(THEME),night)

story:
	uv run tiktoks story --slug $(SLUG)

# Build the next batch from the country pool and render it.
quiz:
	uv run tiktoks quiz next --tier $(TIER) --count $(or $(COUNT),3)

quiz-silhouette:
	uv run tiktoks quiz next --tier $(TIER) --count $(or $(COUNT),3) --variant silhouette

quiz-progressive:
	uv run tiktoks quiz next --tier $(TIER) --count $(or $(COUNT),3) --variant progressive

quiz-status:
	uv run tiktoks quiz status --validate

# Render a curated land-area quiz; defaults to the pilot in the night theme.
area-quiz:
	uv run tiktoks area-quiz --config content/area-quiz/$(or $(SLUG),area-001)/quiz.yaml --theme $(or $(THEME),night)

publish-status:
	uv run tiktoks publish status

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

name-trends:
	uv run python content/stories/2026-ssa-name-trends/rank_names.py
	uv run python content/stories/2026-ssa-name-trends/render.py

texas-top-names:
	uv run python content/stories/2026-ssa-texas-top-names/fetch.py
	uv run python content/stories/2026-ssa-texas-top-names/process.py
	uv run python content/stories/2026-ssa-texas-top-names/render.py

karen:
	uv run python content/stories/2026-ssa-name-karen/process.py
	uv run python content/stories/2026-ssa-name-karen/render.py

matthew:
	uv run python content/stories/2026-ssa-name-matthew/process.py
	uv run python content/stories/2026-ssa-name-matthew/render.py

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
