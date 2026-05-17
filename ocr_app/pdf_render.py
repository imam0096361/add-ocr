from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image

from .models import PageLayout


def render_pdf_pages(pdf_path: Path, pages_dir: Path, dpi: int = 240) -> list[PageLayout]:
    doc = fitz.open(pdf_path)
    rendered: list[PageLayout] = []
    scale = dpi / 72
    matrix = fitz.Matrix(scale, scale)

    for index, page in enumerate(doc):
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image_path = pages_dir / f"page-{index + 1:03d}.png"
        pix.save(image_path)

        rotation = _basic_rotation_hint(image_path)
        if rotation:
            image_path = _rotate_image(image_path, rotation)

        with Image.open(image_path) as img:
            width, height = img.size

        rendered.append(
            PageLayout(
                page_index=index,
                width_px=width,
                height_px=height,
                rotation_degrees=rotation,
                image_path=str(image_path),
                blocks=[],
            )
        )
    return rendered


def _basic_rotation_hint(image_path: Path) -> int:
    # Keep the source page orientation unless the rendered raster is landscape.
    # Text-orientation detection is delegated to Gemini because these demo PDFs
    # include portrait pages with rotated scan content.
    with Image.open(image_path) as img:
        width, height = img.size
    return 90 if width > height else 0


def _rotate_image(image_path: Path, degrees: int) -> Path:
    with Image.open(image_path) as img:
        rotated = img.rotate(-degrees, expand=True)
        out = image_path.with_name(f"{image_path.stem}-rotated.png")
        rotated.save(out)
        return out
