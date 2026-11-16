from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from photo_assistant.agent import ApplicationPhotoAgent, ToolRegistry
from photo_assistant.image_tools import encode_to_limit, fit_image, load_image, validate_output
from photo_assistant.models import PhotoRequirements
from photo_assistant.security import (
    SecurityError,
    provider_key_from_environment,
    validate_provider_endpoint,
)
from photo_assistant.services.batch_service import process_batch
from photo_assistant.version import __version__

ROOT = Path(__file__).resolve().parents[1]


def image_bytes() -> bytes:
    image = Image.new("RGB", (800, 1000), (120, 150, 180))
    output = BytesIO()
    image.save(output, "JPEG", quality=92)
    return output.getvalue()


def test_agent_trace_has_plan_parameters_and_stable_trace_id() -> None:
    result = ApplicationPhotoAgent().run(image_bytes(), PhotoRequirements())

    assert result.plan_summary == "inspect_image → fit_image → compress_image → validate_output"
    assert len(result.trace_id) == 12
    assert result.attempts == 1
    assert {event.trace_id for event in result.events} == {result.trace_id}
    assert result.events[0].parameters["source"]["size_bytes"] == len(image_bytes())


def test_validator_feedback_retries_once_without_weakening_constraints() -> None:
    calls = 0

    def flaky_validate(data: bytes, requirements: PhotoRequirements):
        nonlocal calls
        calls += 1
        report = validate_output(data, requirements)
        if calls == 1:
            failed_item = report.items[0].model_copy(update={"passed": False, "actual": "temporary mismatch"})
            return report.model_copy(update={"passed": False, "items": [failed_item, *report.items[1:]]})
        return report

    registry = ToolRegistry()
    registry.register("inspect_image", load_image)
    registry.register("fit_image", fit_image)
    registry.register("compress_image", encode_to_limit)
    registry.register("validate_output", flaky_validate)

    requirements = PhotoRequirements(min_quality=42)
    result = ApplicationPhotoAgent(registry).run(image_bytes(), requirements)

    assert result.validation.passed
    assert result.attempts == 2
    assert result.requirements.min_quality == 42
    assert len(result.events) == 6
    assert result.events[3].status == "failed"
    assert result.events[3].recovery_action == "重新编码并再次独立验收"


def test_web_deployment_rejects_custom_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHOTO_ASSISTANT_DEPLOYMENT", "web")

    with pytest.raises(SecurityError, match="在线版已禁用"):
        validate_provider_endpoint(
            "https://example.com/v1",
            provider_id="custom",
            trusted_url="",
        )

    assert (
        validate_provider_endpoint(
            "https://api.openai.com/v1",
            provider_id="openai",
            trusted_url="https://api.openai.com/v1",
        )
        == "https://api.openai.com/v1"
    )


def test_web_deployment_never_reads_provider_key_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHOTO_ASSISTANT_DEPLOYMENT", "web")
    monkeypatch.setenv("OPENAI_API_KEY", "server-secret-must-not-reach-browser")

    assert provider_key_from_environment("OPENAI_API_KEY") == ""


def test_desktop_environment_key_and_local_http_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHOTO_ASSISTANT_DEPLOYMENT", "desktop")
    monkeypatch.setenv("OPENAI_API_KEY", "desktop-only-key")

    assert provider_key_from_environment("OPENAI_API_KEY") == "desktop-only-key"
    assert (
        validate_provider_endpoint(
            "http://127.0.0.1:8000/v1",
            provider_id="custom",
            trusted_url="",
        )
        == "http://127.0.0.1:8000/v1"
    )

    with pytest.raises(SecurityError, match="必须使用 HTTPS"):
        validate_provider_endpoint(
            "http://example.com/v1",
            provider_id="custom",
            trusted_url="",
        )


def test_provider_endpoint_rejects_query_and_fragment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHOTO_ASSISTANT_DEPLOYMENT", "desktop")

    with pytest.raises(SecurityError, match="查询参数或片段"):
        validate_provider_endpoint(
            "https://example.com/v1?token=unsafe",
            provider_id="custom",
            trusted_url="",
        )


def test_batch_unexpected_error_is_sanitized() -> None:
    outcome = process_batch([("broken.jpg", object())], PhotoRequirements())  # type: ignore[list-item]

    assert outcome.failed == 1
    assert outcome.items[0].error_code == "AGENT_EXECUTION_FAILED"
    assert "seek" not in (outcome.items[0].error or "")
    assert outcome.items[0].trace_id


def test_release_files_and_versions_are_consistent() -> None:
    assert __version__ == "2026.11.17"
    assert 'version = "2026.11.17"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    installer = (ROOT / "installer" / "ApplicationPhotoAssistant.iss").read_text(encoding="utf-8")
    assert '#define MyAppVersion "2026.11.17"' in installer
    assert (ROOT / "docs" / "RELEASE_NOTES_2026.11.17.md").is_file()
    assert (ROOT / "assets" / "app.ico").read_bytes().startswith(b"\x00\x00\x01\x00")
    assert (ROOT / ".github" / "workflows" / "release.yml").is_file()
