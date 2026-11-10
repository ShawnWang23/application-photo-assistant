from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

from PIL import Image, ImageColor, ImageOps, UnidentifiedImageError

from .errors import AppError, ErrorCategory
from .models import (
    FitMode,
    ImageFormat,
    ImageMetadata,
    PhotoRequirements,
    ValidationItem,
    ValidationReport,
)


class ImageProcessingError(AppError, ValueError):
    """Raised when input cannot be safely decoded or constraints are impossible."""

    default_code = "IMAGE_PROCESSING_ERROR"
    default_category = ErrorCategory.IMAGE_PROCESSING


MAX_INPUT_PIXELS = 40_000_000
MAX_INPUT_BYTES = 25 * 1024 * 1024


@dataclass(slots=True)
class EncodedImage:
    data: bytes
    quality: int | None
    palette_colors: int | None = None


def _read_source(source: bytes | bytearray | BinaryIO) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    source.seek(0)
    return source.read()


def load_image(source: bytes | bytearray | BinaryIO) -> tuple[Image.Image, ImageMetadata]:
    raw = _read_source(source)
    if not raw:
        raise ImageProcessingError("上传的文件为空。")
    if len(raw) > MAX_INPUT_BYTES:
        raise ImageProcessingError("图片文件不能超过 25 MB。")
    try:
        with Image.open(BytesIO(raw)) as opened:
            opened.verify()
        with Image.open(BytesIO(raw)) as reopened:
            if reopened.width * reopened.height > MAX_INPUT_PIXELS:
                raise ImageProcessingError(
                    "图片像素总量过大；为避免内存占用，请上传不超过 4000 万像素的照片。"
                )
            image_format = reopened.format or "UNKNOWN"
            image = ImageOps.exif_transpose(reopened).copy()
    except ImageProcessingError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageProcessingError("无法识别该图片，请上传有效的 JPG 或 PNG 文件。") from exc

    metadata = ImageMetadata(
        width=image.width,
        height=image.height,
        format=image_format.upper(),
        mode=image.mode,
        size_bytes=len(raw),
    )
    return image, metadata


def _flatten_alpha(image: Image.Image, color: str) -> Image.Image:
    rgb = Image.new("RGB", image.size, ImageColor.getrgb(color))
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        rgb.paste(rgba, mask=rgba.getchannel("A"))
    else:
        rgb.paste(image.convert("RGB"))
    return rgb


def fit_image(image: Image.Image, requirements: PhotoRequirements) -> Image.Image:
    """Resize without distortion, then crop around a focal point or add padding."""

    target = (requirements.width, requirements.height)
    if requirements.fit_mode == FitMode.CROP:
        scale = max(requirements.width / image.width, requirements.height / image.height)
        if scale > 1 and not requirements.allow_upscale:
            raise ImageProcessingError(
                "原图像素不足以铺满目标尺寸；请允许放大、改用留白，或上传更清晰的照片。"
            )
        return ImageOps.fit(
            image,
            target,
            method=Image.Resampling.LANCZOS,
            centering=(requirements.focal_x, requirements.focal_y),
        )

    if (
        not requirements.allow_upscale
        and image.width <= requirements.width
        and image.height <= requirements.height
    ):
        contained = image.copy()
    else:
        contained = ImageOps.contain(image, target, method=Image.Resampling.LANCZOS)
    has_alpha = contained.mode in ("RGBA", "LA") or (
        contained.mode == "P" and "transparency" in contained.info
    )
    canvas_mode = "RGBA" if has_alpha and requirements.output_format == ImageFormat.PNG else "RGB"
    base_color: tuple[int, ...]
    rgb_color = ImageColor.getrgb(requirements.background_color)
    base_color = (*rgb_color, 255) if canvas_mode == "RGBA" else rgb_color
    canvas = Image.new(canvas_mode, target, base_color)
    x = (requirements.width - contained.width) // 2
    y = (requirements.height - contained.height) // 2
    if has_alpha:
        rgba = contained.convert("RGBA")
        canvas.paste(rgba, (x, y), rgba)
    else:
        canvas.paste(contained.convert(canvas_mode), (x, y))
    return canvas


def _save_once(
    image: Image.Image,
    output_format: ImageFormat,
    *,
    quality: int | None = None,
    background_color: str = "#FFFFFF",
    png_colors: int | None = None,
) -> bytes:
    buffer = BytesIO()
    if output_format == ImageFormat.JPEG:
        prepared = _flatten_alpha(image, background_color)
        prepared.save(
            buffer,
            format="JPEG",
            quality=quality or 95,
            optimize=True,
            progressive=True,
            subsampling=2,
            exif=b"",
        )
    elif output_format == ImageFormat.WEBP:
        prepared = _flatten_alpha(image, background_color)
        prepared.save(buffer, format="WEBP", quality=quality or 95, method=6, exif=b"")
    else:
        prepared = image
        if png_colors is not None:
            prepared = image.convert("RGBA" if image.mode == "RGBA" else "RGB").quantize(
                colors=png_colors,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
        prepared.save(buffer, format="PNG", optimize=True, compress_level=9, exif=b"")
    return buffer.getvalue()


def encode_to_limit(image: Image.Image, requirements: PhotoRequirements) -> EncodedImage:
    """Encode an image and find the highest quality that satisfies max_size_kb."""

    max_bytes = requirements.max_size_kb * 1024
    output_format = requirements.output_format

    if output_format == ImageFormat.PNG:
        lossless = _save_once(image, output_format)
        if len(lossless) <= max_bytes:
            return EncodedImage(lossless, None)
        for colors in (256, 192, 128, 96, 64, 48, 32, 24, 16, 8):
            candidate = _save_once(image, output_format, png_colors=colors)
            if len(candidate) <= max_bytes:
                return EncodedImage(candidate, None, palette_colors=colors)
        raise ImageProcessingError(
            f"PNG 在最低调色板设置下仍超过 {requirements.max_size_kb} KB；请提高大小限制或改用 JPG/WEBP。"
        )

    minimum_quality = requirements.min_quality
    minimum = _save_once(
        image,
        output_format,
        quality=minimum_quality,
        background_color=requirements.background_color,
    )
    if len(minimum) > max_bytes:
        raise ImageProcessingError(
            f"目标尺寸在质量下限 {minimum_quality} 时仍超过 "
            f"{requirements.max_size_kb} KB；请提高大小限制、降低质量下限或减小像素尺寸。"
        )

    low, high = minimum_quality, 95
    best_data, best_quality = minimum, minimum_quality
    while low <= high:
        quality = (low + high) // 2
        candidate = _save_once(
            image,
            output_format,
            quality=quality,
            background_color=requirements.background_color,
        )
        if len(candidate) <= max_bytes:
            best_data, best_quality = candidate, quality
            low = quality + 1
        else:
            high = quality - 1
    return EncodedImage(best_data, best_quality)


def make_preview(
    source: bytes | bytearray | BinaryIO,
    requirements: PhotoRequirements,
    mode: FitMode,
) -> Image.Image:
    image, _ = load_image(source)
    preview_requirements = requirements.model_copy(update={"fit_mode": mode})
    fitted = fit_image(image, preview_requirements)
    if preview_requirements.output_format != ImageFormat.PNG:
        fitted = _flatten_alpha(fitted, preview_requirements.background_color)
    return fitted


def inspect_encoded(data: bytes) -> ImageMetadata:
    with Image.open(BytesIO(data)) as image:
        return ImageMetadata(
            width=image.width,
            height=image.height,
            format=(image.format or "UNKNOWN").upper(),
            mode=image.mode,
            size_bytes=len(data),
        )


def validate_output(data: bytes, requirements: PhotoRequirements) -> ValidationReport:
    metadata = inspect_encoded(data)
    expected_format = requirements.output_format.value
    format_actual = "JPEG" if metadata.format == "JPG" else metadata.format
    items = [
        ValidationItem(
            name="图片尺寸",
            expected=f"{requirements.width} × {requirements.height} px",
            actual=f"{metadata.width} × {metadata.height} px",
            passed=(metadata.width, metadata.height) == (requirements.width, requirements.height),
        ),
        ValidationItem(
            name="文件格式",
            expected=expected_format,
            actual=format_actual,
            passed=format_actual == expected_format,
        ),
        ValidationItem(
            name="文件大小",
            expected=f"≤ {requirements.max_size_kb} KB",
            actual=f"{metadata.size_kb:.1f} KB",
            passed=metadata.size_bytes <= requirements.max_size_kb * 1024,
        ),
    ]
    return ValidationReport(
        passed=all(item.passed for item in items),
        items=items,
        metadata=metadata,
    )
