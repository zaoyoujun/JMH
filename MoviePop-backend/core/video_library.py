import json

from config.app_config import AppConfig
from core.remote_source import (
    get_remote_provider_label,
    infer_remote_provider,
    make_remote_client,
    make_remote_provider_config,
)
from utils.filename_parser import merge_series_videos, parse_video_filename
from utils.logger import get_logger

logger = get_logger()


class VideoLibraryManager:
    _cached_list = None
    _cache_file = None

    def __init__(self):
        self.config = AppConfig()
        if VideoLibraryManager._cache_file is None:
            VideoLibraryManager._cache_file = self.config.DATA_DIR / "video_library_cache.json"

    def get_video_list(self, force_refresh=False):
        if not force_refresh and VideoLibraryManager._cached_list is not None:
            logger.info("使用远程媒体库内存缓存")
            return VideoLibraryManager._cached_list

        if not force_refresh and self._has_valid_cache():
            logger.info("读取远程媒体库缓存")
            VideoLibraryManager._cached_list = self._load_cache()
            return VideoLibraryManager._cached_list

        # 非强制刷新且无缓存时，不触发扫描（避免阻塞启动）
        if not force_refresh:
            return []

        logger.info("开始扫描远程媒体源...")
        try:
            video_files = self._scan_remote_sources()
            if not video_files:
                logger.warning("远程媒体源扫描为空")
                if self._has_valid_cache():
                    return self._load_cache()
                return []

            movie_list = merge_series_videos(video_files)
            self._save_cache(movie_list)
            VideoLibraryManager._cached_list = movie_list
            logger.info("远程媒体源扫描完成: %s", len(movie_list))
            return movie_list
        except Exception as exc:  # noqa: BLE001
            logger.error("远程媒体源扫描异常: %s", exc)
            if self._has_valid_cache():
                return self._load_cache()
            return []

    def _scan_remote_sources(self):
        all_files = []
        for provider in ("webdav", "openlist"):
            provider_config = make_remote_provider_config(self.config, provider)
            mount_dirs = list(provider_config.SAVED_MOUNT_DIRS or [])
            if not mount_dirs:
                continue

            if provider == "openlist":
                if not provider_config.WEBDAV_HOST:
                    logger.warning("跳过 %s 扫描：OpenList 未运行", provider)
                    continue
            elif not (provider_config.WEBDAV_HOST and provider_config.WEBDAV_USER and provider_config.WEBDAV_PASS):
                logger.warning("跳过 %s 扫描：缺少地址或账号密码", provider)
                continue

            client = make_remote_client(self.config, provider)
            source_label = get_remote_provider_label(provider)
            for dir_path in mount_dirs:
                try:
                    files = client.list_directory(dir_path, provider_config.SCAN_MAX_DEPTH)
                    all_files.extend(
                        {
                            "file_path": file_path,
                            "remote_provider": provider,
                            "source_label": source_label,
                        }
                        for file_path in files
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("扫描目录失败 %s:%s -> %s", provider, dir_path, exc)
        return all_files

    def _has_valid_cache(self):
        if not VideoLibraryManager._cache_file.exists():
            return False
        try:
            with open(VideoLibraryManager._cache_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            return isinstance(data, list) and len(data) > 0
        except Exception:  # noqa: BLE001
            return False

    def _load_cache(self):
        try:
            with open(VideoLibraryManager._cache_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            normalized = []
            for item in data if isinstance(data, list) else []:
                if not isinstance(item, dict):
                    continue
                provider = item.get("remote_provider") or infer_remote_provider(
                    item.get("path"),
                    item.get("source_label"),
                    "webdav",
                )
                cache_item = dict(item)
                cache_item["remote_provider"] = provider
                cache_item["source_label"] = cache_item.get("source_label") or get_remote_provider_label(provider)
                cache_item = self._rehydrate_cached_fields(cache_item)
                normalized.append(cache_item)
            return normalized
        except Exception:  # noqa: BLE001
            return []

    def _rehydrate_cached_fields(self, movie: dict):
        path = str(movie.get("path") or "").strip()
        if not path:
            return movie
        parsed = parse_video_filename(path)
        for key in (
            "category",
            "media_type",
            "franchise",
            "sort_bucket",
            "sort_title",
            "release_group",
            "resolution",
            "codec",
            "subtitle_info",
            "audio_info",
            "year_hint",
        ):
            if not movie.get(key) and parsed.get(key) not in (None, ""):
                movie[key] = parsed.get(key)
        return movie

    def _save_cache(self, movie_list):
        try:
            cache_data = []
            for movie in movie_list:
                cache_item = {
                    key: value
                    for key, value in movie.items()
                    if key
                    in [
                        "title",
                        "name",
                        "type",
                        "year",
                        "duration",
                        "director",
                        "actors",
                        "intro",
                        "is_series",
                        "episodes",
                        "episode_files",
                        "path",
                        "cover_path",
                        "season",
                        "remote_provider",
                        "source_label",
                        "category",
                        "media_type",
                        "franchise",
                        "sort_bucket",
                        "sort_title",
                        "release_group",
                        "resolution",
                        "codec",
                        "subtitle_info",
                        "audio_info",
                        "year_hint",
                    ]
                }
                cache_data.append(cache_item)

            with open(VideoLibraryManager._cache_file, "w", encoding="utf-8") as file:
                json.dump(cache_data, file, ensure_ascii=False, indent=2)
        except Exception as exc:  # noqa: BLE001
            logger.error("保存远程媒体库缓存失败: %s", exc)

    def update_movie_cover(self, movie_path, cover_path):
        if VideoLibraryManager._cached_list:
            for movie in VideoLibraryManager._cached_list:
                if movie.get("path") == movie_path:
                    movie["cover_path"] = cover_path
                    break
            self._save_cache(VideoLibraryManager._cached_list)

    def clear_cache(self):
        VideoLibraryManager._cached_list = None
        if VideoLibraryManager._cache_file and VideoLibraryManager._cache_file.exists():
            try:
                VideoLibraryManager._cache_file.unlink()
            except Exception:  # noqa: BLE001
                pass
