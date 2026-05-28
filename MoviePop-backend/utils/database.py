import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.app_config import AppConfig
from utils.logger import get_logger

logger = get_logger()


class VideoCacheBase:
    def save_cache(self, video_list: List[Dict[str, Any]]) -> bool:
        raise NotImplementedError

    def load_cache(self) -> Optional[List[Dict[str, Any]]]:
        raise NotImplementedError

    def update_video_cover(self, video_path: str, cover_path: str) -> None:
        raise NotImplementedError

    def clear_cache(self) -> None:
        raise NotImplementedError

    def add_favorite(self, movie_data: Dict[str, Any]) -> None:
        raise NotImplementedError

    def remove_favorite(self, movie_path: str) -> None:
        raise NotImplementedError

    def get_favorites(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def is_favorite(self, movie_path: str) -> bool:
        raise NotImplementedError

    def add_recent_play(self, movie_data: Dict[str, Any]) -> None:
        raise NotImplementedError

    def get_recent_play(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def clear_recent_play(self) -> None:
        raise NotImplementedError

    def save_custom_info(self, movie_path: str, custom_data: Dict[str, Any]) -> None:
        raise NotImplementedError

    def get_custom_info(self, movie_path: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_all_custom_info(self) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError

    def update_movie(self, movie_data: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def get_all_tags(self) -> Dict[str, int]:
        raise NotImplementedError

    def get_movie_tags(self, movie_path: str) -> List[str]:
        raise NotImplementedError

    def add_movie_tag(self, movie_path: str, tag: str) -> None:
        raise NotImplementedError

    def remove_movie_tag(self, movie_path: str, tag: str) -> None:
        raise NotImplementedError

    def get_movies_by_tag(self, tag: str) -> List[str]:
        raise NotImplementedError

    def save_playback_progress(self, movie_path: str, progress: int, duration: int, episode_index: int = None) -> None:
        raise NotImplementedError

    def get_playback_progress(self, movie_path: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_all_playback_progress(self) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError

    def clear_playback_progress(self, movie_path: str = None) -> None:
        raise NotImplementedError


class VideoCacheJson(VideoCacheBase):
    def __init__(self):
        self.config = AppConfig()
        self.cache_file = self.config.DATA_DIR / "video_cache.json"
        self.favorite_file = self.config.DATA_DIR / "favorite.json"
        self.recent_file = self.config.DATA_DIR / "recent_play.json"
        self.custom_info_file = self.config.DATA_DIR / "custom_movie_info.json"
        self.tags_file = self.config.DATA_DIR / "movie_tags.json"
        self.playback_file = self.config.DATA_DIR / "playback_progress.json"

    def _is_valid_video_list(self, data):
        if not isinstance(data, list):
            return False
        for item in data:
            if not isinstance(item, dict):
                return False
            if "path" not in item or "title" not in item:
                return False
        return True

    def save_cache(self, video_list):
        try:
            cache_data = {
                "webdav_host": self.config.WEBDAV_HOST,
                "version": 2,
                "videos": []
            }
            for video in video_list:
                if not isinstance(video, dict):
                    continue
                cache_item = {
                    "title": video.get("title", ""),
                    "name": video.get("name", ""),
                    "type": video.get("type", "视频"),
                    "year": video.get("year", 2024),
                    "duration": video.get("duration", "未知"),
                    "director": video.get("director", "未知"),
                    "actors": video.get("actors", "未知"),
                    "intro": video.get("intro", ""),
                    "is_series": video.get("is_series", False),
                    "episodes": video.get("episodes", []),
                    "episode_files": video.get("episode_files", []),
                    "path": video.get("path", ""),
                    "cover_path": video.get("cover_path", ""),
                    "series_title": video.get("series_title", ""),
                    "season_title": video.get("season_title", ""),
                    "special_type": video.get("special_type", ""),
                    "part": video.get("part", 0),
                    "season": video.get("season", 0),
                    "category": video.get("category", ""),
                    "franchise": video.get("franchise", ""),
                    "sort_bucket": video.get("sort_bucket", 9),
                    "sort_title": video.get("sort_title", ""),
                    "year_hint": video.get("year_hint", 0),
                    "rating": video.get("rating", 0.0),
                    "remote_provider": video.get("remote_provider", ""),
                    "source_label": video.get("source_label", ""),
                    "resolution": video.get("resolution", ""),
                    "video_codec": video.get("video_codec", ""),
                    "audio_info": video.get("audio_info", ""),
                    "subtitle_info": video.get("subtitle_info", ""),
                    "release_group": video.get("release_group", ""),
                    "cover_url": video.get("cover_url", ""),
                    "last_play_time": video.get("last_play_time", ""),
                    "is_favorite": video.get("is_favorite", False),
                    "tags": video.get("tags", []),
                    "inferred_tags": video.get("inferred_tags", []),
                    "manual_tags": video.get("manual_tags", []),
                    "playback": video.get("playback", {}),
                    "episode_count": video.get("episode_count", 0),
                }
                cache_data["videos"].append(cache_item)

            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
            return False

    def load_cache(self):
        if not self.cache_file.exists():
            return None
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            if not isinstance(cache_data, dict):
                raise ValueError("缓存格式错误")

            if cache_data.get("webdav_host") != self.config.WEBDAV_HOST:
                logger.info("缓存服务器不匹配，跳过")
                return None

            video_list = cache_data.get("videos", [])
            if not self._is_valid_video_list(video_list):
                raise ValueError("视频列表格式错误")

            custom_info = self.get_all_custom_info()
            for video in video_list:
                if video.get("path") in custom_info:
                    video.update(custom_info[video["path"]])

            logger.info(f"成功加载缓存，共 {len(video_list)} 个视频")
            return video_list

        except Exception as e:
            logger.error(f"加载缓存失败: {e}，自动清除旧缓存")
            self.clear_cache()
            return None

    def update_video_cover(self, video_path, cover_path):
        cache_data = self.load_cache()
        if not cache_data:
            return
        for video in cache_data:
            if video.get("path") == video_path:
                video["cover_path"] = cover_path
                break
        self.save_cache(cache_data)

    def clear_cache(self):
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
                logger.info("旧缓存已清除")
            except:
                pass

    def add_favorite(self, movie_data):
        try:
            favorites = self.get_favorites()
            for item in favorites:
                if item.get("path") == movie_data.get("path"):
                    return
            favorites.append(movie_data)
            with open(self.favorite_file, "w", encoding="utf-8") as f:
                json.dump(favorites, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"添加收藏失败: {e}")

    def remove_favorite(self, movie_path):
        try:
            favorites = self.get_favorites()
            favorites = [item for item in favorites if item.get("path") != movie_path]
            with open(self.favorite_file, "w", encoding="utf-8") as f:
                json.dump(favorites, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"取消收藏失败: {e}")

    def get_favorites(self):
        if not self.favorite_file.exists():
            return []
        try:
            with open(self.favorite_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except:
            pass
        return []

    def is_favorite(self, movie_path):
        favorites = self.get_favorites()
        for item in favorites:
            if item.get("path") == movie_path:
                return True
        return False

    def add_recent_play(self, movie_data):
        try:
            recent = self.get_recent_play()
            recent = [item for item in recent if item.get("path") != movie_data.get("path")]
            recent.insert(0, movie_data)
            recent = recent[:100]
            with open(self.recent_file, "w", encoding="utf-8") as f:
                json.dump(recent, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"添加最近播放失败: {e}")

    def get_recent_play(self):
        if not self.recent_file.exists():
            return []
        try:
            with open(self.recent_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except:
            pass
        return []

    def clear_recent_play(self):
        try:
            if self.recent_file.exists():
                self.recent_file.unlink()
        except Exception as e:
            logger.error(f"清除最近播放失败: {e}")

    def save_custom_info(self, movie_path, custom_data):
        try:
            all_info = self.get_all_custom_info()
            all_info[movie_path] = custom_data
            with open(self.custom_info_file, "w", encoding="utf-8") as f:
                json.dump(all_info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存自定义信息失败: {e}")

    def get_custom_info(self, movie_path):
        all_info = self.get_all_custom_info()
        return all_info.get(movie_path, {})

    def get_all_custom_info(self):
        if not self.custom_info_file.exists():
            return {}
        try:
            with open(self.custom_info_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except:
            pass
        return {}

    def update_movie(self, movie_data):
        try:
            cache_data = self.load_cache()
            if not cache_data:
                return False

            target_path = movie_data.get("path")
            if not target_path:
                return False

            updated = False
            for video in cache_data:
                if video.get("path") == target_path:
                    video.update(movie_data)
                    updated = True
                    break

            if updated:
                self.save_cache(cache_data)
                return True
            return False
        except Exception as e:
            logger.error(f"更新视频信息失败: {e}")
            return False

    def get_all_tags(self):
        if not self.tags_file.exists():
            return {}
        try:
            with open(self.tags_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except:
            pass
        return {}

    def get_movie_tags(self, movie_path):
        all_tags = self.get_all_tags()
        movie_tags = []
        for tag, movies in all_tags.items():
            if isinstance(movies, list) and movie_path in movies:
                movie_tags.append(tag)
        return movie_tags

    def add_movie_tag(self, movie_path, tag):
        try:
            all_tags = self.get_all_tags()
            if tag not in all_tags:
                all_tags[tag] = []
            if movie_path not in all_tags[tag]:
                all_tags[tag].append(movie_path)
            with open(self.tags_file, "w", encoding="utf-8") as f:
                json.dump(all_tags, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"添加标签失败: {e}")

    def remove_movie_tag(self, movie_path, tag):
        try:
            all_tags = self.get_all_tags()
            if tag in all_tags and movie_path in all_tags[tag]:
                all_tags[tag].remove(movie_path)
                if not all_tags[tag]:
                    del all_tags[tag]
            with open(self.tags_file, "w", encoding="utf-8") as f:
                json.dump(all_tags, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"移除标签失败: {e}")

    def get_movies_by_tag(self, tag):
        all_tags = self.get_all_tags()
        return all_tags.get(tag, [])

    def save_playback_progress(self, movie_path, progress, duration, episode_index=None):
        try:
            playback_data = self.get_all_playback_progress()
            playback_data[movie_path] = {
                "progress": progress,
                "duration": duration,
                "episode_index": int(episode_index or 0),
                "timestamp": self._get_timestamp()
            }
            with open(self.playback_file, "w", encoding="utf-8") as f:
                json.dump(playback_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存播放进度失败: {e}")

    def get_playback_progress(self, movie_path):
        playback_data = self.get_all_playback_progress()
        return playback_data.get(movie_path, {})

    def get_all_playback_progress(self):
        if not self.playback_file.exists():
            return {}
        try:
            with open(self.playback_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except:
            pass
        return {}

    def clear_playback_progress(self, movie_path=None):
        try:
            if movie_path:
                playback_data = self.get_all_playback_progress()
                if movie_path in playback_data:
                    del playback_data[movie_path]
                with open(self.playback_file, "w", encoding="utf-8") as f:
                    json.dump(playback_data, f, ensure_ascii=False, indent=2)
            else:
                if self.playback_file.exists():
                    self.playback_file.unlink()
        except Exception as e:
            logger.error(f"清除播放进度失败: {e}")

    def _get_timestamp(self):
        import time
        return int(time.time())


class VideoCacheSQLite(VideoCacheBase):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        from utils.sqlite_dao import SQLiteVideoCache
        self.cache = SQLiteVideoCache()
        self._initialized = True

    @classmethod
    def reset(cls):
        """Reset the cache instance and close database connection."""
        from utils.sqlite_connection import get_sqlite_connection
        conn = get_sqlite_connection()
        conn.reset()
        cls._instance = None
        logger.info("VideoCacheSQLite reset completed")

    def save_cache(self, video_list: List[Dict[str, Any]]) -> bool:
        return self.cache.save_cache(video_list)

    def load_cache(self) -> Optional[List[Dict[str, Any]]]:
        return self.cache.load_cache()

    def update_video_cover(self, video_path: str, cover_path: str) -> None:
        self.cache.update_video_cover(video_path, cover_path)

    def clear_cache(self) -> None:
        self.cache.clear_cache()

    def add_favorite(self, movie_data: Dict[str, Any]) -> None:
        self.cache.add_favorite(movie_data)

    def remove_favorite(self, movie_path: str) -> None:
        self.cache.remove_favorite(movie_path)

    def get_favorites(self) -> List[Dict[str, Any]]:
        return self.cache.get_favorites()

    def is_favorite(self, movie_path: str) -> bool:
        return self.cache.is_favorite(movie_path)

    def add_recent_play(self, movie_data: Dict[str, Any]) -> None:
        self.cache.add_recent_play(movie_data)

    def get_recent_play(self) -> List[Dict[str, Any]]:
        return self.cache.get_recent_play()

    def clear_recent_play(self) -> None:
        self.cache.clear_recent_play()

    def save_custom_info(self, movie_path: str, custom_data: Dict[str, Any]) -> None:
        self.cache.save_custom_info(movie_path, custom_data)

    def get_custom_info(self, movie_path: str) -> Dict[str, Any]:
        return self.cache.get_custom_info(movie_path)

    def get_all_custom_info(self) -> Dict[str, Dict[str, Any]]:
        return self.cache.get_all_custom_info()

    def update_movie(self, movie_data: Dict[str, Any]) -> bool:
        return self.cache.update_movie(movie_data)

    def get_all_tags(self) -> Dict[str, int]:
        return self.cache.get_all_tags()

    def get_movie_tags(self, movie_path: str) -> List[str]:
        return self.cache.get_movie_tags(movie_path)

    def add_movie_tag(self, movie_path: str, tag: str) -> None:
        self.cache.add_movie_tag(movie_path, tag)

    def remove_movie_tag(self, movie_path: str, tag: str) -> None:
        self.cache.remove_movie_tag(movie_path, tag)

    def get_movies_by_tag(self, tag: str) -> List[str]:
        return self.cache.get_movies_by_tag(tag)

    def save_playback_progress(self, movie_path: str, progress: int, duration: int, episode_index: int = None) -> bool:
        return self.cache.save_playback_progress(movie_path, progress, duration, episode_index)

    def get_playback_progress(self, movie_path: str) -> Dict[str, Any]:
        return self.cache.get_playback_progress(movie_path)

    def get_all_playback_progress(self) -> Dict[str, Dict[str, Any]]:
        return self.cache.get_all_playback_progress()

    def clear_playback_progress(self, movie_path: str = None) -> bool:
        return self.cache.clear_playback_progress(movie_path)


class VideoCache:
    _instance = None
    _cache: Optional[VideoCacheBase] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self.config = AppConfig()
        self._initialized = True

    @classmethod
    def reset(cls):
        """Reset the cache and close database connections for clean shutdown."""
        VideoCacheSQLite.reset()
        cls._instance = None
        cls._cache = None
        logger.info("VideoCache reset completed")

    def _get_cache(self) -> VideoCacheBase:
        if self._cache is None:
            self._initialize_sqlite()
        return self._cache

    def _initialize_sqlite(self):
        try:
            from utils.sqlite_initializer import init_sqlite_database
            if init_sqlite_database():
                self._cache = VideoCacheSQLite()
                logger.info("Using SQLite cache (built-in)")
            else:
                self._cache = VideoCacheJson()
                logger.warning("SQLite initialization failed, falling back to JSON cache")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite cache: {e}, falling back to JSON")
            self._cache = VideoCacheJson()

    def save_cache(self, video_list: List[Dict[str, Any]]) -> bool:
        return self._get_cache().save_cache(video_list)

    def load_cache(self) -> Optional[List[Dict[str, Any]]]:
        return self._get_cache().load_cache()

    def update_video_cover(self, video_path: str, cover_path: str) -> None:
        self._get_cache().update_video_cover(video_path, cover_path)

    def clear_cache(self) -> None:
        self._get_cache().clear_cache()

    def add_favorite(self, movie_data: Dict[str, Any]) -> None:
        self._get_cache().add_favorite(movie_data)

    def remove_favorite(self, movie_path: str) -> None:
        self._get_cache().remove_favorite(movie_path)

    def get_favorites(self) -> List[Dict[str, Any]]:
        return self._get_cache().get_favorites()

    def is_favorite(self, movie_path: str) -> bool:
        return self._get_cache().is_favorite(movie_path)

    def add_recent_play(self, movie_data: Dict[str, Any]) -> None:
        self._get_cache().add_recent_play(movie_data)

    def get_recent_play(self) -> List[Dict[str, Any]]:
        return self._get_cache().get_recent_play()

    def clear_recent_play(self) -> None:
        self._get_cache().clear_recent_play()

    def save_custom_info(self, movie_path: str, custom_data: Dict[str, Any]) -> None:
        self._get_cache().save_custom_info(movie_path, custom_data)

    def get_custom_info(self, movie_path: str) -> Dict[str, Any]:
        return self._get_cache().get_custom_info(movie_path)

    def get_all_custom_info(self) -> Dict[str, Dict[str, Any]]:
        return self._get_cache().get_all_custom_info()

    def update_movie(self, movie_data: Dict[str, Any]) -> bool:
        return self._get_cache().update_movie(movie_data)

    def get_all_tags(self) -> Dict[str, int]:
        return self._get_cache().get_all_tags()

    def get_movie_tags(self, movie_path: str) -> List[str]:
        return self._get_cache().get_movie_tags(movie_path)

    def add_movie_tag(self, movie_path: str, tag: str) -> None:
        self._get_cache().add_movie_tag(movie_path, tag)

    def remove_movie_tag(self, movie_path: str, tag: str) -> None:
        self._get_cache().remove_movie_tag(movie_path, tag)

    def get_movies_by_tag(self, tag: str) -> List[str]:
        return self._get_cache().get_movies_by_tag(tag)

    def save_playback_progress(self, movie_path: str, progress: int, duration: int, episode_index: int = None) -> bool:
        return self._get_cache().save_playback_progress(movie_path, progress, duration, episode_index)

    def get_playback_progress(self, movie_path: str) -> Dict[str, Any]:
        return self._get_cache().get_playback_progress(movie_path)

    def get_all_playback_progress(self) -> Dict[str, Dict[str, Any]]:
        return self._get_cache().get_all_playback_progress()

    def clear_playback_progress(self, movie_path: str = None) -> bool:
        return self._get_cache().clear_playback_progress(movie_path)