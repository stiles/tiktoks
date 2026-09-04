from pathlib import Path

from PIL import Image

from tiktoks.config import CANVAS_SIZE


def validate_export(path: Path | str, expected_size: tuple[int, int] = CANVAS_SIZE) -> None:
    image_path = Path(path)
    with Image.open(image_path) as image:
        if image.size != expected_size:
            raise ValueError(f"{image_path} is {image.size}, expected {expected_size}")


def validate_exports(paths: list[Path]) -> None:
    for path in paths:
        validate_export(path)


def contact_sheet(
    paths: list[Path],
    destination: Path,
    *,
    columns: int = 4,
    thumb_width: int = 270,
    gap: int = 16,
    matte: str = "#555555",
) -> Path:
    """Tile slides into one image for reviewing a batch at thumbnail size."""
    thumb_height = round(thumb_width * CANVAS_SIZE[1] / CANVAS_SIZE[0])
    thumbs = [Image.open(path).resize((thumb_width, thumb_height), Image.LANCZOS) for path in paths]
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (
            columns * thumb_width + (columns + 1) * gap,
            rows * thumb_height + (rows + 1) * gap,
        ),
        matte,
    )
    for index, thumb in enumerate(thumbs):
        sheet.paste(
            thumb,
            (
                gap + (index % columns) * (thumb_width + gap),
                gap + (index // columns) * (thumb_height + gap),
            ),
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)
    return destination
