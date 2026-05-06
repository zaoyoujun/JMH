from __future__ import annotations

import copy
import logging
import os
import re
import shutil
import string
import subprocess
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, unquote, urlencode

from backend.analytics import AnalyticsETLService, TFIDFRecommendationEngine
from backend.recommendations import RecommendationEngine, RecommendationRepository
from config.app_config import AppConfig
from core.cover_scraper import CoverScraper
from core.local_video_library import LocalVideoLibraryManager
from core.remote_source import get_remote_provider_label, infer_remote_provider, make_remote_client
from core.video_library import VideoLibraryManager
from utils.database import VideoCache
from utils.logger import get_logger, release_logger_handlers, reconfigure_logger

logger = get_logger()
FIRST_RUN_FLAG = AppConfig().BASE_DIR / ".first_run_complete"


ProgressCallback = Callable[[int, int, str], None]
LOCAL_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")


def build_remote_client(config: AppConfig, provider: str | None = None):
    return make_remote_client(config, provider or config.REMOTE_PROVIDER)


class ConfigService:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.config.load_config()

    def _snapshot(self) -> dict[str, Any]:
        return {
            "remote_provider": self.config.REMOTE_PROVIDER,
            "remote_profiles": copy.deepcopy(self.config.get_remote_profiles()),
            "webdav_host": self.config.WEBDAV_HOST,
            "webdav_user": self.config.WEBDAV_USER,
            "webdav_pass": self.config.WEBDAV_PASS,
            "remote_cookie": self.config.REMOTE_COOKIE,
            "openlist_source_mode": self.config.OPENLIST_SOURCE_MODE,
            "scan_max_depth": self.config.SCAN_MAX_DEPTH,
            "saved_mount_dirs": list(self.config.SAVED_MOUNT_DIRS),
            "local_scan_max_depth": self.config.LOCAL_SCAN_MAX_DEPTH,
            "local_mount_dirs": list(self.config.LOCAL_MOUNT_DIRS),
            "potplayer_path": self.config.POTPLAYER_PATH,
            "vlc_path": self.config.VLC_PATH,
            "default_player": self.config.DEFAULT_PLAYER,
            "video_formats": self.config.VIDEO_FORMATS,
            "enable_auto_scrape": self.config.ENABLE_AUTO_SCRAPE,
            "scrape_source": self.config.SCRAPE_SOURCE,
            "tmdb_api_key": self.config.TMDB_API_KEY,
            "tmdb_api_base": self.config.TMDB_API_BASE,
            "tmdb_web_base": self.config.TMDB_WEB_BASE,
            "tmdb_image_base": self.config.TMDB_IMAGE_BASE,
            "interface_theme": self.config.INTERFACE_THEME,
            "ui_theme": self.config.UI_THEME,
            "interface_language": self.config.INTERFACE_LANGUAGE,
        }

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        remote_profiles = payload.get("remote_profiles")
        if isinstance(remote_profiles, dict):
            normalized_profiles = self.config.get_remote_profiles()
            for provider, values in remote_profiles.items():
                key = self.config.normalize_remote_provider(provider)
                if not isinstance(values, dict):
                    continue
                normalized_profiles[key] = {
                    "webdav_host": str(values.get("webdav_host", normalized_profiles.get(key, {}).get("webdav_host", ""))).strip(),
                    "webdav_user": str(values.get("webdav_user", normalized_profiles.get(key, {}).get("webdav_user", ""))).strip(),
                    "webdav_pass": str(values.get("webdav_pass", normalized_profiles.get(key, {}).get("webdav_pass", ""))).strip(),
                    "remote_cookie": str(values.get("remote_cookie", normalized_profiles.get(key, {}).get("remote_cookie", ""))).strip(),
                    "openlist_source_mode": self.config.normalize_openlist_source_mode(
                        values.get("openlist_source_mode", normalized_profiles.get(key, {}).get("openlist_source_mode", "builtin"))
                    ),
                    "saved_mount_dirs": [
                        str(item).strip()
                        for item in self.config.normalize_remote_mount_dirs(
                            key,
                            values.get(
                                "saved_mount_dirs",
                                normalized_profiles.get(key, {}).get("saved_mount_dirs", []),
                            )
                            if isinstance(
                                values.get(
                                    "saved_mount_dirs",
                                    normalized_profiles.get(key, {}).get("saved_mount_dirs", []),
                                ),
                                list,
                            )
                            else [],
                        )
                    ],
                }
            self.config.REMOTE_PROFILES = normalized_profiles

        self.config.REMOTE_PROVIDER = self.config.normalize_remote_provider(
            payload.get("remote_provider", self.config.REMOTE_PROVIDER)
        )
        active_profile = self.config.get_remote_profiles().get(self.config.REMOTE_PROVIDER, {})
        self.config.WEBDAV_HOST = str(payload.get("webdav_host", active_profile.get("webdav_host", self.config.WEBDAV_HOST))).strip()
        self.config.WEBDAV_USER = str(payload.get("webdav_user", active_profile.get("webdav_user", self.config.WEBDAV_USER))).strip()
        self.config.WEBDAV_PASS = str(payload.get("webdav_pass", active_profile.get("webdav_pass", self.config.WEBDAV_PASS))).strip()
        self.config.REMOTE_COOKIE = str(payload.get("remote_cookie", active_profile.get("remote_cookie", self.config.REMOTE_COOKIE))).strip()
        self.config.OPENLIST_SOURCE_MODE = self.config.normalize_openlist_source_mode(
            payload.get("openlist_source_mode", active_profile.get("openlist_source_mode", self.config.OPENLIST_SOURCE_MODE))
        )
        self.config.SCAN_MAX_DEPTH = int(payload.get("scan_max_depth", self.config.SCAN_MAX_DEPTH or 2))

        saved_mount_dirs = payload.get("saved_mount_dirs")
        if isinstance(saved_mount_dirs, list):
            self.config.SAVED_MOUNT_DIRS = self.config.normalize_remote_mount_dirs(
                self.config.REMOTE_PROVIDER,
                saved_mount_dirs,
            )
        else:
            self.config.SAVED_MOUNT_DIRS = self.config.normalize_remote_mount_dirs(
                self.config.REMOTE_PROVIDER,
                active_profile.get("saved_mount_dirs", self.config.SAVED_MOUNT_DIRS),
            )
        self.config._sync_active_remote_profile()

        self.config.LOCAL_SCAN_MAX_DEPTH = int(
            payload.get("local_scan_max_depth", self.config.LOCAL_SCAN_MAX_DEPTH or 3)
        )
        local_mount_dirs = payload.get("local_mount_dirs")
        if isinstance(local_mount_dirs, list):
            self.config.LOCAL_MOUNT_DIRS = [str(item).strip() for item in local_mount_dirs if str(item).strip()]

        self.config.POTPLAYER_PATH = str(payload.get("potplayer_path", self.config.POTPLAYER_PATH)).strip()
        self.config.VLC_PATH = str(payload.get("vlc_path", self.config.VLC_PATH)).strip()
        default_player = str(payload.get("default_player", self.config.DEFAULT_PLAYER)).strip().lower()
        self.config.DEFAULT_PLAYER = default_player if default_player in {"potplayer", "vlc"} else "potplayer"

        video_formats = payload.get("video_formats")
        if isinstance(video_formats, list):
            self.config.VIDEO_FORMATS = [str(fmt).strip() for fmt in video_formats if str(fmt).strip()]

        self.config.ENABLE_AUTO_SCRAPE = bool(payload.get("enable_auto_scrape", self.config.ENABLE_AUTO_SCRAPE))

        self.config.SCRAPE_SOURCE = "auto"
        self.config.TMDB_API_KEY = str(payload.get("tmdb_api_key", self.config.TMDB_API_KEY)).strip()
        self.config.TMDB_API_BASE = str(payload.get("tmdb_api_base", self.config.TMDB_API_BASE)).strip() or "https://api.themoviedb.org/3"
        self.config.TMDB_WEB_BASE = str(payload.get("tmdb_web_base", self.config.TMDB_WEB_BASE)).strip() or "https://www.themoviedb.org"
        self.config.TMDB_IMAGE_BASE = str(payload.get("tmdb_image_base", self.config.TMDB_IMAGE_BASE)).strip() or "https://image.tmdb.org/t/p/w500"

        interface_theme = payload.get("ui_theme", payload.get("interface_theme", self.config.UI_THEME))
        self.config.UI_THEME = self.config.normalize_theme(interface_theme)
        self.config.INTERFACE_THEME = self.config.UI_THEME

        interface_language = str(payload.get("interface_language", self.config.INTERFACE_LANGUAGE)).strip().lower()
        self.config.INTERFACE_LANGUAGE = interface_language if interface_language in {"zh", "en"} else "zh"

    def _restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._apply_payload(snapshot)

    def get_public_config(self) -> dict[str, Any]:
        return {
            "remote_provider": self.config.REMOTE_PROVIDER,
            "remote_provider_label": self.config.get_remote_provider_label(),
            "remote_profiles": copy.deepcopy(self.config.get_remote_profiles()),
            "webdav_host": self.config.WEBDAV_HOST,
            "webdav_user": self.config.WEBDAV_USER,
            "webdav_pass": self.config.WEBDAV_PASS,
            "remote_cookie": self.config.REMOTE_COOKIE,
            "openlist_source_mode": self.config.OPENLIST_SOURCE_MODE,
            "scan_max_depth": self.config.SCAN_MAX_DEPTH,
            "saved_mount_dirs": list(self.config.SAVED_MOUNT_DIRS),
            "local_scan_max_depth": self.config.LOCAL_SCAN_MAX_DEPTH,
            "local_mount_dirs": list(self.config.LOCAL_MOUNT_DIRS),
            "potplayer_path": self.config.POTPLAYER_PATH,
            "vlc_path": self.config.VLC_PATH,
            "default_player": self.config.DEFAULT_PLAYER,
            "video_formats": self.config.VIDEO_FORMATS,
            "enable_auto_scrape": self.config.ENABLE_AUTO_SCRAPE,
            "scrape_source": self.config.SCRAPE_SOURCE,
            "tmdb_api_key": self.config.TMDB_API_KEY,
            "tmdb_api_base": self.config.TMDB_API_BASE,
            "tmdb_web_base": self.config.TMDB_WEB_BASE,
            "tmdb_image_base": self.config.TMDB_IMAGE_BASE,
            "interface_theme": self.config.INTERFACE_THEME,
            "ui_theme": self.config.UI_THEME,
            "available_themes": list(self.config.AVAILABLE_THEMES),
            "interface_language": self.config.INTERFACE_LANGUAGE,
            "has_basic_config": self.config.has_basic_config(),
            "has_local_config": self.config.has_local_config(),
            "has_any_library": self.config.has_basic_config() or self.config.has_local_config(),
            "openlist_enabled": self.config.OPENLIST_ENABLED,
            "openlist_source_mode": self.config.OPENLIST_SOURCE_MODE,
            "openlist_port": self.config.OPENLIST_PORT or 5244,
            "openlist_admin_password": self.config.OPENLIST_ADMIN_PASSWORD,
            "openlist_auto_start": self.config.OPENLIST_AUTO_START,
            "openlist_binary_version": self.config.OPENLIST_BINARY_VERSION,
        }

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        previous_remote_signature = (
            self.config.REMOTE_PROVIDER,
            copy.deepcopy(self.config.get_remote_profiles()),
            self.config.WEBDAV_HOST,
            self.config.WEBDAV_USER,
            self.config.WEBDAV_PASS,
            self.config.REMOTE_COOKIE,
            tuple(self.config.SAVED_MOUNT_DIRS),
            self.config.SCAN_MAX_DEPTH,
        )
        previous_local_signature = (
            tuple(self.config.LOCAL_MOUNT_DIRS),
            self.config.LOCAL_SCAN_MAX_DEPTH,
        )

        self._apply_payload(payload)
        self.config.save_config()

        current_remote_signature = (
            self.config.REMOTE_PROVIDER,
            copy.deepcopy(self.config.get_remote_profiles()),
            self.config.WEBDAV_HOST,
            self.config.WEBDAV_USER,
            self.config.WEBDAV_PASS,
            self.config.REMOTE_COOKIE,
            tuple(self.config.SAVED_MOUNT_DIRS),
            self.config.SCAN_MAX_DEPTH,
        )
        current_local_signature = (
            tuple(self.config.LOCAL_MOUNT_DIRS),
            self.config.LOCAL_SCAN_MAX_DEPTH,
        )

        if previous_remote_signature != current_remote_signature:
            VideoLibraryManager().clear_cache()
        if previous_local_signature != current_local_signature:
            LocalVideoLibraryManager().clear_cache()

        return self.get_public_config()

    def test_connection(self, payload: dict[str, Any] | None = None) -> tuple[bool, str]:
        if payload:
            snapshot = self._snapshot()
            try:
                self._apply_payload(payload)
                return build_remote_client(self.config).test_connection()
            finally:
                self._restore_snapshot(snapshot)
        return build_remote_client(self.config).test_connection()

    def list_directories(self, path: str = "/", payload: dict[str, Any] | None = None) -> list[dict[str, str]]:
        if payload:
            snapshot = self._snapshot()
            try:
                self._apply_payload(payload)
                return build_remote_client(self.config).list_directories(path)
            finally:
                self._restore_snapshot(snapshot)
        return build_remote_client(self.config).list_directories(path)

    def list_local_directories(self, path: str = "") -> list[dict[str, str]]:
        if not path:
            drives = []
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append({"name": drive.rstrip("\\"), "full_path": drive})
            return drives

        root = Path(path)
        if not root.exists() or not root.is_dir():
            raise ValueError("本地目录不存在")

        directories = []
        for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
            if child.is_dir():
                directories.append({"name": child.name, "full_path": str(child.resolve())})
        return directories


class LibraryService:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.config.load_config()
        self.remote_library = VideoLibraryManager()
        self.local_library = LocalVideoLibraryManager()
        self.cache = VideoCache()

    def _manager_for(self, source: str):
        if source == "local":
            return self.local_library
        return self.remote_library

    def _source_for_path(self, movie_path: str) -> str:
        return "local" if LOCAL_PATH_RE.match(movie_path or "") else "remote"

    def _resolve_cover_path(self, cover_path: str | None) -> Path | None:
        if not cover_path:
            return None

        candidate = Path(cover_path)
        if candidate.exists():
            return candidate

        fallback = self.config.COVERS_DIR / candidate.name
        if fallback.exists():
            return fallback
        return None

    def _get_remote_source_label(self) -> str:
        provider = self.config.normalize_remote_provider(self.config.REMOTE_PROVIDER)
        return get_remote_provider_label(provider)

    def _load_raw_library(self, source: str = "remote", force_refresh: bool = False) -> list[dict[str, Any]]:
        manager = self._manager_for(source)
        return copy.deepcopy(manager.get_video_list(force_refresh=force_refresh) or [])

    def _save_raw_library(self, source: str, movies: list[dict[str, Any]]) -> None:
        manager = self._manager_for(source)
        manager._save_cache(movies)  # noqa: SLF001
        if source == "local":
            LocalVideoLibraryManager._cached_list = copy.deepcopy(movies)  # noqa: SLF001
        else:
            VideoLibraryManager._cached_list = copy.deepcopy(movies)  # noqa: SLF001

    def _decorate_movie(
        self,
        movie: dict[str, Any],
        favorite_paths: set[str] | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        item = copy.deepcopy(movie)
        item_source = source or item.get("source") or self._source_for_path(item.get("path", ""))
        item.setdefault("title", item.get("name", "未命名"))
        item.setdefault("name", item.get("title", "未命名"))
        item.setdefault("type", "视频")
        item.setdefault("year", 2024)
        item.setdefault("intro", "")
        item.setdefault("rating", 0.0)
        item.setdefault("duration", "未知")
        item.setdefault("is_series", False)
        item.setdefault("episodes", [])
        item.setdefault("episode_files", [])
        item.setdefault("path", "")
        item.setdefault("cover_path", "")

        resolved_cover = self._resolve_cover_path(item.get("cover_path"))
        item["cover_path"] = str(resolved_cover) if resolved_cover else ""
        if resolved_cover:
            try:
                version = int(resolved_cover.stat().st_mtime)
            except OSError:
                version = 0
            item["cover_url"] = f"/covers/{quote(resolved_cover.name)}?v={version}"
        else:
            item["cover_url"] = ""
        item["is_favorite"] = item.get("path", "") in (favorite_paths or set())
        item["episode_count"] = len(item.get("episode_files", []))
        item["source"] = item_source
        if item_source == "local":
            item["remote_provider"] = None
            item["source_label"] = "本地视频"
        else:
            inferred_provider = infer_remote_provider(
                item.get("path", ""),
                item.get("source_label"),
                item.get("remote_provider") or self.config.normalize_remote_provider(self.config.REMOTE_PROVIDER),
            )
            item["remote_provider"] = inferred_provider
            item["source_label"] = item.get("source_label") or get_remote_provider_label(inferred_provider)
        playback = self.cache.get_playback_progress(item.get("path", "")) or {}
        progress_value = float(playback.get("progress") or 0)
        duration_value = float(playback.get("duration") or 0)
        progress_percent = 0
        if duration_value > 0 and progress_value > 0:
            progress_percent = max(0, min(100, round((progress_value / duration_value) * 100)))
        item["playback"] = {
            "progress": progress_value,
            "duration": duration_value,
            "percent": progress_percent,
            "timestamp": int(playback.get("timestamp") or 0),
            "has_progress": progress_percent > 0,
        }
        
        # 添加标签信息
        item["tags"] = self.cache.get_movie_tags(item.get("path", ""))
        return item

    def _movie_matches_source(self, movie: dict[str, Any], source: str) -> bool:
        if source == "combined":
            return True
        return self._source_for_path(movie.get("path", "")) == source

    def _catalog_for_source(self, source: str, force_refresh: bool = False) -> list[dict[str, Any]]:
        if source == "combined":
            return self.get_library("remote", force_refresh=force_refresh) + self.get_library(
                "local",
                force_refresh=force_refresh,
            )
        return self.get_library(source, force_refresh=force_refresh)

    def get_library(self, source: str = "remote", force_refresh: bool = False) -> list[dict[str, Any]]:
        if source == "combined":
            return self._catalog_for_source("combined", force_refresh=force_refresh)

        # 批量获取自定义信息和收藏信息，减少数据库查询
        custom_info = self.cache.get_all_custom_info()
        favorite_paths = {item.get("path", "") for item in self.cache.get_favorites()}
        
        # 加载原始库
        movies = self._load_raw_library(source=source, force_refresh=force_refresh)
        
        # 批量更新自定义信息
        for movie in movies:
            path = movie.get("path", "")
            if path in custom_info:
                movie.update(custom_info[path])
        
        # 批量装饰电影，避免重复操作
        decorated_movies = []
        for movie in movies:
            decorated_movies.append(self._decorate_movie(movie, favorite_paths, source=source))
        
        return decorated_movies

    def get_movie(self, movie_path: str, source: str | None = None) -> dict[str, Any] | None:
        source_candidates = []
        if source in {"remote", "local"}:
            source_candidates.append(source)
        guessed_source = self._source_for_path(movie_path)
        source_candidates.append(guessed_source)
        source_candidates.append("local" if guessed_source == "remote" else "remote")

        checked = set()
        for current_source in source_candidates:
            if current_source in checked:
                continue
            checked.add(current_source)
            for movie in self.get_library(current_source, force_refresh=False):
                if movie.get("path") == movie_path:
                    return movie

        favorite_paths = {item.get("path", "") for item in self.cache.get_favorites()}
        custom_info = self.cache.get_all_custom_info()
        for fallback_movie in self.cache.get_recent_play() + self.cache.get_favorites():
            if fallback_movie.get("path") == movie_path:
                fallback_copy = copy.deepcopy(fallback_movie)
                if movie_path in custom_info:
                    fallback_copy.update(custom_info[movie_path])
                return self._decorate_movie(fallback_copy, favorite_paths)
        return None

    def get_movies(
        self,
        mode: str = "all",
        source: str = "remote",
        search: str = "",
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        mode = (mode or "all").lower()
        source = (source or "remote").lower()
        
        # 只在需要时加载库，避免重复加载
        if mode in ["favorite", "recent"]:
            # 对于收藏和最近播放，只需要从缓存获取
            favorite_paths = {item.get("path", ""): True for item in self.cache.get_favorites()}
            
            if mode == "favorite":
                source_items = [
                    item for item in self.cache.get_favorites() if self._movie_matches_source(item, source)
                ]
            else:  # recent
                source_items = [
                    item for item in self.cache.get_recent_play() if self._movie_matches_source(item, source)
                ]
            
            # 只装饰需要的电影，避免重复装饰
            movies = []
            for item in source_items:
                path = item.get("path", "")
                # 尝试从缓存获取完整信息
                movie = None
                if source == "remote" and self.remote_library._cached_list:
                    for m in self.remote_library._cached_list:
                        if m.get("path") == path:
                            movie = m
                            break
                if not movie and source in ["local", "combined"] and self.local_library._cached_list:
                    for m in self.local_library._cached_list:
                        if m.get("path") == path:
                            movie = m
                            break
                if movie:
                    movies.append(self._decorate_movie(movie, set(favorite_paths.keys()), source=source))
                else:
                    movies.append(self._decorate_movie(item, set(favorite_paths.keys())))
        else:
            # 对于全部模式，加载完整库
            catalog = self._catalog_for_source(source, force_refresh=force_refresh)
            movies = catalog

        # 应用搜索过滤
        keyword = (search or "").strip().lower()
        if keyword:
            movies = [
                movie
                for movie in movies
                if keyword in movie.get("title", "").lower()
                or keyword in movie.get("name", "").lower()
                or keyword in movie.get("intro", "").lower()
                or keyword in movie.get("type", "").lower()
                or keyword in movie.get("source_label", "").lower()
            ]
        return movies

    def refresh_library(self, source: str = "remote") -> list[dict[str, Any]]:
        return self.get_library(source=source, force_refresh=True)

    def update_library_fields(
        self,
        movie_path: str,
        updates: dict[str, Any],
        source: str | None = None,
    ) -> dict[str, Any]:
        source_candidates = [source] if source in {"remote", "local"} else [self._source_for_path(movie_path)]
        source_candidates.append("local" if source_candidates[0] == "remote" else "remote")

        favorite_paths = {item.get("path", "") for item in self.cache.get_favorites()}
        checked = set()
        for current_source in source_candidates:
            if current_source in checked:
                continue
            checked.add(current_source)
            movies = self._load_raw_library(current_source, force_refresh=False)
            for movie in movies:
                if movie.get("path") == movie_path:
                    movie.update(updates)
                    self._save_raw_library(current_source, movies)
                    return self._decorate_movie(movie, favorite_paths, source=current_source)
        raise ValueError("未找到对应的视频条目")

    def save_custom_info(
        self,
        movie_path: str,
        updates: dict[str, Any],
        source: str | None = None,
    ) -> dict[str, Any]:
        current = self.cache.get_custom_info(movie_path)
        current.update(updates)
        self.cache.save_custom_info(movie_path, current)
        try:
            return self.update_library_fields(movie_path, updates, source=source)
        except ValueError:
            movie = self.get_movie(movie_path, source=source)
            if not movie:
                raise
            movie.update(updates)
            favorite_paths = {item.get("path", "") for item in self.cache.get_favorites()}
            return self._decorate_movie(movie, favorite_paths, source=movie.get("source"))

    def toggle_favorite(self, movie_path: str) -> dict[str, Any]:
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")

        if self.cache.is_favorite(movie_path):
            self.cache.remove_favorite(movie_path)
        else:
            self.cache.add_favorite(movie)
        return self.get_movie(movie_path) or movie

    def add_recent(self, movie_path: str) -> dict[str, Any]:
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        self.cache.add_recent_play(movie)
        return movie

    def get_stats(self) -> dict[str, int]:
        # 只从缓存获取统计信息，不触发扫描（避免阻塞启动）
        try:
            remote_count = len(self.remote_library._cached_list) if self.remote_library._cached_list is not None else 0
            local_count = len(self.local_library._cached_list) if self.local_library._cached_list is not None else 0
            return {
                "all": remote_count + local_count,
                "remote": remote_count,
                "local": local_count,
                "favorite": len(self.cache.get_favorites()),
                "recent": len(self.cache.get_recent_play()),
            }
        except Exception:
            # 出错时回退到原始方法
            return {
                "all": len(self.get_library("remote", force_refresh=False)) + len(self.get_library("local", force_refresh=False)),
                "remote": len(self.get_library("remote", force_refresh=False)),
                "local": len(self.get_library("local", force_refresh=False)),
                "favorite": len(self.cache.get_favorites()),
                "recent": len(self.cache.get_recent_play()),
            }

    def clear_library_cache(self, source: str | None = None) -> None:
        if source == "local":
            self.local_library.clear_cache()
            return
        if source == "remote":
            self.remote_library.clear_cache()
            return
        self.remote_library.clear_cache()
        self.local_library.clear_cache()

    def clear_all_cache(self) -> None:
        self.clear_library_cache()
        release_logger_handlers()
        try:
            if self.config.COVERS_DIR.exists():
                shutil.rmtree(self.config.COVERS_DIR, ignore_errors=True)
            self.config.COVERS_DIR.mkdir(exist_ok=True)

            cache_targets = [
                self.config.DATA_DIR / "app.log",
                self.config.DATA_DIR / "video_library_cache.json",
                self.config.DATA_DIR / "local_video_library_cache.json",
                self.config.DATA_DIR / "playback_progress.json",
            ]
            for file_path in cache_targets:
                if file_path.exists():
                    file_path.unlink(missing_ok=True)

            potplayer_cache = self.config.DATA_DIR / "potplayer_cache"
            if potplayer_cache.exists():
                shutil.rmtree(potplayer_cache, ignore_errors=True)
        finally:
            reconfigure_logger()

    def clear_all_data(self) -> None:
        release_logger_handlers()
        try:
            # 先停止 OpenList 进程并禁用自动重启
            try:
                from core.openlist_manager import openlist_manager
                openlist_manager.stop()
                # 禁用自动重启，防止 health_check_loop 在删除过程中重启进程
                openlist_manager._stop_event.set()
            except Exception:
                pass

            self.clear_library_cache()
            shutil.rmtree(self.config.COVERS_DIR, ignore_errors=True)
            if FIRST_RUN_FLAG.exists():
                FIRST_RUN_FLAG.unlink(missing_ok=True)

            # 逐个删除 data 下的子目录（webview 目录可能被锁定，单独处理）
            if self.config.DATA_DIR.exists():
                for item in self.config.DATA_DIR.iterdir():
                    try:
                        if item.is_dir():
                            shutil.rmtree(item, ignore_errors=True)
                        else:
                            item.unlink(missing_ok=True)
                    except Exception:
                        # 某些文件可能被 webview 进程锁定，跳过
                        logger.warning("无法删除: %s（可能被其他进程占用）", item)

            # 如果 data 目录仍然存在且非空，尝试系统命令强制删除
            if self.config.DATA_DIR.exists():
                remaining = list(self.config.DATA_DIR.iterdir())
                if remaining:
                    data_dir_str = str(self.config.DATA_DIR)
                    if os.name == "nt":
                        subprocess.run(
                            ["cmd", "/c", "rd", "/s", "/q", data_dir_str],
                            capture_output=True, timeout=30,
                        )
                    else:
                        subprocess.run(
                            ["rm", "-rf", data_dir_str],
                            capture_output=True, timeout=30,
                        )

            self.config.DATA_DIR.mkdir(exist_ok=True)
            self.config.COVERS_DIR.mkdir(exist_ok=True)
            self.config.WEBDAV_HOST = ""
            self.config.WEBDAV_USER = ""
            self.config.WEBDAV_PASS = ""
            self.config.REMOTE_PROVIDER = "webdav"
            self.config.REMOTE_PROFILES = {}
            self.config.SAVED_MOUNT_DIRS = []
            self.config.SCAN_MAX_DEPTH = 2
            self.config.LOCAL_MOUNT_DIRS = []
            self.config.LOCAL_SCAN_MAX_DEPTH = 3
            self.config.POTPLAYER_PATH = ""
            self.config.VLC_PATH = ""
            self.config.DEFAULT_PLAYER = "potplayer"
            self.config.TMDB_API_KEY = ""
            self.config.TMDB_API_BASE = "https://api.themoviedb.org/3"
            self.config.TMDB_WEB_BASE = "https://www.themoviedb.org"
            self.config.TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
            self.config.ENABLE_AUTO_SCRAPE = True
            self.config.SCRAPE_SOURCE = "auto"
            self.config.VIDEO_FORMATS = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"]
            self.config.UI_THEME = "amber"
            self.config.INTERFACE_THEME = "amber"
            self.config.INTERFACE_LANGUAGE = "zh"
            self.config.OPENLIST_ENABLED = False
            self.config.OPENLIST_PORT = 5244
            self.config.OPENLIST_ADMIN_PASSWORD = ""
            self.config.OPENLIST_AUTO_START = True
            self.config.OPENLIST_BINARY_VERSION = ""
            self.config.save_config()

            # 重新加载 openlist_manager 的配置（数据已删除）
            try:
                from core.openlist_manager import openlist_manager
                openlist_manager.reload_config()
            except Exception:
                pass
        finally:
            reconfigure_logger(include_file_handler=False)

    def save_playback_progress(self, movie_path: str, progress: float, duration: float) -> dict[str, Any]:
        """
        保存视频播放进度
        """
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        
        self.cache.save_playback_progress(movie_path, progress, duration)
        return {"success": True, "movie": movie}

    def get_playback_progress(self, movie_path: str) -> dict[str, Any]:
        """
        获取视频播放进度
        """
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        
        progress = self.cache.get_playback_progress(movie_path)
        return {"success": True, "progress": progress, "movie": movie}

    def clear_playback_progress(self, movie_path: str) -> dict[str, Any]:
        """
        清除视频播放进度
        """
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        
        self.cache.clear_playback_progress(movie_path)
        return {"success": True, "movie": movie}

    def get_all_tags(self) -> dict[str, int]:
        """
        获取所有标签及其使用次数
        """
        tags = self.cache.get_all_tags()
        result = {}
        for tag, movies in tags.items():
            if isinstance(movies, list):
                result[tag] = len(movies)
        return result

    def get_movie_tags(self, movie_path: str) -> list[str]:
        """
        获取电影的标签
        """
        return self.cache.get_movie_tags(movie_path)

    def add_movie_tag(self, movie_path: str, tag: str) -> dict[str, Any]:
        """
        为电影添加标签
        """
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        
        self.cache.add_movie_tag(movie_path, tag)
        return self.get_movie(movie_path) or movie

    def remove_movie_tag(self, movie_path: str, tag: str) -> dict[str, Any]:
        """
        从电影移除标签
        """
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        
        self.cache.remove_movie_tag(movie_path, tag)
        return self.get_movie(movie_path) or movie

    def get_movies_by_tag(self, tag: str, source: str = "remote") -> list[dict[str, Any]]:
        """
        获取具有特定标签的电影
        """
        movie_paths = self.cache.get_movies_by_tag(tag)
        movies = []
        favorite_paths = {item.get("path", "") for item in self.cache.get_favorites()}
        
        for path in movie_paths:
            movie = self.get_movie(path, source=self._source_for_path(path))
            if movie:
                movies.append(movie)
        
        return movies


class RecommendationService:
    def __init__(self, library_service: LibraryService) -> None:
        self.library_service = library_service
        self.repository = RecommendationRepository()
        self.engine = RecommendationEngine(self.repository)
        self.analytics_engine = TFIDFRecommendationEngine()
        self.analytics = AnalyticsETLService(library_service, self.repository)

    def get_dashboard(self, limit: int = 18, external_limit: int = 8) -> dict[str, Any]:
        profile = self.repository.load_profile()
        recommendation_payload = self.repository.load_recommendations(limit=limit)
        external_payload = self.repository.load_external_recommendations(limit=external_limit)

        if not recommendation_payload["items"] or profile.get("algorithm") != "tfidf_cosine":
            refreshed = self.refresh()
            recommendation_payload = {
                "items": refreshed.get("items", [])[:limit],
                "generated_at": refreshed.get("generated_at", 0),
            }
            external_payload = {
                "items": refreshed.get("external_items", [])[:external_limit],
                "generated_at": refreshed.get("generated_at", 0),
            }
            profile = refreshed.get("profile", profile)

        return {
            "items": recommendation_payload.get("items", []),
            "external_items": external_payload.get("items", []),
            "profile": profile,
            "generated_at": max(
                int(recommendation_payload.get("generated_at") or 0),
                int(external_payload.get("generated_at") or 0),
            ),
            "stats": {
                "library_recommendations": len(recommendation_payload.get("items", [])),
                "external_recommendations": len(external_payload.get("items", [])),
                "profile_tags": len(profile.get("top_tags", [])) if isinstance(profile, dict) else 0,
                "seed_count": int(profile.get("seed_count") or 0) if isinstance(profile, dict) else 0,
            },
        }

    def refresh(self) -> dict[str, Any]:
        snapshot = self.analytics.build_snapshot()
        warehouse_status = self.analytics.sync_snapshot(snapshot)
        analytics_payload = self.analytics_engine.generate(snapshot.get("movies", []))
        for movie_path, tags in analytics_payload.get("auto_tags_map", {}).items():
            self.repository.save_tags(movie_path, tags)
        profile = analytics_payload.get("profile", {})
        self.repository.save_profile(profile)
        self.repository.save_recommendations(analytics_payload.get("items", []))
        external_items = self.engine.fetch_external_recommendations(profile)
        self.repository.save_external_recommendations(external_items)
        payload = {
            "items": analytics_payload.get("items", []),
            "profile": profile,
            "generated_at": int(time.time()),
            "external_items": external_items[:15],
            "warehouse_status": warehouse_status,
        }
        profile = payload.get("profile", {})
        payload["stats"] = {
            "library_recommendations": len(payload.get("items", [])),
            "external_recommendations": len(payload.get("external_items", [])),
            "profile_tags": len(profile.get("top_tags", [])) if isinstance(profile, dict) else 0,
            "seed_count": int(profile.get("seed_count") or 0) if isinstance(profile, dict) else 0,
        }
        return payload

    def rate_movie(self, movie_path: str, rating: float) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的影视条目")
        rating = max(0.0, min(5.0, float(rating)))
        self.repository.upsert_feedback(movie_path, rating=rating)
        snapshot = self.analytics.build_snapshot()
        analytics_payload = self.analytics_engine.generate(snapshot.get("movies", []))
        for path_key, tags in analytics_payload.get("auto_tags_map", {}).items():
            self.repository.save_tags(path_key, tags)
        self.repository.save_profile(analytics_payload.get("profile", {}))
        self.repository.save_recommendations(analytics_payload.get("items", []))
        return {
            "movie": self.library_service.get_movie(movie_path) or movie,
            "rating": rating,
            "profile": analytics_payload.get("profile", {}),
        }


class PlaybackService:
    def __init__(self, library_service: LibraryService) -> None:
        self.config = AppConfig()
        self.config.load_config()
        self.library_service = library_service

    def _resolve_player(self) -> tuple[str, str]:
        if (
            self.config.DEFAULT_PLAYER == "vlc"
            and self.config.VLC_PATH
            and os.path.exists(self.config.VLC_PATH)
        ):
            return self.config.VLC_PATH, "VLC"
        if self.config.POTPLAYER_PATH and os.path.exists(self.config.POTPLAYER_PATH):
            return self.config.POTPLAYER_PATH, "PotPlayer"
        if self.config.VLC_PATH and os.path.exists(self.config.VLC_PATH):
            return self.config.VLC_PATH, "VLC"
        raise FileNotFoundError("未找到可用播放器，请先在设置中配置 PotPlayer 或 VLC。")

    def build_proxy_play_url(self, movie_path: str, episode_index: int = 0) -> str:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")

        file_path = movie.get("path", "")
        if movie.get("is_series") and movie.get("episode_files"):
            episode_files = movie.get("episode_files", [])
            if 0 <= episode_index < len(episode_files):
                file_path = episode_files[episode_index]

        if not file_path:
            raise ValueError("视频路径无效")

        query = urlencode(
            {
                "movie_path": file_path,
                "provider": movie.get("remote_provider") or "",
            }
        )
        raw_name = os.path.basename(str(file_path).rstrip("/")) or "media"
        display_name = unquote(raw_name) or "media"
        encoded_name = quote(display_name, safe="._-()[] ")
        encoded_name = encoded_name.replace(" ", "%20")
        from backend.server import resolved_port
        return f"http://127.0.0.1:{resolved_port}/api/stream/media/{encoded_name}?{query}"

    def play(self, movie_path: str, episode_index: int = 0) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")

        file_path = movie.get("path", "")
        if movie.get("is_series") and movie.get("episode_files"):
            episode_files = movie.get("episode_files", [])
            if 0 <= episode_index < len(episode_files):
                file_path = episode_files[episode_index]

        if not file_path:
            raise ValueError("视频路径无效")

        player_path, player_name = self._resolve_player()
        is_local_source = movie.get("source") == "local"
        if is_local_source:
            play_target = file_path
        else:
            play_target = build_remote_client(self.config, movie.get("remote_provider")).get_file_url(file_path)
        cmd = [player_path]

        if player_name == "PotPlayer":
            cache_dir = self.config.DATA_DIR / "potplayer_cache"
            cache_dir.mkdir(exist_ok=True)
            cmd.extend(
                [
                    "/buftime:5",
                    "/http_bufsize:102400",
                    "/diskcache:1",
                    "/diskcachesize:2048",
                    f'/cachepath:"{cache_dir.absolute()}"',
                ]
            )
        elif not is_local_source:
            cmd.append("--network-caching=3000")

        cmd.append(play_target)
        subprocess.Popen(cmd, shell=False)
        self.library_service.add_recent(movie_path)
        logger.info("启动播放器成功: %s -> %s", player_name, play_target)
        return {
            "player": player_name,
            "file_path": file_path,
            "play_url": play_target,
            "source": movie.get("source"),
        }


class ScraperService:
    def __init__(self, library_service: LibraryService) -> None:
        self.library_service = library_service
        self.scraper = CoverScraper()

    def search_candidates(self, movie_path: str, custom_name: str | None = None) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")

        candidates = self.scraper.search_candidates(movie, custom_name=custom_name)
        serialized: list[dict[str, Any]] = []
        for item in candidates:
            year = item.get("year")
            if not isinstance(year, int) or not 1900 <= year <= 2030:
                year = None
            serialized.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", ""),
                    "year": year,
                    "match_score": item.get("match_score"),
                    "matched_query": item.get("matched_query", ""),
                    "strategy_source": item.get("strategy_source", ""),
                }
            )
        diagnostics: list[dict[str, Any]] = []
        for item in getattr(self.scraper, "_last_candidate_diagnostics", []) or []:
            diagnostics.append(
                {
                    "source": item.get("source", ""),
                    "queries": int(item.get("queries") or 0),
                    "hits": int(item.get("hits") or 0),
                    "status": item.get("status", "idle"),
                    "error": str(item.get("error") or "").strip(),
                }
            )
        return {"items": serialized, "diagnostics": diagnostics}

    def apply_candidate(self, movie_path: str, candidate: dict[str, Any]) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")

        candidate_payload = dict(candidate)
        if candidate_payload.get("source") == "TMDB":
            candidate_payload["parse_func"] = self.scraper._get_tmdb_cover  # noqa: SLF001
        elif candidate_payload.get("source") == "Douban":
            candidate_payload["parse_func"] = self.scraper._get_douban_cover  # noqa: SLF001
        else:
            candidate_payload["parse_func"] = self.scraper._get_anibk_cover  # noqa: SLF001

        cover_path, intro_text, scraped_year = self.scraper.download_by_candidate(candidate_payload, movie)
        updates: dict[str, Any] = {}
        if cover_path:
            updates["cover_path"] = cover_path
        if candidate_payload.get("title"):
            updates["title"] = candidate_payload["title"]
            updates["name"] = candidate_payload["title"]
        if intro_text and intro_text.strip():
            updates["intro"] = intro_text.strip()
        if scraped_year:
            updates["year"] = scraped_year
        elif isinstance(candidate_payload.get("year"), int) and 1900 <= candidate_payload["year"] <= 2030:
            updates["year"] = candidate_payload["year"]

        if not updates:
            raise ValueError("未能从所选结果中更新任何信息")
        return self.library_service.save_custom_info(movie_path, updates, source=movie.get("source"))

    def scrape_single(self, movie_path: str, custom_name: str | None = None) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")

        cover_path, intro_text, scraped_year = self.scraper.search_cover(
            movie,
            custom_name=custom_name,
            force_update_meta=True,
        )
        updates: dict[str, Any] = {}
        if cover_path:
            updates["cover_path"] = cover_path
        if intro_text and intro_text.strip():
            updates["intro"] = intro_text.strip()
        if scraped_year:
            updates["year"] = scraped_year
        if not updates:
            raise ValueError("没有获取到新的封面或元数据")
        return self.library_service.update_library_fields(movie_path, updates, source=movie.get("source"))

    def scrape_library(self, source: str = "remote", progress: ProgressCallback | None = None) -> dict[str, Any]:
        raw_movies = self.library_service._load_raw_library(source, force_refresh=False)  # noqa: SLF001
        total = len(raw_movies)
        updated_count = 0
        for index, movie in enumerate(raw_movies, start=1):
            title = movie.get("title") or movie.get("name") or "未命名"
            if progress:
                progress(index - 1, total, f"正在补全《{title}》")

            try:
                cover_path, intro_text, scraped_year = self.scraper.search_cover(
                    movie,
                    force_update_meta=True,
                )
            except Exception:
                logger.exception("刮削失败: %s", title)
                continue

            if cover_path:
                movie["cover_path"] = cover_path
            if intro_text and intro_text.strip():
                movie["intro"] = intro_text.strip()
            if scraped_year:
                movie["year"] = scraped_year
            if cover_path or (intro_text and intro_text.strip()) or scraped_year:
                updated_count += 1

        self.library_service._save_raw_library(source, raw_movies)  # noqa: SLF001
        if progress:
            progress(total, total, "元数据补全完成")
        return {"total": total, "updated": updated_count}


class OpenListService:
    def __init__(self) -> None:
        self.config = AppConfig()

    @staticmethod
    def _normalize_openlist_path(path: str) -> str:
        value = str(path or "/").strip().replace("\\", "/")
        while "//" in value:
            value = value.replace("//", "/")
        if not value.startswith("/"):
            value = "/" + value
        return value.rstrip("/") or "/"

    def _normalize_storage_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload or {})
        driver = str(normalized.get("driver") or "").strip()
        addition = normalized.get("addition") or {}
        if not isinstance(addition, dict):
            addition = {}

        if driver == "Quark":
            root_folder_id = str(addition.get("root_folder_id") or "").strip()
            if not root_folder_id:
                addition["root_folder_id"] = "0"

        normalized["addition"] = addition
        mount_path = normalized.get("mount_path")
        if mount_path is not None:
            normalized["mount_path"] = self._normalize_openlist_path(str(mount_path))
        return normalized

    def get_status(self) -> dict[str, Any]:
        from core.openlist_manager import openlist_manager
        return openlist_manager.get_status()

    def get_config(self) -> dict[str, Any]:
        return {
            "enabled": self.config.OPENLIST_ENABLED,
            "port": self.config.OPENLIST_PORT or 5244,
            "admin_password": self.config.OPENLIST_ADMIN_PASSWORD,
            "auto_start": self.config.OPENLIST_AUTO_START,
            "binary_version": self.config.OPENLIST_BINARY_VERSION,
        }

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "enabled" in payload:
            self.config.OPENLIST_ENABLED = bool(payload["enabled"])
        if "port" in payload:
            port = int(payload["port"])
            if 1024 <= port <= 65535:
                self.config.OPENLIST_PORT = port
        if "admin_password" in payload:
            password = str(payload["admin_password"]).strip()
            # 空密码不覆盖已有密码（浏览器不会预填 type=password 的真实值）
            if password:
                self.config.OPENLIST_ADMIN_PASSWORD = password
        if "auto_start" in payload:
            self.config.OPENLIST_AUTO_START = bool(payload["auto_start"])
        self.config.save_config()
        return self.get_config()

    def start(self) -> dict[str, Any]:
        from core.openlist_manager import openlist_manager
        if not openlist_manager.is_binary_available():
            return {"success": False, "message": "OpenList 二进制文件不存在，请先下载"}
        if not self.config.OPENLIST_ADMIN_PASSWORD:
            import secrets
            self.config.OPENLIST_ADMIN_PASSWORD = secrets.token_urlsafe(16)
            self.config.save_config()
        result = openlist_manager.start()
        if result.get("success"):
            self._sync_password_via_api()
        return result

    def _sync_password_via_api(self) -> None:
        """用 API 验证/同步密码：admin set 修改数据库但运行中服务读的是内存缓存"""
        from core.openlist_manager import openlist_manager
        from core.openlist_client import OpenListAdminClient
        port = openlist_manager._active_port or self.config.OPENLIST_PORT or 5244
        target_password = self.config.OPENLIST_ADMIN_PASSWORD
        if not target_password:
            return
        client = OpenListAdminClient(f"http://127.0.0.1:{port}")
        # 1) 先用目标密码试登录
        try:
            client.login(target_password)
            return  # 密码已正确
        except Exception:
            pass
        # 2) 目标密码不对，用默认密码登录后通过 API 修改
        for default_pwd in ("123456", "", "admin"):
            try:
                client.login(default_pwd)
                resp = client.session.post(
                    f"{client.base_url}/api/me/password",
                    headers={"Authorization": client._token},
                    json={"old_password": default_pwd, "new_password": target_password},
                    timeout=10,
                )
                if resp.status_code == 200 and resp.json().get("code") == 200:
                    logger.info("OpenList 密码已通过 API 同步")
                    return
                break
            except Exception:
                continue
        # 3) API 也失败，回退到 admin set + 重启
        logger.warning("API 密码同步失败，尝试 admin set + 重启")
        import subprocess
        import platform
        binary = openlist_manager.get_binary_path()
        data_dir = openlist_manager._get_openlist_data_dir()
        try:
            subprocess.run(
                [str(binary), "admin", "set", target_password, "--data", str(data_dir)],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
            )
            # 重启使 admin set 的修改生效
            openlist_manager.restart()
        except Exception:
            pass

    def stop(self) -> dict[str, Any]:
        from core.openlist_manager import openlist_manager
        return openlist_manager.stop()

    def restart(self) -> dict[str, Any]:
        from core.openlist_manager import openlist_manager
        return openlist_manager.restart()

    def reset_password(self, password: str) -> dict[str, Any]:
        from core.openlist_manager import openlist_manager
        from core.openlist_client import OpenListAdminClient
        # 先尝试用 API 修改（OpenList 运行中时有效）
        port = openlist_manager._active_port or self.config.OPENLIST_PORT or 5244
        client = OpenListAdminClient(f"http://127.0.0.1:{port}")
        old_password = self.config.OPENLIST_ADMIN_PASSWORD or "123456"
        try:
            client.login(old_password)
            resp = client.session.post(
                f"{client.base_url}/api/me/password",
                headers={"Authorization": client._token},
                json={"old_password": old_password, "new_password": password},
                timeout=10,
            )
            if resp.status_code == 200 and resp.json().get("code") == 200:
                self.config.OPENLIST_ADMIN_PASSWORD = password
                self.config.save_config()
                return {"success": True, "message": "密码重置成功"}
        except Exception:
            pass
        # API 失败，回退到 admin set
        result = openlist_manager.reset_admin_password(password)
        return result

    def download_binary(self) -> str:
        from backend.jobs import job_manager
        from core.openlist_manager import openlist_binary_manager

        def task(update):
            update(0, 100, "正在获取最新版本信息...")
            version = openlist_binary_manager.get_latest_version()
            update(10, 100, f"正在下载 OpenList {version}...")
            openlist_binary_manager.download_binary(
                version,
                progress_cb=lambda cur, total: update(
                    10 + int(cur / total * 80), 100, "正在下载..."
                ) if total > 0 else None,
            )
            update(95, 100, "正在验证文件...")
            self.config.OPENLIST_BINARY_VERSION = version
            self.config.save_config()
            update(100, 100, f"OpenList {version} 下载完成")
            return {"version": version}

        job = job_manager.start("download-openlist-binary", task)
        return job.job_id

    def check_binary_update(self) -> dict[str, Any]:
        from core.openlist_manager import openlist_binary_manager
        has_update, current, latest = openlist_binary_manager.is_update_available()
        return {
            "has_update": has_update,
            "current_version": current,
            "latest_version": latest,
            "binary_available": openlist_binary_manager._openlist_dir.joinpath(
                "openlist.exe" if os.name == "nt" else "openlist"
            ).is_file(),
        }

    def _get_openlist_client(self):
        from core.openlist_manager import openlist_manager
        from core.openlist_client import OpenListAdminClient
        port = openlist_manager._active_port or self.config.OPENLIST_PORT or 5244
        return OpenListAdminClient(f"http://127.0.0.1:{port}")

    def list_storages(self) -> list[dict[str, Any]]:
        client = self._get_openlist_client()
        return client.list_storages(self.config.OPENLIST_ADMIN_PASSWORD)

    def list_directories(self, path: str = "/", recursive: bool = False) -> list[dict[str, str]]:
        """列目录。recursive=True 时递归返回所有嵌套目录（用于树形视图）。"""
        client = self._get_openlist_client()
        password = self._ensure_openlist_password(client)
        if recursive:
            return self._list_dirs_recursive(client, password, path)
        return self._list_dirs_at(client, password, path)

    def _ensure_openlist_password(self, client) -> str:
        """确保能登录 OpenList，尝试配置密码和常见默认密码。"""
        password = self.config.OPENLIST_ADMIN_PASSWORD or ""
        try:
            client.login(password)
            return password
        except Exception:
            pass
        for default_pwd in ("123456", "", "admin"):
            try:
                client.login(default_pwd)
                if not self.config.OPENLIST_ADMIN_PASSWORD:
                    self.config.OPENLIST_ADMIN_PASSWORD = default_pwd
                    self.config.save_config()
                    logger.info("OpenList 密码已自动同步: %s", default_pwd[:3] + "***")
                return default_pwd
            except Exception:
                continue
        return password

    def _list_dirs_at(self, client, password: str, path: str) -> list[dict[str, str]]:
        """用 OpenList /api/fs/list 返回当前层级的子目录。"""
        try:
            normalized_path = self._normalize_openlist_path(path)
            data = client.list_files(password, normalized_path)
            content = data.get("data", {}).get("content") or []
            result = []
            seen: set[str] = set()
            for item in content:
                if not item.get("is_dir"):
                    continue
                name = str(item.get("name") or "").strip().strip("/")
                if not name:
                    continue
                full_path = self._normalize_openlist_path(f"{normalized_path}/{name}")
                if full_path in seen:
                    continue
                seen.add(full_path)
                result.append({"name": name, "full_path": full_path})
            logger.info("OpenList /api/fs/list path=%s -> %s dirs", path, len(result))
            return result
        except Exception as exc:
            logger.error("OpenList /api/fs/list 失败 path=%s: %s", path, exc)
            raise

    def _list_dirs_recursive(self, client, password: str, root_path: str, max_depth: int = 5) -> list[dict[str, str]]:
        """BFS 递归列出所有嵌套目录。"""
        all_dirs: list[dict[str, str]] = []
        queue = [(root_path, 0)]
        visited: set[str] = set()
        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            try:
                dirs = self._list_dirs_at(client, password, current)
                for d in dirs:
                    all_dirs.append(d)
                    if depth < max_depth:
                        queue.append((d["full_path"], depth + 1))
            except Exception as exc:
                logger.warning("递归列出目录失败 %s: %s", current, exc)
        return all_dirs

    def add_storage(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._get_openlist_client()
        normalized_payload = self._normalize_storage_payload(payload)
        return client.add_storage(self.config.OPENLIST_ADMIN_PASSWORD, normalized_payload)

    def update_storage(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._get_openlist_client()
        normalized_payload = self._normalize_storage_payload(payload)
        return client.update_storage(self.config.OPENLIST_ADMIN_PASSWORD, normalized_payload)

    def delete_storage(self, storage_id: int) -> dict[str, Any]:
        client = self._get_openlist_client()
        return client.delete_storage(self.config.OPENLIST_ADMIN_PASSWORD, storage_id)

    def enable_storage(self, storage_id: int) -> dict[str, Any]:
        client = self._get_openlist_client()
        return client.enable_storage(self.config.OPENLIST_ADMIN_PASSWORD, storage_id)

    def disable_storage(self, storage_id: int) -> dict[str, Any]:
        client = self._get_openlist_client()
        return client.disable_storage(self.config.OPENLIST_ADMIN_PASSWORD, storage_id)

    @staticmethod
    def get_supported_drivers() -> list[dict[str, Any]]:
        from core.openlist_client import OpenListAdminClient
        return OpenListAdminClient.get_supported_drivers()


class ReportService:
    def __init__(self, library_service: LibraryService, recommendation_service: RecommendationService) -> None:
        self.library_service = library_service
        self.recommendation_service = recommendation_service
        self.cache = VideoCache()
        self.analytics = AnalyticsETLService(library_service, recommendation_service.repository)

    def get_report(self) -> dict[str, Any]:
        snapshot = self.analytics.build_snapshot()
        warehouse_status = self.analytics.sync_snapshot(snapshot)
        payload = self.analytics.build_report_payload(snapshot)
        payload["warehouse_status"] = warehouse_status
        return payload

        movies = self.library_service.get_movies(mode="all", source="combined", search="", force_refresh=False)
        favorites = self.cache.get_favorites()
        recent_play = self.cache.get_recent_play()
        playback_data = self.cache.get_all_playback_progress()
        feedback_map = self.recommendation_service.repository.get_feedback_map()

        total = len(movies)
        fav_paths = {item.get("path") for item in favorites}
        recent_paths = {item.get("path") for item in recent_play}

        # 类型分布
        type_counter: dict[str, int] = {}
        for movie in movies:
            mtype = movie.get("type") or "视频"
            type_counter[mtype] = type_counter.get(mtype, 0) + 1

        type_distribution = []
        for name, count in sorted(type_counter.items(), key=lambda x: x[1], reverse=True):
            type_distribution.append({"name": name, "count": count, "percent": round(count / total * 100) if total else 0})

        # 年代分布
        def year_bucket(year: int) -> str:
            if year >= 2022:
                return "2022-至今"
            if year >= 2016:
                return "2016-2021"
            if year >= 2010:
                return "2010-2015"
            if year > 0:
                return "2010年以前"
            return "年份未知"

        year_counter: dict[str, int] = {}
        for movie in movies:
            bucket = year_bucket(int(movie.get("year") or 0))
            year_counter[bucket] = year_counter.get(bucket, 0) + 1

        year_distribution = [
            {"name": name, "count": count}
            for name, count in sorted(year_counter.items(), key=lambda x: x[1], reverse=True)
        ]

        # 来源分布
        source_counter: dict[str, int] = {"远程": 0, "本地": 0}
        for movie in movies:
            path = movie.get("path", "")
            if LOCAL_PATH_RE.match(path):
                source_counter["本地"] += 1
            else:
                source_counter["远程"] += 1

        source_distribution = [{"name": name, "count": count} for name, count in source_counter.items()]

        # 完播统计
        completed = 0
        in_progress = 0
        not_started = 0
        for movie in movies:
            path = movie.get("path", "")
            pb = playback_data.get(path, {})
            percent = 0
            if pb:
                progress_sec = float(pb.get("progress") or 0)
                duration_sec = float(pb.get("duration") or 0)
                if duration_sec > 0:
                    percent = min(100, round(progress_sec / duration_sec * 100))
            if percent >= 90:
                completed += 1
            elif percent > 0:
                in_progress += 1
            else:
                not_started += 1

        # 总观影时长（小时）
        total_seconds = sum(float(pb.get("progress") or 0) for pb in playback_data.values())
        total_watch_hours = round(total_seconds / 3600, 1)

        # 平均评分
        ratings = [v["rating"] for v in feedback_map.values() if v.get("rating") and v["rating"] > 0]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

        # 偏好标签（从推荐引擎画像获取）
        profile = self.recommendation_service.repository.load_profile()
        genre_preferences = profile.get("top_tags", []) if isinstance(profile, dict) else []

        # 近期动态（最近 10 条有播放进度的记录）
        activity_items = []
        sorted_playback = sorted(
            playback_data.items(),
            key=lambda x: int(x[1].get("timestamp") or 0),
            reverse=True,
        )
        for path, pb in sorted_playback[:10]:
            movie = self.library_service.get_movie(path)
            title = movie.get("title") or movie.get("name") or path.split("/")[-1] if movie else path.split("/")[-1]
            mtype = movie.get("type") or "视频" if movie else "视频"
            progress_sec = float(pb.get("progress") or 0)
            duration_sec = float(pb.get("duration") or 0)
            percent = min(100, round(progress_sec / duration_sec * 100)) if duration_sec > 0 else 0
            activity_items.append({
                "title": title,
                "type": mtype,
                "timestamp": int(pb.get("timestamp") or 0),
                "progress": percent,
            })

        return {
            "overview": {
                "total_movies": total,
                "favorites": len(fav_paths),
                "watched": len(recent_paths),
                "total_watch_hours": total_watch_hours,
                "avg_rating": avg_rating,
            },
            "type_distribution": type_distribution,
            "genre_preferences": genre_preferences,
            "year_distribution": year_distribution,
            "source_distribution": source_distribution,
            "completion_stats": {
                "completed": completed,
                "in_progress": in_progress,
                "not_started": not_started,
            },
            "recent_activity": activity_items,
        }
