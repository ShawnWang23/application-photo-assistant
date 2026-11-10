import json
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image

from photo_assistant.agent import ApplicationPhotoAgent
from photo_assistant.batch import build_batch_zip, process_batch
from photo_assistant.image_tools import ImageProcessingError
from photo_assistant.models import FitMode, PhotoRequirements
from photo_assistant.presets import PRESETS
from photo_assistant.provider import ExtractedRequirements, _parse_json_content
from photo_assistant.reporting import result_manifest_json


def image_bytes(size: tuple[int, int] = (800, 1000)) -> bytes:
    image = Image.new("RGB", size, (108, 142, 186))
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=92)
    return buffer.getvalue()


def test_all_presets_are_valid_and_named() -> None:
    assert len(PRESETS) >= 5
    for name, preset in PRESETS.items():
        assert name == preset.name
        assert preset.requirements.width >= 16
        assert preset.requirements.height >= 16


def test_provider_json_parser_accepts_fenced_json() -> None:
    content = """```json
    {"width": 295, "height": 413, "output_format": "JPEG",
     "max_size_kb": 100, "fit_mode": "crop", "background_color": null}
    ```"""
    parsed = _parse_json_content(content)

    assert isinstance(parsed, ExtractedRequirements)
    assert parsed.width == 295
    assert parsed.max_size_kb == 100


def test_no_upscale_crop_rejects_tiny_source() -> None:
    requirements = PhotoRequirements(
        width=600,
        height=800,
        fit_mode=FitMode.CROP,
        allow_upscale=False,
    )
    with pytest.raises(ImageProcessingError, match="像素不足"):
        ApplicationPhotoAgent().run(image_bytes((100, 100)), requirements)


def test_report_contains_validation_and_trace() -> None:
    result = ApplicationPhotoAgent().run(image_bytes(), PhotoRequirements(), original_name="portrait.jpg")
    report = json.loads(result_manifest_json(result, source_name="portrait.jpg"))

    assert report["validation"]["passed"] is True
    assert report["source"]["filename"] == "portrait.jpg"
    assert len(report["tool_trace"]) == 4
    assert report["output"]["filename"].endswith(".jpg")


def test_batch_zip_contains_photos_and_reports() -> None:
    outcome = process_batch(
        [("a.jpg", image_bytes()), ("b.jpg", image_bytes((900, 1200)))],
        PhotoRequirements(),
    )
    archive_bytes = build_batch_zip(outcome)

    assert outcome.succeeded == 2
    with ZipFile(BytesIO(archive_bytes)) as archive:
        names = archive.namelist()
        assert "batch_manifest.json" in names
        assert sum(name.startswith("photos/") for name in names) == 2
        assert sum(name.startswith("reports/") for name in names) == 2


def test_batch_renames_duplicate_output_filenames() -> None:
    outcome = process_batch(
        [("portrait.jpg", image_bytes()), ("portrait.png", image_bytes((900, 1200)))],
        PhotoRequirements(),
    )
    filenames = [item.result.filename for item in outcome.items if item.result]

    assert filenames == ["portrait_295x413.jpg", "portrait_295x413_2.jpg"]
    with ZipFile(BytesIO(build_batch_zip(outcome))) as archive:
        photo_names = [name for name in archive.namelist() if name.startswith("photos/")]
        assert len(photo_names) == len(set(photo_names)) == 2
