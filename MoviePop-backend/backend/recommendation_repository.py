from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from config.app_config import AppConfig


class RecommendationRepository:
    """
    推荐数据存储库 - 用于存储用户偏好、标签和反馈数据
    """

    def __init__(self) -> None:
        config = AppConfig()
        config.load_config()
        self.db_path = config.DATA_DIR / "recommendations.sqlite3"
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    movie_path TEXT PRIMARY KEY,
                    rating REAL,
                    watch_count INTEGER DEFAULT 0,
                    last_watched INTEGER DEFAULT 0,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tags (
                    movie_path TEXT,
                    tag TEXT,
                    weight REAL DEFAULT 1.0,
                    PRIMARY KEY (movie_path, tag)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profile (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT,
                    generated_at INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS external_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT,
                    generated_at INTEGER
                )
                """
            )
            conn.commit()

    def upsert_feedback(self, movie_path: str, **kwargs: Any) -> None:
        """更新或插入反馈数据"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO feedback (movie_path, rating, watch_count, last_watched)
                VALUES (?, COALESCE(?, (SELECT rating FROM feedback WHERE movie_path = ?)),
                        COALESCE(?, (SELECT watch_count FROM feedback WHERE movie_path = ?)),
                        COALESCE(?, (SELECT last_watched FROM feedback WHERE movie_path = ?)))
                """,
                (
                    movie_path,
                    kwargs.get("rating"),
                    movie_path,
                    kwargs.get("watch_count"),
                    movie_path,
                    kwargs.get("last_watched"),
                    movie_path,
                ),
            )
            conn.commit()

    def get_feedback_map(self) -> dict[str, dict[str, Any]]:
        """获取所有反馈数据"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT movie_path, rating, watch_count, last_watched FROM feedback")
            result = {}
            for row in cursor.fetchall():
                result[row[0]] = {
                    "rating": row[1],
                    "watch_count": row[2] or 0,
                    "last_watched": row[3] or 0,
                }
            return result

    def save_tags(self, movie_path: str, tags: list[str]) -> None:
        """保存电影标签"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM tags WHERE movie_path = ?", (movie_path,))
            for tag in tags:
                conn.execute("INSERT INTO tags (movie_path, tag) VALUES (?, ?)", (movie_path, tag))
            conn.commit()

    def get_tags(self, movie_path: str) -> list[str]:
        """获取电影标签"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT tag FROM tags WHERE movie_path = ?", (movie_path,))
            return [row[0] for row in cursor.fetchall()]

    def save_profile(self, profile: dict[str, Any]) -> None:
        """保存用户配置文件"""
        with sqlite3.connect(self.db_path) as conn:
            for key, value in profile.items():
                conn.execute(
                    "INSERT OR REPLACE INTO profile (key, value) VALUES (?, ?)",
                    (key, json.dumps(value)),
                )
            conn.commit()

    def load_profile(self) -> dict[str, Any]:
        """加载用户配置文件"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT key, value FROM profile")
            result = {}
            for row in cursor.fetchall():
                try:
                    result[row[0]] = json.loads(row[1])
                except json.JSONDecodeError:
                    result[row[0]] = row[1]
            return result

    def save_recommendations(self, items: list[dict[str, Any]]) -> None:
        """保存推荐结果"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM recommendations")
            conn.execute(
                "INSERT INTO recommendations (data, generated_at) VALUES (?, ?)",
                (json.dumps(items), int(__import__('time').time())),
            )
            conn.commit()

    def load_recommendations(self, limit: int = 24) -> dict[str, Any]:
        """加载推荐结果"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data, generated_at FROM recommendations ORDER BY generated_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                return {
                    "items": json.loads(row[0])[:limit],
                    "generated_at": row[1],
                }
            return {"items": [], "generated_at": 0}

    def save_external_recommendations(self, items: list[dict[str, Any]]) -> None:
        """保存外部推荐结果"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM external_recommendations")
            conn.execute(
                "INSERT INTO external_recommendations (data, generated_at) VALUES (?, ?)",
                (json.dumps(items), int(__import__('time').time())),
            )
            conn.commit()

    def load_external_recommendations(self, limit: int = 12) -> dict[str, Any]:
        """加载外部推荐结果"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data, generated_at FROM external_recommendations ORDER BY generated_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                return {
                    "items": json.loads(row[0])[:limit],
                    "generated_at": row[1],
                }
            return {"items": [], "generated_at": 0}
