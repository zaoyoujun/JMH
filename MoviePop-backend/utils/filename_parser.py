import os
import re
from collections import defaultdict
from urllib.parse import unquote


SEASON_PATTERNS = [
    re.compile(r"[.\s_-]S(?P<season>\d{1,2})[.\s_-]?E\d{1,3}", re.IGNORECASE),
    re.compile(r"\b(?P<season>\d{1,2})x\d{1,3}\b", re.IGNORECASE),
    re.compile(r"第\s*(?P<season>\d{1,2})\s*季", re.IGNORECASE),
    re.compile(r"Season\s*(?P<season>\d{1,2})", re.IGNORECASE),
    re.compile(r"\bS(?P<season>\d{1,2})\b", re.IGNORECASE),
]

EPISODE_PATTERNS = [
    re.compile(r"S(?P<season>\d{1,2})E(?P<episode>\d{1,3})", re.IGNORECASE),
    re.compile(r"\b(?P<season>\d{1,2})x(?P<episode>\d{1,3})\b", re.IGNORECASE),
    re.compile(r"第\s*(?P<episode>\d{1,3})\s*[集话話]", re.IGNORECASE),
]

NOISE_PATTERNS = [
    r"\b(?:WEB[-_. ]?DL|WEB[-_. ]?RIP|BLU[-_. ]?RAY|BDRIP|REMUX|HDRIP|DVDRIP|HDTV|UHD|4K|1080P|720P|2160P)\b",
    r"\b(?:X264|X265|H264|H265|HEVC|AVC|AAC(?:\d\.\d)?|DTS(?:-HD)?|TRUEHD|ATMOS|DDP?\d\.\d)\b",
    r"\b(?:中字|双语|国语|粤语|简繁|内封字幕|外挂字幕|特效字幕|收藏版|完整版|未删减版|已刮削)\b",
    r"\b(?:NF|NFX|AMZN|DSNP|HMAX|BILI|BILIBILI)\b",
]

BRACKET_CONTENT = re.compile(r"[\[\(（【](.*?)[\]\)）】]")
YEAR_PATTERN = re.compile(r"(?<!\d)(19\d{2}|20\d{2}|21\d{2})(?!\d)")
CHINESE_SEASON_WORDS = {
    "第一季": 1,
    "第二季": 2,
    "第三季": 3,
    "第四季": 4,
    "第五季": 5,
    "第六季": 6,
    "第七季": 7,
    "第八季": 8,
    "第九季": 9,
    "第十季": 10,
}


def _detect_season(*parts):
    for part in parts:
        if not part:
            continue
        text = str(part)
        for literal, season in CHINESE_SEASON_WORDS.items():
            if literal in text:
                return season
        for pattern in SEASON_PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    return int(match.group("season"))
                except (TypeError, ValueError):
                    continue
    return None


def _detect_episode(text):
    if not text:
        return None
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(str(text))
        if match:
            try:
                return int(match.group("episode"))
            except (TypeError, ValueError, IndexError):
                continue
    return None


def _clean_text(text):
    value = unquote(str(text or ""))
    for pattern in NOISE_PATTERNS:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    value = re.sub(r"S\d{1,2}E\d{1,3}", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b\d{1,2}x\d{1,3}\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"第\s*\d{1,3}\s*[集话話]", " ", value)
    value = re.sub(r"第\s*\d{1,2}\s*季", " ", value)
    value = re.sub(r"Season\s*\d{1,2}", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bS\d{1,2}\b", " ", value, flags=re.IGNORECASE)
    value = YEAR_PATTERN.sub(" ", value)
    value = value.replace("/", " ").replace("\\", " ")
    value = re.sub(r"[_\-.]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _extract_series_name(parent_dir, name):
    candidates = []
    if parent_dir and parent_dir not in {"/", "\\"}:
        candidates.append(parent_dir)
    candidates.append(name)

    for text in candidates:
        if not text:
            continue
        cleaned = _clean_text(text)
        if cleaned:
            return cleaned
        for inner in BRACKET_CONTENT.findall(text):
            cleaned_inner = _clean_text(inner)
            if cleaned_inner and not YEAR_PATTERN.fullmatch(cleaned_inner):
                return cleaned_inner
    return _clean_text(name) or name


def _infer_media_type(series_name, file_path, season):
    series_text = str(series_name or "").lower()
    if any(marker in series_text for marker in ["动漫", "动画", "anibk", "bangumi"]):
        return "动画"
    if season is not None:
        return "剧集"
    return "电影"


def parse_video_filename(file_path):
    metadata = file_path if isinstance(file_path, dict) else {}
    raw_path = metadata.get("file_path", file_path)
    decoded_path = unquote(str(raw_path or ""))
    parent_dir = unquote(os.path.basename(os.path.dirname(decoded_path)))
    filename = unquote(os.path.basename(decoded_path))
    name, _ = os.path.splitext(filename)

    season = _detect_season(name, parent_dir, os.path.dirname(decoded_path))
    episode = _detect_episode(name)
    clean_name = _extract_series_name(parent_dir, name)
    media_type = _infer_media_type(clean_name, decoded_path, season)

    if season is not None or episode is not None:
        return {
            "type": "series",
            "name": clean_name,
            "full_name": clean_name,
            "season": int(season or 1),
            "episode": int(episode) if episode is not None else None,
            "media_type": media_type,
            "file_path": raw_path,
            "filename": filename,
            "remote_provider": metadata.get("remote_provider", ""),
            "source_label": metadata.get("source_label", ""),
        }

    return {
        "type": "movie",
        "name": clean_name,
        "full_name": clean_name,
        "media_type": media_type,
        "file_path": raw_path,
        "filename": filename,
        "remote_provider": metadata.get("remote_provider", ""),
        "source_label": metadata.get("source_label", ""),
    }


def merge_series_videos(file_list):
    series_dict = defaultdict(list)
    movie_list = []

    for file_path in file_list:
        parsed = parse_video_filename(file_path)
        if parsed["type"] == "series":
            series_key = f"{parsed['name']}__S{parsed['season']}"
            series_dict[series_key].append(parsed)
        else:
            movie_list.append(parsed)

    result = []

    for _, ep_list in series_dict.items():
        ep_list_sorted = sorted(
            ep_list,
            key=lambda item: (
                int(item.get("season") or 1),
                int(item.get("episode") or 999),
                item.get("filename", ""),
            ),
        )
        first_ep = ep_list_sorted[0]
        season = int(first_ep.get("season") or 1)
        episode_titles = []
        for index, ep in enumerate(ep_list_sorted, start=1):
            episode_number = ep.get("episode") or index
            episode_titles.append(f"第 {episode_number} 集")

        result.append(
            {
                "title": first_ep["name"],
                "name": first_ep["name"],
                "season": season,
                "type": first_ep.get("media_type") or "剧集",
                "rating": 0.0,
                "year": 2024,
                "duration": "未知",
                "director": "未知",
                "actors": "未知",
                "intro": first_ep["name"],
                "is_series": True,
                "episodes": episode_titles,
                "episode_files": [ep["file_path"] for ep in ep_list_sorted],
                "path": ep_list_sorted[0]["file_path"],
                "cover_path": None,
                "remote_provider": first_ep.get("remote_provider", ""),
                "source_label": first_ep.get("source_label", ""),
            }
        )

    for movie in movie_list:
        result.append(
            {
                "title": movie["full_name"],
                "name": movie["name"],
                "type": movie.get("media_type") or "电影",
                "rating": 0.0,
                "year": 2024,
                "duration": "未知",
                "director": "未知",
                "actors": "未知",
                "intro": movie["full_name"],
                "is_series": False,
                "episodes": [],
                "path": movie["file_path"],
                "cover_path": None,
                "remote_provider": movie.get("remote_provider", ""),
                "source_label": movie.get("source_label", ""),
            }
        )

    return result
