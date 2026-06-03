from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config.app_config import AppConfig
from utils.sqlite_storage import (
    SQLiteStorage,
    VideoDAO,
    FavoriteDAO,
    PlaybackDAO,
    TagDAO,
    RecentPlayDAO,
    ConfigDAO,
    FeedbackDAO,
    ProfileDAO,
    RecommendationDAO
)


class VideoCache:
    """
    视频缓存管理器 - 基于SQLite的统一数据存储适配器
    保持与原有API的向后兼容性
    """
    
    def __init__(self):
        self.config = AppConfig()
        self.storage = SQLiteStorage()
        
        # 初始化各个数据访问对象
        self.video_dao = VideoDAO(self.storage)
        self.favorite_dao = FavoriteDAO(self.storage)
        self.playback_dao = PlaybackDAO(self.storage)
        self.tag_dao = TagDAO(self.storage)
        self.recent_dao = RecentPlayDAO(self.storage)
        self.config_dao = ConfigDAO(self.storage)
        self.feedback_dao = FeedbackDAO(self.storage)
        self.profile_dao = ProfileDAO(self.storage)
        self.recommendation_dao = RecommendationDAO(self.storage)
    
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
        """保存视频缓存"""
        try:
            webdav_host = self.config.WEBDAV_HOST
            
            for video in video_list:
                if not isinstance(video, dict):
                    continue
                
                # 确保字典值不包含None
                video_copy = {}
                for k, v in video.items():
                    # SQLite不能存储None，需要转换
                    if v is None:
                        if isinstance(v, str):
                            video_copy[k] = ""
                        elif isinstance(v, int):
                            video_copy[k] = 0
                        elif isinstance(v, float):
                            video_copy[k] = 0.0
                        else:
                            video_copy[k] = ""
                    else:
                        # 复杂类型转JSON字符串
                        if isinstance(v, (dict, list)):
                            video_copy[k] = json.dumps(v)
                        else:
                            video_copy[k] = v
                
                video_copy['webdav_host'] = webdav_host
                self.video_dao.insert_video(video_copy)
            
            # 保存webdav_host到配置
            self.config_dao.set_config('webdav_host', webdav_host)
            self.config_dao.set_config('cache_version', 2)
            
            return True
        except Exception as e:
            print(f"保存缓存失败: {e}")
            return False
    
    def load_cache(self):
        """加载视频缓存"""
        try:
            cached_host = self.config_dao.get_config('webdav_host', '')
            
            if cached_host != self.config.WEBDAV_HOST:
                print("缓存服务器不匹配，跳过")
                return None
            
            videos = self.video_dao.get_all_videos()
            
            # 解析JSON字段
            for video in videos:
                for field in ['episodes', 'episode_files', 'tags', 'inferred_tags', 'manual_tags', 'playback']:
                    if field in video and video[field]:
                        try:
                            video[field] = json.loads(video[field])
                        except json.JSONDecodeError:
                            video[field] = [] if field in ['episodes', 'episode_files', 'tags', 'inferred_tags', 'manual_tags'] else {}
            
            print(f"成功加载缓存，共 {len(videos)} 个视频")
            return videos
        
        except Exception as e:
            print(f"加载缓存失败: {e}")
            return None
    
    def update_video_cover(self, video_path, cover_path):
        """更新视频封面"""
        self.video_dao.update_video(video_path, {'cover_path': cover_path})
    
    def clear_cache(self):
        """清除缓存"""
        try:
            # 删除所有视频记录
            self.storage.execute("DELETE FROM videos")
            self.storage.execute("DELETE FROM favorites")
            self.storage.execute("DELETE FROM playback_progress")
            self.storage.execute("DELETE FROM video_tags")
            self.storage.execute("DELETE FROM recent_play")
            print("缓存已清除")
        except Exception as e:
            print(f"清除缓存失败: {e}")
    
    def add_favorite(self, movie_data):
        """添加收藏"""
        try:
            movie_path = movie_data.get("path")
            if not movie_path:
                return
            
            # 先确保视频存在
            existing = self.video_dao.get_video_by_path(movie_path)
            if not existing:
                self.video_dao.insert_video(movie_data)
            
            self.favorite_dao.add_favorite(movie_path)
        except Exception as e:
            print(f"添加收藏失败: {e}")
    
    def remove_favorite(self, movie_path):
        """移除收藏"""
        try:
            self.favorite_dao.remove_favorite(movie_path)
        except Exception as e:
            print(f"取消收藏失败: {e}")
    
    def get_favorites(self):
        """获取收藏列表"""
        try:
            favorites = self.favorite_dao.get_favorites()
            # 解析JSON字段
            for video in favorites:
                for field in ['episodes', 'episode_files', 'tags', 'inferred_tags', 'manual_tags', 'playback']:
                    if field in video and video[field]:
                        try:
                            video[field] = json.loads(video[field])
                        except json.JSONDecodeError:
                            video[field] = [] if field in ['episodes', 'episode_files', 'tags', 'inferred_tags', 'manual_tags'] else {}
            return favorites
        except Exception as e:
            print(f"获取收藏失败: {e}")
            return []
    
    def is_favorite(self, movie_path):
        """检查是否已收藏"""
        return self.favorite_dao.is_favorite(movie_path)
    
    def add_recent_play(self, movie_data):
        """添加最近播放"""
        try:
            movie_path = movie_data.get("path")
            if not movie_path:
                return
            
            # 先确保视频存在
            existing = self.video_dao.get_video_by_path(movie_path)
            if not existing:
                self.video_dao.insert_video(movie_data)
            
            self.recent_dao.add_recent_play(movie_path)
        except Exception as e:
            print(f"添加最近播放失败: {e}")
    
    def get_recent_play(self):
        """获取最近播放列表"""
        try:
            recent = self.recent_dao.get_recent_play(limit=100)
            # 解析JSON字段
            for video in recent:
                for field in ['episodes', 'episode_files', 'tags', 'inferred_tags', 'manual_tags', 'playback']:
                    if field in video and video[field]:
                        try:
                            video[field] = json.loads(video[field])
                        except json.JSONDecodeError:
                            video[field] = [] if field in ['episodes', 'episode_files', 'tags', 'inferred_tags', 'manual_tags'] else {}
            return recent
        except Exception as e:
            print(f"获取最近播放失败: {e}")
            return []
    
    def clear_recent_play(self):
        """清除最近播放"""
        try:
            self.recent_dao.clear_recent_play()
        except Exception as e:
            print(f"清除最近播放失败: {e}")
    
    def save_custom_info(self, movie_path, custom_data):
        """保存自定义信息"""
        try:
            # 获取现有信息
            existing = self.video_dao.get_video_by_path(movie_path)
            if existing:
                # 合并自定义数据
                update_data = {}
                for k, v in custom_data.items():
                    if isinstance(v, (dict, list)):
                        update_data[k] = json.dumps(v)
                    else:
                        update_data[k] = v
                self.video_dao.update_video(movie_path, update_data)
        except Exception as e:
            print(f"保存自定义信息失败: {e}")
    
    def get_custom_info(self, movie_path):
        """获取自定义信息"""
        video = self.video_dao.get_video_by_path(movie_path)
        if video:
            return video
        return {}
    
    def get_all_custom_info(self):
        """获取所有自定义信息"""
        videos = self.video_dao.get_all_videos()
        result = {}
        for video in videos:
            result[video.get('path', '')] = video
        return result
    
    def update_movie(self, movie_data):
        """更新视频信息"""
        try:
            target_path = movie_data.get("path")
            if not target_path:
                return False
            
            update_data = {}
            for k, v in movie_data.items():
                if v is None:
                    continue
                if isinstance(v, (dict, list)):
                    update_data[k] = json.dumps(v)
                else:
                    update_data[k] = v
            
            if update_data:
                self.video_dao.update_video(target_path, update_data)
                return True
            return False
        except Exception as e:
            print(f"更新视频信息失败: {e}")
            return False
    
    def get_all_tags(self):
        """获取所有标签"""
        try:
            tags = self.tag_dao.get_all_tags()
            result = {}
            for tag in tags:
                # 获取标签关联的视频数量
                count = len(self.tag_dao.get_movies_by_tag(tag['name']))
                result[tag['name']] = count
            return result
        except Exception as e:
            print(f"获取标签失败: {e}")
            return {}
    
    def get_movie_tags(self, movie_path):
        """获取电影标签"""
        return self.tag_dao.get_video_tags(movie_path)
    
    def add_movie_tag(self, movie_path, tag):
        """添加电影标签"""
        try:
            self.tag_dao.add_video_tag(movie_path, tag)
        except Exception as e:
            print(f"添加标签失败: {e}")
    
    def remove_movie_tag(self, movie_path, tag):
        """移除电影标签"""
        try:
            self.tag_dao.remove_video_tag(movie_path, tag)
        except Exception as e:
            print(f"移除标签失败: {e}")
    
    def get_movies_by_tag(self, tag):
        """获取具有指定标签的电影"""
        try:
            movies = self.tag_dao.get_movies_by_tag(tag)
            for movie in movies:
                for field in ['episodes', 'episode_files', 'tags', 'inferred_tags', 'manual_tags', 'playback']:
                    if field in movie and movie[field]:
                        try:
                            movie[field] = json.loads(movie[field])
                        except json.JSONDecodeError:
                            movie[field] = [] if field in ['episodes', 'episode_files', 'tags', 'inferred_tags', 'manual_tags'] else {}
            return [m['path'] for m in movies]
        except Exception as e:
            print(f"获取标签电影失败: {e}")
            return []
    
    def save_playback_progress(self, movie_path, progress, duration, episode_index=None):
        """保存播放进度"""
        try:
            self.playback_dao.save_progress(movie_path, progress, duration, episode_index or 0)
        except Exception as e:
            print(f"保存播放进度失败: {e}")
    
    def get_playback_progress(self, movie_path):
        """获取播放进度"""
        progress = self.playback_dao.get_progress(movie_path)
        if progress:
            return {
                'progress': progress.get('progress', 0),
                'duration': progress.get('duration', 0),
                'episode_index': progress.get('episode_index', 0),
                'timestamp': progress.get('timestamp', 0)
            }
        return {}
    
    def get_all_playback_progress(self):
        """获取所有播放进度"""
        progress_list = self.playback_dao.get_all_progress()
        result = {}
        for p in progress_list:
            result[p['video_path']] = {
                'progress': p.get('progress', 0),
                'duration': p.get('duration', 0),
                'episode_index': p.get('episode_index', 0),
                'timestamp': p.get('timestamp', 0)
            }
        return result
    
    def clear_playback_progress(self, movie_path=None):
        """清除播放进度"""
        try:
            self.playback_dao.clear_progress(movie_path)
        except Exception as e:
            print(f"清除播放进度失败: {e}")
    
    def _get_timestamp(self):
        """获取时间戳"""
        import time
        return int(time.time())
    
    # 备份与恢复方法
    def backup_database(self, backup_path=None):
        """备份数据库"""
        return self.storage.backup(backup_path)
    
    def restore_database(self, backup_path):
        """恢复数据库"""
        return self.storage.restore(backup_path)
    
    def optimize_database(self):
        """优化数据库"""
        self.storage.vacuum()
    
    def get_database_size(self):
        """获取数据库大小"""
        return self.storage.get_db_size()