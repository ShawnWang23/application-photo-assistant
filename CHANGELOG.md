# Changelog

## 4.0.0 - 2026-11-06

### Added

- Planner、Executor、Validator、Feedback 与有限重试闭环。
- 统一 `ToolResult`、工具参数摘要、错误码、Trace ID 和处理计划报告。
- `services/` 业务服务层和 `interfaces/` 界面层；根 `app.py` 只保留稳定入口。
- Inno Setup 安装器，支持开始菜单、可选桌面快捷方式和卸载。
- Windows GitHub Actions 自动构建、打包自检、安装器、SHA256 和 Tag Release。
- MIT License、公开项目链接和面向最终用户的 4.0.0 Release Notes。
- 桌面端/Web 端独立隐私说明和 Web 自定义模型地址防护。
- EXE 版本资源、轮转诊断日志和 4.0 工程化专项测试。

### Changed

- 批量未知异常不再直接显示 Python 异常正文或本地路径。
- 报告版本改用语义化版本，并加入计划、尝试次数与 Trace ID。
- 原 `batch.py` 变为兼容导入；最新业务实现位于 `services/batch_service.py`。

### Preserved

- 原有图片校验、EXIF 修正、裁剪/留白、格式转换、大小搜索和输出验收逻辑。
- 原有多模型要求解析、本地 OCR、批量 ZIP、CLI 和 Docker 能力。
