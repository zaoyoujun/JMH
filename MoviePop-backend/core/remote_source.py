from types import SimpleNamespace

from config.app_config import AppConfig
from core.openlist_manager import openlist_manager
from core.webdav_client import WebDAVClient


PROVIDER_LABELS = {
    "webdav": "WebDAV",
    "openlist": "OpenList 网盘",
}


class RemoteProviderConfig(SimpleNamespace):
    def normalize_remote_provider(self, provider: str):
        value = str(provider or "").strip().lower()
        if value in {"webdav", "openlist"}:
            return value
        return "webdav"


def get_remote_provider_label(provider: str) -> str:
    key = str(provider or "").strip().lower()
    return PROVIDER_LABELS.get(key, "远程媒体源")


def infer_remote_provider(
    path: str | None = None,
    source_label: str | None = None,
    default: str = "webdav",
) -> str:
    raw_label = str(source_label or "").strip()
    for provider, label in PROVIDER_LABELS.items():
        if raw_label == label:
            return provider

    value = str(default or "webdav").strip().lower()
    return value if value in PROVIDER_LABELS else "webdav"


def make_remote_provider_config(base_config: AppConfig, provider: str) -> RemoteProviderConfig:
    key = base_config.normalize_remote_provider(provider)
    profiles = base_config.get_remote_profiles()
    profile = profiles.get(key, {})

    if key == "openlist":
        source_mode = base_config.normalize_openlist_source_mode(
            profile.get("openlist_source_mode", getattr(base_config, "OPENLIST_SOURCE_MODE", "builtin"))
        )
        if source_mode == "external":
            return RemoteProviderConfig(
                REMOTE_PROVIDER=key,
                OPENLIST_SOURCE_MODE=source_mode,
                WEBDAV_HOST=str(profile.get("webdav_host", "")).strip(),
                WEBDAV_USER=str(profile.get("webdav_user", "")).strip(),
                WEBDAV_PASS=str(profile.get("webdav_pass", "")).strip(),
                REMOTE_COOKIE=str(profile.get("remote_cookie", "")).strip(),
                USE_PROXY=bool(getattr(base_config, "USE_PROXY", False)),
                PROXY_URL=str(getattr(base_config, "PROXY_URL", "")).strip(),
                VIDEO_FORMATS=list(getattr(base_config, "VIDEO_FORMATS", [])),
                SAVED_MOUNT_DIRS=list(profile.get("saved_mount_dirs", []) or []),
                SCAN_MAX_DEPTH=int(getattr(base_config, "SCAN_MAX_DEPTH", 2) or 2),
            )

        status = openlist_manager.get_status()
        port = status.get("port") or base_config.OPENLIST_PORT or 5244
        webdav_host = f"http://127.0.0.1:{port}/dav"
        return RemoteProviderConfig(
            REMOTE_PROVIDER=key,
            OPENLIST_SOURCE_MODE=source_mode,
            WEBDAV_HOST=webdav_host,
            WEBDAV_USER="admin",
            WEBDAV_PASS=base_config.OPENLIST_ADMIN_PASSWORD or "",
            REMOTE_COOKIE="",
            USE_PROXY=False,
            PROXY_URL="",
            VIDEO_FORMATS=list(getattr(base_config, "VIDEO_FORMATS", [])),
            SAVED_MOUNT_DIRS=list(profile.get("saved_mount_dirs", []) or []),
            SCAN_MAX_DEPTH=int(getattr(base_config, "SCAN_MAX_DEPTH", 2) or 2),
        )

    return RemoteProviderConfig(
        REMOTE_PROVIDER=key,
        OPENLIST_SOURCE_MODE="builtin",
        WEBDAV_HOST=str(profile.get("webdav_host", "")).strip(),
        WEBDAV_USER=str(profile.get("webdav_user", "")).strip(),
        WEBDAV_PASS=str(profile.get("webdav_pass", "")).strip(),
        REMOTE_COOKIE=str(profile.get("remote_cookie", "")).strip(),
        USE_PROXY=bool(getattr(base_config, "USE_PROXY", False)),
        PROXY_URL=str(getattr(base_config, "PROXY_URL", "")).strip(),
        VIDEO_FORMATS=list(getattr(base_config, "VIDEO_FORMATS", [])),
        SAVED_MOUNT_DIRS=list(profile.get("saved_mount_dirs", []) or []),
        SCAN_MAX_DEPTH=int(getattr(base_config, "SCAN_MAX_DEPTH", 2) or 2),
    )


def make_remote_client(base_config: AppConfig, provider: str):
    config = make_remote_provider_config(base_config, provider)
    return WebDAVClient(config)
