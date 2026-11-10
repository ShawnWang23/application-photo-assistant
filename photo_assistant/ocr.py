from __future__ import annotations

import io
import threading
from dataclasses import dataclass
from typing import Any

from PIL import Image, UnidentifiedImageError

MAX_OCR_BYTES = 25 * 1024 * 1024
MAX_OCR_PIXELS = 40_000_000


class OCRError(RuntimeError):
    """Friendly OCR error safe to display in the UI."""


@dataclass(frozen=True, slots=True)
class OCRTextResult:
    text: str
    line_count: int
    average_confidence: float | None
    elapsed_seconds: float | None


_engine: Any = None
_engine_lock = threading.Lock()
_inference_lock = threading.Lock()


def _get_engine() -> Any:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                try:
                    from rapidocr import RapidOCR
                except ImportError as exc:
                    raise OCRError("当前版本未包含本地 OCR 组件，请重新安装或下载完整版。") from exc
                _engine = RapidOCR()
    return _engine


def result_to_text(result: Any) -> OCRTextResult:
    texts = tuple(str(item).strip() for item in (getattr(result, "txts", None) or ()) if str(item).strip())
    scores = tuple(float(item) for item in (getattr(result, "scores", None) or ()))
    confidence = sum(scores) / len(scores) if scores else None
    elapsed = getattr(result, "elapse", None)
    return OCRTextResult(
        text="\n".join(texts),
        line_count=len(texts),
        average_confidence=confidence,
        elapsed_seconds=float(elapsed) if elapsed is not None else None,
    )


def recognize_requirement_screenshot(data: bytes) -> OCRTextResult:
    if not data:
        raise OCRError("截图内容为空。")
    if len(data) > MAX_OCR_BYTES:
        raise OCRError("要求截图不能超过 25 MB。")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > MAX_OCR_PIXELS:
                raise OCRError("截图像素过大，请裁剪到包含要求文字的区域后重试。")
            image.verify()
    except OCRError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise OCRError("无法识别该截图，请上传有效的 JPG 或 PNG 图片。") from exc

    try:
        with _inference_lock:
            output = _get_engine()(data, use_det=True, use_cls=True, use_rec=True)
    except Exception as exc:
        raise OCRError(f"本地文字识别失败：{type(exc).__name__}") from exc
    parsed = result_to_text(output)
    if not parsed.text:
        raise OCRError("截图中没有识别到文字，请裁剪并放大要求区域后重试。")
    return parsed
