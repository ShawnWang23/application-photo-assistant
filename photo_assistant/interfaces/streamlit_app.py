from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any

import streamlit as st

from photo_assistant.errors import AppError, public_error_message
from photo_assistant.image_tools import ImageProcessingError
from photo_assistant.models import AgentResult, FitMode, ImageFormat, PhotoRequirements
from photo_assistant.ocr import OCRError, recognize_requirement_screenshot
from photo_assistant.parser import parse_requirements_rules
from photo_assistant.presets import PRESETS
from photo_assistant.provider import (
    PROVIDER_PROFILES,
    OpenAICompatibleProvider,
    ProviderProfile,
)
from photo_assistant.reporting import result_manifest_json
from photo_assistant.security import deployment_mode
from photo_assistant.services import BatchOutcome, ProcessingService, build_batch_zip, process_batch
from photo_assistant.version import __version__

MAX_BATCH_FILES = 20
MAX_BATCH_TOTAL_BYTES = 100 * 1024 * 1024
PROCESSING = ProcessingService()
IS_WEB = deployment_mode() == "web"
OCR_LOCATION = "服务器" if IS_WEB else "本机"


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    profile: ProviderProfile
    api_key: str
    model: str
    base_url: str

    @property
    def ready(self) -> bool:
        return bool(self.api_key.strip() and self.model.strip() and self.base_url.strip())

    def client(self) -> OpenAICompatibleProvider:
        return OpenAICompatibleProvider(
            self.api_key,
            provider_id=self.profile.id,
            model=self.model,
            base_url=self.base_url,
        )


st.set_page_config(
    page_title="Application Photo Assistant", page_icon="🪪", layout="wide", initial_sidebar_state="expanded"
)
st.markdown(
    """
<style>
  :root {
    --ink:#172033; --muted:#657089; --line:#e4e8f2; --surface:#ffffff;
    --primary:#6257e8; --primary-dark:#4438c8; --cyan:#2ab7ca;
    --success:#16805a; --success-bg:#edf9f4; --warning:#946016; --warning-bg:#fff8e8;
  }
  .stApp {background:
    radial-gradient(circle at 8% 5%,rgba(98,87,232,.07),transparent 24rem),
    radial-gradient(circle at 96% 25%,rgba(42,183,202,.06),transparent 22rem),#f7f8fc}
  .block-container {max-width:1220px; padding-top:1.35rem; padding-bottom:4rem}
  [data-testid="stSidebar"] {border-right:1px solid #e2e6f0; background:rgba(255,255,255,.9)}
  [data-testid="stSidebar"] > div:first-child {padding-top:1.25rem}
  header[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {display:none !important}
  h1,h2,h3 {color:var(--ink); letter-spacing:-.025em}
  .sidebar-brand {padding:1rem 1.05rem; margin:0 0 1rem; border:1px solid #e4e5f5; border-radius:18px;
    background:linear-gradient(145deg,#fafaff,#f0efff); box-shadow:0 8px 24px rgba(55,48,140,.07)}
  .sidebar-brand-row {display:flex;align-items:center;gap:.7rem}
  .sidebar-logo {display:grid;place-items:center;width:2.35rem;height:2.35rem;border-radius:12px;color:white;font-size:1.15rem;
    background:linear-gradient(135deg,var(--primary),var(--cyan));box-shadow:0 6px 14px rgba(98,87,232,.25)}
  .sidebar-brand strong {display:block;color:var(--ink);font-size:.93rem}.sidebar-brand small{color:var(--muted)}
  .hero {position:relative;overflow:hidden;padding:2.25rem 2.35rem;border-radius:28px;color:white;margin-bottom:1.2rem;
    background:radial-gradient(circle at 88% 2%,rgba(68,219,228,.55) 0,transparent 28%),
      radial-gradient(circle at 70% 110%,rgba(126,107,255,.72) 0,transparent 35%),
      linear-gradient(132deg,#151b3d 0%,#2d327c 50%,#3f45a4 100%);
    box-shadow:0 22px 55px rgba(35,40,105,.22)}
  .hero:after {content:"";position:absolute;right:-4rem;top:-5rem;width:18rem;height:18rem;border:1px solid rgba(255,255,255,.18);border-radius:50%}
  .hero-badge {display:inline-flex;align-items:center;gap:.4rem;padding:.32rem .65rem;border:1px solid rgba(255,255,255,.22);
    border-radius:99px;background:rgba(255,255,255,.1);font-size:.72rem;letter-spacing:.09em;color:#e3e7ff;font-weight:750}
  .hero h1 {color:white;font-size:2.45rem;margin:.65rem 0 .38rem;letter-spacing:-.045em;line-height:1.1}
  .hero p {color:#dce3ff;margin:0;max-width:720px;font-size:1.02rem;line-height:1.75}
  .hero-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.65rem;margin-top:1.35rem;max-width:760px}
  .hero-card {padding:.72rem .82rem;border:1px solid rgba(255,255,255,.13);background:rgba(255,255,255,.08);border-radius:14px;backdrop-filter:blur(5px)}
  .hero-card b {display:block;font-size:.84rem;color:white}.hero-card span{font-size:.72rem;color:#bdc8f4}
  .section-heading {display:flex;gap:.82rem;align-items:flex-start;margin:.35rem 0 .9rem}
  .section-number {flex:0 0 auto;display:grid;place-items:center;width:2.05rem;height:2.05rem;border-radius:10px;
    background:linear-gradient(135deg,#ebe9ff,#e5f7fa);color:var(--primary-dark);font-size:.72rem;font-weight:850}
  .section-heading h3 {margin:0;font-size:1.12rem}.section-heading p{margin:.12rem 0 0;color:var(--muted);font-size:.82rem;line-height:1.5}
  .section-note {padding:.82rem 1rem;border:1px solid #e1e6f2;border-radius:14px;background:rgba(255,255,255,.78);color:#56617a}
  .pass-box {padding:1rem 1.1rem;border:1px solid #b6e3d2;background:var(--success-bg);color:var(--success);border-radius:16px;font-weight:750}
  .warn-box {padding:.82rem 1rem;margin-top:.5rem;border:1px solid #f0d89e;background:var(--warning-bg);color:var(--warning);border-radius:14px}
  .validation-row {display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.68rem .8rem;margin:.38rem 0;
    border:1px solid var(--line);border-radius:12px;background:#fbfcff;font-size:.84rem}
  .validation-row b {color:var(--ink)}.validation-row span{color:var(--muted);text-align:right}
  .trace {position:relative;padding:.72rem .85rem .72rem 1rem;margin:.5rem 0;border:1px solid #e4e7f2;background:#fbfbfe;border-radius:13px;color:#58627a;font-size:.84rem}
  .trace:before {content:"";position:absolute;left:-1px;top:.65rem;bottom:.65rem;width:3px;border-radius:4px;background:linear-gradient(var(--primary),var(--cyan))}
  .trace b{color:var(--ink)}.trace-meta{float:right;color:#8992a7;font-size:.72rem}
  div[data-testid="stMetric"] {border:1px solid var(--line);padding:.82rem 1rem;border-radius:16px;background:rgba(255,255,255,.9);box-shadow:0 6px 18px rgba(44,50,95,.045)}
  [data-testid="stFileUploader"] {border:1px dashed #9eaae0;border-radius:18px;padding:.4rem;background:linear-gradient(145deg,#fbfbff,#f5f7ff)}
  [data-testid="stStatusWidget"] {border-color:#dedff1!important;border-radius:15px!important}
  .stTabs [data-baseweb="tab-list"] {gap:.35rem;padding:.3rem;background:#eceef5;border-radius:14px}
  .stTabs [data-baseweb="tab"] {height:2.7rem;border-radius:10px;padding:.55rem 1rem;color:#59637a}
  .stTabs [aria-selected="true"] {background:white!important;color:var(--primary-dark)!important;box-shadow:0 3px 10px rgba(35,40,105,.08)}
  .stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"] {border:0;background:linear-gradient(135deg,var(--primary),var(--primary-dark));box-shadow:0 8px 18px rgba(98,87,232,.2)}
  .stButton>button,.stDownloadButton>button {border-radius:11px;font-weight:700}
  hr {border-color:#e5e8f1!important}
  @media (max-width:700px) {.hero{padding:1.5rem}.hero h1{font-size:1.85rem}.hero-grid{grid-template-columns:1fr}.block-container{padding:.8rem 1rem 3rem}}
</style>
""",
    unsafe_allow_html=True,
)


def render_section(number: str, title: str, description: str) -> None:
    st.markdown(
        f"""
<div class="section-heading">
  <span class="section-number">{number}</span>
  <div><h3>{title}</h3><p>{description}</p></div>
</div>
""",
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = PhotoRequirements()
    for prefix in ("single", "batch"):
        initial: dict[str, Any] = {
            f"{prefix}_width": defaults.width,
            f"{prefix}_height": defaults.height,
            f"{prefix}_format": "JPG",
            f"{prefix}_max_kb": defaults.max_size_kb,
            f"{prefix}_fit": defaults.fit_mode.value,
            f"{prefix}_background": defaults.background_color,
            f"{prefix}_focal_x": defaults.focal_x,
            f"{prefix}_focal_y": defaults.focal_y,
            f"{prefix}_min_quality": defaults.min_quality,
            f"{prefix}_allow_upscale": defaults.allow_upscale,
        }
        for key, value in initial.items():
            st.session_state.setdefault(key, value)
    st.session_state.setdefault("history", [])


def set_requirement_widgets(prefix: str, requirements: PhotoRequirements) -> None:
    st.session_state[f"{prefix}_width"] = requirements.width
    st.session_state[f"{prefix}_height"] = requirements.height
    st.session_state[f"{prefix}_format"] = (
        "JPG" if requirements.output_format == ImageFormat.JPEG else requirements.output_format.value
    )
    st.session_state[f"{prefix}_max_kb"] = requirements.max_size_kb
    st.session_state[f"{prefix}_fit"] = requirements.fit_mode.value
    st.session_state[f"{prefix}_background"] = requirements.background_color
    st.session_state[f"{prefix}_focal_x"] = requirements.focal_x
    st.session_state[f"{prefix}_focal_y"] = requirements.focal_y
    st.session_state[f"{prefix}_min_quality"] = requirements.min_quality
    st.session_state[f"{prefix}_allow_upscale"] = requirements.allow_upscale


def current_requirements(prefix: str) -> PhotoRequirements:
    return PhotoRequirements(
        width=int(st.session_state[f"{prefix}_width"]),
        height=int(st.session_state[f"{prefix}_height"]),
        output_format=ImageFormat.normalize(st.session_state[f"{prefix}_format"]),
        max_size_kb=int(st.session_state[f"{prefix}_max_kb"]),
        fit_mode=FitMode(st.session_state[f"{prefix}_fit"]),
        background_color=st.session_state[f"{prefix}_background"],
        focal_x=float(st.session_state[f"{prefix}_focal_x"]),
        focal_y=float(st.session_state[f"{prefix}_focal_y"]),
        min_quality=int(st.session_state[f"{prefix}_min_quality"]),
        allow_upscale=bool(st.session_state[f"{prefix}_allow_upscale"]),
    )


def render_provider_sidebar() -> ProviderConfig:
    with st.sidebar:
        st.markdown(
            f"""
<div class="sidebar-brand">
  <div class="sidebar-brand-row">
    <span class="sidebar-logo">◈</span>
    <div><strong>Photo Assistant</strong><small>Agent Edition · {__version__}</small></div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown("### AI 服务（可选）")
        st.caption("AI 只理解要求文字；证件照和要求截图都不会上传给模型厂商。")
        provider_ids = [item for item in PROVIDER_PROFILES if not (IS_WEB and item == "custom")]
        st.session_state.setdefault("ai_provider_id", "siliconflow")
        provider_id = st.selectbox(
            "模型厂商",
            provider_ids,
            format_func=lambda item: PROVIDER_PROFILES[item].label,
            key="ai_provider_id",
        )
        profile = PROVIDER_PROFILES[provider_id]
        saved_key_state = f"provider_saved_key_{provider_id}"
        api_key = st.text_input(
            profile.key_label,
            type="password",
            value=st.session_state.get(saved_key_state, os.getenv(profile.key_env, "")),
            placeholder="仅保存在当前运行会话",
            key=f"provider_key_{provider_id}",
        )
        st.session_state[saved_key_state] = api_key
        model_state_key = f"provider_model_value_{provider_id}"
        default_model = os.getenv(f"{provider_id.upper()}_MODEL", profile.default_model)
        available_models: list[str] = st.session_state.get(f"provider_models_{provider_id}", [])
        preferred = st.session_state.get(model_state_key, default_model)
        if available_models:
            options = list(available_models)
            if preferred and preferred not in options:
                options.insert(0, preferred)
            index = options.index(preferred) if preferred in options else 0
            model = st.selectbox(
                "模型 ID / 推理接入点",
                options,
                index=index,
                key=f"provider_model_select_{provider_id}",
            )
        else:
            model = st.text_input(
                "模型 ID / 推理接入点",
                value=preferred,
                placeholder="例如模型 ID 或 ep-……",
                key=f"provider_model_text_{provider_id}",
            )
        st.session_state[model_state_key] = model
        if profile.model_help:
            st.caption(profile.model_help)

        with st.expander("高级连接设置"):
            base_url = st.text_input(
                "API Base URL",
                value=st.session_state.get(f"provider_base_value_{provider_id}", profile.base_url),
                placeholder="https://…/v1",
                key=f"provider_base_{provider_id}",
            )
            st.session_state[f"provider_base_value_{provider_id}"] = base_url
            st.caption("只有使用代理、海外站或自定义兼容服务时才需要修改。")

        config = ProviderConfig(profile=profile, api_key=api_key, model=model, base_url=base_url)
        if st.button(
            "测试连接并同步模型",
            use_container_width=True,
            disabled=not api_key or not base_url,
            key=f"provider_sync_{provider_id}",
        ):
            try:
                with st.spinner(f"正在连接 {profile.label}…"):
                    models = config.client().list_models()
                st.session_state[f"provider_models_{provider_id}"] = models
                st.session_state[f"provider_notice_{provider_id}"] = (
                    "success",
                    f"连接成功，账户返回 {len(models)} 个模型。",
                )
                st.rerun()
            except AppError as exc:
                st.session_state[f"provider_notice_{provider_id}"] = (
                    "error",
                    public_error_message(exc),
                )
        notice = st.session_state.get(f"provider_notice_{provider_id}")
        if notice:
            getattr(st, notice[0])(notice[1])
        if not config.ready:
            st.info("未完成 AI 配置也不影响图片处理、本地 OCR 和本地规则解析。")
        st.divider()
        st.markdown("### 隐私与安全")
        privacy_caption = (
            "Web 版：照片和截图会上传到本服务处理，但不会发送给模型厂商。"
            if IS_WEB
            else "桌面版：照片只在本机内存处理；截图由本地 OCR 读取。"
        )
        st.caption(f"{privacy_caption} API Key 不写入磁盘。")
        st.caption(f"Application Photo Assistant · v{__version__}")
    return config


def render_requirements_editor(prefix: str, *, provider: ProviderConfig) -> PhotoRequirements:
    pending = st.session_state.pop(f"{prefix}_pending_requirements", None)
    if pending:
        set_requirement_widgets(prefix, PhotoRequirements.model_validate(pending))
    pending_ocr = st.session_state.pop(f"{prefix}_pending_ocr_text", None)
    if pending_ocr is not None:
        st.session_state[f"{prefix}_ocr_text"] = pending_ocr
    preset_col, apply_col = st.columns([3, 1])
    with preset_col:
        preset_name = st.selectbox(
            "快速预设",
            list(PRESETS),
            format_func=lambda name: f"{name} · {PRESETS[name].description}",
            key=f"{prefix}_preset",
        )
    with apply_col:
        st.write("")
        st.write("")
        if st.button("应用预设", key=f"{prefix}_apply_preset", use_container_width=True):
            set_requirement_widgets(prefix, PRESETS[preset_name].requirements)
            st.session_state[f"{prefix}_notice"] = f"已应用：{preset_name}"
            st.rerun()
    if st.session_state.get(f"{prefix}_notice"):
        st.success(st.session_state.pop(f"{prefix}_notice"))

    row1 = st.columns(4)
    row1[0].number_input("宽度（px）", 16, 10_000, key=f"{prefix}_width")
    row1[1].number_input("高度（px）", 16, 10_000, key=f"{prefix}_height")
    row1[2].selectbox("输出格式", ["JPG", "PNG", "WEBP"], key=f"{prefix}_format")
    row1[3].number_input("最大大小（KB）", 1, 50_000, key=f"{prefix}_max_kb")
    st.radio(
        "构图方式",
        [FitMode.CROP.value, FitMode.PAD.value],
        format_func=lambda value: (
            "保持比例并裁剪（铺满）" if value == "crop" else "保持比例并留白（完整保留）"
        ),
        horizontal=True,
        key=f"{prefix}_fit",
    )
    if st.session_state[f"{prefix}_fit"] == FitMode.CROP.value:
        focus_cols = st.columns(2)
        focus_cols[0].slider("水平焦点", 0.0, 1.0, step=0.05, key=f"{prefix}_focal_x")
        focus_cols[1].slider("垂直焦点", 0.0, 1.0, step=0.05, key=f"{prefix}_focal_y")
    else:
        st.color_picker("留白颜色", key=f"{prefix}_background")
    with st.expander("高级画质设置"):
        advanced = st.columns(2)
        advanced[0].slider(
            "最低压缩质量", 5, 95, key=f"{prefix}_min_quality", help="达不到该画质时拒绝输出。"
        )
        advanced[1].toggle(
            "允许放大小图", key=f"{prefix}_allow_upscale", help="放大不改变比例，但可能降低清晰度。"
        )

    requirements = current_requirements(prefix)

    def render_parse_actions(text: str, suffix: str) -> None:
        local_col, ai_col = st.columns(2)
        if local_col.button(
            "本地解析并填入",
            key=f"{prefix}_{suffix}_local_parse",
            disabled=not text.strip(),
            use_container_width=True,
        ):
            try:
                parsed = parse_requirements_rules(text, requirements)
                st.session_state[f"{prefix}_pending_requirements"] = parsed.model_dump(mode="json")
                st.session_state[f"{prefix}_notice"] = "已用本地规则解析并填入。"
                st.rerun()
            except ValueError as exc:
                st.error(f"要求中的参数无效：{exc}")
        if ai_col.button(
            f"用 {provider.profile.label} 智能解析",
            key=f"{prefix}_{suffix}_ai_parse",
            disabled=not text.strip() or not provider.ready,
            type="primary",
            use_container_width=True,
        ):
            try:
                with st.spinner("AI 正在识别尺寸、格式、大小与构图方式…"):
                    parsed = provider.client().extract_requirements(text, requirements)
                st.session_state[f"{prefix}_pending_requirements"] = parsed.model_dump(mode="json")
                st.session_state[f"{prefix}_notice"] = f"{provider.profile.label} 已完成结构化解析。"
                st.rerun()
            except AppError as exc:
                st.error(public_error_message(exc))
        if not provider.ready:
            st.caption("侧边栏完成厂商、Key 和模型配置后可启用 AI；本地解析始终可用。")

    with st.expander("从网申要求智能填写 · 支持文字和截图", expanded=False):
        text_tab, screenshot_tab = st.tabs(["粘贴文字", f"上传要求截图（{OCR_LOCATION} OCR）"])
        with text_tab:
            text = st.text_area(
                "要求原文",
                placeholder="例如：JPG，295×413 像素，不超过 100KB，不能裁剪人物",
                key=f"{prefix}_natural_text",
            )
            render_parse_actions(text, "text")
        with screenshot_tab:
            screenshot = st.file_uploader(
                "上传招聘页面或网申要求截图",
                type=["jpg", "jpeg", "png"],
                key=f"{prefix}_requirement_screenshot",
                help="建议先把截图裁到只保留要求文字，识别更快、更准确。",
            )
            if screenshot:
                screenshot_digest = hashlib.sha256(screenshot.getvalue()).hexdigest()
                previous_digest = st.session_state.get(f"{prefix}_ocr_screenshot_digest")
                if previous_digest != screenshot_digest:
                    st.session_state[f"{prefix}_ocr_screenshot_digest"] = screenshot_digest
                    st.session_state[f"{prefix}_ocr_text"] = ""
                    st.session_state.pop(f"{prefix}_ocr_meta", None)
                st.image(screenshot, caption="待识别的要求截图", use_container_width=True)
                if st.button(
                    f"在{OCR_LOCATION}识别截图文字",
                    key=f"{prefix}_run_ocr",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        with st.spinner("首次识别会加载本地中英文 OCR 模型，请稍候…"):
                            ocr_result = recognize_requirement_screenshot(screenshot.getvalue())
                        st.session_state[f"{prefix}_pending_ocr_text"] = ocr_result.text
                        confidence = (
                            f"，平均置信度 {ocr_result.average_confidence:.0%}"
                            if ocr_result.average_confidence is not None
                            else ""
                        )
                        st.session_state[f"{prefix}_ocr_meta"] = (
                            f"已识别 {ocr_result.line_count} 行{confidence}。请检查并修改错字后再填入参数。"
                        )
                        st.rerun()
                    except OCRError as exc:
                        st.error(str(exc))
            else:
                st.caption(
                    "OCR 在本服务的服务器运行，不会发送给模型厂商。"
                    if IS_WEB
                    else "OCR 完全在本机运行，不需要 API Key，截图不会发送到网络。"
                )
            ocr_text = st.text_area(
                "识别结果（可编辑）",
                placeholder="上传截图并点击识别后，文字会显示在这里。",
                key=f"{prefix}_ocr_text",
                height=150,
            )
            if st.session_state.get(f"{prefix}_ocr_meta"):
                st.success(st.session_state[f"{prefix}_ocr_meta"])
            render_parse_actions(ocr_text, "ocr")
    return requirements


def result_key(source: bytes, requirements: PhotoRequirements) -> str:
    return f"{hashlib.sha256(source).hexdigest()}:{requirements.model_dump_json()}"


def batch_result_key(uploaded_files: list[Any], requirements: PhotoRequirements) -> str:
    digest = hashlib.sha256()
    for uploaded in uploaded_files:
        digest.update(uploaded.name.encode("utf-8", errors="replace"))
        digest.update(uploaded.getvalue())
    return f"{digest.hexdigest()}:{requirements.model_dump_json()}"


def mime_for(image_format: ImageFormat) -> str:
    return {ImageFormat.JPEG: "image/jpeg", ImageFormat.PNG: "image/png", ImageFormat.WEBP: "image/webp"}[
        image_format
    ]


def render_result(result: AgentResult, source_name: str, *, key_prefix: str) -> None:
    st.markdown(
        f"<div class='pass-box'>✓ 输出已通过全部约束　·　Trace {result.trace_id}</div>",
        unsafe_allow_html=True,
    )
    for warning in result.warnings:
        st.markdown(f"<div class='warn-box'>⚠ {warning}</div>", unsafe_allow_html=True)
    left, right = st.columns([1, 1.12], gap="large")
    with left:
        st.image(result.output_bytes, caption="最终输出", use_container_width=True)
    with right:
        metrics = st.columns(3)
        metrics[0].metric("尺寸", f"{result.validation.metadata.width}×{result.validation.metadata.height}")
        metrics[1].metric("大小", f"{result.validation.metadata.size_kb:.1f} KB")
        quality_label: str | int = "无损"
        if result.quality is not None:
            quality_label = result.quality
        elif result.palette_colors is not None:
            quality_label = f"{result.palette_colors} 色"
        metrics[2].metric("质量", quality_label)
        for item in result.validation.items:
            st.markdown(
                f"""
<div class="validation-row">
  <b>{'✓' if item.passed else '×'}　{item.name}</b>
  <span>{item.actual}　·　要求 {item.expected}</span>
</div>
""",
                unsafe_allow_html=True,
            )
        downloads = st.columns(2)
        downloads[0].download_button(
            "下载合规照片",
            result.output_bytes,
            file_name=result.filename,
            mime=mime_for(result.requirements.output_format),
            type="primary",
            use_container_width=True,
            key=f"{key_prefix}_photo",
        )
        downloads[1].download_button(
            "下载验收报告",
            result_manifest_json(result, source_name=source_name),
            file_name=f"{result.filename}.json",
            mime="application/json",
            use_container_width=True,
            key=f"{key_prefix}_report",
        )
        with st.expander("查看 Agent 工具调用记录"):
            st.caption(f"执行计划：{result.plan_summary}　·　共 {result.attempts} 次尝试")
            for event in result.events:
                timing = f" · {event.duration_ms:.1f} ms" if event.duration_ms is not None else ""
                attempt = f"第 {event.attempt} 次" if event.attempt > 1 else ""
                st.markdown(
                    f"<div class='trace'><b>{event.tool}</b>"
                    f"<span class='trace-meta'>{attempt}{timing}</span><br>{event.detail}</div>",
                    unsafe_allow_html=True,
                )


def render_single(provider: ProviderConfig) -> None:
    top_left, top_right = st.columns([0.9, 1.1], gap="large")
    source_bytes: bytes | None = None
    uploaded = None
    with top_left:
        render_section("01", "上传照片", "先检查文件真实性、方向、像素和大小，不覆盖原图。")
        uploaded = st.file_uploader(
            "JPG / JPEG / PNG，单文件最大 25 MB", type=["jpg", "jpeg", "png"], key="single_uploader"
        )
        if uploaded:
            try:
                source_bytes = uploaded.getvalue()
                image, metadata = PROCESSING.inspect(source_bytes)
                st.image(image, caption="待处理原图", use_container_width=True)
                cols = st.columns(3)
                cols[0].metric("原始尺寸", f"{metadata.width}×{metadata.height}")
                cols[1].metric("格式", metadata.format)
                cols[2].metric("大小", f"{metadata.size_kb:.1f} KB")
            except ImageProcessingError as exc:
                st.error(public_error_message(exc))
                source_bytes = None
        else:
            st.markdown(
                "<div class='section-note'>上传后先检查文件真实性、像素总量与 EXIF 方向，不会覆盖原图。</div>",
                unsafe_allow_html=True,
            )
    with top_right:
        render_section("02", "设置目标要求", "选择预设或输入网申页面的精确限制。")
        requirements = render_requirements_editor("single", provider=provider)

    st.divider()
    render_section("03", "对比预览与处理", "并排检查裁剪与留白效果，再启动受控 Agent。")
    if source_bytes is None:
        st.info("请先上传一张证件照。")
        return
    preview_cols = st.columns(2, gap="large")
    preview_cols[0].image(
        PROCESSING.preview(source_bytes, requirements, FitMode.CROP),
        caption="裁剪预览",
        use_container_width=True,
    )
    preview_cols[0].caption("铺满目标画布；边缘可能被移除，可调整焦点。")
    preview_cols[1].image(
        PROCESSING.preview(source_bytes, requirements, FitMode.PAD),
        caption="留白预览",
        use_container_width=True,
    )
    preview_cols[1].caption("完整保留构图；空余区域使用背景色。")

    chosen = "裁剪" if requirements.fit_mode == FitMode.CROP else "留白"
    if st.button(f"启动 Agent · {chosen}并自动验收", type="primary", use_container_width=True):
        try:
            with st.status("正在执行图片工具链…", expanded=True) as status:
                result = PROCESSING.process(source_bytes, requirements, original_name=uploaded.name)
                for event in result.events:
                    st.write(f"✓ {event.tool} — {event.detail}")
                status.update(label="处理与验收完成", state="complete", expanded=False)
            st.session_state["single_result"] = result
            st.session_state["single_result_key"] = result_key(source_bytes, requirements)
            history: list[dict[str, Any]] = st.session_state["history"]
            history.insert(0, {"source_name": uploaded.name, "result": result})
            del history[12:]
        except (ImageProcessingError, ValueError, RuntimeError) as exc:
            st.error(public_error_message(exc))
    result = st.session_state.get("single_result")
    if result and st.session_state.get("single_result_key") == result_key(source_bytes, requirements):
        st.divider()
        render_section("04", "验收结果", "尺寸、格式和真实文件大小全部通过后即可下载。")
        render_result(result, uploaded.name, key_prefix="single_current")


def render_batch(provider: ProviderConfig) -> None:
    render_section("B", "批量适配", "对多张照片应用同一规格，每张独立处理与验收。")
    st.markdown(
        "<div class='section-note'>为多张照片应用同一要求，成功文件与逐项报告打包为 ZIP。最多 20 张。</div>",
        unsafe_allow_html=True,
    )
    uploaded_files = st.file_uploader(
        "批量上传 JPG / JPEG / PNG",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="batch_uploader",
    )
    requirements = render_requirements_editor("batch", provider=provider)
    if len(uploaded_files) > MAX_BATCH_FILES:
        st.error(f"一次最多处理 {MAX_BATCH_FILES} 张，请减少文件数量。")
        return
    total_size = sum(file.size for file in uploaded_files)
    if total_size > MAX_BATCH_TOTAL_BYTES:
        st.error("一次批量上传的总大小不能超过 100 MB，请分批处理。")
        return
    if uploaded_files:
        cols = st.columns(3)
        cols[0].metric("文件数", len(uploaded_files))
        cols[1].metric("总大小", f"{total_size / 1024 / 1024:.1f} MB")
        cols[2].metric("输出规格", f"{requirements.width}×{requirements.height}")
    if st.button("批量处理并生成 ZIP", type="primary", use_container_width=True, disabled=not uploaded_files):
        with st.status(f"正在处理 {len(uploaded_files)} 张照片…", expanded=True) as status:
            outcome = process_batch([(file.name, file.getvalue()) for file in uploaded_files], requirements)
            status.update(
                label=f"批量任务完成：{outcome.succeeded} 成功，{outcome.failed} 失败",
                state="complete" if not outcome.failed else "error",
                expanded=False,
            )
        st.session_state["batch_outcome"] = outcome
        st.session_state["batch_zip"] = build_batch_zip(outcome)
        st.session_state["batch_result_key"] = batch_result_key(uploaded_files, requirements)
    outcome: BatchOutcome | None = st.session_state.get("batch_outcome")
    current_batch_key = batch_result_key(uploaded_files, requirements) if uploaded_files else None
    if outcome and st.session_state.get("batch_result_key") == current_batch_key:
        rows = [
            {
                "源文件": item.source_name,
                "状态": "通过" if item.succeeded else "失败",
                "输出文件": item.result.filename if item.result else "—",
                "输出大小": f"{item.result.validation.metadata.size_kb:.1f} KB" if item.result else "—",
                "说明": "全部约束通过" if item.succeeded else item.error,
            }
            for item in outcome.items
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.download_button(
            "下载批量结果 ZIP",
            st.session_state["batch_zip"],
            file_name="application_photos.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            disabled=not outcome.succeeded,
        )


def render_history() -> None:
    title_col, clear_col = st.columns([4, 1])
    with title_col:
        render_section("H", "本次会话历史", "快速找回当前会话中已经通过验收的结果。")
    if clear_col.button("清空历史", use_container_width=True):
        st.session_state["history"] = []
        st.rerun()
    history: list[dict[str, Any]] = st.session_state["history"]
    if not history:
        st.info("尚无处理记录。历史只保存在当前浏览器会话中。")
        return
    for index, record in enumerate(history):
        result: AgentResult = record["result"]
        with st.expander(
            f"{index + 1}. {record['source_name']} → {result.filename} · {result.validation.metadata.size_kb:.1f} KB"
        ):
            render_result(result, record["source_name"], key_prefix=f"history_{index}")


def render_guide() -> None:
    render_section("?", "使用说明与产品边界", "了解推荐流程、隐私边界和输出验收方式。")
    st.markdown(
        f"""
#### 推荐流程

1. 复制网申页面要求，或上传要求截图并在{OCR_LOCATION} OCR 识别。
2. 检查识别文字，用本地规则或所选 AI 厂商解析填入。
3. 对比裁剪和留白，确认头顶、下巴和肩部没有被误裁。
4. 启动 Agent，等待尺寸、格式、文件大小全部通过。
5. 下载照片；重要申请建议同时保存 JSON 验收报告。

#### Agent 架构

```text
网申要求 → Pydantic 参数校验
                 ↓
 inspect_image → fit_image → compress_image → validate_output
```

要求截图由{OCR_LOCATION} OCR 读取；AI 只接收确认后的文字要求，不接触照片。改变文件的步骤全部由可测试、确定性的 Pillow 工具执行。

#### 启动方式

直接双击 `ApplicationPhotoAssistant.exe` 即可，日常使用不需要打开 PowerShell，也不需要安装 Python。

#### 注意事项

- 预设是常见参考值，最终以目标网申系统的最新要求为准。
- 软件不会美颜、换脸或修改身份特征。
- 无法同时满足尺寸、大小和最低画质时会明确失败，不输出假装合规的文件。
- `KB` 按 `1024 bytes` 验证。
"""
    )


def run() -> None:
    """Render the Streamlit application without leaking business logic into app.py."""

    init_state()
    provider = render_provider_sidebar()
    st.markdown(
        f"""
<div class="hero">
  <div class="hero-badge">●　APPLICATION PHOTO AGENT · {__version__}</div>
  <h1>网申照片智能适配助手</h1>
  <p>理解照片要求，调用受控工具执行，并用独立验证器逐项验收。每一步可解释，每一个结果可核验。</p>
  <div class="hero-grid">
    <div class="hero-card"><b>01 · 理解</b><span>文字、截图与常用规格</span></div>
    <div class="hero-card"><b>02 · 执行</b><span>裁剪、缩放、转换与压缩</span></div>
    <div class="hero-card"><b>03 · 验收</b><span>尺寸、格式与字节数复核</span></div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    tabs = st.tabs(["单张适配", "批量处理", "会话历史", "使用说明"])
    with tabs[0]:
        render_single(provider)
    with tabs[1]:
        render_batch(provider)
    with tabs[2]:
        render_history()
    with tabs[3]:
        render_guide()
