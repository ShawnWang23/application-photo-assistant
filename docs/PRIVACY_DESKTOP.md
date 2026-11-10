# Desktop Privacy Policy

适用于本地安装版和便携版 4.0。

- 证件照由本机 Pillow 进程处理，不上传给模型厂商。
- 要求截图由本机 RapidOCR 处理。
- 只有用户确认并主动点击 AI 解析后的“要求文字”会发送给所选模型服务。
- API Key 默认只保存在当前 Streamlit 会话内存，不持久化。
- 应用不默认保存原始照片或输出照片；下载位置由用户选择。
- 会话历史在应用关闭后消失，不包含持久化图片数据库。
- 本地诊断日志位于 `%LOCALAPPDATA%\ApplicationPhotoAssistant\logs`，只记录时间、错误码、Trace ID 和步骤，不记录图片字节或 API Key。
- WebView 缓存位于 `%LOCALAPPDATA%\ApplicationPhotoAssistant\WebView`，卸载器会删除该目录。

用户可通过应用内“清空历史”删除当前会话记录，也可卸载软件并删除上述日志目录。
