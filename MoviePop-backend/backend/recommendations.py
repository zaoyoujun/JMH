from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from config.app_config import AppConfig
from core.cover_scraper import CoverScraper
from utils.logger import get_logger


logger = get_logger()


class RecommendationRepository:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.db_path = self.config.DATA_DIR / "recommendations.sqlite3"
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS recommendation_feedback (
                    movie_path TEXT PRIMARY KEY,
                    rating REAL,
                    favorite INTEGER DEFAULT 0,
                    playback_percent REAL DEFAULT 0,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS recommendation_tags (
                    movie_path TEXT PRIMARY KEY,
                    tags_json TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS recommendation_profile (
                    profile_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS recommendation_results (
                    movie_path TEXT PRIMARY KEY,
                    score REAL NOT NULL,
                    reasons_json TEXT NOT NULL,
                    breakdown_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    generated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS recommendation_external_results (
                    external_key TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    display_order INTEGER DEFAULT 0,
                    score REAL NOT NULL,
                    reasons_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    generated_at INTEGER NOT NULL
                );
                """
            )
            external_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(recommendation_external_results)").fetchall()
            }
            if "display_order" not in external_columns:
                connection.execute(
                    "ALTER TABLE recommendation_external_results ADD COLUMN display_order INTEGER DEFAULT 0"
                )

    def upsert_feedback(
        self,
        movie_path: str,
        *,
        rating: float | None = None,
        favorite: bool | None = None,
        playback_percent: float | None = None,
    ) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT rating, favorite, playback_percent FROM recommendation_feedback WHERE movie_path = ?",
                (movie_path,),
            ).fetchone()
            next_rating = rating if rating is not None else (row["rating"] if row else None)
            next_favorite = int(favorite if favorite is not None else (row["favorite"] if row else 0))
            next_playback = float(
                playback_percent if playback_percent is not None else (row["playback_percent"] if row else 0)
            )
            connection.execute(
                """
                INSERT INTO recommendation_feedback(movie_path, rating, favorite, playback_percent, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(movie_path) DO UPDATE SET
                    rating = excluded.rating,
                    favorite = excluded.favorite,
                    playback_percent = excluded.playback_percent,
                    updated_at = excluded.updated_at
                """,
                (movie_path, next_rating, next_favorite, next_playback, int(time.time())),
            )

    def get_feedback_map(self) -> dict[str, dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM recommendation_feedback").fetchall()
        return {
            row["movie_path"]: {
                "rating": row["rating"],
                "favorite": bool(row["favorite"]),
                "playback_percent": float(row["playback_percent"] or 0),
                "updated_at": int(row["updated_at"] or 0),
            }
            for row in rows
        }

    def save_tags(self, movie_path: str, tags: list[str]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO recommendation_tags(movie_path, tags_json, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(movie_path) DO UPDATE SET
                    tags_json = excluded.tags_json,
                    updated_at = excluded.updated_at
                """,
                (movie_path, json.dumps(tags, ensure_ascii=False), int(time.time())),
            )

    def get_tags_map(self) -> dict[str, list[str]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT movie_path, tags_json FROM recommendation_tags").fetchall()
        tags_map: dict[str, list[str]] = {}
        for row in rows:
            try:
                value = json.loads(row["tags_json"] or "[]")
            except json.JSONDecodeError:
                value = []
            tags_map[row["movie_path"]] = [str(item).strip() for item in value if str(item).strip()]
        return tags_map

    def save_profile(self, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO recommendation_profile(profile_key, payload_json, updated_at)
                VALUES('default', ?, ?)
                ON CONFLICT(profile_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (json.dumps(payload, ensure_ascii=False), int(time.time())),
            )

    def load_profile(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json, updated_at FROM recommendation_profile WHERE profile_key = 'default'"
            ).fetchone()
        if not row:
            return {}
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        payload["updated_at"] = int(row["updated_at"] or 0)
        return payload

    def save_recommendations(self, items: list[dict[str, Any]]) -> None:
        generated_at = int(time.time())
        with self._connect() as connection:
            connection.execute("DELETE FROM recommendation_results")
            connection.executemany(
                """
                INSERT INTO recommendation_results(movie_path, score, reasons_json, breakdown_json, payload_json, generated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["path"],
                        float(item.get("recommendation_score") or 0),
                        json.dumps(item.get("recommendation_reasons") or [], ensure_ascii=False),
                        json.dumps(item.get("recommendation_breakdown") or {}, ensure_ascii=False),
                        json.dumps(item, ensure_ascii=False),
                        generated_at,
                    )
                    for item in items
                ],
            )

    def load_recommendations(self, limit: int = 24) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json, generated_at
                FROM recommendation_results
                ORDER BY score DESC, generated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        items: list[dict[str, Any]] = []
        generated_at = 0
        for row in rows:
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except json.JSONDecodeError:
                continue
            generated_at = max(generated_at, int(row["generated_at"] or 0))
            items.append(payload)
        return {"items": items, "generated_at": generated_at}

    def save_external_recommendations(self, items: list[dict[str, Any]]) -> None:
        generated_at = int(time.time())
        with self._connect() as connection:
            connection.execute("DELETE FROM recommendation_external_results")
            connection.executemany(
                """
                INSERT INTO recommendation_external_results(external_key, source, display_order, score, reasons_json, payload_json, generated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["external_key"],
                        item.get("source", ""),
                        index,
                        float(item.get("score") or 0),
                        json.dumps(item.get("reasons") or [], ensure_ascii=False),
                        json.dumps(item, ensure_ascii=False),
                        generated_at,
                    )
                    for index, item in enumerate(items)
                ],
            )

    def load_external_recommendations(self, limit: int = 12) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json, generated_at
                FROM recommendation_external_results
                ORDER BY display_order ASC, score DESC, generated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        items: list[dict[str, Any]] = []
        generated_at = 0
        for row in rows:
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except json.JSONDecodeError:
                continue
            generated_at = max(generated_at, int(row["generated_at"] or 0))
            items.append(payload)
        return {"items": items, "generated_at": generated_at}

    def clear(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink(missing_ok=True)
        self._ensure_schema()


class RecommendationEngine:
    GENERIC_QUERY_TERMS = {
        "视频",
        "电影",
        "剧集",
        "动画",
        "动漫",
        "近年作品",
        "经典补片",
        "第一季",
        "第二季",
        "第三季",
        "第四季",
        "第五季",
    }

    KEYWORD_TAGS = {
        "科幻": ["科幻", "未来", "外星", "宇宙", "机甲", "赛博", "太空", "time travel", "space"],
        "动作": ["动作", "枪战", "追击", "格斗", "战斗", "复仇", "特工"],
        "悬疑": ["悬疑", "谜案", "凶手", "真相", "烧脑", "推理"],
        "奇幻": ["奇幻", "魔法", "神话", "龙", "异世界", "超自然"],
        "冒险": ["冒险", "旅程", "探索", "寻宝", "远征"],
        "喜剧": ["喜剧", "搞笑", "幽默", "轻松"],
        "爱情": ["爱情", "恋爱", "心动", "婚姻", "情感"],
        "犯罪": ["犯罪", "黑帮", "警匪", "毒品", "抢劫"],
        "战争": ["战争", "前线", "士兵", "战场", "军队"],
        "动画": ["动画", "动漫", "番剧", "剧场版"],
        "家庭": ["家庭", "亲子", "成长", "治愈"],
        "惊悚": ["惊悚", "惊魂", "恐惧", "逃生", "诡异"],
    }

    def __init__(self, repository: RecommendationRepository) -> None:
        self.repository = repository
        self.config = AppConfig()
        self.config.load_config()
        self.scraper = CoverScraper()

    def _local_cover_url(self, cover_path: str) -> str:
        resolved = Path(cover_path)
        if not resolved.exists():
            return ""
        try:
            version = int(resolved.stat().st_mtime)
        except OSError:
            version = 0
        return f"/covers/{quote(resolved.name)}?v={version}"

    def _cache_external_cover(self, image_url: str, cache_key: str) -> str:
        if not image_url:
            return ""
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(cache_key or "external_cover")).strip("_") or "external_cover"
        for suffix in ("webp", "jpg", "png"):
            existing = self.config.COVERS_DIR / f"{safe_name}.{suffix}"
            if existing.exists():
                return self._local_cover_url(str(existing))
        cover_path = self.scraper._download_cover(image_url, safe_name)  # noqa: SLF001
        if not cover_path:
            return image_url
        return self._local_cover_url(cover_path)

    def generate_auto_tags(self, movie: dict[str, Any]) -> list[str]:
        title = str(movie.get("title") or movie.get("name") or "")
        intro = str(movie.get("intro") or "")
        raw_text = f"{title} {intro} {movie.get('type', '')} {' '.join(movie.get('tags') or [])}".lower()
        tags = set(str(item).strip() for item in (movie.get("tags") or []) if str(item).strip())
        media_type = str(movie.get("type") or "").strip()
        if media_type:
            tags.add(media_type)
        if movie.get("is_series"):
            tags.add("剧集")
        else:
            tags.add("电影")

        year = int(movie.get("year") or 0)
        if year >= 2022:
            tags.add("近年作品")
        elif year and year <= 2015:
            tags.add("经典补片")

        for tag, keywords in self.KEYWORD_TAGS.items():
            if any(keyword.lower() in raw_text for keyword in keywords):
                tags.add(tag)

        for token in self._tokenize_text(title):
            if 1 < len(token) <= 8 and not token.isdigit():
                tags.add(token)

        return sorted(tags)

    def build_profile(self, movies: list[dict[str, Any]], feedback_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
        tag_counter: Counter[str] = Counter()
        type_counter: Counter[str] = Counter()
        year_counter: Counter[str] = Counter()
        seed_titles: list[str] = []
        seed_count = 0

        for movie in movies:
            path = movie.get("path", "")
            feedback = feedback_map.get(path, {})
            weight = self._behavior_weight(movie, feedback)
            if weight <= 0:
                continue
            seed_count += 1
            seed_titles.append(str(movie.get("title") or movie.get("name") or ""))
            for tag in movie.get("auto_tags", []):
                tag_counter[tag] += weight
            type_counter[str(movie.get("type") or "视频")] += weight
            year_counter[self._year_bucket(int(movie.get("year") or 0))] += weight

        profile = {
            "seed_count": seed_count,
            "top_tags": [{"name": name, "weight": round(weight, 2)} for name, weight in tag_counter.most_common(8)],
            "top_types": [{"name": name, "weight": round(weight, 2)} for name, weight in type_counter.most_common(4)],
            "top_year_buckets": [
                {"name": name, "weight": round(weight, 2)} for name, weight in year_counter.most_common(4)
            ],
            "seed_titles": [title for title in seed_titles[:6] if title],
        }
        self.repository.save_profile(profile)
        return profile

    def generate_library_recommendations(self, movies: list[dict[str, Any]]) -> dict[str, Any]:
        feedback_map = self.repository.get_feedback_map()
        prepared_movies = []
        for movie in movies:
            path = movie.get("path", "")
            feedback = feedback_map.get(path, {})
            self.repository.upsert_feedback(
                path,
                favorite=bool(movie.get("is_favorite")),
                playback_percent=float(movie.get("playback", {}).get("percent") or 0),
            )
            auto_tags = self.generate_auto_tags(movie)
            self.repository.save_tags(path, auto_tags)
            prepared = dict(movie)
            prepared["auto_tags"] = auto_tags
            prepared["feedback"] = feedback
            prepared["behavior_weight"] = self._behavior_weight(movie, feedback)
            prepared_movies.append(prepared)

        feedback_map = self.repository.get_feedback_map()
        for movie in prepared_movies:
            movie["feedback"] = feedback_map.get(movie.get("path", ""), movie.get("feedback", {}))
            movie["behavior_weight"] = self._behavior_weight(movie, movie["feedback"])

        profile = self.build_profile(prepared_movies, feedback_map)
        seeds = [movie for movie in prepared_movies if movie["behavior_weight"] >= 0.45]
        if not seeds:
            seeds = sorted(
                prepared_movies,
                key=lambda item: (float(item.get("rating") or 0), int(item.get("year") or 0)),
                reverse=True,
            )[:3]

        recommendations: list[dict[str, Any]] = []
        for movie in prepared_movies:
            if movie["behavior_weight"] >= 0.9:
                continue
            score, breakdown, reasons = self._score_movie(movie, seeds, profile)
            if score <= 0:
                continue
            recommendation = dict(movie)
            recommendation["recommendation_score"] = round(score, 3)
            recommendation["recommendation_breakdown"] = breakdown
            recommendation["recommendation_reasons"] = reasons[:3]
            recommendations.append(recommendation)

        type_counts: Counter[str] = Counter()
        for rec in sorted(recommendations, key=lambda x: x.get("recommendation_score", 0), reverse=True):
            rec_type = str(rec.get("type") or "视频")
            type_counts[rec_type] += 1
            if type_counts[rec_type] > 3:
                rec["recommendation_score"] = round(rec.get("recommendation_score", 0) * 0.88, 3)

        recommendations.sort(
            key=lambda item: (
                item.get("recommendation_score", 0),
                float(item.get("rating") or 0),
                int(item.get("year") or 0),
            ),
            reverse=True,
        )
        self.repository.save_recommendations(recommendations[:36])
        return {
            "items": recommendations[:24],
            "profile": profile,
            "generated_at": int(time.time()),
        }

    def score_library_only(self, movies: list[dict[str, Any]]) -> dict[str, Any]:
        """只重新计算库内推荐分数，不调用外部 API。"""
        return self.generate_library_recommendations(movies)

    def generate_full_recommendations(self, movies: list[dict[str, Any]]) -> dict[str, Any]:
        """完整推荐：库内评分 + 外部抓取。"""
        payload = self.generate_library_recommendations(movies)
        profile = payload.get("profile", {})
        external_items = self.fetch_external_recommendations(profile)
        self.repository.save_external_recommendations(external_items)
        payload["external_items"] = external_items[:15]
        return payload

    def fetch_external_recommendations(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        seed_titles = [title for title in profile.get("seed_titles", [])[:4] if title]
        tag_terms = [
            item["name"]
            for item in profile.get("top_tags", [])[:6]
            if item.get("name") and not self._is_generic_query_term(item.get("name"))
        ]
        type_terms = [
            item["name"]
            for item in profile.get("top_types", [])[:3]
            if item.get("name") and not self._is_generic_query_term(item.get("name"))
        ]
        query_terms = seed_titles + tag_terms + type_terms
        dedupe: set[str] = set()
        results: list[dict[str, Any]] = []
        blended_terms: list[str] = []
        seed_titles = [title for title in seed_titles[:3] if title]
        top_tags = [item for item in tag_terms[:3] if item]
        for title in seed_titles:
            for tag in top_tags:
                blended_terms.append(f"{title} {tag}")

        for term in self._unique_terms(query_terms + blended_terms)[:10]:
            results.extend(self._fetch_tmdb_candidates(term, dedupe))
            results.extend(self._fetch_douban_candidates(term, dedupe))
            results.extend(self._fetch_bangumi_candidates(term, dedupe))
            results.extend(self._fetch_anibk_candidates(term, dedupe))
            results.extend(self._fetch_imdb_candidates(term, dedupe))
        return self._blend_external_results(results)[:15]

    def _unique_terms(self, terms: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for term in terms:
            normalized = re.sub(r"\s+", " ", str(term or "").strip())
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            ordered.append(normalized)
        return ordered

    def _is_generic_query_term(self, term: str) -> bool:
        normalized = re.sub(r"\s+", "", str(term or "").strip().lower())
        if not normalized:
            return True
        if normalized in self.GENERIC_QUERY_TERMS:
            return True
        return bool(re.fullmatch(r"第?[一二三四五六七八九十0-9]+季", normalized))

    def _blend_external_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in sorted(results, key=lambda value: value.get("score", 0), reverse=True):
            grouped.setdefault(str(item.get("source") or "Other"), []).append(item)

        preferred_order = ["Douban", "TMDB", "Bangumi", "AniBK", "IMDb"]
        ordered_sources = [source for source in preferred_order if grouped.get(source)]
        ordered_sources.extend(source for source in grouped.keys() if source not in ordered_sources)

        blended: list[dict[str, Any]] = []
        per_source_cap = {"Douban": 4, "TMDB": 4, "Bangumi": 3, "AniBK": 3, "IMDb": 3}
        used_counts = {source: 0 for source in ordered_sources}

        while ordered_sources:
            progressed = False
            next_sources: list[str] = []
            for source in ordered_sources:
                queue = grouped.get(source) or []
                cap = per_source_cap.get(source, 3)
                if queue and used_counts.get(source, 0) < cap:
                    blended.append(queue.pop(0))
                    used_counts[source] = used_counts.get(source, 0) + 1
                    progressed = True
                if queue and used_counts.get(source, 0) < cap:
                    next_sources.append(source)
            if not progressed:
                break
            ordered_sources = next_sources

        leftovers = []
        for source, queue in grouped.items():
            leftovers.extend(queue)
        leftovers.sort(key=lambda value: value.get("score", 0), reverse=True)
        blended.extend(leftovers)
        return blended

    def _fetch_tmdb_candidates(self, term: str, dedupe: set[str]) -> list[dict[str, Any]]:
        api_key = str(getattr(self.config, "TMDB_API_KEY", "") or "").strip()
        if not api_key or not term:
            return []
        try:
            response = requests.get(
                f"{self.config.TMDB_API_BASE.rstrip('/')}/search/multi",
                params={"api_key": api_key, "language": "zh-CN", "query": term, "include_adult": "false"},
                timeout=4,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("TMDB recommendation fetch failed for %s: %s", term, exc)
            return []

        items: list[dict[str, Any]] = []
        for item in payload.get("results", [])[:6]:
            title = item.get("title") or item.get("name") or ""
            if not title:
                continue
            year = (item.get("release_date") or item.get("first_air_date") or "")[:4]
            key = f"tmdb::{title}::{year}"
            if key in dedupe:
                continue
            dedupe.add(key)
            poster_path = item.get("poster_path") or ""
            poster_url = f"{self.config.TMDB_IMAGE_BASE.rstrip('/')}{poster_path}" if poster_path else ""
            score = float(item.get("vote_average") or 0) * 0.1 + float(item.get("popularity") or 0) * 0.01
            items.append(
                {
                    "external_key": key,
                    "source": "TMDB",
                    "title": title,
                    "year": int(year) if year.isdigit() else None,
                    "intro": item.get("overview") or "",
                    "poster_url": poster_url,
                    "url": f"{self.config.TMDB_WEB_BASE.rstrip('/')}/{item.get('media_type') or 'movie'}/{item.get('id')}",
                    "score": round(score, 3),
                    "reasons": [f"来自 TMDB 的 {term} 相关条目", "适合站外补片"],
                }
            )
        return items

    def _fetch_douban_candidates(self, term: str, dedupe: set[str]) -> list[dict[str, Any]]:
        if not term:
            return []
        try:
            response = requests.get(
                "https://movie.douban.com/j/subject_suggest",
                params={"q": term},
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://movie.douban.com/"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("Douban recommendation fetch failed for %s: %s", term, exc)
            return []

        items: list[dict[str, Any]] = []
        for item in payload[:5]:
            title = item.get("title") or ""
            year = item.get("year") or ""
            key = f"douban::{title}::{year}"
            if not title or key in dedupe:
                continue
            dedupe.add(key)
            detail_url = item.get("url") or ""
            poster_url = item.get("img") or ""
            if detail_url:
                try:
                    poster_url = self.scraper._get_douban_cover(detail_url) or poster_url  # noqa: SLF001
                except Exception as exc:
                    logger.warning("Douban cover resolve failed for %s: %s", detail_url, exc)
            poster_url = self._cache_external_cover(poster_url, key)
            items.append(
                {
                    "external_key": key,
                    "source": "Douban",
                    "title": title,
                    "year": int(year) if str(year).isdigit() else None,
                    "intro": "",
                    "poster_url": poster_url,
                    "url": detail_url,
                    "score": 0.62,
                    "reasons": [f"豆瓣搜索命中“{term}”", "适合中文片库继续扩展"],
                }
            )
        return items

    def _fetch_anibk_candidates(self, term: str, dedupe: set[str]) -> list[dict[str, Any]]:
        if not term:
            return []
        try:
            payload = self.scraper._fetch_anibk_list(term)[:5]
        except Exception as exc:
            logger.warning("AniBK recommendation fetch failed for %s: %s", term, exc)
            return []

        items: list[dict[str, Any]] = []
        for item in payload:
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            key = f"anibk::{url or title}"
            if not title or not url or key in dedupe:
                continue
            dedupe.add(key)
            poster_url = ""
            try:
                poster_url = self.scraper._get_anibk_cover(url) or ""
            except Exception:
                poster_url = ""
            items.append(
                {
                    "external_key": key,
                    "source": "AniBK",
                    "title": title,
                    "year": None,
                    "intro": "",
                    "poster_url": poster_url,
                    "url": url,
                    "score": 0.56,
                    "reasons": [f"AniBK 命中“{term}”", "适合补动漫和番剧"],
                }
            )
        return items

    def _fetch_imdb_candidates(self, term: str, dedupe: set[str]) -> list[dict[str, Any]]:
        if not term:
            return []
        safe_term = re.sub(r"[^a-z0-9]+", "", term.lower())[:2] or "a"
        try:
            response = requests.get(
                f"https://v3.sg.media-imdb.com/suggestion/{safe_term}/{quote(term)}.json",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("IMDb recommendation fetch failed for %s: %s", term, exc)
            return []

        items: list[dict[str, Any]] = []
        for item in payload.get("d", [])[:5]:
            title = item.get("l") or ""
            year = item.get("y") or ""
            key = f"imdb::{title}::{year}"
            if not title or key in dedupe:
                continue
            dedupe.add(key)
            imdb_id = item.get("id") or ""
            items.append(
                {
                    "external_key": key,
                    "source": "IMDb",
                    "title": title,
                    "year": int(year) if str(year).isdigit() else None,
                    "intro": "",
                    "poster_url": item.get("i", {}).get("imageUrl", "") if isinstance(item.get("i"), dict) else "",
                    "url": f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else "",
                    "score": 0.58,
                    "reasons": [f"IMDb 搜索命中“{term}”", "适合做站外发现"],
                }
            )
        return items

    def _fetch_bangumi_candidates(self, term: str, dedupe: set[str]) -> list[dict[str, Any]]:
        if not term:
            return []
        items: list[dict[str, Any]] = []
        try:
            response = requests.get(
                f"https://api.bgm.tv/search/subject/{quote(term)}",
                params={"type": 2, "limit": 5, "responseGroup": "medium"},
                headers={"User-Agent": "JimiHua/1.0"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("data", [])[:5]:
                title = str(item.get("name") or item.get("name_cn") or "")
                if not title:
                    continue
                dedupe_key = f"bangumi::{title}::{item.get('id')}"
                if dedupe_key in dedupe:
                    continue
                dedupe.add(dedupe_key)
                images = item.get("images") or {}
                poster_url = images.get("large") or images.get("common") or ""
                rating_val = float((item.get("rating") or {}).get("score") or 0)
                items.append(
                    {
                        "external_key": dedupe_key,
                        "source": "Bangumi",
                        "title": title,
                        "year": None,
                        "intro": str(item.get("summary") or ""),
                        "poster_url": poster_url,
                        "url": f"https://bgm.tv/subject/{item.get('id')}",
                        "score": rating_val / 10 if rating_val else 0.5,
                        "reasons": ["Bangumi 高分动漫推荐", "适合补番"],
                    }
                )
        except Exception:
            logger.warning("Bangumi 查询失败: %s", term, exc_info=True)
        return items

    def _score_movie(
        self,
        movie: dict[str, Any],
        seeds: list[dict[str, Any]],
        profile: dict[str, Any],
    ) -> tuple[float, dict[str, float], list[str]]:
        tag_weights = {item["name"]: float(item["weight"]) for item in profile.get("top_tags", [])}
        type_weights = {item["name"]: float(item["weight"]) for item in profile.get("top_types", [])}
        year_weights = {item["name"]: float(item["weight"]) for item in profile.get("top_year_buckets", [])}
        movie_tags = set(movie.get("auto_tags") or [])

        content_score = sum(tag_weights.get(tag, 0) for tag in movie_tags)
        if tag_weights:
            content_score /= max(sum(tag_weights.values()), 1)

        type_score = type_weights.get(str(movie.get("type") or "视频"), 0)
        if type_weights:
            type_score /= max(sum(type_weights.values()), 1)

        year_score = year_weights.get(self._year_bucket(int(movie.get("year") or 0)), 0)
        if year_weights:
            year_score /= max(sum(year_weights.values()), 1)

        collaborative_score = 0.0
        collaborative_reason = ""
        for seed in seeds[:5]:
            similarity = self._movie_similarity(seed, movie)
            weighted = similarity * max(float(seed.get("behavior_weight") or 0), 0.3)
            if weighted > collaborative_score:
                collaborative_score = weighted
                collaborative_reason = str(seed.get("title") or seed.get("name") or "")

        rating_score = min(max(float(movie.get("rating") or 0) / 10, 0), 1)
        freshness_bonus = 0.18 if not movie.get("playback", {}).get("has_progress") else 0.04
        final_score = (
            0.40 * content_score
            + 0.14 * type_score
            + 0.12 * year_score
            + 0.24 * collaborative_score
            + 0.10 * rating_score
            + freshness_bonus
        )

        reasons: list[str] = []
        top_matches = [tag for tag in movie_tags if tag in tag_weights][:2]
        if top_matches:
            reasons.append(f"命中你的偏好标签：{' / '.join(top_matches)}")
        if collaborative_reason:
            reasons.append(f"与《{collaborative_reason}》风格接近")
        if type_score > 0.15:
            reasons.append(f"属于你最近偏好的{movie.get('type') or '影视类型'}")
        if year_score > 0.1:
            reasons.append(f"年代段匹配：{self._year_bucket(int(movie.get('year') or 0))}")
        if rating_score >= 0.7:
            reasons.append(f"片库评分表现较好：{movie.get('rating')}")
        if not reasons:
            reasons.append("综合你的收藏、播放和标签偏好生成")

        breakdown = {
            "content": round(content_score, 3),
            "type": round(type_score, 3),
            "year": round(year_score, 3),
            "collaborative": round(collaborative_score, 3),
            "rating": round(rating_score, 3),
        }
        return final_score, breakdown, reasons

    def _movie_similarity(self, left: dict[str, Any], right: dict[str, Any]) -> float:
        left_tags = set(left.get("auto_tags") or [])
        right_tags = set(right.get("auto_tags") or [])
        tag_score = 0.0
        if left_tags or right_tags:
            union = left_tags | right_tags
            inter = left_tags & right_tags
            tag_score = len(inter) / max(len(union), 1)

        type_score = 1.0 if str(left.get("type")) == str(right.get("type")) else 0.0
        year_gap = abs(int(left.get("year") or 0) - int(right.get("year") or 0))
        year_score = max(0.0, 1 - min(year_gap, 12) / 12)
        return (0.55 * tag_score) + (0.25 * type_score) + (0.2 * year_score)

    def _behavior_weight(self, movie: dict[str, Any], feedback: dict[str, Any]) -> float:
        rating = float((feedback or {}).get("rating") or 0)
        favorite = bool((feedback or {}).get("favorite") or movie.get("is_favorite"))
        playback_percent = float((feedback or {}).get("playback_percent") or movie.get("playback", {}).get("percent") or 0)
        score = 0.0
        if favorite:
            score += 0.55
        if rating > 0:
            score += min(rating / 5, 1) * 0.45
        if playback_percent >= 75:
            score += 0.25
        elif playback_percent >= 25:
            score += 0.12
        updated_at = int((feedback or {}).get("updated_at") or 0)
        if updated_at > 0:
            days_old = max(0, (time.time() - updated_at) / 86400)
            recency_factor = max(0.6, 1.0 - days_old * 0.005)
            score *= recency_factor
        return min(score, 1.4)

    def _year_bucket(self, year: int) -> str:
        if year >= 2022:
            return "2022-至今"
        if year >= 2016:
            return "2016-2021"
        if year >= 2010:
            return "2010-2015"
        if year > 0:
            return "2010年以前"
        return "年份未知"

    def _tokenize_text(self, text: str) -> list[str]:
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        latin = re.findall(r"[A-Za-z][A-Za-z0-9'\-]{2,}", text)
        return chinese + latin
