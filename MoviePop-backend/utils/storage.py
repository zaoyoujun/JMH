"""
Unified SQLite storage layer for MoviePop.
Replaces scattered JSON files and the old recommendation_repository.
Only playback_progress.json remains as JSON for real-time frontend access.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from config.app_config import AppConfig


class Storage:
    """Central SQLite-backed storage for all business data."""

    DB_FILENAME = "moviepop.sqlite3"

    def __init__(self) -> None:
        config = AppConfig()
        config.load_config()
        self.db_path = config.DATA_DIR / self.DB_FILENAME
        self._init_db()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(_SCHEMA)
            conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> int:
        return int(time.time())

    @staticmethod
    def _json_dumps(obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)

    @staticmethod
    def _json_loads(text: str | None) -> Any:
        if not text:
            return None
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    # ------------------------------------------------------------------
    # video_cache
    # ------------------------------------------------------------------

    def save_video_cache(self, video_list: list[dict[str, Any]]) -> None:
        now = self._now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM video_cache")
            for v in video_list:
                if not isinstance(v, dict) or not v.get("path"):
                    continue
                conn.execute(
                    """INSERT OR REPLACE INTO video_cache (
                        path, title, name, type, year, duration, director, actors, intro,
                        is_series, season, season_title, series_title, special_type, part,
                        category, franchise, resolution, video_codec, audio_info,
                        subtitle_info, release_group, rating, remote_provider, source_label,
                        cover_path, cover_url, sort_bucket, sort_title, year_hint,
                        episode_count, episode_files_json, tags_json, source, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        v.get("path", ""),
                        v.get("title", ""),
                        v.get("name", ""),
                        v.get("type", "视频"),
                        v.get("year", 0),
                        v.get("duration", ""),
                        v.get("director", ""),
                        v.get("actors", ""),
                        v.get("intro", ""),
                        1 if v.get("is_series") else 0,
                        v.get("season", 0),
                        v.get("season_title", ""),
                        v.get("series_title", ""),
                        v.get("special_type", ""),
                        v.get("part", 0),
                        v.get("category", ""),
                        v.get("franchise", ""),
                        v.get("resolution", ""),
                        v.get("video_codec", ""),
                        v.get("audio_info", ""),
                        v.get("subtitle_info", ""),
                        v.get("release_group", ""),
                        v.get("rating", 0.0),
                        v.get("remote_provider", ""),
                        v.get("source_label", ""),
                        v.get("cover_path", ""),
                        v.get("cover_url", ""),
                        v.get("sort_bucket", 9),
                        v.get("sort_title", ""),
                        v.get("year_hint", 0),
                        v.get("episode_count", 0),
                        self._json_dumps(v.get("episode_files", [])),
                        self._json_dumps(v.get("tags", [])),
                        v.get("source", v.get("source_label", "")),
                        now,
                    ),
                )
            conn.commit()

    def load_video_cache(self) -> list[dict[str, Any]] | None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM video_cache").fetchall()
        if not rows:
            return None
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["is_series"] = bool(item.get("is_series"))
            item["episode_files"] = self._json_loads(item.get("episode_files_json")) or []
            item["tags"] = self._json_loads(item.get("tags_json")) or []
            item.pop("episode_files_json", None)
            item.pop("tags_json", None)
            item.pop("updated_at", None)
            # Back-compat: expose source_label from source if not set
            if not item.get("source_label"):
                item["source_label"] = item.get("source", "")
            result.append(item)
        return result

    def get_video_by_path(self, path: str) -> dict[str, Any] | None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM video_cache WHERE path = ?", (path,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["is_series"] = bool(item.get("is_series"))
        item["episode_files"] = self._json_loads(item.get("episode_files_json")) or []
        item["tags"] = self._json_loads(item.get("tags_json")) or []
        item.pop("episode_files_json", None)
        item.pop("tags_json", None)
        item.pop("updated_at", None)
        return item

    # ------------------------------------------------------------------
    # favorites
    # ------------------------------------------------------------------

    def get_favorites(self) -> list[dict[str, Any]]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT f.*, v.title, v.name, v.type, v.year, v.cover_path,
                          v.cover_url, v.is_series, v.remote_provider, v.source_label,
                          v.path as vpath
                   FROM favorites f
                   LEFT JOIN video_cache v ON f.path = v.path
                   ORDER BY f.added_at DESC"""
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            if not item.get("path"):
                item["path"] = item.pop("vpath", "")
            if not item.get("title"):
                item["title"] = item.get("name", "")
            item["is_series"] = bool(item.get("is_series"))
            item["is_favorite"] = True
            result.append(item)
        return result

    def is_favorite(self, movie_path: str) -> bool:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM favorites WHERE path = ?", (movie_path,)
            ).fetchone()
        return row is not None

    def add_favorite(self, movie: dict[str, Any]) -> None:
        path = movie.get("path", "")
        if not path:
            return
        now = self._now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO favorites (path, added_at) VALUES (?, ?)",
                (path, now),
            )
            conn.commit()

    def remove_favorite(self, movie_path: str) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM favorites WHERE path = ?", (movie_path,))
            conn.commit()

    # ------------------------------------------------------------------
    # recent_play
    # ------------------------------------------------------------------

    def get_recent_play(self, limit: int = 10) -> list[dict[str, Any]]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT r.*, v.title, v.name, v.type, v.year, v.cover_path,
                          v.cover_url, v.is_series, v.remote_provider, v.source_label,
                          v.path as vpath
                   FROM recent_play r
                   LEFT JOIN video_cache v ON r.path = v.path
                   ORDER BY r.played_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            if not item.get("path"):
                item["path"] = item.pop("vpath", "")
            if not item.get("title"):
                item["title"] = item.get("name", "")
            item["is_series"] = bool(item.get("is_series"))
            result.append(item)
        return result

    def add_recent_play(self, movie: dict[str, Any]) -> None:
        path = movie.get("path", "")
        if not path:
            return
        now = self._now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO recent_play (path, played_at, movie_json) VALUES (?, ?, ?)",
                (path, now, self._json_dumps(movie)),
            )
            # Keep only last 50
            conn.execute(
                "DELETE FROM recent_play WHERE path NOT IN (SELECT path FROM recent_play ORDER BY played_at DESC LIMIT 50)"
            )
            conn.commit()

    # ------------------------------------------------------------------
    # movie_tags
    # ------------------------------------------------------------------

    def get_all_tags(self) -> dict[str, list[str]]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT tag, path FROM movie_tags ORDER BY tag"
            ).fetchall()
        result: dict[str, list[str]] = {}
        for tag, path in rows:
            if tag not in result:
                result[tag] = []
            if path not in result[tag]:
                result[tag].append(path)
        return result

    def get_movie_tags(self, movie_path: str) -> list[str]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT tag FROM movie_tags WHERE path = ?", (movie_path,)
            ).fetchall()
        return [row[0] for row in rows]

    def add_movie_tag(self, movie_path: str, tag: str) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO movie_tags (path, tag, source) VALUES (?, ?, 'manual')",
                (movie_path, tag),
            )
            conn.commit()

    def remove_movie_tag(self, movie_path: str, tag: str) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "DELETE FROM movie_tags WHERE path = ? AND tag = ? AND source = 'manual'",
                (movie_path, tag),
            )
            conn.commit()

    def get_movies_by_tag(self, tag: str) -> list[str]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT DISTINCT path FROM movie_tags WHERE tag = ?", (tag,)
            ).fetchall()
        return [row[0] for row in rows]

    def save_tags(self, movie_path: str, tags: list[str]) -> None:
        """Replace all tags for a movie (compatibility with RecommendationRepository)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM movie_tags WHERE path = ? AND source = 'manual'", (movie_path,))
            for tag in tags:
                conn.execute("INSERT OR IGNORE INTO movie_tags (path, tag, source) VALUES (?, ?, 'manual')", (movie_path, tag))
            conn.commit()

    def get_tags_map(self) -> dict[str, list[str]]:
        """Get tag mapping: {movie_path: [tag, ...]}"""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute("SELECT path, tag FROM movie_tags").fetchall()
        result: dict[str, list[str]] = {}
        for path, tag in rows:
            if path not in result:
                result[path] = []
            result[path].append(tag)
        return result

    def save_movie_tags_batch(self, movie_path: str, tags: list[str]) -> None:
        """Replace all tags for a movie."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM movie_tags WHERE path = ? AND source != 'manual'", (movie_path,))
            for tag in tags:
                conn.execute(
                    "INSERT OR IGNORE INTO movie_tags (path, tag, source) VALUES (?, ?, 'auto')",
                    (movie_path, tag),
                )
            conn.commit()

    # ------------------------------------------------------------------
    # custom_info
    # ------------------------------------------------------------------

    def get_all_custom_info(self) -> dict[str, dict[str, Any]]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute("SELECT path, data_json FROM custom_info").fetchall()
        result: dict[str, dict[str, Any]] = {}
        for path, data_json in rows:
            parsed = self._json_loads(data_json)
            if isinstance(parsed, dict):
                result[path] = parsed
        return result

    def get_custom_info(self, movie_path: str) -> dict[str, Any]:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT data_json FROM custom_info WHERE path = ?", (movie_path,)
            ).fetchone()
        if row:
            parsed = self._json_loads(row[0])
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def save_custom_info(self, movie_path: str, info: dict[str, Any]) -> None:
        now = self._now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO custom_info (path, data_json, updated_at) VALUES (?, ?, ?)",
                (movie_path, self._json_dumps(info), now),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # feedback (ratings + watch stats)
    # ------------------------------------------------------------------

    def get_feedback_map(self) -> dict[str, dict[str, Any]]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT path, rating, watch_count, last_watched FROM feedback"
            ).fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            result[row[0]] = {
                "rating": row[1],
                "watch_count": row[2] or 0,
                "last_watched": row[3] or 0,
            }
        return result

    def upsert_feedback(self, movie_path: str, **kwargs: Any) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT INTO feedback (path, rating, watch_count, last_watched, updated_at)
                   VALUES (?, COALESCE(?, (SELECT rating FROM feedback WHERE path = ?)),
                           COALESCE(?, (SELECT watch_count FROM feedback WHERE path = ?)),
                           COALESCE(?, (SELECT last_watched FROM feedback WHERE path = ?)),
                           ?)
                   ON CONFLICT(path) DO UPDATE SET
                       rating = COALESCE(excluded.rating, feedback.rating),
                       watch_count = COALESCE(excluded.watch_count, feedback.watch_count),
                       last_watched = COALESCE(excluded.last_watched, feedback.last_watched),
                       updated_at = excluded.updated_at""",
                (
                    movie_path,
                    kwargs.get("rating"),
                    movie_path,
                    kwargs.get("watch_count"),
                    movie_path,
                    kwargs.get("last_watched"),
                    movie_path,
                    self._now(),
                ),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # recommendation profile
    # ------------------------------------------------------------------

    def save_profile(self, profile: dict[str, Any]) -> None:
        now = self._now()
        with sqlite3.connect(str(self.db_path)) as conn:
            for key, value in profile.items():
                conn.execute(
                    "INSERT OR REPLACE INTO rec_profile (key, value_json, updated_at) VALUES (?, ?, ?)",
                    (key, self._json_dumps(value), now),
                )
            conn.commit()

    def load_profile(self) -> dict[str, Any]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute("SELECT key, value_json FROM rec_profile").fetchall()
        result: dict[str, Any] = {}
        for key, value_json in rows:
            result[key] = self._json_loads(value_json)
        return result

    # ------------------------------------------------------------------
    # recommendation results
    # ------------------------------------------------------------------

    def save_recommendations(self, items: list[dict[str, Any]]) -> None:
        now = self._now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM rec_results")
            conn.execute(
                "INSERT INTO rec_results (data_json, generated_at) VALUES (?, ?)",
                (self._json_dumps(items), now),
            )
            conn.commit()

    def load_recommendations(self, limit: int = 24) -> dict[str, Any]:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT data_json, generated_at FROM rec_results ORDER BY generated_at DESC LIMIT 1"
            ).fetchone()
        if row:
            items = self._json_loads(row[0]) or []
            return {"items": items[:limit], "generated_at": row[1]}
        return {"items": [], "generated_at": 0}

    def save_external_recommendations(self, items: list[dict[str, Any]]) -> None:
        now = self._now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM rec_external_results")
            conn.execute(
                "INSERT INTO rec_external_results (data_json, generated_at) VALUES (?, ?)",
                (self._json_dumps(items), now),
            )
            conn.commit()

    def load_external_recommendations(self, limit: int = 12) -> dict[str, Any]:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT data_json, generated_at FROM rec_external_results ORDER BY generated_at DESC LIMIT 1"
            ).fetchone()
        if row:
            items = self._json_loads(row[0]) or []
            return {"items": items[:limit], "generated_at": row[1]}
        return {"items": [], "generated_at": 0}

    # ------------------------------------------------------------------
    # user_behavior
    # ------------------------------------------------------------------

    def record_watch_behavior(
        self,
        media_path: str,
        duration: int,
        progress: float | None = None,
        media_type: str | None = None,
        genres: list[str] | None = None,
    ) -> None:
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT INTO user_behavior (media_path, duration, progress, media_type, genres_json, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    media_path,
                    duration,
                    progress,
                    media_type,
                    self._json_dumps(genres or []),
                    now_iso,
                ),
            )
            conn.commit()

    def get_behavior_data(self) -> list[dict[str, Any]]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM user_behavior ORDER BY timestamp DESC"
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["genres"] = self._json_loads(item.get("genres_json")) or []
            item.pop("genres_json", None)
            result.append(item)
        return result

    def has_behavior_data(self) -> bool:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM user_behavior").fetchone()
        return (row[0] if row else 0) > 0

    # ------------------------------------------------------------------
    # system_config (sensitive settings)
    # ------------------------------------------------------------------

    def get_config(self, key: str, default: str = "") -> str:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT value FROM system_config WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else default

    def set_config(self, key: str, value: str) -> None:
        now = self._now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )
            conn.commit()

    def get_all_config(self) -> dict[str, str]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute("SELECT key, value FROM system_config").fetchall()
        return {row[0]: row[1] for row in rows}

    # ------------------------------------------------------------------
    # operation_log
    # ------------------------------------------------------------------

    def log_operation(self, action: str, target: str = "", detail: str = "") -> None:
        now = self._now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO operation_log (action, target, detail, created_at) VALUES (?, ?, ?, ?)",
                (action, target, detail, now),
            )
            conn.commit()

    def get_operation_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM operation_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]


# ------------------------------------------------------------------
# SQL Schema
# ------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS video_cache (
    path              TEXT PRIMARY KEY,
    title             TEXT NOT NULL DEFAULT '',
    name              TEXT DEFAULT '',
    type              TEXT DEFAULT '视频',
    year              INTEGER DEFAULT 0,
    duration          TEXT DEFAULT '',
    director          TEXT DEFAULT '',
    actors            TEXT DEFAULT '',
    intro             TEXT DEFAULT '',
    is_series         INTEGER DEFAULT 0,
    season            INTEGER DEFAULT 0,
    season_title      TEXT DEFAULT '',
    series_title      TEXT DEFAULT '',
    special_type      TEXT DEFAULT '',
    part              INTEGER DEFAULT 0,
    category          TEXT DEFAULT '',
    franchise         TEXT DEFAULT '',
    resolution        TEXT DEFAULT '',
    video_codec       TEXT DEFAULT '',
    audio_info        TEXT DEFAULT '',
    subtitle_info     TEXT DEFAULT '',
    release_group     TEXT DEFAULT '',
    rating            REAL DEFAULT 0.0,
    remote_provider   TEXT DEFAULT '',
    source_label      TEXT DEFAULT '',
    cover_path        TEXT DEFAULT '',
    cover_url         TEXT DEFAULT '',
    sort_bucket       INTEGER DEFAULT 9,
    sort_title        TEXT DEFAULT '',
    year_hint         INTEGER DEFAULT 0,
    episode_count     INTEGER DEFAULT 0,
    episode_files_json TEXT DEFAULT '[]',
    tags_json         TEXT DEFAULT '[]',
    source            TEXT DEFAULT '',
    updated_at        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS favorites (
    path      TEXT PRIMARY KEY,
    added_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS recent_play (
    path       TEXT PRIMARY KEY,
    played_at  INTEGER NOT NULL,
    movie_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS movie_tags (
    path   TEXT NOT NULL,
    tag    TEXT NOT NULL,
    source TEXT DEFAULT 'manual',
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (path, tag, source)
);
CREATE INDEX IF NOT EXISTS idx_movie_tags_tag ON movie_tags(tag);

CREATE TABLE IF NOT EXISTS custom_info (
    path       TEXT PRIMARY KEY,
    data_json  TEXT NOT NULL DEFAULT '{}',
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    path         TEXT PRIMARY KEY,
    rating       REAL,
    watch_count  INTEGER DEFAULT 0,
    last_watched INTEGER DEFAULT 0,
    created_at   INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at   INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS rec_profile (
    key        TEXT PRIMARY KEY,
    value_json TEXT NOT NULL DEFAULT '{}',
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rec_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    data_json    TEXT NOT NULL DEFAULT '[]',
    generated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rec_external_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    data_json    TEXT NOT NULL DEFAULT '[]',
    generated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_behavior (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    media_path  TEXT NOT NULL,
    duration    INTEGER NOT NULL DEFAULT 0,
    progress    REAL,
    media_type  TEXT,
    genres_json TEXT DEFAULT '[]',
    timestamp   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_user_behavior_media ON user_behavior(media_path);
CREATE INDEX IF NOT EXISTS idx_user_behavior_ts ON user_behavior(timestamp);

CREATE TABLE IF NOT EXISTS system_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS operation_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    action     TEXT NOT NULL DEFAULT '',
    target     TEXT DEFAULT '',
    detail     TEXT DEFAULT '',
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_operation_log_action ON operation_log(action);
CREATE INDEX IF NOT EXISTS idx_operation_log_created ON operation_log(created_at);
"""
