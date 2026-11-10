# Archived implementation notes

运行树中不保留 v3 的重复代码副本，以免用户误认旧 Agent 为最新实现。

- v3 的完整历史由 Git 提交记录保存。
- 原 29 KB `app.py` 已迁移到 `photo_assistant/interfaces/streamlit_app.py`；根入口只负责启动。
- 原 `photo_assistant/batch.py` 仅保留兼容导入；当前实现位于 `photo_assistant/services/batch_service.py`。
- 最新 Agent 固定是 `photo_assistant/agent.py`，版本来源固定是 `photo_assistant/version.py`。

如果未来需要保留无法兼容的旧实验，应放在此目录下并明确标注版本、停止维护日期和不可用于生产；不要让归档代码进入 PyInstaller 或 Python 包发现范围。
