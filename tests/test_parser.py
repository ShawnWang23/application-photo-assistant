import pytest
from pydantic import ValidationError

from photo_assistant.models import FitMode, ImageFormat, PhotoRequirements
from photo_assistant.parser import parse_requirements_rules


def test_parse_chinese_application_requirement() -> None:
    defaults = PhotoRequirements(width=100, height=100, max_size_kb=500)
    parsed = parse_requirements_rules(
        "银行网申要求 JPG，295 × 413 px，文件不超过 100KB，保持比例裁剪",
        defaults,
    )

    assert parsed.width == 295
    assert parsed.height == 413
    assert parsed.output_format == ImageFormat.JPEG
    assert parsed.max_size_kb == 100
    assert parsed.fit_mode == FitMode.CROP


def test_parse_separate_dimensions_mb_and_padding() -> None:
    parsed = parse_requirements_rules(
        "width: 600, height: 800, PNG, maximum 1.5MB, do not crop; pad it",
        PhotoRequirements(),
    )

    assert parsed.width == 600
    assert parsed.height == 800
    assert parsed.output_format == ImageFormat.PNG
    assert parsed.max_size_kb == 1536
    assert parsed.fit_mode == FitMode.PAD


def test_unspecified_fields_keep_form_defaults() -> None:
    defaults = PhotoRequirements(width=320, height=480, max_size_kb=88)
    parsed = parse_requirements_rules("请输出 PNG", defaults)

    assert parsed.width == 320
    assert parsed.height == 480
    assert parsed.max_size_kb == 88
    assert parsed.output_format == ImageFormat.PNG


def test_parsed_values_still_pass_pydantic_validation() -> None:
    with pytest.raises(ValidationError):
        parse_requirements_rules("99999×99999 JPG 100KB", PhotoRequirements())


def test_parse_chinese_requirement_without_spaces() -> None:
    parsed = parse_requirements_rules("照片格式JPG，尺寸295×413像素，大小不超过100KB", PhotoRequirements())

    assert parsed.output_format == ImageFormat.JPEG
    assert parsed.width == 295
    assert parsed.height == 413
    assert parsed.max_size_kb == 100
