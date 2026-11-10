from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.mark.parametrize("provider_id", ["openai", "deepseek", "kimi", "doubao", "siliconflow", "custom"])
def test_app_renders_for_every_provider(provider_id: str) -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=20)
    app.session_state["ai_provider_id"] = provider_id
    app.run()

    assert not app.exception
    provider_widget = next(item for item in app.selectbox if item.key == "ai_provider_id")
    assert provider_widget.value == provider_id
