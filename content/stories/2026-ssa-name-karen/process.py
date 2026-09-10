from pathlib import Path

from tiktoks.ssa_story import process_single_name_story

HERE = Path(__file__).resolve().parent


def main() -> None:
    path = process_single_name_story(HERE)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
