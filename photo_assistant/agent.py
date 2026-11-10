from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from .errors import AgentExecutionError, AppError
from .image_tools import EncodedImage, encode_to_limit, fit_image, load_image, validate_output
from .logging_config import LOGGER
from .models import AgentResult, PhotoRequirements, ToolEvent, ToolResult, ValidationReport
from .planning import FeedbackController, Planner


def _safe_parameters(arguments: dict[str, Any]) -> dict[str, object]:
    """Record useful tool inputs without retaining images, API keys, or file contents."""

    safe: dict[str, object] = {}
    for name, value in arguments.items():
        if isinstance(value, (bytes, bytearray)):
            safe[name] = {"type": "bytes", "size_bytes": len(value)}
        elif isinstance(value, PhotoRequirements):
            safe[name] = value.model_dump(mode="json")
        elif hasattr(value, "size") and hasattr(value, "mode"):
            safe[name] = {"type": type(value).__name__, "size": list(value.size), "mode": value.mode}
        else:
            safe[name] = str(value)[:160]
    return safe


class ToolRegistry:
    """Explicit tool layer with argument checks and a uniform result envelope."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, function: Callable[..., Any]) -> None:
        if not name or name in self._tools:
            raise ValueError(f"工具名称无效或重复：{name}")
        self._tools[name] = function

    def call(self, name: str, *, trace_id: str, attempt: int = 1, **arguments: Any) -> ToolResult:
        started = perf_counter()
        parameters = _safe_parameters(arguments)
        if name not in self._tools:
            return ToolResult(
                success=False,
                error_code="UNKNOWN_TOOL",
                error_message=f"未注册工具：{name}",
                execution_time_ms=0,
                metadata={"parameters": parameters},
                trace_id=trace_id,
                attempt=attempt,
                exception=KeyError(name),
            )
        try:
            function = self._tools[name]
            inspect.signature(function).bind(**arguments)
            data = function(**arguments)
            return ToolResult(
                success=True,
                data=data,
                execution_time_ms=(perf_counter() - started) * 1000,
                metadata={"parameters": parameters},
                trace_id=trace_id,
                attempt=attempt,
            )
        except Exception as exc:
            code = exc.code if isinstance(exc, AppError) else "TOOL_EXECUTION_ERROR"
            message = exc.public_message if isinstance(exc, AppError) else "工具执行失败。"
            return ToolResult(
                success=False,
                error_code=code,
                error_message=message,
                execution_time_ms=(perf_counter() - started) * 1000,
                metadata={"parameters": parameters},
                trace_id=trace_id,
                attempt=attempt,
                exception=exc,
            )

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)


class ApplicationPhotoAgent:
    """Planner/executor/validator loop backed by deterministic image tools."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        *,
        planner: Planner | None = None,
        feedback: FeedbackController | None = None,
    ) -> None:
        self.registry = registry or ToolRegistry()
        self.planner = planner or Planner()
        self.feedback = feedback or FeedbackController()
        if not self.registry.names:
            self.registry.register("inspect_image", load_image)
            self.registry.register("fit_image", fit_image)
            self.registry.register("compress_image", encode_to_limit)
            self.registry.register("validate_output", validate_output)

    def _execute(
        self,
        name: str,
        events: list[ToolEvent],
        *,
        trace_id: str,
        attempt: int = 1,
        detail: Callable[[Any], str],
        **arguments: Any,
    ) -> Any:
        result = self.registry.call(name, trace_id=trace_id, attempt=attempt, **arguments)
        parameters = result.metadata.get("parameters", {})
        if not result.success:
            events.append(
                ToolEvent(
                    tool=name,
                    status="failed",
                    detail=result.error_message or "工具执行失败",
                    duration_ms=result.execution_time_ms,
                    trace_id=trace_id,
                    attempt=attempt,
                    parameters=parameters if isinstance(parameters, dict) else {},
                    error_code=result.error_code,
                )
            )
            exc = result.exception
            if isinstance(exc, AppError):
                exc.trace_id = trace_id
                raise exc
            LOGGER.exception("tool_failed trace_id=%s tool=%s", trace_id, name, exc_info=exc)
            raise AgentExecutionError("图片处理工具执行失败。", trace_id=trace_id) from exc
        events.append(
            ToolEvent(
                tool=name,
                detail=detail(result.data),
                duration_ms=result.execution_time_ms,
                trace_id=trace_id,
                attempt=attempt,
                parameters=parameters if isinstance(parameters, dict) else {},
            )
        )
        return result.data

    def run(
        self,
        source: bytes,
        requirements: PhotoRequirements,
        *,
        original_name: str = "photo",
    ) -> AgentResult:
        trace_id = uuid4().hex[:12]
        plan = self.planner.create(requirements)
        events: list[ToolEvent] = []
        warnings: list[str] = []
        LOGGER.info("agent_started trace_id=%s plan=%s", trace_id, plan.summary)

        image, input_metadata = self._execute(
            "inspect_image",
            events,
            trace_id=trace_id,
            source=source,
            detail=lambda data: (
                f"识别输入：{data[1].width} × {data[1].height} px，"
                f"{data[1].format}，{data[1].size_kb:.1f} KB"
            ),
        )
        if input_metadata.width < requirements.width or input_metadata.height < requirements.height:
            warnings.append("原图至少有一边小于目标尺寸，输出清晰度可能受放大影响。")

        mode_label = "保持比例并裁剪" if requirements.fit_mode.value == "crop" else "保持比例并留白"
        fitted = self._execute(
            "fit_image",
            events,
            trace_id=trace_id,
            image=image,
            requirements=requirements,
            detail=lambda _: f"{mode_label}到 {requirements.width} × {requirements.height} px",
        )

        encoded: EncodedImage | None = None
        report: ValidationReport | None = None
        attempts = 0
        for attempt in range(1, plan.max_attempts + 1):
            attempts = attempt
            encoded = self._execute(
                "compress_image",
                events,
                trace_id=trace_id,
                attempt=attempt,
                image=fitted,
                requirements=requirements,
                detail=lambda value: self._compression_detail(value, requirements),
            )
            report = self._execute(
                "validate_output",
                events,
                trace_id=trace_id,
                attempt=attempt,
                data=encoded.data,
                requirements=requirements,
                detail=lambda value: "全部约束均已通过" if value.passed else "存在未通过的输出约束",
            )
            if report.passed:
                break
            decision = self.feedback.evaluate(report, attempt=attempt, max_attempts=plan.max_attempts)
            events[-1].status = "failed"
            events[-1].recovery_action = decision.recovery_action
            if not decision.retry:
                raise AgentExecutionError(decision.reason, trace_id=trace_id)

        if encoded is None or report is None or not report.passed:
            raise AgentExecutionError("自动验证未通过。", trace_id=trace_id)
        if encoded.quality is not None and encoded.quality <= 30:
            warnings.append("为满足文件大小限制，输出使用了较强压缩；建议放大预览确认面部细节。")
        if encoded.palette_colors is not None and encoded.palette_colors <= 32:
            warnings.append("PNG 使用了较小调色板；建议放大预览确认肤色渐变是否自然。")

        stem = Path(original_name).stem or "photo"
        stem = re.sub(r"[^\w\-\u4e00-\u9fff]+", "_", stem).strip("_") or "photo"
        filename = f"{stem}_{requirements.width}x{requirements.height}.{requirements.output_format.extension}"
        LOGGER.info("agent_completed trace_id=%s attempts=%s", trace_id, attempts)
        return AgentResult(
            output_bytes=encoded.data,
            filename=filename,
            requirements=requirements,
            input_metadata=input_metadata,
            validation=report,
            events=events,
            quality=encoded.quality,
            palette_colors=encoded.palette_colors,
            warnings=warnings,
            trace_id=trace_id,
            plan_summary=plan.summary,
            attempts=attempts,
        )

    @staticmethod
    def _compression_detail(encoded: EncodedImage, requirements: PhotoRequirements) -> str:
        if encoded.quality is not None:
            quality_detail = f"，质量参数 {encoded.quality}"
        elif encoded.palette_colors is not None:
            quality_detail = f"，调色板 {encoded.palette_colors} 色"
        else:
            quality_detail = "，无损优化"
        return f"转换为 {requirements.output_format.value}{quality_detail}"
