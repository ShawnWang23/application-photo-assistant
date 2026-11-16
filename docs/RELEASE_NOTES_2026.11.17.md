# Application Photo Assistant · 2026.11.17

面向普通 Windows 用户的公开发行版。版本号采用发布日期，方便用户判断安装包的新旧。

## 亮点

- 提供 Windows x64 安装器和免安装便携版，不要求安装 Python。
- Agent 采用 Planner → Executor → Validator → Feedback 的受控闭环。
- 支持精确尺寸、格式和文件大小验收，全部通过后才允许下载。
- 支持单张处理、批量 ZIP、本地 OCR、多模型文字要求解析和 JSON 验收报告。
- 每次执行包含 Trace ID、工具耗时和失败恢复记录。
- 桌面版照片仅在本机处理；图片不会发送给模型厂商。

## 下载建议

普通用户请选择：

```text
ApplicationPhotoAssistant-Setup-2026.11.17-windows-x64.exe
```

便携使用请选择：

```text
ApplicationPhotoAssistant.exe
```

下载后可使用同一 Release 中的 `SHA256SUMS.txt` 校验文件完整性。

## 系统要求

- Windows 10/11 x64。
- Microsoft Edge WebView2 Runtime。大多数受支持的 Windows 系统已预装。
- AI 文字解析为可选功能；图片处理和本地 OCR 不需要 API Key。

## 隐私说明

- 桌面版在本机内存中处理照片，默认不保存原图或结果图。
- 只有在用户主动启用在线 AI 文字解析时，提取或输入的文字才会发给所选模型服务；照片不会发送。
- 项目提交和正式构建使用 GitHub `noreply` 身份，不在发行文件中公开维护者个人邮箱。

## 已知边界

- 暂不提供自动人脸构图、自动换背景和美颜。
- 暂不提供内置自动更新；新版本通过 GitHub Releases 发布。
- 极端尺寸与文件大小组合可能无法在最低画质约束内完成，应用会明确拒绝不合规输出。
