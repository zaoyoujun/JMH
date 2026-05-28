import json
from typing import Any, Dict, List, Optional

from utils.logger import get_logger
from utils.sqlite_connection import get_sqlite_connection

logger = get_logger()


class SQLiteVideoDAO:
    def __init__(self):
        self.conn = get_sqlite_connection()

    def insert_video(self, video_data: Dict[str, Any]) -> int:
        sql = """
        INSERT OR REPLACE INTO videos (
            title, name, type, year, duration, director, actors, intro,
            is_series, episodes, episode_files, path, cover_path, series_title,
            season_title, special_type, part, season, category, franchise,
            sort_bucket, sort_title, year_hint, rating, remote_provider,
            source_label, resolution, video_codec, audio_info, subtitle_info,
            release_group, cover_url, last_play_time, is_favorite, tags,
            inferred_tags, manual_tags, playback, episode_count
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """

        data = (
            video_data.get("title", ""),
            video_data.get("name", ""),
            video_data.get("type", "视频"),
            video_data.get("year", 2024),
            video_data.get("duration", "未知"),
            video_data.get("director", "未知"),
            video_data.get("actors", "未知"),
            video_data.get("intro", ""),
            1 if video_data.get("is_series", False) else 0,
            json.dumps(video_data.get("episodes", [])),
            json.dumps(video_data.get("episode_files", [])),
            video_data.get("path", ""),
            video_data.get("cover_path", ""),
            video_data.get("series_title", ""),
            video_data.get("season_title", ""),
            video_data.get("special_type", ""),
            video_data.get("part", 0),
            video_data.get("season", 0),
            video_data.get("category", ""),
            video_data.get("franchise", ""),
            video_data.get("sort_bucket", 9),
            video_data.get("sort_title", ""),
            video_data.get("year_hint", 0),
            float(video_data.get("rating", 0.0)),
            video_data.get("remote_provider", ""),
            video_data.get("source_label", ""),
            video_data.get("resolution", ""),
            video_data.get("video_codec", ""),
            video_data.get("audio_info", ""),
            video_data.get("subtitle_info", ""),
            video_data.get("release_group", ""),
            video_data.get("cover_url", ""),
            video_data.get("last_play_time", ""),
            1 if video_data.get("is_favorite", False) else 0,
            json.dumps(video_data.get("tags", [])),
            json.dumps(video_data.get("inferred_tags", [])),
            json.dumps(video_data.get("manual_tags", [])),
            json.dumps(video_data.get("playback", {})),
            video_data.get("episode_count", 0),
        )

        try:
            cursor = self.conn.execute(sql, data)
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to insert video: {e}")
            return 0

    def get_video_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM videos WHERE path = ?"
        try:
            result = self.conn.query(sql, (path,))
            if result:
                return self._convert_row_to_dict(result[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get video by path: {e}")
            return None

    def get_video_by_id(self, video_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM videos WHERE id = ?"
        try:
            result = self.conn.query(sql, (video_id,))
            if result:
                return self._convert_row_to_dict(result[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get video by id: {e}")
            return None

    def get_all_videos(self) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM videos ORDER BY title ASC"
        try:
            results = self.conn.query(sql)
            return [self._convert_row_to_dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to get all videos: {e}")
            return []

    def get_favorite_videos(self) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM videos WHERE is_favorite = 1 ORDER BY title ASC"
        try:
            results = self.conn.query(sql)
            return [self._convert_row_to_dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to get favorite videos: {e}")
            return []

    def update_video(self, video_id: int, video_data: Dict[str, Any]) -> bool:
        set_parts = []
        params = []

        for key, value in video_data.items():
            if key == "episodes" or key == "episode_files" or key == "tags" or \
               key == "inferred_tags" or key == "manual_tags" or key == "playback":
                set_parts.append(f"{key}=?")
                params.append(json.dumps(value))
            elif key == "is_series" or key == "is_favorite":
                set_parts.append(f"{key}=?")
                params.append(1 if value else 0)
            elif key == "rating":
                set_parts.append(f"{key}=?")
                params.append(float(value))
            elif key != "id" and key != "path":
                set_parts.append(f"{key}=?")
                params.append(value)

        params.append(video_id)

        if not set_parts:
            return False

        sql = f"UPDATE videos SET {', '.join(set_parts)} WHERE id = ?"

        try:
            self.conn.execute(sql, tuple(params))
            return True
        except Exception as e:
            logger.error(f"Failed to update video: {e}")
            return False

    def delete_video(self, video_id: int) -> bool:
        sql = "DELETE FROM videos WHERE id = ?"
        try:
            self.conn.execute(sql, (video_id,))
            return True
        except Exception as e:
            logger.error(f"Failed to delete video: {e}")
            return False

    def search_videos(self, keyword: str) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM videos WHERE title LIKE ? OR name LIKE ? ORDER BY title ASC"
        try:
            results = self.conn.query(sql, (f"%{keyword}%", f"%{keyword}%"))
            return [self._convert_row_to_dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to search videos: {e}")
            return []

    def _convert_row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(row)
        for key in ["episodes", "episode_files", "tags", "inferred_tags", "manual_tags", "playback"]:
            if result.get(key):
                try:
                    result[key] = json.loads(result[key])
                except:
                    result[key] = [] if key in ["episodes", "episode_files", "tags", "inferred_tags", "manual_tags"] else {}
        for key in ["is_series", "is_favorite"]:
            if result.get(key) is not None:
                result[key] = bool(result[key])
        return result


class SQLiteFavoriteDAO:
    def __init__(self):
        self.conn = get_sqlite_connection()
        self.video_dao = SQLiteVideoDAO()

    def add_favorite(self, video_id: int) -> bool:
        delete_sql = "DELETE FROM favorites WHERE video_id = ?"
        insert_sql = "INSERT INTO favorites (video_id) VALUES (?)"

        try:
            self.conn.execute(delete_sql, (video_id,))
            self.conn.execute(insert_sql, (video_id,))
            self.video_dao.update_video(video_id, {"is_favorite": True})
            return True
        except Exception as e:
            logger.error(f"Failed to add favorite: {e}")
            return False

    def remove_favorite(self, video_id: int) -> bool:
        sql = "DELETE FROM favorites WHERE video_id = ?"
        try:
            self.conn.execute(sql, (video_id,))
            self.video_dao.update_video(video_id, {"is_favorite": False})
            return True
        except Exception as e:
            logger.error(f"Failed to remove favorite: {e}")
            return False

    def is_favorite(self, video_id: int) -> bool:
        sql = "SELECT COUNT(*) as count FROM favorites WHERE video_id = ?"
        try:
            result = self.conn.query(sql, (video_id,))
            return result[0]["count"] > 0 if result else False
        except Exception as e:
            logger.error(f"Failed to check favorite: {e}")
            return False

    def get_all_favorites(self) -> List[Dict[str, Any]]:
        sql = "SELECT v.* FROM videos v JOIN favorites f ON v.id = f.video_id ORDER BY f.added_at DESC"
        try:
            results = self.conn.query(sql)
            return [self.video_dao._convert_row_to_dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to get all favorites: {e}")
            return []


class SQLiteRecentPlayDAO:
    def __init__(self):
        self.conn = get_sqlite_connection()
        self.video_dao = SQLiteVideoDAO()

    def add_recent_play(self, video_id: int) -> bool:
        delete_sql = "DELETE FROM recent_plays WHERE video_id = ?"
        insert_sql = "INSERT INTO recent_plays (video_id) VALUES (?)"

        try:
            self.conn.execute(delete_sql, (video_id,))
            self.conn.execute(insert_sql, (video_id,))
            
            trim_sql = """
            DELETE FROM recent_plays 
            WHERE id NOT IN (SELECT id FROM recent_plays ORDER BY played_at DESC LIMIT 100)
            """
            self.conn.execute(trim_sql)
            return True
        except Exception as e:
            logger.error(f"Failed to add recent play: {e}")
            return False

    def get_recent_plays(self, limit: int = 100) -> List[Dict[str, Any]]:
        sql = f"""
        SELECT v.* FROM videos v 
        JOIN recent_plays r ON v.id = r.video_id 
        ORDER BY r.played_at DESC 
        LIMIT {limit}
        """
        try:
            results = self.conn.query(sql)
            return [self.video_dao._convert_row_to_dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to get recent plays: {e}")
            return []

    def clear_recent_plays(self) -> bool:
        sql = "DELETE FROM recent_plays"
        try:
            self.conn.execute(sql)
            return True
        except Exception as e:
            logger.error(f"Failed to clear recent plays: {e}")
            return False


class SQLitePlaybackProgressDAO:
    def __init__(self):
        self.conn = get_sqlite_connection()

    def save_progress(self, video_id: int, progress: int, duration: int, episode_index: int = 0) -> bool:
        import time
        sql = """
        INSERT OR REPLACE INTO playback_progress (video_id, progress, duration, episode_index, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """
        try:
            self.conn.execute(sql, (video_id, progress, duration, episode_index, int(time.time())))
            return True
        except Exception as e:
            logger.error(f"Failed to save playback progress: {e}")
            return False

    def get_progress(self, video_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM playback_progress WHERE video_id = ?"
        try:
            result = self.conn.query(sql, (video_id,))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to get playback progress: {e}")
            return None

    def get_all_progress(self) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM playback_progress"
        try:
            return self.conn.query(sql)
        except Exception as e:
            logger.error(f"Failed to get all playback progress: {e}")
            return []

    def clear_progress(self, video_id: int = None) -> bool:
        if video_id:
            sql = "DELETE FROM playback_progress WHERE video_id = ?"
            params = (video_id,)
        else:
            sql = "DELETE FROM playback_progress"
            params = ()

        try:
            self.conn.execute(sql, params)
            return True
        except Exception as e:
            logger.error(f"Failed to clear playback progress: {e}")
            return False


class SQLiteTagDAO:
    def __init__(self):
        self.conn = get_sqlite_connection()

    def get_or_create_tag(self, tag_name: str) -> int:
        sql = "INSERT OR IGNORE INTO tags (name) VALUES (?)"
        try:
            self.conn.execute(sql, (tag_name,))
            result = self.conn.query("SELECT id FROM tags WHERE name = ?", (tag_name,))
            return result[0]["id"] if result else 0
        except Exception as e:
            logger.error(f"Failed to get or create tag: {e}")
            return 0

    def add_movie_tag(self, video_id: int, tag_name: str) -> bool:
        tag_id = self.get_or_create_tag(tag_name)
        if not tag_id:
            return False

        sql = "INSERT OR IGNORE INTO movie_tags (video_id, tag_id) VALUES (?, ?)"
        try:
            self.conn.execute(sql, (video_id, tag_id))
            return True
        except Exception as e:
            logger.error(f"Failed to add movie tag: {e}")
            return False

    def remove_movie_tag(self, video_id: int, tag_name: str) -> bool:
        sql = """
        DELETE FROM movie_tags 
        WHERE video_id = ? AND tag_id = (SELECT id FROM tags WHERE name = ?)
        """
        try:
            self.conn.execute(sql, (video_id, tag_name))
            return True
        except Exception as e:
            logger.error(f"Failed to remove movie tag: {e}")
            return False

    def get_movie_tags(self, video_id: int) -> List[str]:
        sql = """
        SELECT t.name FROM tags t 
        JOIN movie_tags mt ON t.id = mt.tag_id 
        WHERE mt.video_id = ?
        """
        try:
            results = self.conn.query(sql, (video_id,))
            return [row["name"] for row in results]
        except Exception as e:
            logger.error(f"Failed to get movie tags: {e}")
            return []

    def get_movies_by_tag(self, tag_name: str) -> List[int]:
        sql = """
        SELECT mt.video_id FROM movie_tags mt 
        JOIN tags t ON mt.tag_id = t.id 
        WHERE t.name = ?
        """
        try:
            results = self.conn.query(sql, (tag_name,))
            return [row["video_id"] for row in results]
        except Exception as e:
            logger.error(f"Failed to get movies by tag: {e}")
            return []

    def get_all_tags(self) -> Dict[str, int]:
        sql = """
        SELECT t.name, COUNT(mt.video_id) as count 
        FROM tags t 
        LEFT JOIN movie_tags mt ON t.id = mt.tag_id 
        GROUP BY t.name
        """
        try:
            results = self.conn.query(sql)
            return {row["name"]: row["count"] for row in results}
        except Exception as e:
            logger.error(f"Failed to get all tags: {e}")
            return {}


class SQLiteCustomInfoDAO:
    def __init__(self):
        self.conn = get_sqlite_connection()

    def save_custom_info(self, video_id: int, custom_data: Dict[str, Any]) -> bool:
        sql = "INSERT OR REPLACE INTO custom_info (video_id, data) VALUES (?, ?)"
        try:
            self.conn.execute(sql, (video_id, json.dumps(custom_data)))
            return True
        except Exception as e:
            logger.error(f"Failed to save custom info: {e}")
            return False

    def get_custom_info(self, video_id: int) -> Dict[str, Any]:
        sql = "SELECT data FROM custom_info WHERE video_id = ?"
        try:
            result = self.conn.query(sql, (video_id,))
            if result:
                return json.loads(result[0]["data"])
            return {}
        except Exception as e:
            logger.error(f"Failed to get custom info: {e}")
            return {}

    def get_all_custom_info(self) -> Dict[int, Dict[str, Any]]:
        sql = "SELECT video_id, data FROM custom_info"
        try:
            results = self.conn.query(sql)
            return {row["video_id"]: json.loads(row["data"]) for row in results}
        except Exception as e:
            logger.error(f"Failed to get all custom info: {e}")
            return {}


class SQLiteVideoCache:
    def __init__(self):
        self.video_dao = SQLiteVideoDAO()
        self.favorite_dao = SQLiteFavoriteDAO()
        self.recent_play_dao = SQLiteRecentPlayDAO()
        self.playback_progress_dao = SQLitePlaybackProgressDAO()
        self.tag_dao = SQLiteTagDAO()
        self.custom_info_dao = SQLiteCustomInfoDAO()

    def save_cache(self, video_list: List[Dict[str, Any]]) -> bool:
        try:
            for video in video_list:
                self.video_dao.insert_video(video)
            return True
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            return False

    def load_cache(self) -> Optional[List[Dict[str, Any]]]:
        return self.video_dao.get_all_videos()

    def update_video_cover(self, video_path: str, cover_path: str) -> bool:
        video = self.video_dao.get_video_by_path(video_path)
        if video:
            return self.video_dao.update_video(video["id"], {"cover_path": cover_path})
        return False

    def clear_cache(self) -> bool:
        try:
            self.conn = get_sqlite_connection()
            self.conn.execute("DELETE FROM videos")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    def add_favorite(self, movie_data: Dict[str, Any]) -> bool:
        video = self.video_dao.get_video_by_path(movie_data.get("path", ""))
        if video:
            return self.favorite_dao.add_favorite(video["id"])
        return False

    def remove_favorite(self, movie_path: str) -> bool:
        video = self.video_dao.get_video_by_path(movie_path)
        if video:
            return self.favorite_dao.remove_favorite(video["id"])
        return False

    def get_favorites(self) -> List[Dict[str, Any]]:
        return self.favorite_dao.get_all_favorites()

    def is_favorite(self, movie_path: str) -> bool:
        video = self.video_dao.get_video_by_path(movie_path)
        if video:
            return self.favorite_dao.is_favorite(video["id"])
        return False

    def add_recent_play(self, movie_data: Dict[str, Any]) -> bool:
        video = self.video_dao.get_video_by_path(movie_data.get("path", ""))
        if video:
            return self.recent_play_dao.add_recent_play(video["id"])
        return False

    def get_recent_play(self) -> List[Dict[str, Any]]:
        return self.recent_play_dao.get_recent_plays()

    def clear_recent_play(self) -> bool:
        return self.recent_play_dao.clear_recent_plays()

    def save_custom_info(self, movie_path: str, custom_data: Dict[str, Any]) -> bool:
        video = self.video_dao.get_video_by_path(movie_path)
        if video:
            return self.custom_info_dao.save_custom_info(video["id"], custom_data)
        return False

    def get_custom_info(self, movie_path: str) -> Dict[str, Any]:
        video = self.video_dao.get_video_by_path(movie_path)
        if video:
            return self.custom_info_dao.get_custom_info(video["id"])
        return {}

    def get_all_custom_info(self) -> Dict[str, Dict[str, Any]]:
        all_info = self.custom_info_dao.get_all_custom_info()
        result = {}
        for video_id, data in all_info.items():
            video = self.video_dao.get_video_by_id(video_id)
            if video:
                result[video["path"]] = data
        return result

    def update_movie(self, movie_data: Dict[str, Any]) -> bool:
        video = self.video_dao.get_video_by_path(movie_data.get("path", ""))
        if video:
            return self.video_dao.update_video(video["id"], movie_data)
        return False

    def get_all_tags(self) -> Dict[str, int]:
        return self.tag_dao.get_all_tags()

    def get_movie_tags(self, movie_path: str) -> List[str]:
        video = self.video_dao.get_video_by_path(movie_path)
        if video:
            return self.tag_dao.get_movie_tags(video["id"])
        return []

    def add_movie_tag(self, movie_path: str, tag: str) -> bool:
        video = self.video_dao.get_video_by_path(movie_path)
        if video:
            return self.tag_dao.add_movie_tag(video["id"], tag)
        return False

    def remove_movie_tag(self, movie_path: str, tag: str) -> bool:
        video = self.video_dao.get_video_by_path(movie_path)
        if video:
            return self.tag_dao.remove_movie_tag(video["id"], tag)
        return False

    def get_movies_by_tag(self, tag: str) -> List[str]:
        video_ids = self.tag_dao.get_movies_by_tag(tag)
        paths = []
        for video_id in video_ids:
            video = self.video_dao.get_video_by_id(video_id)
            if video:
                paths.append(video["path"])
        return paths

    def save_playback_progress(self, movie_path: str, progress: int, duration: int, episode_index: int = None) -> bool:
        video = self.video_dao.get_video_by_path(movie_path)
        if video:
            return self.playback_progress_dao.save_progress(
                video["id"], progress, duration, episode_index or 0
            )
        return False

    def get_playback_progress(self, movie_path: str) -> Dict[str, Any]:
        video = self.video_dao.get_video_by_path(movie_path)
        if video:
            progress = self.playback_progress_dao.get_progress(video["id"])
            return progress if progress else {}
        return {}

    def get_all_playback_progress(self) -> Dict[str, Dict[str, Any]]:
        all_progress = self.playback_progress_dao.get_all_progress()
        result = {}
        for progress in all_progress:
            video = self.video_dao.get_video_by_id(progress["video_id"])
            if video:
                result[video["path"]] = progress
        return result

    def clear_playback_progress(self, movie_path: str = None) -> bool:
        if movie_path:
            video = self.video_dao.get_video_by_path(movie_path)
            if video:
                return self.playback_progress_dao.clear_progress(video["id"])
            return False
        return self.playback_progress_dao.clear_progress()