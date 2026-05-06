import base64
import configparser
import json
import os
from pathlib import Path


class AppConfig:
    _instance = None
    AVAILABLE_THEMES = ("amber", "graphite", "forest", "coast")

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
            cls._instance._init_config()
        return cls._instance

    def _init_config(self):
        self.BASE_DIR = Path(__file__).parent.parent
        self.DATA_DIR = self.BASE_DIR / "data"
        self.COVERS_DIR = self.BASE_DIR / "covers"
        self.CONFIG_FILE = self.DATA_DIR / "config.ini"

        self.WEBDAV_HOST = ""
        self.WEBDAV_USER = ""
        self.WEBDAV_PASS = ""
        self.REMOTE_PROVIDER = "webdav"
        self.REMOTE_COOKIE = ""
        self.REMOTE_PROFILES = {}
        self.USE_PROXY = False
        self.PROXY_URL = ""
        self.SAVED_MOUNT_DIRS = []
        self.SCAN_MAX_DEPTH = 2

        self.LOCAL_MOUNT_DIRS = []
        self.LOCAL_SCAN_MAX_DEPTH = 3
        self.UI_THEME = "amber"

        self.POTPLAYER_PATH = ""
        self.DEFAULT_POTPLAYER_PATHS = [
            r"C:\Program Files\DAUM\PotPlayer\PotPlayer.exe",
            r"C:\Program Files (x86)\DAUM\PotPlayer\PotPlayer.exe",
        ]

        self.VLC_PATH = ""
        self.DEFAULT_VLC_PATHS = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ]
        self.DEFAULT_PLAYER = "potplayer"

        self.VIDEO_FORMATS = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"]
        self.ENABLE_AUTO_SCRAPE = True
        self.SCRAPE_SOURCE = "auto"
        self.TMDB_API_KEY = ""
        self.TMDB_API_BASE = "https://api.themoviedb.org/3"
        self.TMDB_WEB_BASE = "https://www.themoviedb.org"
        self.TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
        self.INTERFACE_THEME = self.UI_THEME
        self.INTERFACE_LANGUAGE = "zh"

        self.OPENLIST_ENABLED = False
        self.OPENLIST_PORT = 5244
        self.OPENLIST_ADMIN_PASSWORD = ""
        self.OPENLIST_AUTO_START = True
        self.OPENLIST_BINARY_VERSION = ""
        self.OPENLIST_SOURCE_MODE = "builtin"

        self.DATA_DIR.mkdir(exist_ok=True)
        self.COVERS_DIR.mkdir(exist_ok=True)

    def save_config(self):
        config = configparser.ConfigParser(interpolation=None)
        self._sync_active_remote_profile()
        config["webdav"] = {
            "provider": self.normalize_remote_provider(self.REMOTE_PROVIDER),
            "host": self.WEBDAV_HOST.strip(),
            "user": self.WEBDAV_USER.strip(),
            "pass": base64.b64encode(self.WEBDAV_PASS.encode()).decode() if self.WEBDAV_PASS else "",
            "cookie": base64.b64encode(self.REMOTE_COOKIE.encode()).decode() if self.REMOTE_COOKIE else "",
            "profiles": base64.b64encode(json.dumps(self.get_remote_profiles(), ensure_ascii=False).encode()).decode(),
            "use_proxy": self.USE_PROXY,
            "proxy_url": self.PROXY_URL.strip(),
            "scan_max_depth": self.SCAN_MAX_DEPTH,
            "saved_mount_dirs": "|".join([item.strip() for item in self.SAVED_MOUNT_DIRS if item.strip()]),
        }
        config["local"] = {
            "scan_max_depth": self.LOCAL_SCAN_MAX_DEPTH,
            "saved_mount_dirs": "|".join([item.strip() for item in self.LOCAL_MOUNT_DIRS if item.strip()]),
        }
        config["player"] = {
            "potplayer_path": self.POTPLAYER_PATH.strip(),
            "vlc_path": self.VLC_PATH.strip(),
            "default_player": self.DEFAULT_PLAYER.strip(),
        }
        config["general"] = {
            "video_formats": ",".join(self.VIDEO_FORMATS),
            "enable_auto_scrape": self.ENABLE_AUTO_SCRAPE,
            "scrape_source": self.SCRAPE_SOURCE.strip(),
            "tmdb_api_key": self.TMDB_API_KEY.strip(),
            "tmdb_api_base": self.TMDB_API_BASE.strip(),
            "tmdb_web_base": self.TMDB_WEB_BASE.strip(),
            "tmdb_image_base": self.TMDB_IMAGE_BASE.strip(),
            "interface_theme": self.normalize_theme(self.UI_THEME),
            "interface_language": self.INTERFACE_LANGUAGE.strip(),
        }
        config["openlist"] = {
            "enabled": self.OPENLIST_ENABLED,
            "port": self.OPENLIST_PORT,
            "admin_password": base64.b64encode(self.OPENLIST_ADMIN_PASSWORD.encode()).decode() if self.OPENLIST_ADMIN_PASSWORD else "",
            "auto_start": self.OPENLIST_AUTO_START,
            "binary_version": self.OPENLIST_BINARY_VERSION,
            "source_mode": self.normalize_openlist_source_mode(self.OPENLIST_SOURCE_MODE),
        }
        with open(self.CONFIG_FILE, "w", encoding="utf-8") as file:
            config.write(file)

    def load_config(self):
        if not self.CONFIG_FILE.exists():
            self._auto_detect_players()
            self.UI_THEME = self.normalize_theme(self.UI_THEME)
            self.INTERFACE_THEME = self.UI_THEME
            return False

        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(self.CONFIG_FILE, encoding="utf-8")

            if "webdav" in config:
                webdav_config = config["webdav"]
                self.REMOTE_PROVIDER = self.normalize_remote_provider(webdav_config.get("provider", "webdav"))
                self.WEBDAV_HOST = webdav_config.get("host", "").strip()
                self.WEBDAV_USER = webdav_config.get("user", "").strip()
                pass_b64 = webdav_config.get("pass", "")
                self.WEBDAV_PASS = base64.b64decode(pass_b64).decode() if pass_b64 else ""
                cookie_b64 = webdav_config.get("cookie", "")
                self.REMOTE_COOKIE = base64.b64decode(cookie_b64).decode() if cookie_b64 else ""
                profiles_b64 = webdav_config.get("profiles", "")
                self.REMOTE_PROFILES = self._parse_remote_profiles(profiles_b64)
                self.USE_PROXY = webdav_config.getboolean("use_proxy", False)
                self.PROXY_URL = webdav_config.get("proxy_url", "").strip()
                self.SCAN_MAX_DEPTH = webdav_config.getint("scan_max_depth", 2)
                saved_dirs = self.normalize_remote_mount_dirs(
                    self.REMOTE_PROVIDER,
                    self._parse_saved_dirs(webdav_config.get("saved_mount_dirs", "")),
                )
                profile_dirs = self.get_remote_profiles().get(self.REMOTE_PROVIDER, {}).get("saved_mount_dirs", [])
                self.SAVED_MOUNT_DIRS = profile_dirs or saved_dirs
                self._sync_active_remote_profile()

            if "local" in config:
                local_config = config["local"]
                self.LOCAL_SCAN_MAX_DEPTH = local_config.getint("scan_max_depth", 3)
                self.LOCAL_MOUNT_DIRS = self._parse_saved_dirs(local_config.get("saved_mount_dirs", ""))

            if "player" in config:
                self.POTPLAYER_PATH = config["player"].get("potplayer_path", "").strip()
                self.VLC_PATH = config["player"].get("vlc_path", "").strip()
                self.DEFAULT_PLAYER = config["player"].get("default_player", "potplayer").strip().lower()

            if "general" in config:
                general_config = config["general"]
                video_formats = general_config.get("video_formats", ",".join(self.VIDEO_FORMATS))
                self.VIDEO_FORMATS = [fmt.strip() for fmt in video_formats.split(",") if fmt.strip()]
                self.ENABLE_AUTO_SCRAPE = general_config.getboolean("enable_auto_scrape", True)
                self.SCRAPE_SOURCE = "auto"
                self.TMDB_API_KEY = general_config.get("tmdb_api_key", "").strip()
                self.TMDB_API_BASE = general_config.get("tmdb_api_base", "https://api.themoviedb.org/3").strip() or "https://api.themoviedb.org/3"
                self.TMDB_WEB_BASE = general_config.get("tmdb_web_base", "https://www.themoviedb.org").strip() or "https://www.themoviedb.org"
                self.TMDB_IMAGE_BASE = general_config.get("tmdb_image_base", "https://image.tmdb.org/t/p/w500").strip() or "https://image.tmdb.org/t/p/w500"
                self.UI_THEME = self.normalize_theme(general_config.get("interface_theme", "amber"))
                self.INTERFACE_THEME = self.UI_THEME
                self.INTERFACE_LANGUAGE = general_config.get("interface_language", "zh").strip().lower()

            if "openlist" in config:
                openlist_config = config["openlist"]
                self.OPENLIST_ENABLED = openlist_config.getboolean("enabled", False)
                self.OPENLIST_PORT = openlist_config.getint("port", 5244)
                pass_b64 = openlist_config.get("admin_password", "")
                self.OPENLIST_ADMIN_PASSWORD = base64.b64decode(pass_b64).decode() if pass_b64 else ""
                self.OPENLIST_AUTO_START = openlist_config.getboolean("auto_start", True)
                self.OPENLIST_BINARY_VERSION = openlist_config.get("binary_version", "").strip()
                self.OPENLIST_SOURCE_MODE = self.normalize_openlist_source_mode(openlist_config.get("source_mode", "builtin"))

            self._auto_detect_players()
            if self.DEFAULT_PLAYER not in {"potplayer", "vlc"}:
                self.DEFAULT_PLAYER = "potplayer"
            self.SCRAPE_SOURCE = "auto"
            self.UI_THEME = self.normalize_theme(self.UI_THEME)
            self.INTERFACE_THEME = self.UI_THEME
            if self.INTERFACE_LANGUAGE not in {"zh", "en"}:
                self.INTERFACE_LANGUAGE = "zh"
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"加载配置失败: {exc}")
            self._auto_detect_players()
            return False

    def _parse_saved_dirs(self, raw_value: str):
        raw_value = raw_value.strip()
        if not raw_value:
            return []
        if "|" in raw_value:
            return [item.strip() for item in raw_value.split("|") if item.strip()]
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    def _auto_detect_players(self):
        self._auto_detect_potplayer()
        self._auto_detect_vlc()

    def _auto_detect_potplayer(self):
        if self.POTPLAYER_PATH and os.path.exists(self.POTPLAYER_PATH):
            return
        for path in self.DEFAULT_POTPLAYER_PATHS:
            if os.path.exists(path):
                self.POTPLAYER_PATH = path
                return

    def _auto_detect_vlc(self):
        if self.VLC_PATH and os.path.exists(self.VLC_PATH):
            return
        for path in self.DEFAULT_VLC_PATHS:
            if os.path.exists(path):
                self.VLC_PATH = path
                return

    def normalize_theme(self, theme: str):
        theme = str(theme or "").strip().lower()
        legacy_map = {"light": "amber", "dark": "graphite"}
        theme = legacy_map.get(theme, theme)
        if theme in self.AVAILABLE_THEMES:
            return theme
        return self.AVAILABLE_THEMES[0]

    def normalize_remote_provider(self, provider: str):
        provider = str(provider or "").strip().lower()
        if provider in {"webdav", "openlist"}:
            return provider
        return "webdav"

    def normalize_openlist_source_mode(self, mode: str):
        value = str(mode or "").strip().lower()
        if value in {"builtin", "external"}:
            return value
        return "builtin"

    def normalize_remote_mount_dirs(self, provider: str, dirs):
        normalized: list[str] = []
        seen: set[str] = set()
        is_remote = self.normalize_remote_provider(provider) in {"webdav", "openlist"}

        for item in dirs or []:
            value = str(item).strip()
            if not value:
                continue

            if is_remote:
                value = value.replace("\\", "/")
                while "//" in value:
                    value = value.replace("//", "/")
                if not value.startswith("/"):
                    value = "/" + value
                value = value.rstrip("/") or "/"

            if value in seen:
                continue
            seen.add(value)
            normalized.append(value)

        return normalized

    def get_remote_profiles(self):
        profiles = {}
        for provider in ("webdav", "openlist"):
            raw = self.REMOTE_PROFILES.get(provider, {}) if isinstance(self.REMOTE_PROFILES, dict) else {}
            profiles[provider] = {
                "webdav_host": str(raw.get("webdav_host", "")).strip(),
                "webdav_user": str(raw.get("webdav_user", "")).strip(),
                "webdav_pass": str(raw.get("webdav_pass", "")).strip(),
                "remote_cookie": str(raw.get("remote_cookie", "")).strip(),
                "openlist_source_mode": self.normalize_openlist_source_mode(raw.get("openlist_source_mode", "builtin")),
                "saved_mount_dirs": [
                    str(item).strip() for item in self.normalize_remote_mount_dirs(
                        provider,
                        raw.get("saved_mount_dirs", []) if isinstance(raw.get("saved_mount_dirs", []), list) else [],
                    )
                ],
            }
        return profiles

    def _sync_active_remote_profile(self):
        profiles = self.get_remote_profiles()
        provider = self.normalize_remote_provider(self.REMOTE_PROVIDER)
        profiles[provider] = {
            "webdav_host": self.WEBDAV_HOST.strip(),
            "webdav_user": self.WEBDAV_USER.strip(),
            "webdav_pass": self.WEBDAV_PASS.strip(),
            "remote_cookie": self.REMOTE_COOKIE.strip(),
            "openlist_source_mode": self.normalize_openlist_source_mode(self.OPENLIST_SOURCE_MODE if provider == "openlist" else "builtin"),
            "saved_mount_dirs": self.normalize_remote_mount_dirs(provider, self.SAVED_MOUNT_DIRS),
        }
        self.REMOTE_PROFILES = profiles

    def _parse_remote_profiles(self, encoded_value: str):
        if not encoded_value:
            return {}
        try:
            decoded = base64.b64decode(encoded_value).decode()
            payload = json.loads(decoded)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def get_remote_provider_label(self):
        mapping = {
            "webdav": "WebDAV",
            "openlist": "OpenList 网盘",
        }
        return mapping.get(self.normalize_remote_provider(self.REMOTE_PROVIDER), "WebDAV")

    def has_remote_auth_config(self):
        provider = self.normalize_remote_provider(self.REMOTE_PROVIDER)
        if provider == "openlist":
            if self.normalize_openlist_source_mode(self.OPENLIST_SOURCE_MODE) == "external":
                return bool(self.WEBDAV_HOST and self.WEBDAV_USER and self.WEBDAV_PASS)
            return self.OPENLIST_ENABLED
        if not self.WEBDAV_HOST:
            return False
        return bool(self.WEBDAV_USER and self.WEBDAV_PASS)

    def has_any_remote_library_config(self):
        profiles = self.get_remote_profiles()
        for provider, profile in profiles.items():
            mount_dirs = profile.get("saved_mount_dirs", []) if isinstance(profile, dict) else []
            if not mount_dirs:
                continue
            if provider == "openlist":
                source_mode = self.normalize_openlist_source_mode(profile.get("openlist_source_mode", self.OPENLIST_SOURCE_MODE))
                if source_mode == "external":
                    if (
                        str(profile.get("webdav_host", "")).strip()
                        and str(profile.get("webdav_user", "")).strip()
                        and str(profile.get("webdav_pass", "")).strip()
                    ):
                        return True
                    continue
                return True
            if (
                str(profile.get("webdav_host", "")).strip()
                and str(profile.get("webdav_user", "")).strip()
                and str(profile.get("webdav_pass", "")).strip()
            ):
                return True
        return False

    def has_basic_config(self):
        return self.has_any_remote_library_config()

    def has_local_config(self):
        return len(self.LOCAL_MOUNT_DIRS) > 0
