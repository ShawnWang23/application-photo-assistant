from __future__ import annotations

from PIL import Image

from ..agent import ApplicationPhotoAgent
from ..image_tools import load_image, make_preview
from ..models import AgentResult, FitMode, ImageMetadata, PhotoRequirements


class ProcessingService:
    """UI-independent use cases for inspecting, previewing, and processing one photo."""

    def __init__(self, agent: ApplicationPhotoAgent | None = None) -> None:
        self.agent = agent or ApplicationPhotoAgent()

    def inspect(self, source: bytes) -> tuple[Image.Image, ImageMetadata]:
        return load_image(source)

    def preview(self, source: bytes, requirements: PhotoRequirements, mode: FitMode) -> Image.Image:
        return make_preview(source, requirements, mode)

    def process(
        self,
        source: bytes,
        requirements: PhotoRequirements,
        *,
        original_name: str,
    ) -> AgentResult:
        return self.agent.run(source, requirements, original_name=original_name)
