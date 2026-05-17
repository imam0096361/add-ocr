from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from .storage import ROOT

CONVERTER_SCRIPT = ROOT / "scripts" / "bijoy_convert.js"


def convert_unicode_to_bijoy(text: str) -> tuple[str, list[str]]:
    if not text:
        return text, []
    node = shutil.which("node")
    if not node:
        return text, ["Bijoy conversion skipped: Node.js is not available."]
    if not CONVERTER_SCRIPT.exists():
        return text, ["Bijoy conversion skipped: converter script is missing."]
    try:
        return _convert_with_node(text, node), []
    except Exception as exc:
        return text, [f"Bijoy conversion failed: {exc}"]


def split_bijoy_font_runs(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    runs: list[tuple[str, str]] = []
    warnings: list[str] = []
    for segment, is_bangla in _split_bangla_segments(text):
        if not segment:
            continue
        if is_bangla:
            converted, segment_warnings = convert_unicode_to_bijoy(segment)
            warnings.extend(segment_warnings)
            runs.append((converted, "bijoy"))
        else:
            runs.append((segment, "latin"))
    return runs, sorted(set(warnings))


def _split_bangla_segments(text: str) -> list[tuple[str, bool]]:
    if not text:
        return []
    segments: list[tuple[str, bool]] = []
    current = [text[0]]
    current_is_bangla = _is_bangla_text_char(text[0])
    for ch in text[1:]:
        is_bangla = _is_bangla_text_char(ch)
        if is_bangla == current_is_bangla:
            current.append(ch)
        else:
            segments.append(("".join(current), current_is_bangla))
            current = [ch]
            current_is_bangla = is_bangla
    segments.append(("".join(current), current_is_bangla))
    return segments


def _is_bangla_text_char(ch: str) -> bool:
    return "\u0980" <= ch <= "\u09ff" or ch in {"\u200c", "\u200d"}


@lru_cache(maxsize=4096)
def _convert_with_node(text: str, node: str) -> str:
    completed = subprocess.run(
        [node, str(CONVERTER_SCRIPT)],
        input=json.dumps([text], ensure_ascii=False),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(ROOT),
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "converter process failed")
    payload = json.loads(completed.stdout)
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return _cleanup_remaining_unicode(str(payload["converted"][0]))


def _cleanup_remaining_unicode(text: str) -> str:
    replacements = {
        "০": "0",
        "১": "1",
        "২": "2",
        "৩": "3",
        "৪": "4",
        "৫": "5",
        "৬": "6",
        "৭": "7",
        "৮": "8",
        "৯": "9",
        "।": "|",
        "॥": "||",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text
