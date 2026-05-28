from pathlib import Path

from config.app_config import AppConfig
from utils.logger import get_logger
from utils.sqlite_connection import get_sqlite_connection

logger = get_logger()


class SQLiteInitializer:
    def __init__(self):
        self.config = AppConfig()
        self.conn = get_sqlite_connection()

    def initialize_database(self) -> bool:
        logger.info("Starting SQLite database initialization...")

        try:
            if not self.conn.initialize():
                return False

            schemas = [
                """
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    type TEXT DEFAULT '视频',
                    year INTEGER DEFAULT 2024,
                    duration TEXT DEFAULT '未知',
                    director TEXT DEFAULT '未知',
                    actors TEXT,
                    intro TEXT,
                    is_series INTEGER DEFAULT 0,
                    episodes TEXT,
                    episode_files TEXT,
                    path TEXT NOT NULL UNIQUE,
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
                    tags TEXT,
                    inferred_tags TEXT,
                    manual_tags TEXT,
                    playback TEXT,
                    episode_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_videos_path ON videos(path)",
                "CREATE INDEX IF NOT EXISTS idx_videos_title ON videos(title)",
                "CREATE INDEX IF NOT EXISTS idx_videos_is_favorite ON videos(is_favorite)",
                "CREATE INDEX IF NOT EXISTS idx_videos_year ON videos(year)",
                "CREATE INDEX IF NOT EXISTS idx_videos_category ON videos(category)",
                """
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
                )
                """,
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_favorites_video_id ON favorites(video_id)",
                """
                CREATE TABLE IF NOT EXISTS recent_plays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_recent_plays_played_at ON recent_plays(played_at)",
                """
                CREATE TABLE IF NOT EXISTS playback_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL UNIQUE,
                    progress INTEGER DEFAULT 0,
                    duration INTEGER DEFAULT 0,
                    episode_index INTEGER DEFAULT 0,
                    timestamp INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
                )
                """,
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_playback_video_id ON playback_progress(video_id)",
                """
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)",
                """
                CREATE TABLE IF NOT EXISTS movie_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                )
                """,
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_movie_tags_video_tag ON movie_tags(video_id, tag_id)",
                """
                CREATE TABLE IF NOT EXISTS custom_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL UNIQUE,
                    data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
                )
                """,
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_custom_info_video_id ON custom_info(video_id)",
                """
                CREATE TABLE IF NOT EXISTS database_version (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL UNIQUE,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ]

            for schema in schemas:
                self.conn.execute(schema.strip())
            
            version_check = self.conn.query("SELECT version FROM database_version ORDER BY applied_at DESC LIMIT 1")
            if not version_check:
                self.conn.execute("INSERT INTO database_version (version) VALUES ('1.0.0')")
                logger.info("Database version 1.0.0 applied")

            logger.info("SQLite database initialization completed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")
            return False

    def backup_database(self, backup_path: str = None) -> str:
        if backup_path is None:
            import time
            backup_path = str(self.config.DATA_DIR / "backups" / f"backup_{time.strftime('%Y%m%d_%H%M%S')}.db")
        
        backup_dir = Path(backup_path).parent
        backup_dir.mkdir(parents=True, exist_ok=True)

        try:
            import shutil
            shutil.copy2(str(self.config.DATA_DIR / "moviepop.db"), backup_path)
            logger.info(f"Database backup completed: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return ""

    def restore_database(self, backup_path: str) -> bool:
        import shutil
        db_path = str(self.config.DATA_DIR / "moviepop.db")

        if not Path(backup_path).exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False

        try:
            shutil.copy2(backup_path, db_path)
            logger.info(f"Database restore completed from: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False

    def get_backup_list(self) -> list:
        backup_dir = self.config.DATA_DIR / "backups"
        if not backup_dir.exists():
            return []
        
        backups = sorted(backup_dir.glob("backup_*.db"), reverse=True)
        return [str(b) for b in backups]


def init_sqlite_database() -> bool:
    initializer = SQLiteInitializer()
    return initializer.initialize_database()


def backup_sqlite_database(backup_path: str = None) -> str:
    initializer = SQLiteInitializer()
    return initializer.backup_database(backup_path)


def restore_sqlite_database(backup_path: str) -> bool:
    initializer = SQLiteInitializer()
    return initializer.restore_database(backup_path)