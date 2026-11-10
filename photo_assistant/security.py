from __future__ import annotations

import os
from urllib.parse import urlsplit

from .errors import AppError, ErrorCategory


class SecurityError(AppError, ValueError):
    default_code = "UNSAFE_ENDPOINT"
    default_category = ErrorCategory.USER_INPUT


def deployment_mode() -> str:
    return os.getenv("PHOTO_ASSISTANT_DEPLOYMENT", "desktop").strip().lower()


def validate_provider_endpoint(
    url: str,
    *,
    provider_id: str,
    trusted_url: str,
) -> str:
    """Validate model endpoints and disable arbitrary server-side URLs on web deployments."""

    cleaned = url.strip().rstrip("/")
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SecurityError("API Base URL 必须是有效的 HTTP(S) 地址。")
    if parsed.username or parsed.password:
        raise SecurityError("API Base URL 不能包含用户名或密码。")

    if deployment_mode() == "web":
        if provider_id == "custom":
            raise SecurityError("在线版已禁用自定义 API 地址；请使用桌面版连接自定义服务。")
        if parsed.scheme != "https" or cleaned != trusted_url.rstrip("/"):
            raise SecurityError("在线版只允许连接内置厂商的 HTTPS 官方地址。")
    return cleaned
