from __future__ import annotations

from dataclasses import dataclass

from .models import PhotoRequirements, ValidationReport


@dataclass(frozen=True, slots=True)
class PlanStep:
    tool: str
    purpose: str


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    steps: tuple[PlanStep, ...]
    max_attempts: int = 2

    @property
    def summary(self) -> str:
        return " → ".join(step.tool for step in self.steps)


@dataclass(frozen=True, slots=True)
class FeedbackDecision:
    retry: bool
    reason: str
    recovery_action: str | None = None


class Planner:
    """Build a bounded plan without inventing or weakening user constraints."""

    def create(self, requirements: PhotoRequirements) -> ExecutionPlan:
        compression_goal = f"在不低于质量 {requirements.min_quality} 的前提下满足大小限制"
        return ExecutionPlan(
            steps=(
                PlanStep("inspect_image", "验证真实图片、方向、大小与像素总量"),
                PlanStep("fit_image", "按用户选择的裁剪或留白方式生成精确尺寸"),
                PlanStep("compress_image", compression_goal),
                PlanStep("validate_output", "重新打开输出并独立核验尺寸、格式和字节数"),
            )
        )


class FeedbackController:
    """Decide whether a failed validation is safely retryable."""

    def evaluate(
        self,
        report: ValidationReport,
        *,
        attempt: int,
        max_attempts: int,
    ) -> FeedbackDecision:
        failed = [item.name for item in report.items if not item.passed]
        if not failed:
            return FeedbackDecision(False, "全部约束已通过")
        if attempt < max_attempts:
            return FeedbackDecision(
                True,
                f"第 {attempt} 次输出未通过：{'、'.join(failed)}",
                "重新编码并再次独立验收",
            )
        return FeedbackDecision(False, f"达到重试上限，仍未通过：{'、'.join(failed)}")
