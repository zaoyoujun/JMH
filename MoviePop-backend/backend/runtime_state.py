from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

from config.app_config import AppConfig


_state: dict[str, Any] = {
    "desktop_mode": False,
    "runtime": "browser",
    "window_title": "",
    "native_handle": None,
    "pywebview_available": False,
    "mpv_available": False,
    "embed_ready": False,
    "reasons": [],
}


def _detect_module_availability() -> tuple[bool, bool]:
    pywebview_available = False
    mpv_available = False
    try:
        import webview  # noqa: F401

        pywebview_available = True
    except Exception:
        pywebview_available = False

    try:
        config = AppConfig()
        config.load_config()
        mpv_available = bool(config.MPV_PATH and Path(config.MPV_PATH).exists())
    except Exception:
        mpv_available = False

    return pywebview_available, mpv_available


def _coerce_native_handle(window: Any) -> int | None:
    native = getattr(window, "native", None)
    if native is None:
        return None

    direct_handle = getattr(native, "Handle", None)
    if direct_handle is None:
        return None

    try:
        to_int = getattr(direct_handle, "ToInt64", None) or getattr(direct_handle, "ToInt32", None)
        if callable(to_int):
            return int(to_int())
        return int(direct_handle)
    except Exception:
        return None


def extract_native_handle(window: Any) -> int | None:
    return _coerce_native_handle(window)


def refresh_runtime_state() -> dict[str, Any]:
    pywebview_available, mpv_available = _detect_module_availability()
    reasons: list[str] = []
    if not pywebview_available:
        reasons.append("未检测到 pywebview，当前不能进入桌面模式。")
    if not mpv_available:
        reasons.append("未检测到 mpv，请先在设置中配置 mpv.exe 路径。")
    if platform.system() != "Windows":
        reasons.append("当前桌面播放器仅支持 Windows。")
    if _state.get("desktop_mode") and _state.get("native_handle") is None:
        reasons.append("桌面窗口句柄尚未就绪，暂时无法启用内置播放器。")
    if not _state.get("desktop_mode"):
        reasons.append("当前运行在浏览器模式，内置 mpv 需要从桌面模式启动。")

    _state["platform"] = platform.system()
    _state["pywebview_available"] = pywebview_available
    _state["mpv_available"] = mpv_available
    _state["embed_ready"] = (
        _state.get("desktop_mode")
        and _state.get("native_handle") is not None
        and pywebview_available
        and mpv_available
        and platform.system() == "Windows"
    )
    _state["reasons"] = reasons
    return get_runtime_state()


def set_desktop_window(window: Any, title: str = "") -> dict[str, Any]:
    _state["desktop_mode"] = True
    _state["runtime"] = "pywebview"
    _state["window_title"] = title or getattr(window, "title", "") or "MoviePop"
    _state["native_handle"] = _coerce_native_handle(window)
    return refresh_runtime_state()


def mark_browser_runtime() -> dict[str, Any]:
    _state["desktop_mode"] = False
    _state["runtime"] = "browser"
    _state["window_title"] = ""
    _state["native_handle"] = None
    return refresh_runtime_state()


def get_runtime_state() -> dict[str, Any]:
    return {
        "desktop_mode": bool(_state.get("desktop_mode")),
        "runtime": str(_state.get("runtime") or "browser"),
        "window_title": str(_state.get("window_title") or ""),
        "native_handle": _state.get("native_handle"),
        "pywebview_available": bool(_state.get("pywebview_available")),
        "mpv_available": bool(_state.get("mpv_available")),
        "embed_ready": bool(_state.get("embed_ready")),
        "platform": str(_state.get("platform") or platform.system()),
        "reasons": list(_state.get("reasons") or []),
    }


refresh_runtime_state()
