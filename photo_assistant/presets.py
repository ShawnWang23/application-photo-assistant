from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .models import FitMode, ImageFormat, PhotoRequirements


class PhotoPreset(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    requirements: PhotoRequirements


PRESETS: dict[str, PhotoPreset] = {
    "银行网申（示例）": PhotoPreset(
        name="银行网申（示例）",
        description="295 × 413 px，JPG，不超过 100 KB",
        requirements=PhotoRequirements(),
    ),
    "一寸电子照（常用）": PhotoPreset(
        name="一寸电子照（常用）",
        description="295 × 413 px，JPG，不超过 200 KB",
        requirements=PhotoRequirements(max_size_kb=200),
    ),
    "二寸电子照（常用）": PhotoPreset(
        name="二寸电子照（常用）",
        description="413 × 626 px，JPG，不超过 300 KB",
        requirements=PhotoRequirements(width=413, height=626, max_size_kb=300),
    ),
    "报名证件照 3:4": PhotoPreset(
        name="报名证件照 3:4",
        description="480 × 640 px，JPG，不超过 300 KB",
        requirements=PhotoRequirements(width=480, height=640, max_size_kb=300),
    ),
    "方形头像": PhotoPreset(
        name="方形头像",
        description="600 × 600 px，JPG，不超过 500 KB",
        requirements=PhotoRequirements(width=600, height=600, max_size_kb=500),
    ),
    "完整保留原图构图": PhotoPreset(
        name="完整保留原图构图",
        description="295 × 413 px，白色留白，JPG，不超过 100 KB",
        requirements=PhotoRequirements(fit_mode=FitMode.PAD),
    ),
    "PNG 格式保真": PhotoPreset(
        name="PNG 格式保真",
        description="295 × 413 px，PNG，留白，不超过 500 KB",
        requirements=PhotoRequirements(
            output_format=ImageFormat.PNG,
            max_size_kb=500,
            fit_mode=FitMode.PAD,
        ),
    ),
}


def get_preset(name: str) -> PhotoPreset:
    return PRESETS[name]
