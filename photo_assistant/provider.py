from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .errors import AppError, ErrorCategory
from .models import FitMode, ImageFormat, PhotoRequirements
from .security import validate_provider_endpoint


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    id: str
    label: str
    base_url: str
    default_model: str
    key_label: str
    key_env: str
    model_help: str = ""
    model_list_query: dict[str, str] | None = None


PROVIDER_PROFILES: dict[str, ProviderProfile] = {
    "openai": ProviderProfile(
        id="openai",
        label="OpenAI（ChatGPT 模型）",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        key_label="OpenAI API Key",
        key_env="OPENAI_API_KEY",
        model_help="API Key 与 ChatGPT 会员是两套独立的账户计费体系。",
    ),
    "deepseek": ProviderProfile(
        id="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com",
        default_model="deepseek-flash",
        key_label="DeepSeek API Key",
        key_env="DEEPSEEK_API_KEY",
    ),
    "kimi": ProviderProfile(
        id="kimi",
        label="Kimi（月之暗面）",
        base_url="https://api.moonshot.cn/v1",
        default_model="kimi-k2.5",
        key_label="Kimi API Key",
        key_env="MOONSHOT_API_KEY",
    ),
    "doubao": ProviderProfile(
        id="doubao",
        label="豆包（火山方舟）",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        default_model="",
        key_label="火山方舟 API Key",
        key_env="ARK_API_KEY",
        model_help="模型通常填写方舟控制台中的推理接入点 ID，例如 ep-……。",
    ),
    "siliconflow": ProviderProfile(
        id="siliconflow",
        label="硅基流动 SiliconFlow",
        base_url="https://api.siliconflow.cn/v1",
        default_model="deepseek-ai/DeepSeek-V4-Flash",
        key_label="SiliconFlow API Key",
        key_env="SILICONFLOW_API_KEY",
        model_list_query={"sub_type": "chat"},
    ),
    "custom": ProviderProfile(
        id="custom",
        label="自定义 OpenAI 兼容服务",
        base_url="",
        default_model="",
        key_label="API Key",
        key_env="CUSTOM_LLM_API_KEY",
        model_help="填写完整 Base URL 与模型 ID；服务需兼容 Chat Completions。",
    ),
}

SILICONFLOW_BASE_URL = PROVIDER_PROFILES["siliconflow"].base_url
DEFAULT_SILICONFLOW_MODEL = PROVIDER_PROFILES["siliconflow"].default_model


class ProviderError(AppError, RuntimeError):
    """Friendly provider error safe to display in the UI."""

    default_code = "PROVIDER_ERROR"
    default_category = ErrorCategory.THIRD_PARTY


class ExtractedRequirements(BaseModel):
    """Only constraints explicitly present in the user's text are populated."""

    model_config = ConfigDict(extra="forbid")
    width: int | None = Field(ge=16, le=10_000)
    height: int | None = Field(ge=16, le=10_000)
    output_format: ImageFormat | None
    max_size_kb: int | None = Field(ge=1, le=50_000)
    fit_mode: FitMode | None
    background_color: str | None = Field(pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("output_format", mode="before")
    @classmethod
    def normalize_output_format(cls, value: object) -> object:
        if isinstance(value, str):
            return ImageFormat.normalize(value)
        return value

    @field_validator("fit_mode", mode="before")
    @classmethod
    def normalize_fit_mode(cls, value: object) -> object:
        if isinstance(value, str):
            aliases = {"裁剪": "crop", "留白": "pad", "不裁剪": "pad", "padding": "pad"}
            return aliases.get(value.strip().lower(), value)
        return value


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    ok: bool
    message: str
    model_count: int = 0


def get_provider_profile(provider_id: str) -> ProviderProfile:
    try:
        return PROVIDER_PROFILES[provider_id]
    except KeyError as exc:
        raise ProviderError(f"不支持的模型厂商：{provider_id}") from exc


def _merge(defaults: PhotoRequirements, extracted: ExtractedRequirements) -> PhotoRequirements:
    values = defaults.model_dump()
    values.update(extracted.model_dump(exclude_none=True))
    return PhotoRequirements.model_validate(values)


def _parse_json_content(content: str) -> ExtractedRequirements:
    cleaned = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.I | re.S)
    if fenced:
        cleaned = fenced.group(1)
    if not cleaned.startswith("{"):
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if match:
            cleaned = match.group(0)
    try:
        return ExtractedRequirements.model_validate(json.loads(cleaned))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ProviderError("模型返回内容不是有效的网申参数 JSON。") from exc


class OpenAICompatibleProvider:
    """Requirement extraction for OpenAI-compatible Chat Completions APIs."""

    def __init__(
        self,
        api_key: str,
        *,
        provider_id: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.profile = get_provider_profile(provider_id)
        if not api_key.strip():
            raise ProviderError(f"尚未配置 {self.profile.label} API Key。")
        resolved_url = (base_url if base_url is not None else self.profile.base_url).strip().rstrip("/")
        if not resolved_url:
            raise ProviderError("请填写 API Base URL。")
        resolved_url = validate_provider_endpoint(
            resolved_url,
            provider_id=provider_id,
            trusted_url=self.profile.base_url,
        )
        self.model = model.strip() or self.profile.default_model

        from openai import OpenAI

        self.client = OpenAI(api_key=api_key.strip(), base_url=resolved_url, timeout=timeout, max_retries=2)

    def list_models(self) -> list[str]:
        try:
            kwargs: dict[str, Any] = {}
            if self.profile.model_list_query:
                kwargs["extra_query"] = self.profile.model_list_query
            page = self.client.models.list(**kwargs)
            return sorted({item.id for item in page.data if getattr(item, "id", None)})
        except Exception as exc:
            raise self._translate_error(exc) from exc

    def check_connection(self) -> ProviderStatus:
        models = self.list_models()
        if self.model not in models:
            return ProviderStatus(True, "连接成功，但当前模型未出现在账户返回的模型列表中。", len(models))
        return ProviderStatus(True, f"连接成功，模型 {self.model} 可见。", len(models))

    def extract_requirements(self, text: str, defaults: PhotoRequirements) -> PhotoRequirements:
        if not text.strip():
            return defaults
        if not self.model:
            raise ProviderError("请填写模型 ID 或推理接入点 ID。")
        schema: dict[str, Any] = ExtractedRequirements.model_json_schema()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是网申证件照要求解析器。只提取用户明确写出的约束，未提及字段必须为 null。"
                    "尺寸顺序是宽×高；JPG 写为 JPEG；裁剪写 crop，留白/不裁剪写 pad。"
                    "只输出 JSON，且必须包含 width、height、output_format、max_size_kb、fit_mode、"
                    "background_color 六个字段。"
                ),
            },
            {"role": "user", "content": text},
        ]
        base_request: dict[str, Any] = {"model": self.model, "messages": messages, "max_tokens": 500}
        formats: list[dict[str, Any] | None] = [
            {
                "type": "json_schema",
                "json_schema": {"name": "application_photo_requirements", "strict": True, "schema": schema},
            },
            {"type": "json_object"},
            None,
        ]
        last_error: Exception | None = None
        try:
            for index, response_format in enumerate(formats):
                request = dict(base_request)
                if response_format is not None:
                    request["response_format"] = response_format
                if index < 2:
                    request["temperature"] = 0
                else:
                    # Newer reasoning models may reject both temperature and
                    # the legacy max_tokens field.
                    request.pop("max_tokens", None)
                try:
                    response = self.client.chat.completions.create(**request)
                    content = response.choices[0].message.content or ""
                    return _merge(defaults, _parse_json_content(content))
                except ProviderError:
                    raise
                except Exception as exc:
                    last_error = exc
                    if getattr(exc, "status_code", None) not in {400, 422}:
                        raise
            assert last_error is not None
            raise last_error
        except ProviderError:
            raise
        except Exception as exc:
            raise self._translate_error(exc) from exc

    def _translate_error(self, exc: Exception) -> ProviderError:
        status = getattr(exc, "status_code", None)
        name = self.profile.label
        if status == 401:
            return ProviderError(f"{name} API Key 无效或已失效，请到厂商控制台检查。")
        if status == 403:
            return ProviderError(f"当前 API Key 没有调用 {name} 或该模型的权限。")
        if status == 404:
            return ProviderError("未找到模型或接口地址，请检查 Base URL 与模型 ID。")
        if status == 429:
            return ProviderError(f"{name} 请求频率或额度已达上限，请稍后重试。")
        if status in {500, 502, 503, 504}:
            return ProviderError(f"{name} 模型服务暂时繁忙，请稍后重试。")
        return ProviderError(f"{name} 调用失败：{type(exc).__name__}")


class SiliconFlowProvider(OpenAICompatibleProvider):
    """Backward-compatible SiliconFlow wrapper."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_SILICONFLOW_MODEL,
        base_url: str = SILICONFLOW_BASE_URL,
        timeout: float = 25.0,
    ) -> None:
        super().__init__(api_key, provider_id="siliconflow", model=model, base_url=base_url, timeout=timeout)
