from pathlib import Path


def main() -> None:
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    print("Add a live data fetch here.")


if __name__ == "__main__":
    main()
