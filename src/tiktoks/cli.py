from pathlib import Path
from shutil import copytree

import click

from tiktoks.export import validate_exports
from tiktoks.geo_quiz import render_geo_quiz
from tiktoks.guess_map import render_guess_map
from tiktoks.style import THEMES


@click.group()
def main() -> None:
    """Render TikTok story slides."""


config_option = click.option(
    "--config", "config_path", required=True, type=click.Path(exists=True, path_type=Path)
)
theme_option = click.option("--theme", type=click.Choice(sorted(THEMES)), default=None)


@main.command("geo-quiz")
@config_option
@theme_option
def geo_quiz(config_path: Path, theme: str | None) -> None:
    rendered = render_geo_quiz(config_path, theme=theme)
    validate_exports(rendered)
    for path in rendered:
        click.echo(path)


@main.command("guess-map")
@config_option
@theme_option
def guess_map(config_path: Path, theme: str | None) -> None:
    rendered = render_guess_map(config_path, theme=theme)
    validate_exports(rendered)
    for path in rendered:
        click.echo(path)


@main.command("story")
@click.option("--slug", required=True)
def story(slug: str) -> None:
    template = Path("templates/story")
    destination = Path("stories") / slug
    if destination.exists():
        raise click.ClickException(f"{destination} already exists")
    copytree(template, destination)
    click.echo(destination)
