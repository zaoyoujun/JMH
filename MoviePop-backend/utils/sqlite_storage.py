from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from config.app_config import AppConfig


class SQLiteStorage:
    """
    SQLite 数据库存储管理器 - 提供连接池、事务处理、错误恢复等功能
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        self.config = AppConfig()
        self.config.load_config()
        self.db_path = self.config.DATA_DIR / "moviepop.sqlite3"
        self._connection_pool = []
        self._pool_lock = threading.Lock()
        self._max_connections = 5
        self._connection_timeout = 30
        
        self._init_database()

    def _init_database(self):
        """初始化数据库表结构"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 数据库版本表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS db_version (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version INTEGER NOT NULL,
                    applied_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # 用户表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT,
                    email TEXT,
                    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                    last_login INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    settings TEXT DEFAULT '{}'
                )
            """)
            
            # 配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # 视频表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    name TEXT,
                    type TEXT DEFAULT '视频',
                    year INTEGER DEFAULT 2024,
                    duration TEXT DEFAULT '未知',
                    director TEXT DEFAULT '未知',
                    actors TEXT DEFAULT '未知',
                    intro TEXT DEFAULT '',
                    is_series INTEGER DEFAULT 0,
                    episodes TEXT DEFAULT '[]',
                    episode_files TEXT DEFAULT '[]',
                    cover_path TEXT DEFAULT '',
                    series_title TEXT DEFAULT '',
                    season_title TEXT DEFAULT '',
                    special_type TEXT DEFAULT '',
                    part INTEGER DEFAULT 0,
                    season INTEGER DEFAULT 0,
                    category TEXT DEFAULT '',
                    franchise TEXT DEFAULT '',
                    sort_bucket INTEGER DEFAULT 9,
                    sort_title TEXT DEFAULT '',
                    year_hint INTEGER DEFAULT 0,
                    rating REAL DEFAULT 0.0,
                    remote_provider TEXT DEFAULT '',
                    source_label TEXT DEFAULT '',
                    resolution TEXT DEFAULT '',
                    video_codec TEXT DEFAULT '',
                    audio_info TEXT DEFAULT '',
                    subtitle_info TEXT DEFAULT '',
                    release_group TEXT DEFAULT '',
                    cover_url TEXT DEFAULT '',
                    last_play_time TEXT DEFAULT '',
                    is_favorite INTEGER DEFAULT 0,
                    tags TEXT DEFAULT '[]',
                    inferred_tags TEXT DEFAULT '[]',
                    manual_tags TEXT DEFAULT '[]',
                    playback TEXT DEFAULT '{}',
                    episode_count INTEGER DEFAULT 0,
                    webdav_host TEXT DEFAULT '',
                    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # 收藏表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_path TEXT NOT NULL,
                    user_id INTEGER DEFAULT 1,
                    added_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (video_path) REFERENCES videos(path) ON DELETE CASCADE,
                    UNIQUE(video_path, user_id)
                )
            """)
            
            # 播放进度表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playback_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_path TEXT NOT NULL,
                    user_id INTEGER DEFAULT 1,
                    progress REAL DEFAULT 0.0,
                    duration REAL DEFAULT 0.0,
                    episode_index INTEGER DEFAULT 0,
                    timestamp INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (video_path) REFERENCES videos(path) ON DELETE CASCADE,
                    UNIQUE(video_path, user_id)
                )
            """)
            
            # 标签表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    color TEXT DEFAULT '#ff9248',
                    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # 视频标签关联表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS video_tags (
                    video_path TEXT NOT NULL,
                    tag_name TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    added_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (video_path) REFERENCES videos(path) ON DELETE CASCADE,
                    FOREIGN KEY (tag_name) REFERENCES tags(name) ON DELETE CASCADE,
                    PRIMARY KEY (video_path, tag_name)
                )
            """)
            
            # 最近播放表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recent_play (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_path TEXT NOT NULL,
                    user_id INTEGER DEFAULT 1,
                    played_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (video_path) REFERENCES videos(path) ON DELETE CASCADE
                )
            """)
            
            # 反馈表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    movie_path TEXT PRIMARY KEY,
                    rating REAL,
                    watch_count INTEGER DEFAULT 0,
                    last_watched INTEGER DEFAULT 0,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # 用户画像表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profile (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # 推荐表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT,
                    generated_at INTEGER
                )
            """)
            
            # 外部推荐表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS external_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT,
                    generated_at INTEGER
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_path ON videos(path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_title ON videos(title)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_type ON videos(type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_year ON videos(year)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_is_favorite ON videos(is_favorite)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_playback_user_id ON playback_progress(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recent_play_user_id ON recent_play(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recent_play_played_at ON recent_play(played_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_tags_tag_name ON video_tags(tag_name)")
            
            conn.commit()
            
            # 设置 SQLite 配置
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA cache_size = 10000")
            cursor.execute("PRAGMA temp_store = MEMORY")
            cursor.execute("PRAGMA mmap_size = 67108864")
            
        self._set_db_version(1)

    def _set_db_version(self, version: int):
        """设置数据库版本"""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM db_version")
            conn.execute("INSERT INTO db_version (version) VALUES (?)", (version,))
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """从连接池获取连接"""
        with self._pool_lock:
            while self._connection_pool:
                conn = self._connection_pool.pop()
                try:
                    # 检查连接是否仍然有效
                    conn.execute("SELECT 1")
                    return conn
                except sqlite3.Error:
                    # 连接已失效，关闭并尝试获取新连接
                    conn.close()
            
            # 创建新连接
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=10,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            return conn

    def _release_connection(self, conn: sqlite3.Connection):
        """释放连接回连接池"""
        with self._pool_lock:
            if len(self._connection_pool) < self._max_connections:
                try:
                    conn.execute("SELECT 1")
                    self._connection_pool.append(conn)
                except sqlite3.Error:
                    conn.close()
            else:
                conn.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行SQL语句（非查询）"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise DatabaseError(f"SQL执行失败: {e}")
        finally:
            if conn:
                self._release_connection(conn)

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """执行查询语句"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.execute(sql, params)
            return cursor.fetchall()
        except sqlite3.Error as e:
            raise DatabaseError(f"SQL查询失败: {e}")
        finally:
            if conn:
                self._release_connection(conn)

    def query_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """执行查询并返回单条记录"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.execute(sql, params)
            return cursor.fetchone()
        except sqlite3.Error as e:
            raise DatabaseError(f"SQL查询失败: {e}")
        finally:
            if conn:
                self._release_connection(conn)

    def transaction(self, func):
        """事务装饰器"""
        def wrapper(*args, **kwargs):
            conn = None
            try:
                conn = self._get_connection()
                conn.execute("BEGIN")
                
                result = func(conn, *args, **kwargs)
                
                conn.commit()
                return result
            except Exception as e:
                if conn:
                    conn.rollback()
                raise TransactionError(f"事务失败: {e}")
            finally:
                if conn:
                    self._release_connection(conn)
        return wrapper

    def backup(self, backup_path: Optional[str] = None) -> str:
        """备份数据库"""
        if backup_path is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = str(self.config.DATA_DIR / f"backup_{timestamp}.sqlite3")
        
        try:
            # 直接复制数据库文件（最简单可靠的方式）
            shutil.copy(str(self.db_path), backup_path)
            return backup_path
        except Exception as e:
            raise BackupError(f"备份失败: {e}")

    def restore(self, backup_path: str) -> bool:
        """从备份恢复数据库"""
        if not os.path.exists(backup_path):
            raise RestoreError("备份文件不存在")
        
        try:
            # 先备份当前数据库
            current_backup = self.backup(str(self.config.DATA_DIR / f"pre_restore_{time.time()}.sqlite3"))
            
            # 关闭所有连接
            with self._pool_lock:
                while self._connection_pool:
                    conn = self._connection_pool.pop()
                    conn.close()
            
            # 删除现有数据库文件
            if self.db_path.exists():
                os.remove(self.db_path)
            
            # 直接从备份文件恢复，不重新初始化
            shutil.copy(backup_path, str(self.db_path))
            
            return True
        except Exception as e:
            raise RestoreError(f"恢复失败: {e}")

    def get_db_size(self) -> int:
        """获取数据库文件大小（字节）"""
        if self.db_path.exists():
            return self.db_path.stat().st_size
        return 0

    def vacuum(self):
        """执行VACUUM操作优化数据库"""
        try:
            with self._get_connection() as conn:
                conn.execute("VACUUM")
                conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"VACUUM操作失败: {e}")

    def get_table_count(self, table_name: str) -> int:
        """获取表记录数"""
        result = self.query_one(f"SELECT COUNT(*) FROM {table_name}")
        return result[0] if result else 0


class DatabaseError(Exception):
    """数据库操作异常"""
    pass


class TransactionError(Exception):
    """事务操作异常"""
    pass


class BackupError(Exception):
    """备份操作异常"""
    pass


class RestoreError(Exception):
    """恢复操作异常"""
    pass


# 数据访问层 - 视频操作
class VideoDAO:
    """视频数据访问对象"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def insert_video(self, video_data: dict) -> int:
        """插入视频记录"""
        keys = [
            'path', 'title', 'name', 'type', 'year', 'duration', 'director',
            'actors', 'intro', 'is_series', 'episodes', 'episode_files',
            'cover_path', 'series_title', 'season_title', 'special_type',
            'part', 'season', 'category', 'franchise', 'sort_bucket',
            'sort_title', 'year_hint', 'rating', 'remote_provider',
            'source_label', 'resolution', 'video_codec', 'audio_info',
            'subtitle_info', 'release_group', 'cover_url', 'last_play_time',
            'is_favorite', 'tags', 'inferred_tags', 'manual_tags',
            'playback', 'episode_count', 'webdav_host'
        ]
        
        columns = ', '.join(keys)
        placeholders = ', '.join('?' * len(keys))
        values = [video_data.get(k, '') for k in keys]
        
        cursor = self.storage.execute(
            f"INSERT OR REPLACE INTO videos ({columns}) VALUES ({placeholders})",
            tuple(values)
        )
        return cursor.lastrowid
    
    def get_video_by_path(self, path: str) -> Optional[dict]:
        """根据路径获取视频"""
        row = self.storage.query_one("SELECT * FROM videos WHERE path = ?", (path,))
        return dict(row) if row else None
    
    def get_all_videos(self) -> list[dict]:
        """获取所有视频"""
        rows = self.storage.query("SELECT * FROM videos ORDER BY title")
        return [dict(row) for row in rows]
    
    def update_video(self, path: str, update_data: dict) -> bool:
        """更新视频信息"""
        if not update_data:
            return False
        
        set_clause = ', '.join(f"{k} = ?" for k in update_data.keys())
        values = list(update_data.values()) + [path]
        
        self.storage.execute(
            f"UPDATE videos SET {set_clause} WHERE path = ?",
            tuple(values)
        )
        return True
    
    def delete_video(self, path: str) -> bool:
        """删除视频"""
        self.storage.execute("DELETE FROM videos WHERE path = ?", (path,))
        return True
    
    def search_videos(self, keyword: str) -> list[dict]:
        """搜索视频"""
        pattern = f"%{keyword}%"
        rows = self.storage.query(
            "SELECT * FROM videos WHERE title LIKE ? OR name LIKE ? ORDER BY title",
            (pattern, pattern)
        )
        return [dict(row) for row in rows]


# 数据访问层 - 收藏操作
class FavoriteDAO:
    """收藏数据访问对象"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def add_favorite(self, video_path: str, user_id: int = 1) -> bool:
        """添加收藏"""
        try:
            self.storage.execute(
                "INSERT INTO favorites (video_path, user_id) VALUES (?, ?)",
                (video_path, user_id)
            )
            # 更新视频的收藏状态
            self.storage.execute(
                "UPDATE videos SET is_favorite = 1 WHERE path = ?",
                (video_path,)
            )
            return True
        except sqlite3.IntegrityError:
            return False
    
    def remove_favorite(self, video_path: str, user_id: int = 1) -> bool:
        """移除收藏"""
        self.storage.execute(
            "DELETE FROM favorites WHERE video_path = ? AND user_id = ?",
            (video_path, user_id)
        )
        # 更新视频的收藏状态
        self.storage.execute(
            "UPDATE videos SET is_favorite = 0 WHERE path = ?",
            (video_path,)
        )
        return True
    
    def get_favorites(self, user_id: int = 1) -> list[dict]:
        """获取用户收藏"""
        rows = self.storage.query(
            """
            SELECT v.* FROM videos v
            JOIN favorites f ON v.path = f.video_path
            WHERE f.user_id = ?
            ORDER BY f.added_at DESC
            """,
            (user_id,)
        )
        return [dict(row) for row in rows]
    
    def is_favorite(self, video_path: str, user_id: int = 1) -> bool:
        """检查是否已收藏"""
        row = self.storage.query_one(
            "SELECT 1 FROM favorites WHERE video_path = ? AND user_id = ?",
            (video_path, user_id)
        )
        return row is not None


# 数据访问层 - 播放进度操作
class PlaybackDAO:
    """播放进度数据访问对象"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def save_progress(self, video_path: str, progress: float, duration: float, 
                     episode_index: int = 0, user_id: int = 1) -> bool:
        """保存播放进度"""
        self.storage.execute(
            """
            INSERT OR REPLACE INTO playback_progress 
            (video_path, user_id, progress, duration, episode_index)
            VALUES (?, ?, ?, ?, ?)
            """,
            (video_path, user_id, progress, duration, episode_index)
        )
        return True
    
    def get_progress(self, video_path: str, user_id: int = 1) -> Optional[dict]:
        """获取播放进度"""
        row = self.storage.query_one(
            "SELECT * FROM playback_progress WHERE video_path = ? AND user_id = ?",
            (video_path, user_id)
        )
        return dict(row) if row else None
    
    def get_all_progress(self, user_id: int = 1) -> list[dict]:
        """获取所有播放进度"""
        rows = self.storage.query(
            "SELECT * FROM playback_progress WHERE user_id = ?",
            (user_id,)
        )
        return [dict(row) for row in rows]
    
    def clear_progress(self, video_path: str = None, user_id: int = 1) -> bool:
        """清除播放进度"""
        if video_path:
            self.storage.execute(
                "DELETE FROM playback_progress WHERE video_path = ? AND user_id = ?",
                (video_path, user_id)
            )
        else:
            self.storage.execute(
                "DELETE FROM playback_progress WHERE user_id = ?",
                (user_id,)
            )
        return True


# 数据访问层 - 标签操作
class TagDAO:
    """标签数据访问对象"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def create_tag(self, name: str, color: str = '#ff9248') -> bool:
        """创建标签"""
        # 使用 INSERT OR IGNORE 避免唯一性约束错误
        self.storage.execute(
            "INSERT OR IGNORE INTO tags (name, color) VALUES (?, ?)",
            (name, color)
        )
        return True
    
    def add_video_tag(self, video_path: str, tag_name: str, weight: float = 1.0) -> bool:
        """为视频添加标签"""
        # 确保标签存在
        self.create_tag(tag_name)
        
        try:
            self.storage.execute(
                """
                INSERT OR REPLACE INTO video_tags 
                (video_path, tag_name, weight)
                VALUES (?, ?, ?)
                """,
                (video_path, tag_name, weight)
            )
            return True
        except sqlite3.IntegrityError:
            return False
    
    def remove_video_tag(self, video_path: str, tag_name: str) -> bool:
        """移除视频标签"""
        self.storage.execute(
            "DELETE FROM video_tags WHERE video_path = ? AND tag_name = ?",
            (video_path, tag_name)
        )
        return True
    
    def get_video_tags(self, video_path: str) -> list[str]:
        """获取视频标签"""
        rows = self.storage.query(
            "SELECT tag_name FROM video_tags WHERE video_path = ?",
            (video_path,)
        )
        return [row['tag_name'] for row in rows]
    
    def get_movies_by_tag(self, tag_name: str) -> list[dict]:
        """获取具有指定标签的视频"""
        rows = self.storage.query(
            """
            SELECT v.* FROM videos v
            JOIN video_tags vt ON v.path = vt.video_path
            WHERE vt.tag_name = ?
            """,
            (tag_name,)
        )
        return [dict(row) for row in rows]
    
    def get_all_tags(self) -> list[dict]:
        """获取所有标签"""
        rows = self.storage.query("SELECT * FROM tags ORDER BY name")
        return [dict(row) for row in rows]


# 数据访问层 - 最近播放操作
class RecentPlayDAO:
    """最近播放数据访问对象"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def add_recent_play(self, video_path: str, user_id: int = 1) -> bool:
        """添加最近播放"""
        # 先删除已存在的记录
        self.storage.execute(
            "DELETE FROM recent_play WHERE video_path = ? AND user_id = ?",
            (video_path, user_id)
        )
        
        self.storage.execute(
            "INSERT INTO recent_play (video_path, user_id) VALUES (?, ?)",
            (video_path, user_id)
        )
        return True
    
    def get_recent_play(self, user_id: int = 1, limit: int = 100) -> list[dict]:
        """获取最近播放"""
        rows = self.storage.query(
            """
            SELECT v.* FROM videos v
            JOIN recent_play rp ON v.path = rp.video_path
            WHERE rp.user_id = ?
            ORDER BY rp.played_at DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        return [dict(row) for row in rows]
    
    def clear_recent_play(self, user_id: int = 1) -> bool:
        """清除最近播放"""
        self.storage.execute(
            "DELETE FROM recent_play WHERE user_id = ?",
            (user_id,)
        )
        return True


# 数据访问层 - 配置操作
class ConfigDAO:
    """配置数据访问对象"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def set_config(self, key: str, value: Any) -> bool:
        """设置配置值"""
        json_value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        self.storage.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, json_value)
        )
        return True
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        row = self.storage.query_one("SELECT value FROM config WHERE key = ?", (key,))
        if row:
            value = row['value']
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return default
    
    def delete_config(self, key: str) -> bool:
        """删除配置"""
        self.storage.execute("DELETE FROM config WHERE key = ?", (key,))
        return True
    
    def get_all_configs(self) -> dict[str, Any]:
        """获取所有配置"""
        rows = self.storage.query("SELECT key, value FROM config")
        result = {}
        for row in rows:
            key = row['key']
            value = row['value']
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError:
                result[key] = value
        return result


# 数据访问层 - 反馈操作
class FeedbackDAO:
    """反馈数据访问对象"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def upsert_feedback(self, movie_path: str, **kwargs) -> bool:
        """更新或插入反馈"""
        self.storage.execute(
            """
            INSERT OR REPLACE INTO feedback 
            (movie_path, rating, watch_count, last_watched)
            VALUES (?, COALESCE(?, (SELECT rating FROM feedback WHERE movie_path = ?)),
                    COALESCE(?, (SELECT watch_count FROM feedback WHERE movie_path = ?)),
                    COALESCE(?, (SELECT last_watched FROM feedback WHERE movie_path = ?)))
            """,
            (
                movie_path, kwargs.get('rating'), movie_path,
                kwargs.get('watch_count'), movie_path,
                kwargs.get('last_watched'), movie_path
            )
        )
        return True
    
    def get_feedback_map(self) -> dict[str, dict]:
        """获取所有反馈"""
        rows = self.storage.query("SELECT movie_path, rating, watch_count, last_watched FROM feedback")
        result = {}
        for row in rows:
            result[row['movie_path']] = {
                'rating': row['rating'],
                'watch_count': row['watch_count'] or 0,
                'last_watched': row['last_watched'] or 0
            }
        return result


# 数据访问层 - 用户画像操作
class ProfileDAO:
    """用户画像数据访问对象"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def save_profile(self, profile: dict) -> bool:
        """保存用户画像"""
        for key, value in profile.items():
            self.storage.execute(
                "INSERT OR REPLACE INTO profile (key, value) VALUES (?, ?)",
                (key, json.dumps(value))
            )
        return True
    
    def load_profile(self) -> dict:
        """加载用户画像"""
        rows = self.storage.query("SELECT key, value FROM profile")
        result = {}
        for row in rows:
            try:
                result[row['key']] = json.loads(row['value'])
            except json.JSONDecodeError:
                result[row['key']] = row['value']
        return result


# 数据访问层 - 推荐操作
class RecommendationDAO:
    """推荐数据访问对象"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def save_recommendations(self, items: list[dict]) -> bool:
        """保存推荐结果"""
        self.storage.execute("DELETE FROM recommendations")
        self.storage.execute(
            "INSERT INTO recommendations (data, generated_at) VALUES (?, ?)",
            (json.dumps(items), int(time.time()))
        )
        return True
    
    def load_recommendations(self, limit: int = 24) -> dict:
        """加载推荐结果"""
        row = self.storage.query_one(
            "SELECT data, generated_at FROM recommendations ORDER BY generated_at DESC LIMIT 1"
        )
        if row:
            return {
                'items': json.loads(row['data'])[:limit],
                'generated_at': row['generated_at']
            }
        return {'items': [], 'generated_at': 0}
    
    def save_external_recommendations(self, items: list[dict]) -> bool:
        """保存外部推荐"""
        self.storage.execute("DELETE FROM external_recommendations")
        self.storage.execute(
            "INSERT INTO external_recommendations (data, generated_at) VALUES (?, ?)",
            (json.dumps(items), int(time.time()))
        )
        return True
    
    def load_external_recommendations(self, limit: int = 12) -> dict:
        """加载外部推荐"""
        row = self.storage.query_one(
            "SELECT data, generated_at FROM external_recommendations ORDER BY generated_at DESC LIMIT 1"
        )
        if row:
            return {
                'items': json.loads(row['data'])[:limit],
                'generated_at': row['generated_at']
            }
        return {'items': [], 'generated_at': 0}