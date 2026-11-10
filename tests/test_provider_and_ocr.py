from types import SimpleNamespace

from photo_assistant.ocr import result_to_text
from photo_assistant.provider import PROVIDER_PROFILES, _parse_json_content


def test_mainstream_provider_profiles_have_connection_defaults() -> None:
    assert {"openai", "deepseek", "kimi", "doubao", "siliconflow", "custom"} <= set(PROVIDER_PROFILES)
    for provider_id in ("openai", "deepseek", "kimi", "doubao", "siliconflow"):
        profile = PROVIDER_PROFILES[provider_id]
        assert profile.base_url.startswith("https://")
        assert profile.key_label


def test_provider_parser_accepts_json_with_explanatory_prefix() -> None:
    parsed = _parse_json_content(
        '识别结果如下： {"width":295,"height":413,"output_format":"JPEG",'
        '"max_size_kb":100,"fit_mode":"crop","background_color":null}'
    )
    assert parsed.width == 295
    assert parsed.height == 413


def test_provider_parser_normalizes_common_aliases() -> None:
    parsed = _parse_json_content(
        '{"width":295,"height":413,"output_format":"JPG",'
        '"max_size_kb":100,"fit_mode":"裁剪","background_color":null}'
    )
    assert parsed.output_format.value == "JPEG"
    assert parsed.fit_mode.value == "crop"


def test_ocr_output_is_combined_and_scored() -> None:
    output = SimpleNamespace(
        txts=("照片格式：JPG", "尺寸：295×413", "不超过100KB"), scores=(0.9, 0.8, 1.0), elapse=0.42
    )
    parsed = result_to_text(output)

    assert parsed.line_count == 3
    assert "295×413" in parsed.text
    assert parsed.average_confidence == 0.9
    assert parsed.elapsed_seconds == 0.42
