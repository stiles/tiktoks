from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_dir(path: Path | str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def output_path(directory: Path | str, name: str) -> Path:
    return ensure_dir(directory) / name


def story_data(slug: str) -> Path:
    """Where a story's raw and processed data goes.

    Story scripts live in `content/`, which holds only hand-written files, so the
    data they fetch and build lands under `data/` instead.
    """
    return repo_root() / "data" / "stories" / slug


def story_posts(slug: str) -> Path:
    """Where a story's rendered slides go."""
    return repo_root() / "posts" / "stories" / slug
