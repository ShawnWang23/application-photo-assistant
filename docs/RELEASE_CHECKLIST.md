# Release Checklist

## 一次性准备

- [ ] 检查仓库历史中是否存在 API Key、真实照片、个人路径或敏感日志。
- [ ] 确认根目录包含 MIT `LICENSE`，GitHub 仓库为 Public。
- [ ] 在 GitHub 仓库设置中允许 Actions 创建 Release。
- [ ] 准备一台没有 Python 的 Windows 10/11 x64 测试机或虚拟机。

## 每次发布

- [ ] 更新 `photo_assistant/version.py`、`pyproject.toml` 和 `CHANGELOG.md`。
- [ ] 本地执行 `pytest` 与 `ruff check .`。
- [ ] 本地执行 `./build_windows.ps1`，确认 EXE 自检和 Smoke Test 通过。
- [ ] 安装生成的 Setup，确认开始菜单、可选桌面快捷方式、启动和卸载。
- [ ] 创建与版本完全一致的 Tag，例如 `v4.0.0` 并推送。
- [ ] 等待 `build-and-release` 工作流完成。
- [ ] 从 GitHub Release 下载安装器，按 `SHA256SUMS.txt` 复核哈希。
- [ ] 在无 Python 测试机完成上传、处理、下载和卸载。
- [ ] 填写 Release Notes、Known Issues 和隐私说明链接。

## 发布边界

`workflow_dispatch` 只生成可下载的 Actions Artifact；只有推送 `v*` Tag 才会创建正式 GitHub Release。
