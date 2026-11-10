# Architecture 4.0

```text
app.py / desktop_launcher.py / CLI
                 │
                 ▼
interfaces/streamlit_app.py
                 │
                 ▼
services/processing_service.py ── services/batch_service.py
                 │
                 ▼
Planner → ToolRegistry/Executor → Validator → Feedback Controller
                 │                         │
                 └──────── retry ≤ 2 ─────┘
                 │
                 ▼
确定性 Pillow 工具：inspect / fit / compress / validate
```

设计原则：

- LLM 只负责把自然语言转成受约束的结构化需求，不接触照片、不执行 Python。
- Planner 不擅自修改用户约束；尤其不会为了成功而突破最低画质或文件要求。
- 每个工具返回统一 `ToolResult`，包含成功状态、错误码、耗时、元数据、Trace ID 和尝试次数。
- 工具参数只记录摘要，图片只记录字节数或尺寸，不写入 Trace。
- Validator 独立重新打开输出；只有全部约束通过才返回下载结果。
- 业务服务不依赖 Streamlit，因此 CLI 或未来原生界面可以复用。

## 尚未完成

- 人脸/人体定位和自动构图。
- 持久化 SQLite 历史与自定义预设。
- PDF、多截图 OCR 与 OCR 冲突检查。
- 自动更新客户端和已上线的 Web 服务。

这些能力不应在 README 中写成已经交付。
