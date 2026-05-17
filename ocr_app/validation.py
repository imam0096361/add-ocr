from __future__ import annotations

from .models import BlockType, DocumentLayout, LayoutBlock


def validate_layout(layout: DocumentLayout) -> list[str]:
    warnings = list(layout.warnings)
    seen_ids: set[str] = set()
    for page in layout.pages:
        if not page.blocks:
            warnings.append(f"Page {page.page_index + 1}: no OCR blocks were detected.")
        for block in page.blocks:
            if block.id in seen_ids:
                warnings.append(f"Duplicate block id: {block.id}")
            seen_ids.add(block.id)
            warnings.extend(_validate_block(page.page_index + 1, block))
    return sorted(set(warnings))


def _validate_block(page_number: int, block: LayoutBlock) -> list[str]:
    warnings: list[str] = []
    if block.bbox.x + block.bbox.w > 1.02 or block.bbox.y + block.bbox.h > 1.02:
        warnings.append(f"Page {page_number}: block {block.id} has coordinates outside the page.")
    if block.confidence < 0.65 and block.type != BlockType.ARTIFACT:
        warnings.append(f"Page {page_number}: block {block.id} has low OCR confidence.")
    if block.type == BlockType.TABLE:
        if not block.table or block.table.row_count == 0 or block.table.col_count == 0:
            warnings.append(f"Page {page_number}: table {block.id} has no dimensions.")
        elif not block.table.cells:
            warnings.append(f"Page {page_number}: table {block.id} has no cells.")
        else:
            max_row = max(cell.row for cell in block.table.cells)
            max_col = max(cell.col for cell in block.table.cells)
            if max_row >= block.table.row_count or max_col >= block.table.col_count:
                warnings.append(f"Page {page_number}: table {block.id} cell index exceeds dimensions.")
            for cell in block.table.cells:
                if not cell.text.strip():
                    warnings.append(f"Page {page_number}: table {block.id} has an empty cell at R{cell.row + 1}C{cell.col + 1}.")
    elif block.type != BlockType.ARTIFACT and not block.text.strip():
        warnings.append(f"Page {page_number}: text block {block.id} is empty.")
    return warnings


def find_bangla_warnings(text: str) -> list[str]:
    warnings: list[str] = []
    for ch in sorted(set(text)):
        if "\u0980" <= ch <= "\u09ff":
            continue
        if ord(ch) > 127 and ch not in "–—‘’“”…°":
            warnings.append(f"Unsupported non-ASCII glyph for Bijoy conversion: U+{ord(ch):04X} {ch}")
    return warnings
