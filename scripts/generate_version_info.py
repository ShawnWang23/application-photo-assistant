from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from photo_assistant.version import __version__  # noqa: E402


def main() -> None:
    parts = [int(part) for part in __version__.split(".")]
    while len(parts) < 4:
        parts.append(0)
    numeric = tuple(parts[:4])
    target = PROJECT_ROOT / "build" / "windows_version_info.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeric}, prodvers={numeric}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('080404b0', [
    StringStruct('CompanyName', 'Application Photo Assistant'),
    StringStruct('FileDescription', '网申照片智能适配助手'),
    StringStruct('FileVersion', '{__version__}'),
    StringStruct('InternalName', 'ApplicationPhotoAssistant'),
    StringStruct('OriginalFilename', 'ApplicationPhotoAssistant.exe'),
    StringStruct('ProductName', 'Application Photo Assistant'),
    StringStruct('ProductVersion', '{__version__}')
  ])]), VarFileInfo([VarStruct('Translation', [2052, 1200])])]
)
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
