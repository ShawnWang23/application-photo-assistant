from io import BytesIO

import pytest
from PIL import Image
from pydantic import ValidationError

from photo_assistant.agent import ApplicationPhotoAgent
from photo_assistant.image_tools import ImageProcessingError, make_preview
from photo_assistant.models import FitMode, ImageFormat, PhotoRequirements


def sample_image_bytes(
    size: tuple[int, int] = (900, 600),
    image_format: str = "PNG",
    mode: str = "RGB",
) -> bytes:
    image = Image.new(mode, size, (42, 110, 180, 180) if mode == "RGBA" else (42, 110, 180))
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.mark.parametrize("fit_mode", [FitMode.CROP, FitMode.PAD])
def test_agent_produces_exact_valid_jpeg(fit_mode: FitMode) -> None:
    requirements = PhotoRequirements(
        width=295,
        height=413,
        output_format=ImageFormat.JPEG,
        max_size_kb=100,
        fit_mode=fit_mode,
    )
    result = ApplicationPhotoAgent().run(sample_image_bytes(), requirements)

    assert result.validation.passed
    assert result.validation.metadata.width == 295
    assert result.validation.metadata.height == 413
    assert result.validation.metadata.format == "JPEG"
    assert len(result.output_bytes) <= 100 * 1024
    assert len(result.events) == 4


def test_transparent_png_can_be_converted_to_jpeg() -> None:
    requirements = PhotoRequirements(output_format="JPG", max_size_kb=100)
    result = ApplicationPhotoAgent().run(sample_image_bytes(mode="RGBA"), requirements)

    with Image.open(BytesIO(result.output_bytes)) as image:
        assert image.mode == "RGB"
        assert image.format == "JPEG"


@pytest.mark.parametrize(
    ("output_format", "pil_format"),
    [(ImageFormat.PNG, "PNG"), (ImageFormat.WEBP, "WEBP")],
)
def test_other_output_formats_are_valid(output_format: ImageFormat, pil_format: str) -> None:
    requirements = PhotoRequirements(
        width=320,
        height=480,
        output_format=output_format,
        max_size_kb=100,
        fit_mode=FitMode.PAD,
    )
    result = ApplicationPhotoAgent().run(sample_image_bytes(), requirements)

    assert result.validation.passed
    assert result.filename.endswith(f".{output_format.extension}")
    with Image.open(BytesIO(result.output_bytes)) as image:
        assert image.format == pil_format
        assert image.size == (320, 480)


def test_crop_and_pad_previews_are_exact_size() -> None:
    source = sample_image_bytes((1200, 500))
    requirements = PhotoRequirements(width=300, height=400)

    crop = make_preview(source, requirements, FitMode.CROP)
    pad = make_preview(source, requirements, FitMode.PAD)

    assert crop.size == (300, 400)
    assert pad.size == (300, 400)


def test_rejects_excessive_output_pixel_count() -> None:
    with pytest.raises(ValidationError, match="4000 万像素"):
        PhotoRequirements(width=10_000, height=10_000)


def test_impossible_size_limit_raises_clear_error() -> None:
    # Large noisy-looking gradient is harder to compress than a flat fixture.
    image = Image.effect_noise((2000, 2000), 100).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    requirements = PhotoRequirements(
        width=2000,
        height=2000,
        output_format=ImageFormat.JPEG,
        max_size_kb=1,
    )

    with pytest.raises(ImageProcessingError, match="质量下限"):
        ApplicationPhotoAgent().run(buffer.getvalue(), requirements)
