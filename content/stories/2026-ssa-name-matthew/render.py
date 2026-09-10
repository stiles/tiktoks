from pathlib import Path

from tiktoks.ssa_story import render_single_name_story

HERE = Path(__file__).resolve().parent


def main() -> None:
    paths = render_single_name_story(HERE)
    print(f"Wrote {len(paths)} slides to 2026-ssa-name-matthew")


if __name__ == "__main__":
    main()
