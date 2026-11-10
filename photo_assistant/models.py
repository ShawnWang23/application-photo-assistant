from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_OUTPUT_PIXELS = 40_000_000


class ImageFormat(str, Enum):
    JPEG = "JPEG"
    PNG = "PNG"
    WEBP = "WEBP"

    @property
    def extension(self) -> str:
        return {self.JPEG: "jpg", self.PNG: "png", self.WEBP: "webp"}[self]

    @classmethod
    def normalize(cls, value: str | ImageFormat) -> ImageFormat:
        if isinstance(value, cls):
            return value
        normalized = value.strip().upper().replace("JPG", "JPEG")
        return cls(normalized)


class FitMode(str, Enum):
    CROP = "crop"
    PAD = "pad"


class PhotoRequirements(BaseModel):
    """Normalized constraints accepted by every image-processing tool."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    width: int = Field(default=295, ge=16, le=10_000, description="目标宽度，像素")
    height: int = Field(default=413, ge=16, le=10_000, description="目标高度，像素")
    output_format: ImageFormat = Field(default=ImageFormat.JPEG, description="输出格式")
    max_size_kb: int = Field(default=100, ge=1, le=50_000, description="最大文件大小，KiB")
    fit_mode: FitMode = Field(default=FitMode.CROP, description="裁剪或留白")
    background_color: str = Field(default="#FFFFFF", description="留白/透明像素背景色")
    focal_x: float = Field(default=0.5, ge=0.0, le=1.0, description="水平裁剪焦点")
    focal_y: float = Field(default=0.45, ge=0.0, le=1.0, description="垂直裁剪焦点")
    min_quality: int = Field(default=20, ge=5, le=95, description="有损压缩最低质量")
    allow_upscale: bool = Field(default=True, description="允许放大小图以达到目标尺寸")

    @field_validator("output_format", mode="before")
    @classmethod
    def normalize_format(cls, value: object) -> object:
        if isinstance(value, str):
            return ImageFormat.normalize(value)
        return value

    @field_validator("fit_mode", mode="before")
    @classmethod
    def normalize_fit_mode(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        lookup = {
            "裁剪": FitMode.CROP,
            "保持比例并裁剪": FitMode.CROP,
            "crop": FitMode.CROP,
            "留白": FitMode.PAD,
            "填充": FitMode.PAD,
            "pad": FitMode.PAD,
        }
        return lookup.get(value.strip().lower(), value)

    @field_validator("background_color")
    @classmethod
    def validate_hex_color(cls, value: str) -> str:
        value = value.strip().upper()
        if not value.startswith("#"):
            value = f"#{value}"
        if len(value) != 7 or any(ch not in "0123456789ABCDEF" for ch in value[1:]):
            raise ValueError("background_color 必须是 #RRGGBB 格式")
        return value

    @model_validator(mode="after")
    def validate_pixel_count(self) -> PhotoRequirements:
        if self.width * self.height > MAX_OUTPUT_PIXELS:
            raise ValueError("目标尺寸不能超过 4000 万像素")
        return self

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height


class ImageMetadata(BaseModel):
    width: int
    height: int
    format: str
    mode: str
    size_bytes: int

    @property
    def size_kb(self) -> float:
        return self.size_bytes / 1024


class ValidationItem(BaseModel):
    name: str
    expected: str
    actual: str
    passed: bool


class ValidationReport(BaseModel):
    passed: bool
    items: list[ValidationItem]
    metadata: ImageMetadata


class ToolEvent(BaseModel):
    tool: str
    status: str = "success"
    detail: str
    duration_ms: float | None = None
    trace_id: str | None = None
    attempt: int = 1
    parameters: dict[str, object] = Field(default_factory=dict)
    error_code: str | None = None
    recovery_action: str | None = None


class ToolResult(BaseModel):
    """Uniform envelope returned by every registered agent tool."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    data: Any = None
    error_code: str | None = None
    error_message: str | None = None
    execution_time_ms: float
    metadata: dict[str, object] = Field(default_factory=dict)
    trace_id: str
    attempt: int = 1
    exception: Exception | None = Field(default=None, exclude=True)


class AgentResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    output_bytes: bytes
    filename: str
    requirements: PhotoRequirements
    input_metadata: ImageMetadata
    validation: ValidationReport
    events: list[ToolEvent]
    quality: int | None = None
    palette_colors: int | None = None
    warnings: list[str] = Field(default_factory=list)
    trace_id: str
    plan_summary: str
    attempts: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
