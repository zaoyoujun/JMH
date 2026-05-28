import sqlite3
import weakref
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

from config.app_config import AppConfig
from utils.logger import get_logger

logger = get_logger()


class SQLiteConnection:
    _instance = None
    _connection: Optional[sqlite3.Connection] = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.config = AppConfig()
        self._db_path = self.config.DATA_DIR / "moviepop.db"
        self._initialized = True
    
    def _ensure_connection(self):
        """Ensure connection is valid, recreate if closed."""
        if self._connection is None:
            return self.initialize()
        try:
            self._connection.execute("SELECT 1")
            return True
        except Exception:
            self._connection = None
            return self.initialize()

    def initialize(self) -> bool:
        try:
            self._connection = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                isolation_level=None
            )
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = DELETE")
            self._connection.execute("PRAGMA synchronous = NORMAL")
            self._connection.execute("PRAGMA cache_size = -20000")
            logger.info(f"SQLite database initialized: {self._db_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")
            self._connection = None
            return False

    @property
    def connection(self) -> Optional[sqlite3.Connection]:
        if self._connection is None:
            self.initialize()
        return self._connection

    @contextmanager
    def get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        if self._connection is None:
            raise RuntimeError("SQLite connection not initialized")

        cursor = self._connection.cursor()
        try:
            yield cursor
        except Exception as e:
            logger.error(f"SQLite operation error: {e}")
            self._connection.rollback()
            raise
        else:
            self._connection.commit()
        finally:
            cursor.close()

    def execute(self, sql: str, params: tuple = ()) -> Any:
        with self.get_cursor() as cursor:
            return cursor.execute(sql, params)

    def query(self, sql: str, params: tuple = ()) -> list:
        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self):
        if self._connection:
            try:
                self._connection.execute("PRAGMA synchronous = FULL")
                self._connection.execute("PRAGMA journal_mode = DELETE")
                self._connection.execute("VACUUM")
            except Exception as e:
                logger.warning(f"Failed to prepare for close: {e}")
            
            try:
                self._connection.execute("BEGIN")
                self._connection.execute("COMMIT")
            except Exception as e:
                logger.warning(f"Failed to sync transaction: {e}")
            
            try:
                self._connection.close()
            except Exception as e:
                logger.warning(f"Error closing SQLite connection: {e}")
            
            self._connection = None
            logger.info("SQLite database closed")

    def reset(self):
        """Reset database connection, allowing files to be deleted."""
        self.close()
        SQLiteConnection._instance = None
        SQLiteConnection._connection = None
        SQLiteConnection._initialized = False
        logger.info("SQLite database connection reset")

    def is_connected(self) -> bool:
        return self._connection is not None


def get_sqlite_connection() -> SQLiteConnection:
    return SQLiteConnection()


def init_sqlite_database() -> bool:
    conn = get_sqlite_connection()
    return conn.initialize()