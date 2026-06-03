from __future__ import annotations

import json
import time
from typing import Any, Optional

from utils.sqlite_storage import SQLiteStorage, FeedbackDAO, ProfileDAO, RecommendationDAO


class RecommendationRepository:
    """
    推荐系统数据仓库 - 基于SQLite存储
    """
    
    def __init__(self):
        self.storage = SQLiteStorage()
        self.feedback_dao = FeedbackDAO(self.storage)
        self.profile_dao = ProfileDAO(self.storage)
        self.recommendation_dao = RecommendationDAO(self.storage)
    
    def upsert_feedback(self, movie_path: str, **kwargs):
        """更新或插入用户反馈"""
        return self.feedback_dao.upsert_feedback(movie_path, **kwargs)
    
    def get_feedback_map(self) -> dict[str, dict]:
        """获取所有反馈数据"""
        return self.feedback_dao.get_feedback_map()
    
    def save_tags(self, movie_path: str, tags: list[tuple[str, float]]):
        """保存标签"""
        from utils.sqlite_storage import TagDAO
        tag_dao = TagDAO(self.storage)
        for tag_name, weight in tags:
            tag_dao.add_video_tag(movie_path, tag_name, weight)
    
    def get_tags(self, movie_path: str) -> list[tuple[str, float]]:
        """获取标签"""
        from utils.sqlite_storage import TagDAO
        tag_dao = TagDAO(self.storage)
        tags = tag_dao.get_video_tags(movie_path)
        return [(tag, 1.0) for tag in tags]
    
    def get_tags_map(self) -> dict[str, list[str]]:
        """获取所有视频的标签映射"""
        from utils.sqlite_storage import TagDAO
        tag_dao = TagDAO(self.storage)
        
        # 获取所有视频标签关联
        rows = self.storage.query(
            """
            SELECT vt.video_path, vt.tag_name, t.name 
            FROM video_tags vt
            JOIN tags t ON vt.tag_name = t.name
            ORDER BY vt.video_path, vt.weight DESC
            """
        )
        
        tag_map = {}
        for row in rows:
            path = row['video_path']
            tag = row['tag_name']
            if path not in tag_map:
                tag_map[path] = []
            tag_map[path].append(tag)
        
        return tag_map
    
    def save_profile(self, profile: dict):
        """保存用户画像"""
        return self.profile_dao.save_profile(profile)
    
    def load_profile(self) -> dict:
        """加载用户画像"""
        return self.profile_dao.load_profile()
    
    def save_recommendations(self, items: list[dict]):
        """保存推荐结果"""
        return self.recommendation_dao.save_recommendations(items)
    
    def load_recommendations(self, limit: int = 24) -> dict:
        """加载推荐结果"""
        return self.recommendation_dao.load_recommendations(limit)
    
    def save_external_recommendations(self, items: list[dict]):
        """保存外部推荐结果"""
        return self.recommendation_dao.save_external_recommendations(items)
    
    def load_external_recommendations(self, limit: int = 12) -> dict:
        """加载外部推荐结果"""
        return self.recommendation_dao.load_external_recommendations(limit)