from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    ARTIFACT = "artifact"


class BoundingBox(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(ge=0.0, le=1.0)
    h: float = Field(ge=0.0, le=1.0)


class TableCell(BaseModel):
    text: str = ""
    row: int = Field(ge=0)
    col: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    col_span: int = Field(default=1, ge=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class TableBlock(BaseModel):
    cells: list[TableCell] = Field(default_factory=list)
    row_count: int = Field(default=0, ge=0)
    col_count: int = Field(default=0, ge=0)

    @field_validator("row_count", "col_count")
    @classmethod
    def non_negative(cls, value: int) -> int:
        return max(0, value)


class LayoutBlock(BaseModel):
    id: str
    type: BlockType
    text: str = ""
    bbox: BoundingBox = Field(default_factory=lambda: BoundingBox(x=0.08, y=0.08, w=0.84, h=0.06))
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    language: Literal["bn", "en", "mixed", "unknown"] = "unknown"
    alignment: Literal["left", "center", "right", "justify", "unknown"] = "unknown"
    underline: bool = False
    table: TableBlock | None = None
    artifact_type: Literal["signature", "stamp", "seal", "handwriting", "other"] | None = None
    image_path: str | None = None


class PageLayout(BaseModel):
    page_index: int = Field(ge=0)
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    rotation_degrees: int = 0
    image_path: str
    blocks: list[LayoutBlock] = Field(default_factory=list)


class DocumentLayout(BaseModel):
    source_pdf: str
    pages: list[PageLayout] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    ocr_provider: str = "gemini"
    ocr_model: str = "gemini-3-flash-preview"
    demo_mode: bool = False
