from pathlib import Path
from shutil import copytree

import click

from tiktoks import batches, catalog, countries, video, youtube
from tiktoks.config import ROOT, STORIES_DIR
from tiktoks.geo_quiz import render_geo_quiz
from tiktoks.guess_map import CATALOG_PATH, render_catalog, render_guess_map
from tiktoks.style import THEMES


@click.group()
def main() -> None:
    """Render slides and publish them to TikTok or YouTube Shorts."""


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


post_dir_option = click.option(
    "--dir",
    "post_dir",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Theme directory with post.json, or the post.json itself.",
)


@main.command("video")
@click.option(
    "--dir",
    "post_dir",
    required=False,
    type=click.Path(exists=True, path_type=Path),
    help="Theme directory with post.json, or the post.json itself.",
)
@click.option("--silent", is_flag=True, help="Assemble without the music bed.")
@click.option(
    "--audio",
    "audio_choice",
    default=None,
    help="Bed slug from content/audio/catalog.yaml, or a path to an mp3.",
)
@click.option("--list-audio", is_flag=True, help="List bed slugs and exit.")
def video_command(
    post_dir: Path | None, silent: bool, audio_choice: str | None, list_audio: bool
) -> None:
    """Assemble a 9:16 MP4 from a rendered post's slides."""
    if list_audio:
        default = video.load_catalog().get("default")
        for slug, entry in video.beds().items():
            mark = " (default)" if slug == default else ""
            click.echo(f"{slug:24} {entry.get('artist', '')}: {entry.get('title', '')}{mark}")
        return
    if post_dir is None:
        raise click.UsageError("Pass --dir, or --list-audio.")
    audio: Path | str | bool | None
    if silent:
        audio = False
    else:
        audio = audio_choice
    try:
        click.echo(video.assemble(post_dir, audio=audio))
    except video.VideoError as exc:
        raise click.ClickException(str(exc)) from exc


@main.group("youtube")
def youtube_group() -> None:
    """Upload assembled videos as YouTube Shorts."""


@youtube_group.command("auth")
def youtube_auth() -> None:
    """Store a YouTube OAuth token. Opens a browser once."""
    try:
        click.echo(youtube.auth())
    except youtube.YouTubeError as exc:
        raise click.ClickException(str(exc)) from exc


@youtube_group.command("upload")
@click.option(
    "--dir",
    "post_dir",
    required=False,
    type=click.Path(exists=True, path_type=Path),
    help="One theme directory, or with --all the tree to walk.",
)
@click.option("--all", "upload_all", is_flag=True, help="Upload every pending MP4 under --dir.")
@click.option(
    "--privacy",
    type=click.Choice(["private", "unlisted", "public"]),
    default="private",
    show_default=True,
)
@click.option("--no-assemble", is_flag=True, help="Fail if the MP4 is missing.")
@click.option(
    "--audio",
    "audio_choice",
    default=None,
    help="Bed slug if the MP4 has to be assembled first.",
)
def youtube_upload(
    post_dir: Path | None,
    upload_all: bool,
    privacy: str,
    no_assemble: bool,
    audio_choice: str | None,
) -> None:
    """Upload a post's MP4. Assembles it first if needed. Default is private."""
    from tiktoks.config import POSTS_DIR

    if upload_all:
        directories = youtube.pending_uploads(post_dir or POSTS_DIR)
        if not directories:
            click.echo("nothing pending")
            return
    elif post_dir is not None:
        directories = [post_dir]
    else:
        raise click.UsageError("Pass --dir, or --all.")

    failures = 0
    for directory in directories:
        try:
            result = youtube.upload(
                directory,
                privacy=privacy,
                assemble_if_missing=not no_assemble,
                audio=audio_choice,
            )
        except (youtube.YouTubeError, video.VideoError) as exc:
            failures += 1
            click.echo(f"FAIL {directory}: {exc}", err=True)
            continue
        except Exception as exc:
            failures += 1
            click.echo(f"FAIL {directory}: {exc}", err=True)
            continue
        click.echo(f"{directory} {result['url']}")
    if failures:
        raise click.ClickException(f"{failures} upload(s) failed")


@main.command("story")
@click.option("--slug", required=True)
def story(slug: str) -> None:
    """Scaffold a new one-off story from the template."""
    template = ROOT / "templates" / "story"
    destination = STORIES_DIR / slug
    if destination.exists():
        raise click.ClickException(f"{destination} already exists")
    copytree(template, destination)
    click.echo(destination)
