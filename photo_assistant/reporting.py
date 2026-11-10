from __future__ import annotations

import json
from typing import Any

from .models import AgentResult
from .version import __version__


def result_manifest(result: AgentResult, *, source_name: str) -> dict[str, Any]:
    return {
        "product": "Application Photo Assistant",
        "version": __version__,
        "trace_id": result.trace_id,
        "agent": {
            "plan": result.plan_summary,
            "attempts": result.attempts,
        },
        "created_at": result.created_at.isoformat(),
        "source": {
            "filename": source_name,
            **result.input_metadata.model_dump(),
            "size_kb": round(result.input_metadata.size_kb, 2),
        },
        "requirements": result.requirements.model_dump(mode="json"),
        "output": {
            "filename": result.filename,
            **result.validation.metadata.model_dump(),
            "size_kb": round(result.validation.metadata.size_kb, 2),
            "quality": result.quality,
            "palette_colors": result.palette_colors,
        },
        "validation": {
            "passed": result.validation.passed,
            "items": [item.model_dump() for item in result.validation.items],
        },
        "warnings": result.warnings,
        "tool_trace": [event.model_dump() for event in result.events],
    }


def result_manifest_json(result: AgentResult, *, source_name: str) -> bytes:
    return json.dumps(
        result_manifest(result, source_name=source_name),
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
