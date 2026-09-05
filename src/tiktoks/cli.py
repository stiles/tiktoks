from pathlib import Path
from shutil import copytree

import click

from tiktoks import catalog
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
