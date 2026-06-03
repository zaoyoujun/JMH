from __future__ import annotations

import copy
import json
import logging
import os
import platform
import re
import secrets
import shutil
import socket
import string
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, unquote, urlencode


from backend.analytics import AnalyticsETLService, TFIDFRecommendationEngine
from backend.recommendation_repository import RecommendationRepository
from config.app_config import AppConfig
from core.cover_scraper import CoverScraper
from core.local_video_library import LocalVideoLibraryManager
from core.remote_source import get_remote_provider_label, infer_remote_provider, make_remote_client
from core.video_library import VideoLibraryManager
from utils.database import VideoCache
from utils.filename_parser import build_media_tags
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
            "mpv_path": self.config.MPV_PATH,
            "default_player": self.config.DEFAULT_PLAYER,
            "video_formats": self.config.VIDEO_FORMATS,
            "enable_auto_scrape": self.config.ENABLE_AUTO_SCRAPE,
            "scrape_source": self.config.SCRAPE_SOURCE,
            "tmdb_api_key": self.config.TMDB_API_KEY,
            "douban_cookie": self.config.DOUBAN_COOKIE,
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

        self.config.MPV_PATH = str(payload.get("mpv_path", self.config.MPV_PATH)).strip()
        self.config.DEFAULT_PLAYER = "mpv_desktop"

        video_formats = payload.get("video_formats")
        if isinstance(video_formats, list):
            self.config.VIDEO_FORMATS = [str(fmt).strip() for fmt in video_formats if str(fmt).strip()]

        self.config.ENABLE_AUTO_SCRAPE = bool(payload.get("enable_auto_scrape", self.config.ENABLE_AUTO_SCRAPE))

        self.config.SCRAPE_SOURCE = "auto"
        self.config.TMDB_API_KEY = str(payload.get("tmdb_api_key", self.config.TMDB_API_KEY)).strip()
        self.config.DOUBAN_COOKIE = str(payload.get("douban_cookie", self.config.DOUBAN_COOKIE)).strip()
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
            "mpv_path": self.config.MPV_PATH,
            "default_player": self.config.DEFAULT_PLAYER,
            "video_formats": self.config.VIDEO_FORMATS,
            "enable_auto_scrape": self.config.ENABLE_AUTO_SCRAPE,
            "scrape_source": self.config.SCRAPE_SOURCE,
            "tmdb_api_key": self.config.TMDB_API_KEY,
            "douban_cookie": self.config.DOUBAN_COOKIE,
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
        playback_items = self._get_playback_progress_candidates(item, item.get("path", ""), 0)
        playback = max(
            (entry for _, entry in playback_items),
            key=lambda entry: int(entry.get("timestamp") or 0),
            default={},
        )
        progress_value = float(playback.get("progress") or 0)
        duration_value = float(playback.get("duration") or 0)
        progress_percent = 0
        if duration_value > 0 and progress_value > 0:
            progress_percent = max(0, min(100, round((progress_value / duration_value) * 100)))
        item["playback"] = {
            "progress": progress_value,
            "duration": duration_value,
            "percent": progress_percent,
            "episode_index": int(playback.get("episode_index") or 0),
            "timestamp": int(playback.get("timestamp") or 0),
            "has_progress": progress_percent > 0 or progress_value >= 5,
        }
        
        # 添加标签信息
        manual_tags = [str(tag).strip() for tag in self.cache.get_movie_tags(item.get("path", "")) if str(tag).strip()]
        inferred_tags = build_media_tags(item)
        item["manual_tags"] = manual_tags
        item["inferred_tags"] = inferred_tags
        item["tags"] = list(dict.fromkeys(manual_tags + inferred_tags))
        item["sort_bucket"] = int(item.get("sort_bucket") or 9)
        item["sort_title"] = str(item.get("sort_title") or item.get("title") or item.get("name") or "").lower()
        return item

    def _get_playback_progress_candidates(
        self,
        movie: dict[str, Any],
        movie_path: str,
        episode_index: int = 0,
    ) -> list[tuple[str, dict[str, Any]]]:
        candidates: list[str] = []
        base_path = str(movie_path or "").strip()
        if base_path:
            candidates.append(base_path)

        if movie.get("is_series") and movie.get("episode_files"):
            episode_files = [str(item).strip() for item in (movie.get("episode_files") or []) if str(item).strip()]
            if 0 <= int(episode_index or 0) < len(episode_files):
                preferred_episode_path = episode_files[int(episode_index or 0)]
                if preferred_episode_path and preferred_episode_path not in candidates:
                    candidates.insert(0, preferred_episode_path)
            for episode_path in episode_files:
                if episode_path not in candidates:
                    candidates.append(episode_path)

        progress_items: list[tuple[str, dict[str, Any]]] = []
        for path in candidates:
            progress = self.cache.get_playback_progress(path) or {}
            if progress:
                progress_items.append((path, progress))
        return progress_items

    def _movie_matches_source(self, movie: dict[str, Any], source: str) -> bool:
        if source == "combined":
            return True
        return self._source_for_path(movie.get("path", "")) == source

    @staticmethod
    def _movie_sort_key(movie: dict[str, Any]) -> tuple[Any, ...]:
        return (
            int(movie.get("sort_bucket") or 9),
            str(movie.get("category") or ""),
            str(movie.get("franchise") or ""),
            str(movie.get("sort_title") or movie.get("title") or movie.get("name") or "").lower(),
            int(movie.get("season") or 0),
            str(movie.get("path") or ""),
        )

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
        
        return sorted(decorated_movies, key=self._movie_sort_key)

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
        
        # 仅在需要时加载库，避免重复加载
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
            
            # 获取需要的视频，避免重复获取
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
        return sorted(movies, key=self._movie_sort_key)

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
        # 只从缓存获取统计信息，不触发扫描（避免冷启动延迟）
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
            # 失败时回退到原始方法
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
        finally:
            reconfigure_logger()

    def clear_all_data(self) -> None:
        release_logger_handlers()
        try:
            preserved_dir_names = {"mpv-profile"}

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

            # 逐个删除 data 下的子项目（webview 目录可能被锁定，单独处理）
            if self.config.DATA_DIR.exists():
                for item in self.config.DATA_DIR.iterdir():
                    try:
                        if item.is_dir() and item.name in preserved_dir_names:
                            continue
                        if item.is_dir():
                            shutil.rmtree(item, ignore_errors=True)
                        else:
                            item.unlink(missing_ok=True)
                    except Exception:
                        # 某些文件可能被其他进程占用，跳过即可。
                        logger.warning("无法删除: %s（可能被其他进程占用）", item)

            # 如果 data 目录仍然存在且非空，尝试系统权限强制删除
            if self.config.DATA_DIR.exists():
                remaining = [
                    item for item in self.config.DATA_DIR.iterdir()
                    if not (item.is_dir() and item.name in preserved_dir_names)
                ]
                if remaining:
                    for item in remaining:
                        try:
                            if item.is_dir():
                                shutil.rmtree(item, ignore_errors=True)
                            else:
                                item.unlink(missing_ok=True)
                        except Exception:
                            logger.warning("无法强制删除: %s（可能被其他进程占用）", item)

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
            self.config.MPV_PATH = ""
            self.config.DEFAULT_PLAYER = "mpv_desktop"
            self.config.TMDB_API_KEY = ""
            self.config.DOUBAN_COOKIE = ""
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

    def save_playback_progress(
        self,
        movie_path: str,
        progress: float,
        duration: float,
        episode_index: int | None = None,
    ) -> dict[str, Any]:
        """
        保存视频播放进度
        """
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        
        self.cache.save_playback_progress(movie_path, progress, duration, episode_index=episode_index)
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

    def get_all_playback_progress(self) -> dict[str, dict]:
        """
        获取所有视频的播放进度
        """
        return self.cache.get_all_playback_progress()

    def get_all_tags(self) -> dict[str, int]:
        """
        获取所有标签及其使用数量
        """
        tags = self.cache.get_all_tags()
        result = {}
        for tag, movies in tags.items():
            if isinstance(movies, list):
                result[tag] = len(movies)
        return result

    def get_movie_tags(self, movie_path: str) -> list[str]:
        """
        获取视频的标签
        """
        return self.cache.get_movie_tags(movie_path)

    def add_movie_tag(self, movie_path: str, tag: str) -> dict[str, Any]:
        """
        为视频添加标签
        """
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        
        self.cache.add_movie_tag(movie_path, tag)
        return self.get_movie(movie_path) or movie

    def remove_movie_tag(self, movie_path: str, tag: str) -> dict[str, Any]:
        """
        从视频移除标签
        """
        movie = self.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        
        self.cache.remove_movie_tag(movie_path, tag)
        return self.get_movie(movie_path) or movie

    def get_movies_by_tag(self, tag: str, source: str = "remote") -> list[dict[str, Any]]:
        """
        获取带有特定标签的视频
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
        self.analytics_engine = TFIDFRecommendationEngine()
        self.analytics = AnalyticsETLService(library_service, self.repository)

    def get_dashboard(self, limit: int = 18, external_limit: int = 8) -> dict[str, Any]:
        profile = self.repository.load_profile()
        recommendation_payload = self.repository.load_recommendations(limit=limit)

        if not recommendation_payload["items"] or profile.get("algorithm") != "tfidf_cosine":
            refreshed = self.refresh()
            recommendation_payload = {
                "items": refreshed.get("items", [])[:limit],
                "generated_at": refreshed.get("generated_at", 0),
            }
            profile = refreshed.get("profile", profile)

        return {
            "items": recommendation_payload.get("items", []),
            "profile": profile,
            "generated_at": int(recommendation_payload.get("generated_at") or 0),
            "stats": {
                "library_recommendations": len(recommendation_payload.get("items", [])),
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
        payload = {
            "items": analytics_payload.get("items", []),
            "profile": profile,
            "generated_at": int(time.time()),
            "warehouse_status": warehouse_status,
        }
        profile = payload.get("profile", {})
        payload["stats"] = {
            "library_recommendations": len(payload.get("items", [])),
            "profile_tags": len(profile.get("top_tags", [])) if isinstance(profile, dict) else 0,
            "seed_count": int(profile.get("seed_count") or 0) if isinstance(profile, dict) else 0,
        }
        return payload

    def rate_movie(self, movie_path: str, rating: float) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
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
        self._mpv_lock = threading.RLock()
        self._mpv_session: dict[str, Any] | None = None
        self._mpv_monitor_thread: threading.Thread | None = None
        self._mpv_session_file = self.config.DATA_DIR / "mpv_controlled_session.json"
        self._restore_mpv_controlled_session()

    def _resolve_mpv_path(self) -> str:
        if self.config.MPV_PATH and os.path.exists(self.config.MPV_PATH):
            return self.config.MPV_PATH
        for path in getattr(self.config, "DEFAULT_MPV_PATHS", []):
            if os.path.exists(path):
                self.config.MPV_PATH = path
                return path
        raise FileNotFoundError("未找到 mpv，请先在设置中配置 mpv 路径。")

    def _ensure_mpv_profile(self) -> str:
        profile_dir = self.config.DATA_DIR / "mpv-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        script_opts_dir = profile_dir / "script-opts"
        script_opts_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir = profile_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        watch_later_dir = profile_dir / "watch_later"
        watch_later_dir.mkdir(parents=True, exist_ok=True)

        mpv_conf = profile_dir / "mpv.conf"
        input_conf = profile_dir / "input.conf"
        osc_conf = script_opts_dir / "osc.conf"

        mpv_conf.write_text(
            "\n".join(
                [
                    "profile=pseudo-gui",
                    "border=no",
                    "keep-open=yes",
                    "force-window=immediate",
                    f"watch-later-dir={watch_later_dir}",
                    f"script-dir={profile_dir / 'scripts'}",
                    "write-filename-in-watch-later-config=yes",
                    "resume-playback=no",
                    "watch-later-options=start",
                    "save-position-on-quit=yes",
                    "autofit-larger=88%x88%",
                    "autofit-smaller=960x540",
                    "geometry=50%:50%",
                    "osc=yes",
                    "osd-bar=yes",
                    "script-opts-append=osc-visibility=always",
                    "osd-font-size=24",
                    "osd-duration=1400",
                    "osd-color=#FFFFFFFF",
                    "osd-border-size=1.6",
                    "osd-shadow-offset=0.8",
                    "cursor-autohide=1200",
                    "cursor-autohide-fs-only=no",
                    "background-color=#050608",
                    "sub-auto=fuzzy",
                    "sub-scale=1.08",
                    "sub-color=#FFFFFFFF",
                    "sub-border-color=#CC000000",
                    "sub-border-size=2.2",
                    "sub-shadow-offset=0.8",
                    "blend-subtitles=yes",
                    "audio-display=no",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        osc_conf.write_text(
            "\n".join(
                [
                    "layout=slimbottombar",
                    "seekbarstyle=knob",
                    "seekbarhandlesize=0.85",
                    "seekrangestyle=line",
                    "seekrangeseparate=no",
                    "visibility=always",
                    "windowcontrols=auto",
                    "windowcontrols_alignment=right",
                    "windowcontrols_independent=no",
                    "windowcontrols_title=${media-title}",
                    "title=${media-title}",
                    "timetotal=yes",
                    "remaining_playtime=yes",
                    "fadein=yes",
                    "fadeduration=120",
                    "hidetimeout=1800",
                    "boxalpha=55",
                    "barmargin=20",
                    "scalewindowed=1.15",
                    "scalefullscreen=1.2",
                    "vidscale=no",
                    "deadzonesize=1.0",
                    "minmousemove=3",
                    "boxvideo=yes",
                    "dynamic_margins=yes",
                    "sub_margins=yes",
                    "osd_margins=yes",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        input_conf.write_text(
            "\n".join(
                [
                    "SPACE cycle pause",
                    "MBTN_LEFT cycle pause",
                    "MBTN_RIGHT quit-watch-later",
                    "MBTN_LEFT_DBL cycle fullscreen",
                    "ESC quit-watch-later",
                    "q quit-watch-later",
                    "f cycle fullscreen",
                    "m cycle mute",
                    "UP add volume 5",
                    "DOWN add volume -5",
                    "LEFT seek -5 exact",
                    "RIGHT seek 5 exact",
                    "WHEEL_UP add volume 3",
                    "WHEEL_DOWN add volume -3",
                    "> script-message next-episode",
                    "< script-message prev-episode",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return str(profile_dir)

    def _get_mpv_watch_later_dir(self) -> Path:
        profile_dir = self.config.DATA_DIR / "mpv-profile"
        return profile_dir / "watch_later"

    def _read_mpv_watch_later_progress(self, session: dict[str, Any]) -> tuple[float, float] | None:
        watch_later_dir = self._get_mpv_watch_later_dir()
        if not watch_later_dir.exists():
            return None

        identifiers = [
            str(session.get("play_url") or "").strip(),
            str(session.get("resolved_path") or "").strip(),
            str(session.get("movie_path") or "").strip(),
        ]
        identifiers = [item for item in identifiers if item]
        if not identifiers:
            return None

        latest_match: tuple[Path, str] | None = None
        for file_path in watch_later_dir.glob("*"):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if not any(identifier in content for identifier in identifiers):
                continue
            if latest_match is None or file_path.stat().st_mtime > latest_match[0].stat().st_mtime:
                latest_match = (file_path, content)

        if latest_match is None:
            return None

        _, content = latest_match
        start_seconds = None
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("start="):
                try:
                    start_seconds = float(line.split("=", 1)[1].strip() or 0)
                except Exception:
                    start_seconds = None
                break

        if start_seconds is None or start_seconds <= 0:
            return None

        duration_seconds = float(session.get("duration_seconds") or 0)
        return start_seconds, duration_seconds

    @staticmethod
    def _mpv_ipc_send(pipe_path: str, command: list[Any], timeout: float = 5.0) -> dict[str, Any] | None:
        try:
            with open(pipe_path, "w+", encoding="utf-8") as pipe:
                payload = json.dumps({"command": command}) + "\n"
                pipe.write(payload)
                pipe.flush()
                import select
                ready, _, _ = select.select([pipe], [], [], timeout)
                if ready:
                    line = pipe.readline().strip()
                    if line:
                        return json.loads(line)
        except Exception:
            logger.debug("mpv IPC send failed for %s", pipe_path, exc_info=True)
        return None

    @staticmethod
    def _mpv_ipc_send_win(pipe_path: str, command: list[Any], timeout: float = 5.0) -> dict[str, Any] | None:
        import ctypes
        from ctypes import wintypes

        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        OPEN_EXISTING = 3
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        CreateFileW = ctypes.windll.kernel32.CreateFileW
        CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        CreateFileW.restype = wintypes.HANDLE

        WriteFile = ctypes.windll.kernel32.WriteFile
        WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        WriteFile.restype = wintypes.BOOL

        ReadFile = ctypes.windll.kernel32.ReadFile
        ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        ReadFile.restype = wintypes.BOOL

        CloseHandle = ctypes.windll.kernel32.CloseHandle
        CloseHandle.argtypes = [wintypes.HANDLE]
        CloseHandle.restype = wintypes.BOOL

        PeekNamedPipe = ctypes.windll.kernel32.PeekNamedPipe
        PeekNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
        PeekNamedPipe.restype = wintypes.BOOL

        handle = CreateFileW(pipe_path, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
        if handle == INVALID_HANDLE_VALUE:
            return None

        try:
            payload = (json.dumps({"command": command}) + "\n").encode("utf-8")
            written = wintypes.DWORD(0)
            if not WriteFile(handle, payload, len(payload), ctypes.byref(written), None):
                return None

            deadline = time.time() + timeout
            buf = b""
            while time.time() < deadline:
                avail = wintypes.DWORD(0)
                if not PeekNamedPipe(handle, None, 0, None, ctypes.byref(avail), None):
                    break
                if avail.value > 0:
                    chunk = ctypes.create_string_buffer(min(avail.value, 65536))
                    bytes_read = wintypes.DWORD(0)
                    if ReadFile(handle, chunk, min(avail.value, 65536), ctypes.byref(bytes_read), None):
                        buf += chunk.raw[:bytes_read.value]
                    if b"\n" in buf:
                        break
                else:
                    time.sleep(0.05)
            if buf:
                for line in buf.decode("utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line:
                        return json.loads(line)
        except Exception:
            logger.debug("mpv IPC send (win32) failed", exc_info=True)
        finally:
            CloseHandle(handle)
        return None

    def _mpv_send_command(self, pipe_path: str, command: list[Any], timeout: float = 5.0) -> dict[str, Any] | None:
        if platform.system() == "Windows":
            return self._mpv_ipc_send_win(pipe_path, command, timeout)
        return self._mpv_ipc_send(pipe_path, command, timeout)

    def _mpv_try_connect_pipe(self, pipe_path: str) -> bool:
        if platform.system() == "Windows":
            import ctypes
            from ctypes import wintypes

            CreateFileW = ctypes.windll.kernel32.CreateFileW
            CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            CreateFileW.restype = wintypes.HANDLE
            CloseHandle = ctypes.windll.kernel32.CloseHandle
            CloseHandle.argtypes = [wintypes.HANDLE]
            CloseHandle.restype = wintypes.BOOL

            GENERIC_READ = 0x80000000
            GENERIC_WRITE = 0x40000000
            OPEN_EXISTING = 3
            INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

            handle = CreateFileW(pipe_path, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
            if handle == INVALID_HANDLE_VALUE:
                return False
            CloseHandle(handle)
            return True
        return os.path.exists(pipe_path)

    def _mpv_get_property(self, pipe_path: str, prop: str) -> Any:
        result = self._mpv_send_command(pipe_path, ["get_property", prop])
        if result and "data" in result:
            return result["data"]
        return None

    @staticmethod
    def _normalize_mpv_track_list(track_list: Any, track_type: str) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        if not isinstance(track_list, list):
            return normalized
        for item in track_list:
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "").strip().lower() != track_type:
                continue
            track_id = item.get("id")
            if track_id in (None, "", "no"):
                continue
            try:
                track_id = int(track_id)
            except Exception:
                continue
            normalized.append(
                {
                    "id": track_id,
                    "title": str(item.get("title") or item.get("lang") or f"{track_type} {track_id}").strip(),
                    "lang": str(item.get("lang") or "").strip(),
                    "selected": bool(item.get("selected")),
                }
            )
        return normalized

    @staticmethod
    def _normalize_mpv_selected_track(value: Any) -> int | None:
        if value in (None, "", "no", "auto"):
            return None
        try:
            return int(float(value))
        except Exception:
            return None

    def _fetch_mpv_status(self, session: dict[str, Any]) -> dict[str, Any]:
        pipe_path = session.get("pipe_path", "")
        if not pipe_path:
            return {}
        pos = self._mpv_get_property(pipe_path, "time-pos")
        dur = self._mpv_get_property(pipe_path, "duration")
        pause = self._mpv_get_property(pipe_path, "pause")
        volume = self._mpv_get_property(pipe_path, "volume")
        mute = self._mpv_get_property(pipe_path, "mute")
        speed = self._mpv_get_property(pipe_path, "speed")
        fullscreen = self._mpv_get_property(pipe_path, "fullscreen")
        media_title = self._mpv_get_property(pipe_path, "media-title")
        aid = self._mpv_get_property(pipe_path, "aid")
        sid = self._mpv_get_property(pipe_path, "sid")
        track_list = self._mpv_get_property(pipe_path, "track-list")
        eof = self._mpv_get_property(pipe_path, "eof-reached")
        idle = self._mpv_get_property(pipe_path, "idle-active")
        if all(value is None for value in (pos, dur, pause, eof, idle, media_title, track_list)):
            return {}
        return {
            "position": float(pos or 0),
            "duration": float(dur or 0),
            "paused": bool(pause),
            "volume": int(float(volume or 100)),
            "muted": bool(mute),
            "speed": float(speed or 1.0),
            "fullscreen": bool(fullscreen),
            "media_title": str(media_title or ""),
            "audio_track": self._normalize_mpv_selected_track(aid),
            "subtitle_track": self._normalize_mpv_selected_track(sid),
            "audio_tracks": self._normalize_mpv_track_list(track_list, "audio"),
            "subtitle_tracks": self._normalize_mpv_track_list(track_list, "sub"),
            "eof_reached": bool(eof),
            "idle_active": bool(idle),
        }

    def _build_persistable_mpv_session(self, session: dict[str, Any]) -> dict[str, Any]:
        return {
            "token": session.get("token"),
            "active": bool(session.get("active")),
            "player": session.get("player"),
            "movie_path": session.get("movie_path"),
            "resolved_path": session.get("resolved_path"),
            "play_url": session.get("play_url"),
            "title": session.get("title"),
            "display_title": session.get("display_title"),
            "source": session.get("source"),
            "remote_provider": session.get("remote_provider"),
            "is_series": bool(session.get("is_series")),
            "episode_index": int(session.get("episode_index") or 0),
            "pipe_path": session.get("pipe_path"),
            "state": session.get("state"),
            "progress_seconds": float(session.get("progress_seconds") or 0),
            "duration_seconds": float(session.get("duration_seconds") or 0),
            "position": float(session.get("position") or 0),
            "volume": int(session.get("volume") or 100),
            "muted": bool(session.get("muted")),
            "speed": float(session.get("speed") or 1.0),
            "fullscreen": bool(session.get("fullscreen")),
            "audio_track": session.get("audio_track"),
            "subtitle_track": session.get("subtitle_track"),
            "audio_tracks": list(session.get("audio_tracks") or []),
            "subtitle_tracks": list(session.get("subtitle_tracks") or []),
            "recent_marked": bool(session.get("recent_marked")),
            "completed": bool(session.get("completed")),
            "started_at": int(session.get("started_at") or 0),
            "updated_at": int(session.get("updated_at") or 0),
        }

    def _persist_mpv_session_locked(self) -> None:
        session = self._mpv_session
        if not session:
            self._clear_persisted_mpv_session()
            return
        try:
            with open(self._mpv_session_file, "w", encoding="utf-8") as f:
                json.dump(self._build_persistable_mpv_session(session), f, ensure_ascii=False, indent=2)
        except Exception:
            logger.debug("persist mpv controlled session failed", exc_info=True)

    def _clear_persisted_mpv_session(self) -> None:
        try:
            if self._mpv_session_file.exists():
                self._mpv_session_file.unlink()
        except Exception:
            logger.debug("clear mpv controlled session cache failed", exc_info=True)

    def _restore_mpv_controlled_session(self) -> None:
        if not self._mpv_session_file.exists():
            return
        try:
            with open(self._mpv_session_file, "r", encoding="utf-8") as f:
                restored = json.load(f)
        except Exception:
            self._clear_persisted_mpv_session()
            return

        if not isinstance(restored, dict) or not restored.get("movie_path") or not restored.get("pipe_path"):
            self._clear_persisted_mpv_session()
            return

        session = dict(restored)
        session["active"] = bool(session.get("active", True))
        session["process"] = None
        session.setdefault("player", "mpv_desktop")
        session.setdefault("display_title", session.get("title") or "")
        session.setdefault("state", "launching")
        session.setdefault("progress_seconds", 0)
        session.setdefault("duration_seconds", 0)
        session.setdefault("position", 0.0)
        session.setdefault("volume", 100)
        session.setdefault("recent_marked", False)
        session.setdefault("completed", False)

        try:
            status = self._fetch_mpv_status(session)
        except Exception:
            self._clear_persisted_mpv_session()
            return

        if not status:
            self._clear_persisted_mpv_session()
            return

        self._merge_mpv_session_status(session, status)
        self._sync_mpv_playback_state(session)
        token = str(session.get("token") or secrets.token_hex(12))
        session["token"] = token
        with self._mpv_lock:
            self._mpv_session = session
            self._persist_mpv_session_locked()
            self._mpv_monitor_thread = threading.Thread(
                target=self._mpv_monitor_loop,
                args=(token,),
                name="moviepop-mpv-monitor-restored",
                daemon=True,
            )
            self._mpv_monitor_thread.start()

    def _merge_mpv_session_status(self, session: dict[str, Any], status: dict[str, Any]) -> None:
        duration = float(status.get("duration") or 0)
        position = float(status.get("position") or 0)
        paused = bool(status.get("paused"))
        eof = bool(status.get("eof_reached"))
        idle = bool(status.get("idle_active"))

        if eof or (idle and duration > 0 and position >= duration - 2):
            session["state"] = "stopped"
        elif paused:
            session["state"] = "paused"
        elif position > 0 or duration > 0:
            session["state"] = "playing"
        else:
            session["state"] = "launching"

        session["progress_seconds"] = max(0.0, position)
        session["duration_seconds"] = max(0.0, duration)
        session["position"] = position / duration if duration > 0 else 0.0
        session["volume"] = int(float(status.get("volume") or 100))
        session["muted"] = bool(status.get("muted"))
        session["speed"] = float(status.get("speed") or 1.0)
        session["fullscreen"] = bool(status.get("fullscreen"))
        session["audio_track"] = status.get("audio_track")
        session["subtitle_track"] = status.get("subtitle_track")
        session["audio_tracks"] = list(status.get("audio_tracks") or [])
        session["subtitle_tracks"] = list(status.get("subtitle_tracks") or [])
        session["updated_at"] = int(time.time())
        media_title = str(status.get("media_title") or "").strip()
        if media_title:
            session["display_title"] = media_title
        elif not session.get("display_title"):
            session["display_title"] = session.get("title") or ""

    def _save_mpv_playback_progress(
        self,
        path: str,
        progress_seconds: float,
        duration_seconds: float,
        episode_index: int,
    ) -> None:
        if not path:
            return
        try:
            self.library_service.save_playback_progress(
                path,
                progress_seconds,
                duration_seconds,
                episode_index=episode_index,
            )
        except ValueError:
            self.library_service.cache.save_playback_progress(
                path,
                progress_seconds,
                duration_seconds,
                episode_index=episode_index,
            )

    def _clear_mpv_playback_progress(self, path: str) -> None:
        if not path:
            return
        try:
            self.library_service.clear_playback_progress(path)
        except ValueError:
            self.library_service.cache.clear_playback_progress(path)

    def _sync_mpv_playback_state(self, session: dict[str, Any]) -> None:
        movie_path = str(session.get("movie_path") or "")
        resolved_path = str(session.get("resolved_path") or "")
        if not movie_path:
            return

        progress_seconds = float(session.get("progress_seconds") or 0)
        duration_seconds = float(session.get("duration_seconds") or 0)
        state = str(session.get("state") or "")
        episode_index = int(session.get("episode_index") or 0)

        if not session.get("recent_marked") and state in {"launching", "playing", "paused"}:
            try:
                self.library_service.add_recent(movie_path)
            except Exception:
                logger.debug("mark recent failed for %s", movie_path, exc_info=True)
            session["recent_marked"] = True

        if progress_seconds > 0 and (duration_seconds > 0 or state in {"playing", "paused", "stopped"}):
            try:
                self._save_mpv_playback_progress(movie_path, progress_seconds, duration_seconds, episode_index)
            except Exception:
                logger.debug("save progress failed for %s", movie_path, exc_info=True)
            if resolved_path and resolved_path != movie_path:
                try:
                    self._save_mpv_playback_progress(resolved_path, progress_seconds, duration_seconds, episode_index)
                except Exception:
                    logger.debug("save progress failed for resolved path %s", resolved_path, exc_info=True)

        completed = duration_seconds > 0 and progress_seconds >= max(duration_seconds - 15, duration_seconds * 0.97)
        if completed:
            # 播放完成时，保存进度为视频完整时长（表示已看完）
            try:
                self._save_mpv_playback_progress(movie_path, duration_seconds, duration_seconds, episode_index)
            except Exception:
                logger.debug("save completed progress failed for %s", movie_path, exc_info=True)
            if resolved_path and resolved_path != movie_path:
                try:
                    self._save_mpv_playback_progress(resolved_path, duration_seconds, duration_seconds, episode_index)
                except Exception:
                    logger.debug("save completed progress failed for resolved path %s", resolved_path, exc_info=True)
            
            # 不清除进度，保留已完成状态
            session["completed"] = True

        self._persist_mpv_session_locked()

    def _mpv_monitor_loop(self, token: str) -> None:
        while True:
            with self._mpv_lock:
                session = self._mpv_session
                if not session or session.get("token") != token or not session.get("active"):
                    return
            try:
                status = self._fetch_mpv_status(session)
                with self._mpv_lock:
                    active = self._mpv_session
                    if not active or active.get("token") != token:
                        return
                    if not status:
                        self._sync_progress_from_watch_later_locked(active)
                        active["active"] = False
                        self._persist_mpv_session_locked()
                        return
                    self._merge_mpv_session_status(active, status)
                    self._sync_mpv_playback_state(active)
                    if active.get("state") == "stopped":
                        self._sync_progress_from_watch_later_locked(active)
                        active["active"] = False
                        self._persist_mpv_session_locked()
            except Exception:
                logger.debug("poll mpv status failed", exc_info=True)
                with self._mpv_lock:
                    active = self._mpv_session
                    if active and active.get("token") == token:
                        self._sync_progress_from_watch_later_locked(active)
                        active["active"] = False
                        self._persist_mpv_session_locked()
            time.sleep(2)

    def _flush_mpv_session_progress_locked(self, session: dict[str, Any] | None = None) -> None:
        active_session = session or self._mpv_session
        if not active_session:
            return
        try:
            status = self._fetch_mpv_status(active_session)
            if status:
                self._merge_mpv_session_status(active_session, status)
                self._sync_mpv_playback_state(active_session)
            else:
                # 如果无法从 mpv 获取状态，尝试从 watch_later 文件中读取进度
                self._sync_progress_from_watch_later_locked(active_session)
        except Exception:
            logger.debug("flush mpv session progress failed", exc_info=True)
            # 如果获取状态失败，尝试从 watch_later 文件中读取进度
            try:
                self._sync_progress_from_watch_later_locked(active_session)
            except Exception:
                logger.debug("sync progress from watch later failed", exc_info=True)

    def _sync_progress_from_watch_later_locked(self, session: dict[str, Any] | None = None) -> None:
        active_session = session or self._mpv_session
        if not active_session:
            return
        watch_later_progress = None
        for attempt in range(5):
            watch_later_progress = self._read_mpv_watch_later_progress(active_session)
            if watch_later_progress:
                break
            if attempt < 4:
                time.sleep(0.2)
        if not watch_later_progress:
            return

        progress_seconds, duration_seconds = watch_later_progress
        active_session["progress_seconds"] = max(float(active_session.get("progress_seconds") or 0), float(progress_seconds or 0))
        if duration_seconds > 0:
            active_session["duration_seconds"] = float(duration_seconds)
            active_session["position"] = active_session["progress_seconds"] / duration_seconds
        if str(active_session.get("state") or "").lower() == "launching":
            active_session["state"] = "stopped"
        active_session["updated_at"] = int(time.time())
        self._sync_mpv_playback_state(active_session)

    def _stop_existing_mpv_session_locked(self) -> None:
        session = self._mpv_session
        if not session:
            self._clear_persisted_mpv_session()
            return
        self._flush_mpv_session_progress_locked(session)
        session["active"] = False
        self._persist_mpv_session_locked()
        try:
            pipe_path = session.get("pipe_path")
            if pipe_path:
                self._mpv_send_command(pipe_path, ["quit"], timeout=2.0)
        except Exception:
            logger.debug("stop mpv ipc session failed", exc_info=True)
        process = session.get("process")
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    logger.debug("kill mpv process failed", exc_info=True)
        self._mpv_session = None
        self._clear_persisted_mpv_session()

    def _resolve_movie_for_playback(self, movie_path: str) -> dict[str, Any]:
        movie = self.library_service.get_movie(movie_path)
        if not movie:
            raise ValueError("未找到对应的视频条目")
        return movie

    def _resolve_file_path(self, movie: dict[str, Any], episode_index: int = 0) -> str:
        file_path = movie.get("path", "")
        if movie.get("is_series") and movie.get("episode_files"):
            episode_files = movie.get("episode_files", [])
            if 0 <= episode_index < len(episode_files):
                file_path = episode_files[episode_index]
        if not file_path:
            raise ValueError("视频路径无效")
        return str(file_path)

    def _get_playback_progress_candidates(
        self,
        movie: dict[str, Any],
        movie_path: str,
        episode_index: int = 0,
    ) -> list[tuple[str, dict[str, Any]]]:
        candidates: list[str] = []
        base_path = str(movie_path or "").strip()
        if base_path:
            candidates.append(base_path)

        if movie.get("is_series") and movie.get("episode_files"):
            episode_files = [str(item).strip() for item in (movie.get("episode_files") or []) if str(item).strip()]
            if 0 <= int(episode_index or 0) < len(episode_files):
                preferred_episode_path = episode_files[int(episode_index or 0)]
                if preferred_episode_path and preferred_episode_path not in candidates:
                    candidates.insert(0, preferred_episode_path)
            for episode_path in episode_files:
                if episode_path not in candidates:
                    candidates.append(episode_path)

        progress_items: list[tuple[str, dict[str, Any]]] = []
        for path in candidates:
            progress = self.library_service.cache.get_playback_progress(path) or {}
            if progress:
                progress_items.append((path, progress))
        return progress_items

    def _get_resume_position(self, movie: dict[str, Any], movie_path: str, episode_index: int = 0) -> float:
        progress_items = self._get_playback_progress_candidates(movie, movie_path, episode_index)
        if not progress_items:
            return 0.0

        preferred_episode_path = ""
        if movie.get("is_series") and movie.get("episode_files"):
            episode_files = movie.get("episode_files") or []
            if 0 <= int(episode_index or 0) < len(episode_files):
                preferred_episode_path = str(episode_files[int(episode_index or 0)] or "").strip()

        progress: dict[str, Any] = {}
        if preferred_episode_path:
            for path, item in progress_items:
                if path == preferred_episode_path:
                    progress = item
                    break

        if not progress and movie.get("is_series"):
            for _, item in progress_items:
                if int(item.get("episode_index") or 0) == int(episode_index or 0):
                    progress = item
                    break

        if not progress and not movie.get("is_series"):
            progress = max(
                (item for _, item in progress_items),
                key=lambda item: int(item.get("timestamp") or 0),
                default={},
            )

        progress_seconds = float(progress.get("progress") or 0)
        duration_seconds = float(progress.get("duration") or 0)
        if progress_seconds < 5:
            return 0.0
        if duration_seconds > 0 and progress_seconds >= max(duration_seconds - 15, duration_seconds * 0.97):
            return 0.0
        return progress_seconds

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

    def start_mpv_controlled_playback(self, movie_path: str, episode_index: int = 0) -> dict[str, Any]:
        movie = self._resolve_movie_for_playback(movie_path)
        file_path = self._resolve_file_path(movie, episode_index)
        mpv_path = self._resolve_mpv_path()
        play_target = file_path if movie.get("source") == "local" else self.build_proxy_play_url(movie_path, episode_index)
        resume_seconds = self._get_resume_position(movie, movie_path, episode_index)
        token = secrets.token_hex(12)
        pipe_name = f"moviepop-mpv-{token[:8]}"
        if platform.system() == "Windows":
            pipe_path = f"\\\\.\\pipe\\{pipe_name}"
        else:
            pipe_path = str(self.config.DATA_DIR / f"mpv-{token[:8]}.sock")

        mpv_profile_dir = self._ensure_mpv_profile()

        with self._mpv_lock:
            self._stop_existing_mpv_session_locked()

        cmd = [
            mpv_path,
            f"--input-ipc-server={pipe_path}",
            f"--config-dir={mpv_profile_dir}",
            "--force-window=immediate",
            "--keep-open=yes",
            "--border=no",
            "--no-terminal",
        ]
        if resume_seconds > 0:
            cmd.append(f"--start={resume_seconds:.3f}")
        cmd.append(play_target)

        process = subprocess.Popen(cmd, shell=False)
        session: dict[str, Any] = {
            "token": token,
            "active": True,
            "player": "mpv_desktop",
            "movie_path": movie_path,
            "resolved_path": file_path,
            "play_url": play_target,
            "title": movie.get("title") or movie.get("name") or os.path.basename(file_path),
            "display_title": movie.get("title") or movie.get("name") or os.path.basename(file_path),
            "source": movie.get("source"),
            "remote_provider": movie.get("remote_provider"),
            "is_series": bool(movie.get("is_series")),
            "episode_index": int(episode_index or 0),
            "pipe_path": pipe_path,
            "state": "launching",
            "progress_seconds": resume_seconds,
            "duration_seconds": 0,
            "position": 0.0,
            "volume": 100,
            "muted": False,
            "speed": 1.0,
            "fullscreen": False,
            "audio_track": None,
            "subtitle_track": None,
            "audio_tracks": [],
            "subtitle_tracks": [],
            "recent_marked": False,
            "completed": False,
            "resume_seconds": resume_seconds,
            "resume_applied": resume_seconds > 0,
            "started_at": int(time.time()),
            "updated_at": int(time.time()),
            "process": process,
        }

        pipe_wait_deadline = time.time() + 15
        pipe_ready = False
        while time.time() < pipe_wait_deadline:
            if process.poll() is not None:
                break
            if self._mpv_try_connect_pipe(pipe_path):
                pipe_ready = True
                break
            time.sleep(0.3)

        if pipe_ready:
            try:
                status = self._fetch_mpv_status(session)
                if status:
                    self._merge_mpv_session_status(session, status)
            except Exception:
                logger.debug("initial mpv status fetch failed", exc_info=True)

        with self._mpv_lock:
            self._mpv_session = session
            self._persist_mpv_session_locked()
            self._mpv_monitor_thread = threading.Thread(
                target=self._mpv_monitor_loop,
                args=(token,),
                name="moviepop-mpv-monitor",
                daemon=True,
            )
            self._mpv_monitor_thread.start()

        return self.get_mpv_controlled_session()

    def get_mpv_controlled_session(self) -> dict[str, Any]:
        with self._mpv_lock:
            session = self._mpv_session
            if not session:
                return {"active": False}
            process = session.get("process")
            if process and process.poll() is not None:
                self._sync_progress_from_watch_later_locked(session)
                session["active"] = False
                self._persist_mpv_session_locked()
            active = bool(session.get("active")) and not (process and process.poll() is not None and session.get("state") == "stopped")
            return {
                "active": active,
                "player": session.get("player"),
                "movie_path": session.get("movie_path"),
                "resolved_path": session.get("resolved_path"),
                "play_url": session.get("play_url"),
                "title": session.get("title"),
                "display_title": session.get("display_title") or session.get("title"),
                "source": session.get("source"),
                "is_series": bool(session.get("is_series")),
                "episode_index": session.get("episode_index", 0),
                "state": session.get("state", "unknown"),
                "progress_seconds": float(session.get("progress_seconds") or 0),
                "duration_seconds": float(session.get("duration_seconds") or 0),
                "position": float(session.get("position") or 0),
                "volume": int(session.get("volume") or 100),
                "muted": bool(session.get("muted")),
                "speed": float(session.get("speed") or 1.0),
                "fullscreen": bool(session.get("fullscreen")),
                "audio_track": session.get("audio_track"),
                "subtitle_track": session.get("subtitle_track"),
                "audio_tracks": list(session.get("audio_tracks") or []),
                "subtitle_tracks": list(session.get("subtitle_tracks") or []),
                "completed": bool(session.get("completed")),
                "resume_seconds": float(session.get("resume_seconds") or 0),
                "resume_applied": bool(session.get("resume_applied")),
                "started_at": int(session.get("started_at") or 0),
                "updated_at": int(session.get("updated_at") or 0),
            }


    def control_mpv_controlled_session(self, action: str, value: str | None = None) -> dict[str, Any]:
        with self._mpv_lock:
            session = self._mpv_session
            if not session:
                raise ValueError("当前没有正在运行的 mpv 会话。")
            pipe_path = session.get("pipe_path", "")
            if not pipe_path:
                raise ValueError("mpv IPC 管道路径不可用。")
            normalized = str(action or "").strip().lower()
            if normalized == "toggle":
                self._mpv_send_command(pipe_path, ["set_property", "pause", "cycle"])
            elif normalized == "pause":
                self._mpv_send_command(pipe_path, ["set_property", "pause", True])
            elif normalized == "resume":
                self._mpv_send_command(pipe_path, ["set_property", "pause", False])
            elif normalized == "stop":
                self._flush_mpv_session_progress_locked(session)
                self._mpv_send_command(pipe_path, ["quit"])
                session["active"] = False
            elif normalized == "seek":
                if value is None:
                    raise ValueError("seek 命令缺少目标位置。")
                self._mpv_send_command(pipe_path, ["seek", value, "absolute"])
            elif normalized == "seek_forward":
                step = int(value or 15)
                self._mpv_send_command(pipe_path, ["seek", step, "relative"])
            elif normalized == "seek_backward":
                step = int(value or 15)
                self._mpv_send_command(pipe_path, ["seek", -step, "relative"])
            elif normalized == "volume":
                if value is None:
                    raise ValueError("volume 命令缺少目标音量。")
                self._mpv_send_command(pipe_path, ["set_property", "volume", float(value)])
            elif normalized == "mute":
                self._mpv_send_command(pipe_path, ["cycle", "mute"])
            elif normalized == "fullscreen":
                self._mpv_send_command(pipe_path, ["cycle", "fullscreen"])
            elif normalized == "speed":
                if value is None:
                    raise ValueError("speed 命令缺少目标倍速。")
                self._mpv_send_command(pipe_path, ["set_property", "speed", float(value)])
            elif normalized == "audio_track":
                if value is None:
                    raise ValueError("audio_track 命令缺少目标音轨。")
                track_value: Any = "no" if str(value).strip().lower() in {"", "off", "none", "no", "-1"} else int(float(value))
                self._mpv_send_command(pipe_path, ["set_property", "aid", track_value])
            elif normalized == "subtitle_track":
                if value is None:
                    raise ValueError("subtitle_track 命令缺少目标字幕。")
                track_value: Any = "no" if str(value).strip().lower() in {"", "off", "none", "no", "-1"} else int(float(value))
                self._mpv_send_command(pipe_path, ["set_property", "sid", track_value])
            else:
                raise ValueError("不支持的 mpv 控制命令。")
            try:
                status = self._fetch_mpv_status(session)
                if status:
                    self._merge_mpv_session_status(session, status)
                    self._sync_mpv_playback_state(session)
            except Exception:
                logger.debug("mpv command status fetch failed", exc_info=True)
        return self.get_mpv_controlled_session()

    def stop_mpv_controlled_session(self) -> dict[str, Any]:
        with self._mpv_lock:
            self._stop_existing_mpv_session_locked()
        return {"success": True}

    def play(self, movie_path: str, episode_index: int = 0) -> dict[str, Any]:
        return self.start_mpv_controlled_playback(movie_path, episode_index)

class ScraperService:
    def __init__(self, library_service: LibraryService) -> None:
        self.library_service = library_service
        self.scraper = CoverScraper()

    @staticmethod
    def _movie_matches_any_path(movie: dict[str, Any], target_paths: set[str]) -> bool:
        movie_path = str(movie.get("path") or "")
        if movie_path in target_paths:
            return True
        for episode_path in movie.get("episode_files") or []:
            if str(episode_path or "") in target_paths:
                return True
        return False

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
            raise ValueError("无法从所选结果中更新任何信息")
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
        return self._scrape_movies(raw_movies, source=source, progress=progress)

    def scrape_paths(
        self,
        paths: list[str],
        *,
        source: str = "remote",
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        target_paths = {str(path or "").strip() for path in paths if str(path or "").strip()}
        raw_movies = self.library_service._load_raw_library(source, force_refresh=False)  # noqa: SLF001
        scoped_movies = [movie for movie in raw_movies if self._movie_matches_any_path(movie, target_paths)]
        return self._scrape_movies(scoped_movies, source=source, progress=progress)

    def _scrape_movies(
        self,
        raw_movies: list[dict[str, Any]],
        *,
        source: str,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        total = len(raw_movies)
        if total > 0:
            logger.info("=" * 50)
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
                logger.exception("抓取失败: %s", title)
                continue

            if cover_path:
                movie["cover_path"] = cover_path
            if intro_text and intro_text.strip():
                movie["intro"] = intro_text.strip()
            if scraped_year:
                movie["year"] = scraped_year
            if cover_path or (intro_text and intro_text.strip()) or scraped_year:
                updated_count += 1

        current_library = self.library_service._load_raw_library(source, force_refresh=False)  # noqa: SLF001
        updated_map = {str(movie.get("path") or ""): movie for movie in raw_movies}
        merged_library: list[dict[str, Any]] = []
        for movie in current_library:
            replacement = updated_map.get(str(movie.get("path") or ""))
            merged_library.append(replacement if replacement else movie)
        self.library_service._save_raw_library(source, merged_library)  # noqa: SLF001
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
            # 空密码不覆盖已有密码（浏览器不会提交 type=password 的真实值）
            if password:
                self.config.OPENLIST_ADMIN_PASSWORD = password
        if "auto_start" in payload:
            self.config.OPENLIST_AUTO_START = bool(payload["auto_start"])
        self.config.save_config()
        return self.get_config()

    def start(self) -> dict[str, Any]:
        from core.openlist_manager import openlist_manager
        if not openlist_manager.is_binary_available():
            return {"success": False, "message": "OpenList 二进制文件不存在，请先下载。"}
        if not self.config.OPENLIST_ADMIN_PASSWORD:
            import secrets
            self.config.OPENLIST_ADMIN_PASSWORD = secrets.token_urlsafe(16)
            self.config.save_config()
        result = openlist_manager.start()
        if result.get("success"):
            self._sync_password_via_api()
        return result

    def _sync_password_via_api(self) -> None:
        """?? API ?? OpenList ?????"""
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
            return  # 密码已匹配
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
        # 先尝试用 API 修改(OpenList 运行时有效)
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
        """?????recursive=True ?????????"""
        client = self._get_openlist_client()
        password = self._ensure_openlist_password(client)
        if recursive:
            return self._list_dirs_recursive(client, password, path)
        return self._list_dirs_at(client, password, path)

    def list_files(self, path: str = "/") -> list[dict[str, Any]]:
        """列出指定目录下的所有文件"""
        client = self._get_openlist_client()
        password = self._ensure_openlist_password(client)
        try:
            normalized_path = self._normalize_openlist_path(path)
            data = client.list_files(password, normalized_path)
            content = data.get("data", {}).get("content") or []
            result = []
            for item in content:
                if item.get("is_dir"):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                result.append({"name": name, "full_path": normalized_path + "/" + name})
            logger.info("OpenList list_files path=%s -> %s files", path, len(result))
            return result
        except Exception as exc:
            logger.error("OpenList list_files 失败 path=%s: %s", path, exc)
            raise

    def _ensure_openlist_password(self, client) -> str:
        """?????? OpenList?????????????"""
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
                    logger.info("OpenList 密码已自动同步 %s", default_pwd[:3] + "***")
                return default_pwd
            except Exception:
                continue
        return password

    def _list_dirs_at(self, client, password: str, path: str) -> list[dict[str, str]]:
        """?? OpenList /api/fs/list ???????????"""
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
        """使用 BFS 递归列出目录"""
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
                logger.warning("遍历列出目录失败 %s: %s", current, exc)
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
    def __init__(self, library_service: LibraryService) -> None:
        self.library_service = library_service
        self.repository = RecommendationRepository()
        self.analytics = AnalyticsETLService(library_service, self.repository)

    def get_report(self) -> dict[str, Any]:
        snapshot = self.analytics.build_snapshot()
        warehouse_status = self.analytics.sync_snapshot(snapshot)
        payload = self.analytics.build_report_payload(snapshot)
        payload["warehouse_status"] = warehouse_status
        return payload


