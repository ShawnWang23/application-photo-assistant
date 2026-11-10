from __future__ import annotations

import re

from .models import FitMode, ImageFormat, PhotoRequirements


def parse_requirements_rules(text: str, defaults: PhotoRequirements) -> PhotoRequirements:
    """Deterministic Chinese/English parser used offline and as an API fallback."""

    updates: dict[str, object] = {}
    normalized = text.strip()

    size_match = re.search(r"(?<!\d)(\d{2,5})\s*(?:[×xX*✕]|乘)\s*(\d{2,5})(?!\d)", normalized)
    if size_match:
        updates["width"], updates["height"] = map(int, size_match.groups())
    else:
        width_match = re.search(r"(?:宽度?|width)\s*[:：为]?\s*(\d{2,5})", normalized, re.I)
        height_match = re.search(r"(?:高度?|height)\s*[:：为]?\s*(\d{2,5})", normalized, re.I)
        if width_match:
            updates["width"] = int(width_match.group(1))
        if height_match:
            updates["height"] = int(height_match.group(1))

    format_match = re.search(r"(?<![A-Za-z0-9])(jpe?g|png|webp)(?![A-Za-z0-9])", normalized, re.I)
    if format_match:
        updates["output_format"] = ImageFormat.normalize(format_match.group(1))

    size_limit = re.search(
        r"(?:不超过|小于(?:等于)?|最多|上限|max(?:imum)?|≤|<=)?\s*"
        r"(\d+(?:\.\d+)?)\s*(kb|k|mb|m)(?![A-Za-z])",
        normalized,
        re.I,
    )
    if size_limit:
        value = float(size_limit.group(1))
        unit = size_limit.group(2).lower()
        updates["max_size_kb"] = max(1, round(value * 1024 if unit in {"mb", "m"} else value))

    lowered = normalized.lower()
    if any(keyword in lowered for keyword in ("留白", "加白边", "padding", "pad", "不裁剪")):
        updates["fit_mode"] = FitMode.PAD
    elif any(keyword in lowered for keyword in ("裁剪", "crop", "铺满")):
        updates["fit_mode"] = FitMode.CROP

    return _merge_requirements(defaults, updates)


def _merge_requirements(defaults: PhotoRequirements, updates: dict[str, object]) -> PhotoRequirements:
    merged = defaults.model_dump()
    merged.update(updates)
    return PhotoRequirements.model_validate(merged)
