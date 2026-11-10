from __future__ import annotations

import json
from dataclasses import dataclass, field
from io import BytesIO
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from ..agent import ApplicationPhotoAgent
from ..errors import AppError, public_error_message
from ..logging_config import LOGGER
from ..models import AgentResult, PhotoRequirements
from ..reporting import result_manifest


@dataclass(slots=True)
class BatchItem:
    source_name: str
    result: AgentResult | None = None
    error: str | None = None
    error_code: str | None = None
    trace_id: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.result is not None and self.error is None


@dataclass(slots=True)
class BatchOutcome:
    items: list[BatchItem] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(item.succeeded for item in self.items)

    @property
    def failed(self) -> int:
        return len(self.items) - self.succeeded


def process_batch(sources: list[tuple[str, bytes]], requirements: PhotoRequirements) -> BatchOutcome:
    agent = ApplicationPhotoAgent()
    outcome = BatchOutcome()
    used_filenames: set[str] = set()
    for index, (name, data) in enumerate(sources):
        try:
            result = agent.run(data, requirements, original_name=name)
            original_filename = result.filename
            suffix = 2
            while result.filename.casefold() in used_filenames:
                stem, dot, extension = original_filename.rpartition(".")
                result.filename = f"{stem}_{suffix}{dot}{extension}"
                suffix += 1
            used_filenames.add(result.filename.casefold())
            outcome.items.append(BatchItem(source_name=name, result=result))
        except Exception as exc:
            trace_id = getattr(exc, "trace_id", None) or uuid4().hex[:12]
            if isinstance(exc, AppError):
                LOGGER.warning(
                    "batch_item_failed index=%s trace_id=%s code=%s",
                    index,
                    trace_id,
                    exc.code,
                )
                error_code = exc.code
            else:
                LOGGER.exception("batch_item_unexpected index=%s trace_id=%s", index, trace_id)
                error_code = "UNEXPECTED_ERROR"
            outcome.items.append(
                BatchItem(
                    source_name=name,
                    error=public_error_message(exc, trace_id=trace_id),
                    error_code=error_code,
                    trace_id=trace_id,
                )
            )
    return outcome


def build_batch_zip(outcome: BatchOutcome) -> bytes:
    buffer = BytesIO()
    manifests: list[dict[str, object]] = []
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for item in outcome.items:
            if item.result is None:
                manifests.append(
                    {
                        "source": item.source_name,
                        "passed": False,
                        "error": item.error,
                        "error_code": item.error_code,
                        "trace_id": item.trace_id,
                    }
                )
                continue
            archive.writestr(f"photos/{item.result.filename}", item.result.output_bytes)
            manifest = result_manifest(item.result, source_name=item.source_name)
            manifests.append(manifest)
            archive.writestr(
                f"reports/{item.result.filename}.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
        archive.writestr(
            "batch_manifest.json",
            json.dumps(
                {
                    "total": len(outcome.items),
                    "succeeded": outcome.succeeded,
                    "failed": outcome.failed,
                    "items": manifests,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    return buffer.getvalue()
