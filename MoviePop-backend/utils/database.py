import json
from pathlib import Path
from config.app_config import AppConfig


class VideoCache:
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
                    "cover_path": video.get("cover_path", "")
                }
                cache_data["videos"].append(cache_item)

            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存缓存失败: {e}")
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
                print("缓存服务器不匹配，跳过")
                return None

            video_list = cache_data.get("videos", [])
            if not self._is_valid_video_list(video_list):
                raise ValueError("视频列表格式错误")

            custom_info = self.get_all_custom_info()
            for video in video_list:
                if video.get("path") in custom_info:
                    video.update(custom_info[video["path"]])

            print(f"成功加载缓存，共 {len(video_list)} 个视频")
            return video_list

        except Exception as e:
            print(f"加载缓存失败: {e}，自动清除旧缓存")
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
                print("旧缓存已清除")
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
            print(f"添加收藏失败: {e}")

    def remove_favorite(self, movie_path):
        try:
            favorites = self.get_favorites()
            favorites = [item for item in favorites if item.get("path") != movie_path]
            with open(self.favorite_file, "w", encoding="utf-8") as f:
                json.dump(favorites, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"取消收藏失败: {e}")

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
            print(f"添加最近播放失败: {e}")

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
            print(f"清除最近播放失败: {e}")

    def save_custom_info(self, movie_path, custom_data):
        try:
            all_info = self.get_all_custom_info()
            all_info[movie_path] = custom_data
            with open(self.custom_info_file, "w", encoding="utf-8") as f:
                json.dump(all_info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存自定义信息失败: {e}")

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
        """
        更新单个视频的完整信息（用于刮削后更新封面和简介）
        :param movie_data: 包含 'path' 及要更新字段的字典
        :return: 是否成功
        """
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
                    # 只更新传入的字段，保留原有数据
                    video.update(movie_data)
                    updated = True
                    break

            if updated:
                self.save_cache(cache_data)
                return True
            return False
        except Exception as e:
            print(f"更新视频信息失败: {e}")
            return False

    def get_all_tags(self):
        """
        获取所有标签
        :return: 标签字典，格式为 {tag_name: count}
        """
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
        """
        获取电影的标签
        :param movie_path: 电影路径
        :return: 标签列表
        """
        all_tags = self.get_all_tags()
        movie_tags = []
        for tag, movies in all_tags.items():
            if isinstance(movies, list) and movie_path in movies:
                movie_tags.append(tag)
        return movie_tags

    def add_movie_tag(self, movie_path, tag):
        """
        为电影添加标签
        :param movie_path: 电影路径
        :param tag: 标签名称
        """
        try:
            all_tags = self.get_all_tags()
            if tag not in all_tags:
                all_tags[tag] = []
            if movie_path not in all_tags[tag]:
                all_tags[tag].append(movie_path)
            with open(self.tags_file, "w", encoding="utf-8") as f:
                json.dump(all_tags, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"添加标签失败: {e}")

    def remove_movie_tag(self, movie_path, tag):
        """
        从电影移除标签
        :param movie_path: 电影路径
        :param tag: 标签名称
        """
        try:
            all_tags = self.get_all_tags()
            if tag in all_tags and movie_path in all_tags[tag]:
                all_tags[tag].remove(movie_path)
                if not all_tags[tag]:
                    del all_tags[tag]
            with open(self.tags_file, "w", encoding="utf-8") as f:
                json.dump(all_tags, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"移除标签失败: {e}")

    def get_movies_by_tag(self, tag):
        """
        获取具有特定标签的电影
        :param tag: 标签名称
        :return: 电影路径列表
        """
        all_tags = self.get_all_tags()
        return all_tags.get(tag, [])

    def save_playback_progress(self, movie_path, progress, duration, episode_index=None):
        """
        保存视频播放进度
        :param movie_path: 电影路径
        :param progress: 播放进度（秒）
        :param duration: 视频总时长（秒）
        """
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
            print(f"保存播放进度失败: {e}")

    def get_playback_progress(self, movie_path):
        """
        获取视频播放进度
        :param movie_path: 电影路径
        :return: 播放进度字典，包含 progress、duration 和 timestamp
        """
        playback_data = self.get_all_playback_progress()
        return playback_data.get(movie_path, {})

    def get_all_playback_progress(self):
        """
        获取所有视频的播放进度
        :return: 播放进度字典
        """
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
        """
        清除视频播放进度
        :param movie_path: 电影路径，None 表示清除所有进度
        """
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
            print(f"清除播放进度失败: {e}")

    def _get_timestamp(self):
        """
        获取当前时间戳
        :return: 当前时间戳
        """
        import time
        return int(time.time())
