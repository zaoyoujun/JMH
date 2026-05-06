import json
from pathlib import Path

from config.app_config import AppConfig
from utils.filename_parser import merge_series_videos
from utils.logger import get_logger

logger = get_logger()


class LocalVideoLibraryManager:
    _cached_list = None
    _cache_file = None

    def __init__(self):
        self.config = AppConfig()
        if LocalVideoLibraryManager._cache_file is None:
            LocalVideoLibraryManager._cache_file = self.config.DATA_DIR / "local_video_library_cache.json"

    def get_video_list(self, force_refresh=False):
        if not force_refresh and LocalVideoLibraryManager._cached_list is not None:
            logger.info("使用本地媒体库内存缓存")
            return LocalVideoLibraryManager._cached_list

        if not force_refresh and self._has_valid_cache():
            logger.info("读取本地媒体库缓存")
            LocalVideoLibraryManager._cached_list = self._load_cache()
            return LocalVideoLibraryManager._cached_list

        video_files = self._scan_local_dirs()
        if not video_files:
            logger.warning("本地目录扫描为空")
            if self._has_valid_cache():
                return self._load_cache()
            return []

        movie_list = merge_series_videos(video_files)
        self._save_cache(movie_list)
        LocalVideoLibraryManager._cached_list = movie_list
        logger.info("本地媒体库扫描完成: %s", len(movie_list))
        return movie_list

    def _scan_local_dirs(self):
        all_files = []
        for dir_path in self.config.LOCAL_MOUNT_DIRS:
            root_path = Path(dir_path)
            if not root_path.exists() or not root_path.is_dir():
                logger.warning("本地目录不存在: %s", dir_path)
                continue

            queue = [(root_path, 0)]
            while queue:
                current_path, current_depth = queue.pop(0)
                try:
                    for child in current_path.iterdir():
                        if child.is_dir():
                            if current_depth < self.config.LOCAL_SCAN_MAX_DEPTH:
                                queue.append((child, current_depth + 1))
                            continue

                        if child.suffix.lower() in self.config.VIDEO_FORMATS:
                            all_files.append(str(child.resolve()))
                except Exception as exc:  # noqa: BLE001
                    logger.error("扫描本地目录失败 %s: %s", current_path, exc)
        return all_files

    def _has_valid_cache(self):
        if not LocalVideoLibraryManager._cache_file.exists():
            return False
        try:
            with open(LocalVideoLibraryManager._cache_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            return isinstance(data, list) and len(data) > 0
        except Exception:  # noqa: BLE001
            return False

    def _load_cache(self):
        try:
            with open(LocalVideoLibraryManager._cache_file, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:  # noqa: BLE001
            return []

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
                    ]
                }
                cache_data.append(cache_item)

            with open(LocalVideoLibraryManager._cache_file, "w", encoding="utf-8") as file:
                json.dump(cache_data, file, ensure_ascii=False, indent=2)
        except Exception as exc:  # noqa: BLE001
            logger.error("保存本地媒体库缓存失败: %s", exc)

    def update_movie_cover(self, movie_path, cover_path):
        if LocalVideoLibraryManager._cached_list:
            for movie in LocalVideoLibraryManager._cached_list:
                if movie.get("path") == movie_path:
                    movie["cover_path"] = cover_path
                    break
            self._save_cache(LocalVideoLibraryManager._cached_list)

    def clear_cache(self):
        LocalVideoLibraryManager._cached_list = None
        if LocalVideoLibraryManager._cache_file and LocalVideoLibraryManager._cache_file.exists():
            try:
                LocalVideoLibraryManager._cache_file.unlink()
            except Exception:  # noqa: BLE001
                pass
