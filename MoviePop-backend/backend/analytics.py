from __future__ import annotations

import datetime as dt
import html
import math
import re
import time
from collections import Counter, defaultdict
from typing import Any

from backend.warehouse import ClickHouseWarehouse, build_time_dimension_rows
from config.app_config import AppConfig
from utils.database import VideoCache
from utils.filename_parser import build_media_tags

LOCAL_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")


class AnalyticsETLService:
    def __init__(self, library_service, recommendation_repository) -> None:
        self.config = AppConfig()
        self.config.load_config()
        self.library_service = library_service
        self.repository = recommendation_repository
        self.cache = VideoCache()
        self.warehouse = ClickHouseWarehouse()

    def build_snapshot(self) -> dict[str, Any]:
        movies = self.library_service.get_movies(mode="all", source="combined", search="", force_refresh=False)
        favorites = self.cache.get_favorites()
        recent_play = self.cache.get_recent_play()
        playback_map = self.cache.get_all_playback_progress()
        feedback_map = self.repository.get_feedback_map()
        tag_map = self.repository.get_tags_map()

        favorite_paths = {str(item.get("path") or "") for item in favorites}
        recent_paths = {str(item.get("path") or "") for item in recent_play}
        now = dt.datetime.now()
        today = now.date()
        dates: set[dt.date] = {today}

        media_rows: list[dict[str, Any]] = []
        tag_rows: list[dict[str, Any]] = []
        scan_rows: list[dict[str, Any]] = []
        behavior_rows: list[dict[str, Any]] = []
        analytics_movies: list[dict[str, Any]] = []

        for movie in movies:
            path = str(movie.get("path") or "").strip()
            if not path:
                continue
            playback = playback_map.get(path, {}) if isinstance(playback_map, dict) else {}
            feedback = feedback_map.get(path, {}) if isinstance(feedback_map, dict) else {}
            base_tags = [
                str(item).strip()
                for item in (movie.get("tags") or [])
                if str(item).strip()
            ]
            auto_tags = self._build_auto_tags(movie, tag_map.get(path, []))
            merged_tags = self._unique(base_tags + auto_tags)
            source = "local" if LOCAL_PATH_RE.match(path) else "remote"
            provider = str(movie.get("remote_provider") or ("local" if source == "local" else self.config.REMOTE_PROVIDER)).strip()
            title = str(movie.get("title") or movie.get("name") or path.split("/")[-1]).strip()
            year = self._safe_int(movie.get("year"), 0)
            playback_percent = self._playback_percent(playback)
            rating = float(feedback.get("rating") or movie.get("rating") or 0)
            updated_at = self._timestamp_to_datetime(
                playback.get("timestamp") or feedback.get("updated_at") or time.time()
            )
            dates.add(updated_at.date())

            analytics_movie = {
                "path": path,
                "title": title,
                "intro": str(movie.get("intro") or "").strip(),
                "type": str(movie.get("type") or "视频").strip(),
                "source": source,
                "provider": provider,
                "year": year,
                "year_bucket": self._year_bucket(year),
                "is_series": bool(movie.get("is_series")),
                "is_favorite": path in favorite_paths or bool(feedback.get("favorite")),
                "is_recent": path in recent_paths,
                "playback_percent": playback_percent,
                "progress_seconds": float(playback.get("progress") or 0),
                "duration_seconds": float(playback.get("duration") or 0),
                "rating": rating,
                "tags": merged_tags,
                "cover_path": str(movie.get("cover_path") or "").strip(),
                "has_intro": bool(str(movie.get("intro") or "").strip()),
                "updated_at": updated_at,
            }
            analytics_movies.append(analytics_movie)

            media_rows.append(
                {
                    "media_path": path,
                    "title": title,
                    "media_type": analytics_movie["type"],
                    "year": year if year > 0 else 0,
                    "year_bucket": analytics_movie["year_bucket"],
                    "source": source,
                    "provider": provider,
                    "is_series": 1 if analytics_movie["is_series"] else 0,
                    "favorite": 1 if analytics_movie["is_favorite"] else 0,
                    "has_intro": 1 if analytics_movie["has_intro"] else 0,
                    "has_cover": 1 if analytics_movie["cover_path"] else 0,
                    "updated_at": updated_at,
                }
            )

            for tag in merged_tags:
                tag_rows.append(
                    {
                        "media_path": path,
                        "tag": tag,
                        "tag_source": "hybrid",
                        "updated_at": updated_at,
                    }
                )

            scan_rows.append(
                {
                    "snapshot_date": today,
                    "media_path": path,
                    "source": source,
                    "provider": provider,
                    "tag_count": len(merged_tags),
                    "playback_percent": playback_percent,
                    "rating": rating,
                    "updated_at": updated_at,
                }
            )

            behavior_rows.append(
                {
                    "event_date": updated_at.date(),
                    "media_path": path,
                    "favorite": 1 if analytics_movie["is_favorite"] else 0,
                    "recent": 1 if analytics_movie["is_recent"] else 0,
                    "playback_percent": playback_percent,
                    "progress_seconds": analytics_movie["progress_seconds"],
                    "duration_seconds": analytics_movie["duration_seconds"],
                    "rating": rating,
                    "watch_seconds": analytics_movie["progress_seconds"],
                    "updated_at": updated_at,
                }
            )

        return {
            "movies": analytics_movies,
            "dim_time_rows": build_time_dimension_rows(dates),
            "dim_media_rows": media_rows,
            "bridge_media_tag_rows": tag_rows,
            "fact_scan_rows": scan_rows,
            "fact_behavior_rows": behavior_rows,
        }

    def sync_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return self.warehouse.sync_snapshot(snapshot)

    def build_report_payload(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        movies = snapshot.get("movies", [])
        if not movies:
            return {
                "overview": {},
                "type_distribution": [],
                "genre_preferences": [],
                "year_distribution": [],
                "source_distribution": [],
                "completion_stats": {},
                "recent_activity": [],
                "dashboard_html": "",
                "warehouse_status": self.warehouse.get_status(),
            }

        total_movies = len(movies)
        favorites = sum(1 for movie in movies if movie.get("is_favorite"))
        watched = sum(1 for movie in movies if movie.get("playback_percent", 0) > 0)
        total_watch_hours = round(sum(float(movie.get("progress_seconds") or 0) for movie in movies) / 3600, 1)
        ratings = [float(movie.get("rating") or 0) for movie in movies if float(movie.get("rating") or 0) > 0]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

        type_counter = Counter(str(movie.get("type") or "视频") for movie in movies)
        type_distribution = [
            {"name": name, "count": count, "percent": round(count / total_movies * 100)}
            for name, count in type_counter.most_common()
        ]

        year_counter = Counter(str(movie.get("year_bucket") or "年份未知") for movie in movies)
        year_distribution = [{"name": name, "count": count} for name, count in year_counter.most_common()]

        source_counter = Counter(str(movie.get("source") or "remote") for movie in movies)
        source_distribution = [{"name": name, "count": count} for name, count in source_counter.most_common()]

        completed = sum(1 for movie in movies if float(movie.get("playback_percent") or 0) >= 90)
        in_progress = sum(1 for movie in movies if 0 < float(movie.get("playback_percent") or 0) < 90)
        not_started = total_movies - completed - in_progress

        tag_weights: Counter[str] = Counter()
        for movie in movies:
            weight = 1.0
            if movie.get("is_favorite"):
                weight += 1.2
            weight += float(movie.get("rating") or 0) * 0.18
            weight += float(movie.get("playback_percent") or 0) / 100 * 0.9
            for tag in movie.get("tags", []):
                tag_weights[tag] += weight
        genre_preferences = [
            {"name": name, "weight": round(weight, 2)}
            for name, weight in tag_weights.most_common(16)
        ]

        activity_items = [
            {
                "title": str(movie.get("title") or ""),
                "type": str(movie.get("type") or "视频"),
                "timestamp": int(self._datetime_from_movie(movie).timestamp()),
                "progress": round(float(movie.get("playback_percent") or 0)),
            }
            for movie in sorted(movies, key=self._datetime_from_movie, reverse=True)
            if float(movie.get("progress_seconds") or 0) > 0 or movie.get("is_recent")
        ][:12]

        payload = {
            "overview": {
                "total_movies": total_movies,
                "favorites": favorites,
                "watched": watched,
                "total_watch_hours": total_watch_hours,
                "avg_rating": avg_rating,
            },
            "type_distribution": type_distribution,
            "genre_preferences": genre_preferences,
            "year_distribution": year_distribution,
            "source_distribution": source_distribution,
            "completion_stats": {
                "completed": completed,
                "in_progress": in_progress,
                "not_started": not_started,
            },
            "recent_activity": activity_items,
            "dashboard_html": self._build_dashboard_html(
                type_distribution,
                year_distribution,
                source_distribution,
                genre_preferences,
                activity_items,
            ),
            "warehouse_status": self.warehouse.get_status(),
        }
        return payload

    def _build_auto_tags(self, movie: dict[str, Any], existing_tags: list[str]) -> list[str]:
        tags = self._unique([str(item).strip() for item in existing_tags if str(item).strip()])
        tags.extend(build_media_tags(movie))
        title = str(movie.get("title") or movie.get("name") or "")
        intro = str(movie.get("intro") or "")
        media_type = str(movie.get("type") or "")
        content = f"{title} {intro} {media_type}".lower()
        keyword_map = {
            "科幻": ["科幻", "宇宙", "太空", "未来", "赛博", "space", "future"],
            "动作": ["动作", "枪", "格斗", "战斗", "追击"],
            "悬疑": ["悬疑", "推理", "真相", "谜案", "烧脑"],
            "奇幻": ["奇幻", "魔法", "神话", "异世界", "超自然"],
            "喜剧": ["喜剧", "搞笑", "轻松", "幽默"],
            "爱情": ["爱情", "恋爱", "心动", "婚姻", "情感"],
            "犯罪": ["犯罪", "黑帮", "毒品", "劫案", "警匪"],
            "动画": ["动画", "动漫", "番剧"],
        }
        for tag, keywords in keyword_map.items():
            if any(keyword.lower() in content for keyword in keywords):
                tags.append(tag)
        if movie.get("is_series"):
            tags.append("剧集")
        else:
            tags.append("电影")
        year = self._safe_int(movie.get("year"), 0)
        if year >= 2022:
            tags.append("近年作品")
        elif 0 < year <= 2015:
            tags.append("经典片")
        tags.extend(self._tokenize_text(title)[:8])
        return self._unique(tags)

    @staticmethod
    def _tokenize_text(text: str) -> list[str]:
        raw = str(text or "").lower()
        latin_tokens = re.findall(r"[a-z0-9]{2,}", raw)
        cjk_sequences = re.findall(r"[\u4e00-\u9fff]{2,}", raw)
        cjk_tokens: list[str] = []
        for seq in cjk_sequences:
            cjk_tokens.append(seq)
            if 2 <= len(seq) <= 8:
                for index in range(len(seq) - 1):
                    cjk_tokens.append(seq[index : index + 2])
        return list(dict.fromkeys(latin_tokens + cjk_tokens))

    @staticmethod
    def _unique(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            value = str(item or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:  # noqa: BLE001
            return default

    @staticmethod
    def _playback_percent(playback: dict[str, Any]) -> float:
        progress = float(playback.get("progress") or 0)
        duration = float(playback.get("duration") or 0)
        if duration <= 0:
            return 0.0
        return max(0.0, min(100.0, round(progress / duration * 100, 2)))

    @staticmethod
    def _timestamp_to_datetime(timestamp: Any) -> dt.datetime:
        try:
            return dt.datetime.fromtimestamp(float(timestamp))
        except Exception:  # noqa: BLE001
            return dt.datetime.now()

    @staticmethod
    def _year_bucket(year: int) -> str:
        if year >= 2022:
            return "2022-至今"
        if year >= 2016:
            return "2016-2021"
        if year >= 2010:
            return "2010-2015"
        if year > 0:
            return "2010年以前"
        return "年份未知"

    @staticmethod
    def _datetime_from_movie(movie: dict[str, Any]) -> dt.datetime:
        if "updated_at" in movie and isinstance(movie["updated_at"], dt.datetime):
            return movie["updated_at"]
        return dt.datetime.now()

    def _build_dashboard_html(
        self,
        type_distribution: list[dict[str, Any]],
        year_distribution: list[dict[str, Any]],
        source_distribution: list[dict[str, Any]],
        genre_preferences: list[dict[str, Any]],
        activity_items: list[dict[str, Any]],
    ) -> str:
        try:
            from pyecharts import options as opts
            from pyecharts.charts import Bar, Funnel, Line, Pie, Tab
            from pyecharts.globals import CurrentConfig

            CurrentConfig.ONLINE_HOST = "https://assets.pyecharts.org/assets/v5/"

            bar = (
                Bar(init_opts=opts.InitOpts(width="1000px", height="360px", bg_color="#10161f"))
                .add_xaxis([item["name"] for item in type_distribution[:10]])
                .add_yaxis("数量", [item["count"] for item in type_distribution[:10]], category_gap="40%")
                .set_global_opts(
                    title_opts=opts.TitleOpts(title="类型分布"),
                    xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(color="#dbe7f5")),
                    yaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(color="#dbe7f5")),
                    legend_opts=opts.LegendOpts(is_show=False),
                )
            )

            pie = (
                Pie(init_opts=opts.InitOpts(width="1000px", height="360px", bg_color="#10161f"))
                .add("来源", [(item["name"], item["count"]) for item in source_distribution])
                .set_global_opts(title_opts=opts.TitleOpts(title="来源分布"))
                .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {d}%"))
            )

            line = (
                Line(init_opts=opts.InitOpts(width="1000px", height="360px", bg_color="#10161f"))
                .add_xaxis([item["name"] for item in year_distribution])
                .add_yaxis("影片数", [item["count"] for item in year_distribution], is_smooth=True)
                .set_global_opts(
                    title_opts=opts.TitleOpts(title="年代分布"),
                    xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(color="#dbe7f5")),
                    yaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(color="#dbe7f5")),
                    legend_opts=opts.LegendOpts(is_show=False),
                )
            )

            funnel = (
                Funnel(init_opts=opts.InitOpts(width="1000px", height="360px", bg_color="#10161f"))
                .add(
                    "标签权重",
                    [(item["name"], item["weight"]) for item in genre_preferences[:10]],
                )
                .set_global_opts(title_opts=opts.TitleOpts(title="偏好标签"))
            )

            timeline = (
                Bar(init_opts=opts.InitOpts(width="1000px", height="360px", bg_color="#10161f"))
                .add_xaxis([item["title"][:14] for item in reversed(activity_items)])
                .add_yaxis("进度", [item["progress"] for item in reversed(activity_items)])
                .set_global_opts(
                    title_opts=opts.TitleOpts(title="近期观看进度"),
                    xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=20, color="#dbe7f5")),
                    yaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(color="#dbe7f5")),
                    legend_opts=opts.LegendOpts(is_show=False),
                )
            )

            tab = Tab(page_title="MoviePop 观影分析")
            tab.add(bar, "类型")
            tab.add(pie, "来源")
            tab.add(line, "年代")
            tab.add(funnel, "标签")
            tab.add(timeline, "动态")
            body = tab.render_embed().replace(
                """
        .tab {
            overflow: hidden;
            border: 1px solid #ccc;
            background-color: #f1f1f1;
        }

        .tab button {
            background-color: inherit;
            float: left;
            border: none;
            outline: none;
            cursor: pointer;
            padding: 12px 16px;
            transition: 0.3s;
        }

        .tab button:hover {
            background-color: #ddd;
        }

        .tab button.active {
            background-color: #ccc;
        }
""",
                """
        .tab {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 0 0 18px;
            padding: 10px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 18px;
            background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
        }

        .tab button {
            background: rgba(255, 255, 255, 0.04);
            color: rgba(238, 245, 255, 0.82);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 999px;
            outline: none;
            cursor: pointer;
            padding: 10px 16px;
            transition: 0.2s ease;
            font-size: 14px;
        }

        .tab button:hover {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.12);
            color: #ffffff;
        }

        .tab button.active {
            background: linear-gradient(135deg, #ff9248 0%, #53d0c2 100%);
            color: #081018;
            border-color: transparent;
            box-shadow: 0 10px 22px rgba(0, 0, 0, 0.18);
        }
""",
            )
            return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MoviePop 观影分析</title>
  <style>
    body {{
      margin: 0;
      padding: 20px;
      background: radial-gradient(circle at top, #1b2636 0%, #0a1018 62%);
      color: #eef5ff;
      font-family: 'Microsoft YaHei', sans-serif;
    }}
    .dashboard-head {{
      margin: 0 0 18px;
    }}
    .dashboard-head h2 {{
      margin: 0 0 6px;
      font-size: 28px;
    }}
    .dashboard-head p {{
      margin: 0;
      color: rgba(238, 245, 255, 0.7);
    }}
    .box {{
      border-radius: 22px;
      overflow: hidden;
    }}
    .chart-container {{
      border-radius: 18px;
      overflow: hidden;
    }}
  </style>
</head>
<body>
  <div class="dashboard-head">
    <h2>观影分析大屏</h2>
    <p>基于片库、播放行为、收藏和评分自动生成</p>
  </div>
  {body}
</body>
</html>
"""
        except Exception as exc:  # noqa: BLE001
            return (
                "<html><body style=\"background:#0f1720;color:#e6edf7;font-family:Microsoft YaHei,sans-serif;\">"
                f"<p>Pyecharts 大屏暂不可用：{html.escape(str(exc))}</p>"
                "</body></html>"
            )


class TFIDFRecommendationEngine:
    def generate(self, movies: list[dict[str, Any]]) -> dict[str, Any]:
        if not movies:
            return {"items": [], "profile": {}, "auto_tags_map": {}}

        prepared_movies = []
        document_frequency: Counter[str] = Counter()
        auto_tags_map: dict[str, list[str]] = {}

        for movie in movies:
            tags = [str(item).strip() for item in movie.get("tags", []) if str(item).strip()]
            auto_tags_map[str(movie.get("path") or "")] = tags
            tokens = self._document_tokens(movie)
            prepared = dict(movie)
            prepared["tokens"] = tokens
            prepared["behavior_weight"] = self._behavior_weight(movie)
            prepared_movies.append(prepared)
            for token in set(tokens):
                document_frequency[token] += 1

        total_docs = max(1, len(prepared_movies))
        vectors: dict[str, dict[str, float]] = {}
        norms: dict[str, float] = {}

        for movie in prepared_movies:
            path = str(movie.get("path") or "")
            vector = self._tfidf_vector(movie.get("tokens", []), document_frequency, total_docs)
            vectors[path] = vector
            norms[path] = math.sqrt(sum(value * value for value in vector.values())) or 1.0

        seed_movies = [movie for movie in prepared_movies if movie["behavior_weight"] >= 0.35]
        if not seed_movies:
            seed_movies = sorted(
                prepared_movies,
                key=lambda item: (float(item.get("rating") or 0), float(item.get("playback_percent") or 0)),
                reverse=True,
            )[:5]

        profile_vector: defaultdict[str, float] = defaultdict(float)
        tag_counter: Counter[str] = Counter()
        type_counter: Counter[str] = Counter()
        year_counter: Counter[str] = Counter()
        seed_titles: list[str] = []

        for movie in seed_movies:
            weight = max(0.25, float(movie.get("behavior_weight") or 0))
            path = str(movie.get("path") or "")
            for token, value in vectors.get(path, {}).items():
                profile_vector[token] += value * weight
            for tag in movie.get("tags", []):
                tag_counter[tag] += weight
            type_counter[str(movie.get("type") or "视频")] += weight
            year_counter[str(movie.get("year_bucket") or "年份未知")] += weight
            if movie.get("title"):
                seed_titles.append(str(movie["title"]))

        profile_norm = math.sqrt(sum(value * value for value in profile_vector.values())) or 1.0
        recommendations: list[dict[str, Any]] = []

        for movie in prepared_movies:
            if float(movie.get("behavior_weight") or 0) >= 0.95:
                continue
            path = str(movie.get("path") or "")
            vector = vectors.get(path, {})
            similarity = self._cosine(profile_vector, vector, profile_norm, norms.get(path, 1.0))
            score = similarity
            if movie.get("type") in type_counter:
                score += 0.08
            if movie.get("year_bucket") in year_counter:
                score += 0.05
            score += min(0.1, float(movie.get("rating") or 0) / 50)
            if score <= 0.08:
                continue

            top_overlap = self._top_overlap(profile_vector, vector)
            reasons = []
            if top_overlap:
                reasons.append("关键词匹配：" + " / ".join(top_overlap[:3]))
            if movie.get("type") in type_counter:
                reasons.append(f"符合你最近常看的{movie.get('type')}")
            if movie.get("year_bucket") in year_counter:
                reasons.append(f"年代偏好命中：{movie.get('year_bucket')}")
            if not reasons:
                reasons.append("与最近观看和收藏内容相似")

            item = dict(movie)
            item["updated_at"] = int(AnalyticsETLService._datetime_from_movie(movie).timestamp())
            item["recommendation_origin"] = "library"
            item["recommendation_score"] = round(score, 3)
            item["recommendation_breakdown"] = {
                "tfidf_similarity": round(similarity, 3),
                "type_bonus": 0.08 if movie.get("type") in type_counter else 0,
                "year_bonus": 0.05 if movie.get("year_bucket") in year_counter else 0,
            }
            item["recommendation_reasons"] = reasons[:3]
            recommendations.append(item)

        recommendations.sort(
            key=lambda item: (
                float(item.get("recommendation_score") or 0),
                float(item.get("rating") or 0),
                int(item.get("year") or 0),
            ),
            reverse=True,
        )
        profile = {
            "seed_count": len(seed_movies),
            "top_tags": [{"name": name, "weight": round(weight, 2)} for name, weight in tag_counter.most_common(8)],
            "top_types": [{"name": name, "weight": round(weight, 2)} for name, weight in type_counter.most_common(4)],
            "top_year_buckets": [{"name": name, "weight": round(weight, 2)} for name, weight in year_counter.most_common(4)],
            "seed_titles": [title for title in seed_titles[:6] if title],
            "algorithm": "tfidf_cosine",
        }
        return {
            "items": recommendations[:24],
            "profile": profile,
            "auto_tags_map": auto_tags_map,
        }

    @staticmethod
    def _behavior_weight(movie: dict[str, Any]) -> float:
        weight = 0.0
        if movie.get("is_favorite"):
            weight += 1.0
        if movie.get("is_recent"):
            weight += 0.35
        weight += min(1.0, float(movie.get("playback_percent") or 0) / 100) * 0.75
        weight += min(1.0, float(movie.get("rating") or 0) / 5) * 0.85
        return weight

    @staticmethod
    def _document_tokens(movie: dict[str, Any]) -> list[str]:
        values = [
            str(movie.get("title") or ""),
            str(movie.get("intro") or ""),
            str(movie.get("type") or ""),
            str(movie.get("source") or ""),
            str(movie.get("provider") or ""),
            str(movie.get("year_bucket") or ""),
            " ".join(str(item) for item in movie.get("tags", [])),
        ]
        tokens: list[str] = []
        for value in values:
            tokens.extend(AnalyticsETLService._tokenize_text(value))
        return tokens

    @staticmethod
    def _tfidf_vector(tokens: list[str], document_frequency: Counter[str], total_docs: int) -> dict[str, float]:
        tf = Counter(tokens)
        vector: dict[str, float] = {}
        total_terms = max(1, sum(tf.values()))
        for token, count in tf.items():
            idf = math.log((1 + total_docs) / (1 + document_frequency[token])) + 1
            vector[token] = (count / total_terms) * idf
        return vector

    @staticmethod
    def _cosine(
        left: dict[str, float],
        right: dict[str, float],
        left_norm: float,
        right_norm: float,
    ) -> float:
        if not left or not right:
            return 0.0
        shared = set(left.keys()) & set(right.keys())
        numerator = sum(left[token] * right[token] for token in shared)
        if numerator <= 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    @staticmethod
    def _top_overlap(profile_vector: dict[str, float], movie_vector: dict[str, float]) -> list[str]:
        overlap = []
        for token in set(profile_vector.keys()) & set(movie_vector.keys()):
            overlap.append((token, profile_vector[token] * movie_vector[token]))
        overlap.sort(key=lambda item: item[1], reverse=True)
        return [token for token, _score in overlap[:5]]
