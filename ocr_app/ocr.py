from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .demo_fallback import build_demo_layout
from .models import BlockType, BoundingBox, DocumentLayout, LayoutBlock, PageLayout, TableBlock, TableCell
from .settings import get_api_key


PAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rotation_degrees": {"type": "integer", "description": "Clockwise rotation needed to make text upright. Use 0, 90, 180, or 270."},
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": ["heading", "paragraph", "table", "artifact"]},
                    "text": {"type": "string"},
                    "bbox": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "w": {"type": "number"},
                            "h": {"type": "number"},
                        },
                        "required": ["x", "y", "w", "h"],
                    },
                    "confidence": {"type": "number"},
                    "language": {"type": "string", "enum": ["bn", "en", "mixed", "unknown"]},
                    "alignment": {"type": "string", "enum": ["left", "center", "right", "justify", "unknown"]},
                    "underline": {"type": "boolean"},
                    "artifact_type": {"type": "string", "enum": ["signature", "stamp", "seal", "handwriting", "other"]},
                    "table": {
                        "type": "object",
                        "properties": {
                            "row_count": {"type": "integer"},
                            "col_count": {"type": "integer"},
                            "cells": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "row": {"type": "integer"},
                                        "col": {"type": "integer"},
                                        "row_span": {"type": "integer"},
                                        "col_span": {"type": "integer"},
                                        "text": {"type": "string"},
                                        "confidence": {"type": "number"},
                                    },
                                    "required": ["row", "col", "text"],
                                },
                            },
                        },
                        "required": ["row_count", "col_count", "cells"],
                    },
                },
                "required": ["id", "type", "bbox", "confidence", "language"],
            },
        },
    },
    "required": ["rotation_degrees", "blocks"],
}


class OcrError(RuntimeError):
    pass


def extract_layout(source_pdf: Path, pages: list[PageLayout], model: str, force_demo: bool = False) -> DocumentLayout:
    api_key = get_api_key()
    if force_demo:
        return build_demo_layout(source_pdf, pages, reason="forced_demo")
    if not api_key:
        return build_demo_layout(source_pdf, pages, reason="missing_api_key")

    warnings: list[str] = []
    ocr_pages: list[PageLayout] = []
    for page in pages:
        try:
            page.blocks, rotation = _ocr_page_with_gemini(Path(page.image_path), page.page_index, model, api_key)
            page.rotation_degrees = rotation
        except Exception as exc:
            warnings.append(f"Page {page.page_index + 1}: Gemini OCR failed: {exc}")
            page.blocks = [
                LayoutBlock(
                    id=f"ocr-error-{page.page_index + 1}",
                    type=BlockType.PARAGRAPH,
                    text="OCR failed for this page. Re-run after checking the Gemini API key/network, or edit this block manually.",
                    bbox=BoundingBox(x=0.1, y=0.1, w=0.8, h=0.08),
                    confidence=0.0,
                    language="en",
                )
            ]
        ocr_pages.append(page)

    return DocumentLayout(
        source_pdf=str(source_pdf),
        pages=ocr_pages,
        warnings=warnings,
        ocr_provider="gemini",
        ocr_model=model,
        demo_mode=False,
    )


def _ocr_page_with_gemini(image_path: Path, page_index: int, model: str, api_key: str) -> tuple[list[LayoutBlock], int]:
    from google import genai
    from google.genai import types
    from PIL import Image

    client = genai.Client(api_key=api_key)
    image_bytes = image_path.read_bytes()
    with Image.open(image_path) as img:
        image_width, image_height = img.size
    prompt = (
        "Extract this scanned Bangla/English government newspaper notice page into editable layout JSON with maximum fidelity. "
        "The output must preserve the original mixed Bangla and English exactly as printed: do not translate, summarize, normalize spelling, "
        "rewrite punctuation, or drop English words inside Bangla lines. Bangla must be Unicode Bangla, not Bijoy/ANSI. "
        "Preserve original line breaks inside each heading/paragraph/table cell so line length and wrapping match the source as closely as possible. "
        "Preserve visible word spacing, repeated spaces, tabs, dotted leaders, and blank-looking gaps; do not collapse spacing when it carries layout meaning. "
        "Preserve every punctuation mark, including colons, Bengali dari, decimal points, slashes, hyphens, brackets, and dotted leader runs such as ........ . "
        "Use separate blocks for visually separate text regions, and assign normalized bbox coordinates from the top-left of the upright page. "
        "Preserve alignment: set alignment to center, left, right, or justify exactly as the source. If body text is visually justified, use justify. "
        "Mark underline=true for underlined headings, website lines, or any underlined text block. "
        "Centered headers should have centered bboxes, right-side dates/memos should have right-side bboxes, and left body text should remain left. "
        "Preserve table rows, columns, row order, column order, and cell text line breaks exactly. "
        "If a table has a narrow punctuation-only separator column such as ':' between labels and values, return that ':' as its own table column; do not merge it into the value text. "
        "For signatures, stamps, seals, and handwritten marks, return artifact blocks with coordinates but do not OCR them as editable text. "
        "If a character is uncertain, keep the nearest visible character and lower the confidence rather than inventing clean text."
    )
    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        prompt,
    ]
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": PAGE_SCHEMA,
        },
    )
    payload = json.loads(response.text or "{}")
    rotation = int(payload.get("rotation_degrees") or 0)
    raw_blocks = payload.get("blocks") or []
    blocks: list[LayoutBlock] = []
    for i, raw in enumerate(raw_blocks):
        raw.setdefault("id", f"p{page_index + 1}-b{i + 1}")
        raw["bbox"] = _normalise_bbox(raw.get("bbox") or {}, image_width=image_width, image_height=image_height)
        if raw.get("type") == "table" and raw.get("table"):
            raw["table"] = _normalise_table(raw["table"])
        try:
            blocks.append(LayoutBlock.model_validate(raw))
        except ValidationError as exc:
            blocks.append(
                LayoutBlock(
                    id=f"invalid-{page_index + 1}-{i + 1}",
                    type=BlockType.PARAGRAPH,
                    text=f"Invalid OCR block skipped: {exc.errors()[0]['msg']}",
                    bbox=BoundingBox(x=0.1, y=0.1, w=0.8, h=0.06),
                    confidence=0.0,
                    language="en",
                )
            )
    return _expand_compressed_layout(blocks), rotation


def _expand_compressed_layout(blocks: list[LayoutBlock]) -> list[LayoutBlock]:
    if len(blocks) < 4:
        return blocks
    max_right = max((block.bbox.x + block.bbox.w for block in blocks), default=1)
    max_bottom = max((block.bbox.y + block.bbox.h for block in blocks), default=1)
    if max_right >= 0.72 or max_bottom >= 0.72:
        return blocks

    x_scale = min(3.0, 0.95 / max(max_right, 0.01))
    y_scale = min(3.4, 0.94 / max(max_bottom, 0.01))
    expanded: list[LayoutBlock] = []
    for block in blocks:
        payload = block.model_copy(deep=True)
        payload.bbox.x = _clamp(payload.bbox.x * x_scale)
        payload.bbox.w = _clamp(payload.bbox.w * x_scale)
        payload.bbox.y = _clamp(payload.bbox.y * y_scale)
        payload.bbox.h = _clamp(payload.bbox.h * y_scale)
        if payload.bbox.x + payload.bbox.w > 1:
            payload.bbox.w = max(0.01, 1 - payload.bbox.x)
        if payload.bbox.y + payload.bbox.h > 1:
            payload.bbox.h = max(0.01, 1 - payload.bbox.y)
        expanded.append(payload)
    return expanded


def _normalise_bbox(raw: dict[str, Any], image_width: int, image_height: int) -> dict[str, float]:
    x = _number(raw, "x", "left", "x_min", "xmin", default=0.1)
    y = _number(raw, "y", "top", "y_min", "ymin", default=0.1)
    w = _number(raw, "w", "width", default=None)
    h = _number(raw, "h", "height", default=None)
    x2 = _number(raw, "x2", "right", "x_max", "xmax", default=None)
    y2 = _number(raw, "y2", "bottom", "y_max", "ymax", default=None)

    if w is None and x2 is not None:
        w = x2 - x
    if h is None and y2 is not None:
        h = y2 - y
    if w is None:
        w = 0.8
    if h is None:
        h = 0.05

    max_value = max(abs(x), abs(y), abs(w), abs(h), abs(x2 or 0), abs(y2 or 0))
    if max_value > 100:
        x = x / max(1, image_width)
        w = w / max(1, image_width)
        y = y / max(1, image_height)
        h = h / max(1, image_height)
    elif max_value > 1:
        x /= 100
        y /= 100
        w /= 100
        h /= 100

    x = _clamp(x)
    y = _clamp(y)
    w = _clamp(w)
    h = _clamp(h)
    if x + w > 1:
        w = max(0.01, 1 - x)
    if y + h > 1:
        h = max(0.01, 1 - y)
    return {"x": x, "y": y, "w": w, "h": h}


def _number(raw: dict[str, Any], *keys: str, default: float | None) -> float | None:
    for key in keys:
        if key in raw and raw[key] is not None:
            try:
                return float(raw[key])
            except (TypeError, ValueError):
                continue
    return default


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _normalise_table(raw: dict[str, Any]) -> TableBlock:
    cells = [
        TableCell(
            row=max(0, int(cell.get("row", 0))),
            col=max(0, int(cell.get("col", 0))),
            row_span=max(1, int(cell.get("row_span", 1) or 1)),
            col_span=max(1, int(cell.get("col_span", 1) or 1)),
            text=str(cell.get("text", "")),
            confidence=max(0.0, min(1.0, float(cell.get("confidence", 0.0) or 0.0))),
        )
        for cell in raw.get("cells", [])
    ]
    row_count = int(raw.get("row_count") or 0)
    col_count = int(raw.get("col_count") or 0)
    if cells:
        row_count = max(row_count, max(cell.row for cell in cells) + 1)
        col_count = max(col_count, max(cell.col for cell in cells) + 1)
    return _restore_colon_separator_column(TableBlock(cells=cells, row_count=row_count, col_count=col_count))


def _restore_colon_separator_column(table: TableBlock) -> TableBlock:
    if table.col_count != 3 or table.row_count == 0:
        return table
    by_position = {(cell.row, cell.col): cell for cell in table.cells}
    value_cells = [by_position.get((row, 2)) for row in range(table.row_count)]
    colon_starts = [cell for cell in value_cells if cell and cell.text.lstrip().startswith(":")]
    should_split_leading_colon = len(colon_starts) >= max(2, table.row_count // 3)
    should_insert_missing_colon = _looks_like_numbered_colon_form(table, by_position)
    if not should_split_leading_colon and not should_insert_missing_colon:
        return table

    restored: list[TableCell] = []
    for cell in table.cells:
        if cell.col < 2:
            restored.append(cell)
            continue
        if cell.col == 2:
            original = cell.text
            stripped = original.lstrip()
            if stripped.startswith(":"):
                leading = original[: len(original) - len(stripped)]
                value = stripped[1:].lstrip()
                restored.append(
                    TableCell(
                        row=cell.row,
                        col=2,
                        text=leading + ":",
                        confidence=cell.confidence,
                        row_span=cell.row_span,
                        col_span=1,
                    )
                )
                restored.append(
                    TableCell(
                        row=cell.row,
                        col=3,
                        text=value,
                        confidence=cell.confidence,
                        row_span=cell.row_span,
                        col_span=max(1, cell.col_span),
                    )
                )
            else:
                restored.append(
                    TableCell(
                        row=cell.row,
                        col=2,
                        text=":",
                        confidence=cell.confidence,
                        row_span=cell.row_span,
                        col_span=1,
                    )
                )
                restored.append(
                    TableCell(
                        row=cell.row,
                        col=3,
                        text=cell.text,
                        confidence=cell.confidence,
                        row_span=cell.row_span,
                        col_span=cell.col_span,
                    )
                )
    return TableBlock(cells=restored, row_count=table.row_count, col_count=4)


def _looks_like_numbered_colon_form(table: TableBlock, by_position: dict[tuple[int, int], TableCell]) -> bool:
    numbered_rows = 0
    label_rows = 0
    for row in range(table.row_count):
        first = (by_position.get((row, 0)).text if by_position.get((row, 0)) else "").strip()
        label = (by_position.get((row, 1)).text if by_position.get((row, 1)) else "").strip()
        value = (by_position.get((row, 2)).text if by_position.get((row, 2)) else "").strip()
        if first and len(first) <= 3 and (_contains_digit(first) or _contains_bangla_digit(first)):
            numbered_rows += 1
        if label and value and len(label) <= 80:
            label_rows += 1
    return numbered_rows >= max(3, table.row_count // 2) and label_rows >= max(3, table.row_count // 2)


def _contains_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def _contains_bangla_digit(text: str) -> bool:
    return any("০" <= ch <= "৯" for ch in text)
