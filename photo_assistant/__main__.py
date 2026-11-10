from __future__ import annotations

import argparse
from pathlib import Path

from .agent import ApplicationPhotoAgent
from .models import FitMode, ImageFormat, PhotoRequirements
from .reporting import result_manifest_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="网申照片智能适配助手")
    parser.add_argument("input", type=Path, help="输入 JPG/PNG 文件")
    parser.add_argument("--output", type=Path, help="输出文件路径")
    parser.add_argument("--width", type=int, default=295)
    parser.add_argument("--height", type=int, default=413)
    parser.add_argument("--format", choices=["JPG", "JPEG", "PNG", "WEBP"], default="JPG")
    parser.add_argument("--max-kb", type=int, default=100)
    parser.add_argument("--mode", choices=["crop", "pad"], default="crop")
    parser.add_argument("--background", default="#FFFFFF")
    parser.add_argument("--min-quality", type=int, default=20)
    parser.add_argument("--no-upscale", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    requirements = PhotoRequirements(
        width=args.width,
        height=args.height,
        output_format=ImageFormat.normalize(args.format),
        max_size_kb=args.max_kb,
        fit_mode=FitMode(args.mode),
        background_color=args.background,
        min_quality=args.min_quality,
        allow_upscale=not args.no_upscale,
    )
    source = args.input.read_bytes()
    result = ApplicationPhotoAgent().run(source, requirements, original_name=args.input.name)
    output = args.output or args.input.with_name(result.filename)
    output.write_bytes(result.output_bytes)
    output.with_suffix(output.suffix + ".json").write_bytes(
        result_manifest_json(result, source_name=args.input.name)
    )
    print(f"PASS {output} ({result.validation.metadata.size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
