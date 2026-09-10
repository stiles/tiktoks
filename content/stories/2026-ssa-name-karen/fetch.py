from pathlib import Path

from tiktoks.ssa_story import ensure_ssa_raw_data

HERE = Path(__file__).resolve().parent


def main() -> None:
    path = ensure_ssa_raw_data(HERE)
    print(f"Wrote SSA name files to {path}")


if __name__ == "__main__":
    main()
