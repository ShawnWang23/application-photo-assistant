# Application Photo Assistant 4.0

[![Tests](https://github.com/ShawnWang23/application-photo-assistant/actions/workflows/tests.yml/badge.svg)](https://github.com/ShawnWang23/application-photo-assistant/actions/workflows/tests.yml)
[![Release](https://github.com/ShawnWang23/application-photo-assistant/actions/workflows/release.yml/badge.svg)](https://github.com/ShawnWang23/application-photo-assistant/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-6c63ff.svg)](LICENSE)

网申照片智能适配助手：让大模型理解要求，由受控图片工具执行，再由独立验证器验收。照片不会交给 LLM 修改。

## 当前交付形态

- Windows 安装版：Inno Setup 安装器，含开始菜单、可选桌面快捷方式和卸载。
- Windows 便携版：单文件 `ApplicationPhotoAssistant.exe`，不要求用户安装 Python。
- 开发者源码版：Streamlit、CLI 和 Docker。
- GitHub Release：推送 `v*` Tag 后自动测试、构建、生成 SHA256 并发布。

仓库源码不跟踪 `dist/` 构建产物。正式用户应从 [GitHub Releases](https://github.com/ShawnWang23/application-photo-assistant/releases) 下载安装器，而不是克隆源码。

## 核心能力

- JPG/JPEG/PNG 输入，JPG/PNG/WEBP 输出。
- EXIF 方向修正、透明通道处理、非法文件和解压炸弹防护。
- 保持比例裁剪或留白，可调焦点和背景色。
- JPEG/WEBP 最高可用质量搜索与 PNG 调色板压缩。
- 输出重新打开，逐项验证尺寸、格式和真实字节数。
- 单张报告和批量 ZIP；单个失败不终止整个批次。
- 本地 RapidOCR 读取要求截图。
- OpenAI、DeepSeek、Kimi、豆包、SiliconFlow 与自定义兼容接口。
- 统一工具结果、错误码、Trace ID、执行耗时和失败恢复轨迹。

## Agent 4.0

```text
自然语言/截图要求
        │
        ├─ 本地规则 / 本地 OCR
        └─ LLM 结构化解析（可选，只发送文字）
                        │
                        ▼
Planner → Executor → Validator → Feedback
            ▲               │
            └── 有限重试 ───┘
                        │
                        ▼
               全部通过后允许下载
```

Agent 不会为了“成功”擅自突破最低画质、尺寸、格式或大小限制。工具仍是确定性的 Pillow 函数；LLM 不生成或执行图片处理代码。详见 [架构文档](docs/ARCHITECTURE.md)。

## 普通用户安装

从 GitHub Release 下载：

```text
ApplicationPhotoAssistant-Setup-4.0.0-windows-x64.exe
SHA256SUMS.txt
```

对照 SHA256 后双击安装。Windows 10/11 通常已包含 Edge WebView2 Runtime；若没有，需要先安装微软官方 WebView2 Runtime。

安装后可从开始菜单启动，也可在安装时选择桌面快捷方式。卸载入口位于 Windows“已安装的应用”。

## 开发运行

要求 Python 3.11+，推荐 3.12。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
streamlit run app.py
```

CLI：

```powershell
python -m photo_assistant input.jpg --width 295 --height 413 --format JPG --max-kb 100
```

Docker：

```powershell
docker build -t application-photo-assistant .
docker run --rm -p 8501:8501 -e PHOTO_ASSISTANT_DEPLOYMENT=web application-photo-assistant
```

Web 部署必须设置 `PHOTO_ASSISTANT_DEPLOYMENT=web`。这会禁用自定义 Base URL 并只允许内置厂商的官方 HTTPS 地址。Web 版会把照片上传到服务器，不能宣传为“照片不离开用户电脑”。上线前必须完成 [Web 隐私模板](docs/PRIVACY_WEB.md)。

## Windows 构建

本机需安装 Python 3.12 和 Inno Setup 6 或 7：

```powershell
.\build_windows.ps1
```

脚本会依次执行测试、Ruff、PyInstaller、打包后自检、HTTP Smoke Test、Inno Setup 和 SHA256。输出：

```text
dist/ApplicationPhotoAssistant.exe
dist/installer/ApplicationPhotoAssistant-Setup-4.0.0-windows-x64.exe
dist/SHA256SUMS.txt
```

只构建便携版可使用 `./build_windows.ps1 -SkipInstaller`。正式发布不应跳过安装器和测试。

## 自动发布

1. 同步修改 `photo_assistant/version.py`、`pyproject.toml` 和 `CHANGELOG.md`。
2. 推送与版本一致的 Tag，例如 `v4.0.0`。
3. `.github/workflows/release.yml` 在 Windows Runner 上完成测试、构建、自检、安装器和 SHA256。
4. 工作流创建 GitHub Release 并上传安装器、便携版和校验文件。

完整人工验收见 [发布清单](docs/RELEASE_CHECKLIST.md)。项目采用 [MIT License](LICENSE)，欢迎提交 Issue 和 Pull Request。

## 测试

```powershell
python -m pytest
python -m ruff check .
```

当前测试覆盖图片边界、解析/OCR、批量与报告、Streamlit 首屏、Agent 反馈重试、Trace、Web SSRF 防护、错误脱敏和发布文件一致性。

## 项目结构

```text
app.py                                  稳定 Streamlit 入口（5 行）
desktop_launcher.py                     桌面进程与 WebView 生命周期
photo_assistant/
  agent.py                              最新 Planner/Executor/Validator Agent
  planning.py                           计划与反馈控制
  models.py                             Pydantic 领域模型与 ToolResult
  image_tools.py                        确定性图片处理与验收
  errors.py / logging_config.py         错误码、脱敏与本地诊断日志
  security.py                           桌面/Web 模式的模型地址策略
  services/                             UI 无关的单张与批量业务
  interfaces/streamlit_app.py           Streamlit 界面
  provider.py / ocr.py / parser.py      模型、本地 OCR 与规则解析
installer/ApplicationPhotoAssistant.iss Windows 安装器
.github/workflows/release.yml           自动构建与 Release
tests/                                  单元、集成与界面 Smoke Tests
docs/archive/                           旧实现去向说明，不参与运行
```

## 隐私、安全与产品边界

- [桌面端隐私说明](docs/PRIVACY_DESKTOP.md)
- [Web 端隐私模板](docs/PRIVACY_WEB.md)
- [安全策略](SECURITY.md)
- [版本记录](CHANGELOG.md)
- [4.0.0 Release Notes](docs/RELEASE_NOTES_4.0.0.md)

软件不会做人脸识别、美颜、换脸或身份特征修改。预设只是常见参考；提交前仍需以目标机构的最新要求为准。当前尚未交付自动人像构图、SQLite 持久历史、PDF OCR、自动更新和正式在线服务，路线图不会伪装成已完成功能。
