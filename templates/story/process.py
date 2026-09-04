from pathlib import Path


def main() -> None:
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    print("Add processing steps here.")


if __name__ == "__main__":
    main()
