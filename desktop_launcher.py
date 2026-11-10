from __future__ import annotations

import ctypes
import multiprocessing as mp
import os
import socket
import sys
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path

from photo_assistant.version import __version__

APP_TITLE = f"Application Photo Assistant {__version__} · 网申照片助手"
PORT_FILE = Path(tempfile.gettempdir()) / "application-photo-assistant.port"
SERVER_LOG = Path(tempfile.gettempdir()) / "application-photo-assistant-server.log"
SMOKE_LOG = Path(tempfile.gettempdir()) / "application-photo-assistant-smoke.log"
OCR_TEST_LOG = Path(tempfile.gettempdir()) / "application-photo-assistant-ocr-test.log"


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def run_streamlit_server(port: int, app_path: str) -> None:
    try:
        os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
        os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
        os.environ["STREAMLIT_SERVER_ADDRESS"] = "127.0.0.1"
        from streamlit.web import bootstrap

        flag_options = {
            "global_developmentMode": False,
            "server_address": "127.0.0.1",
            "server_port": port,
            "server_headless": True,
            "server_maxUploadSize": 25,
            "browser_gatherUsageStats": False,
            "server_fileWatcherType": "none",
        }
        # The public CLI loads flag options before calling bootstrap.run. When
        # embedding Streamlit, perform the same initialization explicitly.
        bootstrap.load_config_options(flag_options)
        bootstrap.run(app_path, False, [], flag_options)
    except Exception:
        SERVER_LOG.write_text(traceback.format_exc(), encoding="utf-8")
        raise


def wait_until_ready(port: int, process: mp.Process, timeout: float = 35.0) -> None:
    health_url = f"http://127.0.0.1:{port}/_stcore/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not process.is_alive():
            raise RuntimeError("本地应用服务启动失败。")
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as response:
                if response.status == 200 and response.read().strip() == b"ok":
                    return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError("应用启动超时，请重新打开。")


def show_native_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)


def self_test() -> int:
    app_path = resource_path("app.py")
    if not app_path.is_file():
        return 2
    try:
        import onnxruntime  # noqa: F401
        import rapidocr  # noqa: F401
        import streamlit  # noqa: F401
        import webview  # noqa: F401

        import photo_assistant  # noqa: F401
    except Exception:
        return 3
    return 0


def smoke_test() -> int:
    app_path = resource_path("app.py")
    if not app_path.is_file():
        return 2
    port = find_free_port()
    server = mp.Process(
        target=run_streamlit_server,
        args=(port, str(app_path)),
        name="ApplicationPhotoAssistantSmokeTest",
        daemon=True,
    )
    try:
        SERVER_LOG.unlink(missing_ok=True)
        SMOKE_LOG.unlink(missing_ok=True)
        server.start()
        wait_until_ready(port, server)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=5.0) as response:
            return 0 if response.status == 200 else 4
    except Exception:
        details = traceback.format_exc()
        if SERVER_LOG.exists():
            details += "\n--- child process ---\n" + SERVER_LOG.read_text(encoding="utf-8")
        SMOKE_LOG.write_text(details, encoding="utf-8")
        return 5
    finally:
        if server.is_alive():
            server.terminate()
            server.join(timeout=5)


def ocr_self_test() -> int:
    """Load packaged OCR models and recognize a synthetic requirement screenshot."""
    try:
        from io import BytesIO

        from PIL import Image, ImageDraw, ImageFont

        from photo_assistant.ocr import recognize_requirement_screenshot

        image = Image.new("RGB", (1000, 260), "white")
        draw = ImageDraw.Draw(image)
        font_path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf"
        font = ImageFont.truetype(str(font_path), 42)
        draw.text((30, 35), "JPG  295 x 413 px", font=font, fill="black")
        draw.text((30, 120), "MAX FILE SIZE 100 KB", font=font, fill="black")
        buffer = BytesIO()
        image.save(buffer, "PNG")
        result = recognize_requirement_screenshot(buffer.getvalue())
        normalized = result.text.upper().replace(" ", "")
        return 0 if all(token in normalized for token in ("JPG", "295", "413", "100", "KB")) else 6
    except Exception:
        OCR_TEST_LOG.write_text(traceback.format_exc(), encoding="utf-8")
        return 7


def main() -> int:
    mp.freeze_support()
    if "--self-test" in sys.argv:
        return self_test()
    if "--smoke-test" in sys.argv:
        return smoke_test()
    if "--ocr-self-test" in sys.argv:
        return ocr_self_test()

    app_path = resource_path("app.py")
    if not app_path.is_file():
        show_native_error("应用资源不完整，请重新下载安装包。")
        return 2

    port = find_free_port()
    server = mp.Process(
        target=run_streamlit_server,
        args=(port, str(app_path)),
        name="ApplicationPhotoAssistantServer",
        daemon=True,
    )
    try:
        server.start()
        wait_until_ready(port, server)
        PORT_FILE.write_text(f"{port}\n{os.getpid()}\n", encoding="utf-8")

        import webview

        local_data = Path(os.getenv("LOCALAPPDATA", tempfile.gettempdir()))
        storage_path = local_data / "ApplicationPhotoAssistant" / "WebView"
        storage_path.mkdir(parents=True, exist_ok=True)
        webview.create_window(
            APP_TITLE,
            f"http://127.0.0.1:{port}",
            width=1320,
            height=880,
            min_size=(980, 680),
            confirm_close=False,
            text_select=True,
        )
        webview.start(debug=False, private_mode=False, storage_path=str(storage_path))
        return 0
    except Exception as exc:
        show_native_error(f"应用无法启动：\n{exc}")
        return 1
    finally:
        if server.is_alive():
            server.terminate()
            server.join(timeout=5)
        try:
            PORT_FILE.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
