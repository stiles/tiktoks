from pathlib import Path
from shutil import copytree

import click

from tiktoks import batches, catalog, countries
from tiktoks.geo_quiz import render_geo_quiz
from tiktoks.guess_map import CATALOG_PATH, render_catalog, render_guess_map
from tiktoks.style import THEMES


@click.group()
def main() -> None:
    """Render TikTok story slides."""


config_option = click.option(
    "--config", "config_path", required=True, type=click.Path(exists=True, path_type=Path)
)
theme_option = click.option("--theme", type=click.Choice(sorted(THEMES)), default=None)


def _echo(paths: list[Path]) -> None:
    for path in paths:
        click.echo(path)
    click.echo(f"{len(paths)} slides")


@main.command("geo-quiz")
@config_option
@theme_option
def geo_quiz(config_path: Path, theme: str | None) -> None:
    """Render a geography quiz batch."""
    _echo(render_geo_quiz(config_path, theme=theme))


@main.command("guess-map")
@config_option
@theme_option
def guess_map(config_path: Path, theme: str | None) -> None:
    """Render one guess-the-map post from a directory config."""
    _echo(render_guess_map(config_path, theme=theme))


@main.command("catalog")
@click.option(
    "--catalog",
    "catalog_path",
    type=click.Path(exists=True, path_type=Path),
    default=CATALOG_PATH,
    show_default=True,
)
@click.option("--slug", default=None, help="Render one entry.")
@click.option("--all", "render_all", is_flag=True, help="Render every entry.")
@click.option("--list", "show_list", is_flag=True, help="List entries and exit.")
@theme_option
def catalog_command(
    catalog_path: Path, slug: str | None, render_all: bool, show_list: bool, theme: str | None
) -> None:
    """Render guess-the-map posts from the query catalog."""
    entries = catalog.load(catalog_path)
    if show_list:
        for name, entry in entries.items():
            kind = entry.get("fetch", {}).get("kind", "?")
            click.echo(f"{name:24} {entry.get('difficulty', ''):8} {kind:18} {entry['answer']}")
        return
    if not slug and not render_all:
        raise click.UsageError("Pass --slug, --all or --list.")
    _echo(render_catalog(catalog_path, slug=slug, theme=theme))


@main.group("quiz")
def quiz() -> None:
    """Build geography quiz batches from the country pool."""


@quiz.command("next")
@click.option("--tier", type=click.Choice(countries.TIERS), required=True)
@click.option("--count", default=3, show_default=True, help="Countries in the batch.")
@click.option("--slug", default=None, help="Batch directory name. Auto-numbered by default.")
@click.option("--dry-run", is_flag=True, help="Show the picks without writing anything.")
@click.option("--no-render", is_flag=True, help="Write the batch config but do not render.")
@theme_option
def quiz_next(
    tier: str, count: int, slug: str | None, dry_run: bool, no_render: bool, theme: str | None
) -> None:
    """Pick the least-recently-used countries in a tier and build a batch."""
    config_path, names = batches.build(tier, count, slug=slug, commit=not dry_run)
    for position, name in enumerate(names, start=1):
        click.echo(f"{position:2}. {name}")
    if dry_run:
        click.echo(f"(dry run) would write {config_path}")
        return

    click.echo(config_path)
    if not no_render:
        _echo(render_geo_quiz(config_path, theme=theme))


@quiz.command("status")
@click.option("--validate", is_flag=True, help="Check every name against the boundary file.")
def quiz_status(validate: bool) -> None:
    """Show pool depth per tier."""
    pool = countries.load()
    click.echo(countries.status(pool).to_string(index=False))
    if validate:
        problems = countries.validate(pool)
        click.echo("")
        for problem in problems:
            click.echo(problem)
        click.echo(f"{len(problems)} name problem(s) in {len(pool)} countries")


@main.command("story")
@click.option("--slug", required=True)
def story(slug: str) -> None:
    """Scaffold a new one-off story from the template."""
    template = Path("templates/story")
    destination = Path("stories") / slug
    if destination.exists():
        raise click.ClickException(f"{destination} already exists")
    copytree(template, destination)
    click.echo(destination)
