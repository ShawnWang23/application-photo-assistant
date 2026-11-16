from __future__ import annotations

import os
from ipaddress import ip_address
from urllib.parse import urlsplit

from .errors import AppError, ErrorCategory


class SecurityError(AppError, ValueError):
    default_code = "UNSAFE_ENDPOINT"
    default_category = ErrorCategory.USER_INPUT


def deployment_mode() -> str:
    return os.getenv("PHOTO_ASSISTANT_DEPLOYMENT", "desktop").strip().lower()


def provider_key_from_environment(key_env: str) -> str:
    """Read desktop convenience keys without leaking server secrets to Web clients."""

    if deployment_mode() == "web":
        return ""
    return os.getenv(key_env, "")


def _is_loopback_host(hostname: str) -> bool:
    normalized = hostname.rstrip(".").lower()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


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
    if parsed.query or parsed.fragment:
        raise SecurityError("API Base URL 不能包含查询参数或片段。")

    mode = deployment_mode()
    if parsed.scheme != "https" and not (mode == "desktop" and _is_loopback_host(parsed.hostname)):
        raise SecurityError("非本机 API 地址必须使用 HTTPS，避免 API Key 被明文传输。")

    if mode == "web":
        if provider_id == "custom":
            raise SecurityError("在线版已禁用自定义 API 地址；请使用桌面版连接自定义服务。")
        if parsed.scheme != "https" or cleaned != trusted_url.rstrip("/"):
            raise SecurityError("在线版只允许连接内置厂商的 HTTPS 官方地址。")
    return cleaned
