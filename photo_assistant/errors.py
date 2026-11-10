from __future__ import annotations

from enum import Enum
from uuid import uuid4


class ErrorCategory(str, Enum):
    USER_INPUT = "user_input"
    IMAGE_PROCESSING = "image_processing"
    THIRD_PARTY = "third_party"
    SYSTEM = "system"


class AppError(Exception):
    """Base error whose message is safe to show to an end user."""

    default_code = "APP_ERROR"
    default_category = ErrorCategory.SYSTEM

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        category: ErrorCategory | None = None,
        retryable: bool = False,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.public_message = message
        self.code = code or self.default_code
        self.category = category or self.default_category
        self.retryable = retryable
        self.trace_id = trace_id or uuid4().hex[:12]


class AgentExecutionError(AppError):
    default_code = "AGENT_EXECUTION_FAILED"
    default_category = ErrorCategory.IMAGE_PROCESSING


def public_error_message(exc: Exception, *, trace_id: str | None = None) -> str:
    """Never expose local paths or third-party exception internals to the UI."""

    if isinstance(exc, AppError):
        return f"[{exc.code}] {exc.public_message}（追踪号：{exc.trace_id}）"
    reference = trace_id or uuid4().hex[:12]
    return f"[UNEXPECTED_ERROR] 处理时发生内部错误，请重试或提交追踪号：{reference}"
