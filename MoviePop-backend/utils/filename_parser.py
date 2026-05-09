import os
import re
from collections import defaultdict
from urllib.parse import unquote


VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"}
YEAR_PATTERN = re.compile(r"(?<!\d)(19\d{2}|20\d{2}|21\d{2})(?!\d)")
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
    re.compile(r"\bE(?P<episode>\d{1,3})\b", re.IGNORECASE),
]
BRACKET_CONTENT = re.compile(r"[\[\(（【](.*?)[\]\)）】]")
RANGE_PATTERN = re.compile(r"\[(\d{1,3})\s*-\s*(\d{1,3})\]")

NOISE_PATTERNS = [
    r"\b(?:WEB[-_. ]?DL|WEB[-_. ]?RIP|BLU[-_. ]?RAY|BDRIP|REMUX|HDRIP|DVDRIP|HDTV|UHD|4K|1080P|720P|2160P)\b",
    r"\b(?:X264|X265|H264|H265|HEVC|AVC|AAC(?:\d\.\d)?|DTS(?:-HD)?|TRUEHD|ATMOS|DDP?\d\.\d|FLAC)\b",
    r"\b(?:MOVIE|剧场版|国语|粤语|英语|日语|多音轨|多字幕)\b",
    r"\b(?:简繁|中字|双语|国语|粤语|日语|英配|内封字幕|外挂字幕|多字幕|收藏版|完整版|未删减版)\b",
    r"\b(?:NF|NFX|AMZN|DSNP|HMAX|BILI|BILIBILI)\b",
]

KNOWN_GROUPS = [
    "MAI",
    "Sakurato",
    "Kamigami",
    "UHA-WINGS",
    "UHA",
    "VCB-Studio",
    "LoliHouse",
    "ANi",
]

MEDIA_CATEGORY_MAP = {
    "动漫": "动漫",
    "动画": "动漫",
    "电视剧": "电视剧",
    "剧集": "电视剧",
    "电影": "电影",
}


def _path_parts(decoded_path):
    normalized = str(decoded_path or "").replace("\\", "/")
    return [part for part in normalized.split("/") if part]


def _detect_season(*parts):
    for part in parts:
        if not part:
            continue
        text = str(part)
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
    range_match = RANGE_PATTERN.search(str(text))
    if range_match:
        try:
            return int(range_match.group(1))
        except (TypeError, ValueError):
            return None
    return None


def _clean_text(text):
    value = unquote(str(text or ""))
    for pattern in NOISE_PATTERNS:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[国粤英日中韩]{1,4}\d*音轨", " ", value)
    value = re.sub(r"S\d{1,2}E\d{1,3}", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b\d{1,2}x\d{1,3}\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"第\s*\d{1,3}\s*[集话話]", " ", value)
    value = re.sub(r"第\s*\d{1,2}\s*季", " ", value)
    value = re.sub(r"Season\s*\d{1,2}", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bS\d{1,2}\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\[[0-9]{1,3}\s*-\s*[0-9]{1,3}\]", " ", value)
    value = YEAR_PATTERN.sub(" ", value)
    value = value.replace("/", " ").replace("\\", " ")
    value = re.sub(r"\(\s*\)", " ", value)
    value = re.sub(r"[_\-.!]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _extract_year(*parts):
    for part in parts:
        match = YEAR_PATTERN.search(str(part or ""))
        if match:
            year = int(match.group(1))
            if 1900 <= year <= 2035:
                return year
    return None


def _extract_resolution(text):
    value = str(text or "")
    if re.search(r"\b(?:2160p|4k|uhd)\b", value, re.IGNORECASE):
        return "2160p"
    if re.search(r"\b1080p\b", value, re.IGNORECASE):
        return "1080p"
    if re.search(r"\b720p\b", value, re.IGNORECASE):
        return "720p"
    return ""


def _extract_codec(text):
    value = str(text or "")
    if re.search(r"\b(?:HEVC|H265|X265)\b", value, re.IGNORECASE):
        return "HEVC"
    if re.search(r"\b(?:AVC|H264|X264)\b", value, re.IGNORECASE):
        return "AVC"
    return ""


def _extract_release_group(*parts):
    values = []
    for part in parts:
        values.extend(BRACKET_CONTENT.findall(str(part or "")))
    for value in values:
        tokens = re.split(r"[&,+/ ]+", value)
        picked = [token for token in tokens if token in KNOWN_GROUPS]
        if picked:
            return "&".join(dict.fromkeys(picked))
    for part in parts:
        text = str(part or "")
        for group in KNOWN_GROUPS:
            if re.search(rf"\b{re.escape(group)}\b", text, re.IGNORECASE):
                return group
    return ""


def _extract_audio_info(text):
    value = str(text or "")
    if "3音轨" in value or "多音轨" in value:
        return "多音轨"
    if any(token in value for token in ["国粤英", "国语", "粤语", "日语", "英语"]):
        return "多语言音轨"
    return ""


def _extract_subtitle_info(text):
    value = str(text or "").lower()
    if "ass" in value and "srt" in value:
        return "ass+srt"
    if "ass" in value:
        return "ass"
    if "srt" in value:
        return "srt"
    if "字幕" in str(text or ""):
        return "多字幕"
    return ""


def _strip_brackets(text):
    return re.sub(r"[\[\(（【].*?[\]\)）】]", " ", str(text or ""))


def _is_season_folder(text):
    value = _clean_text(_strip_brackets(text)).lower()
    if not value:
        return True
    patterns = [
        r"^s\d{1,2}$",
        r"^season\s*\d{1,2}$",
        r"^第\s*[一二三四五六七八九十\d]+\s*季$",
    ]
    return any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns)


def _infer_media_category(parts, season):
    lowered = [str(part).lower() for part in parts]
    for part in lowered:
        for key, value in MEDIA_CATEGORY_MAP.items():
            if key in part:
                return value
    if season is not None:
        return "电视剧"
    return "电影"


def _pick_title_candidate(parts, filename_stem, season):
    candidates = []
    if len(parts) >= 1:
        candidates.append(parts[-1])
    if len(parts) >= 2:
        candidates.append(parts[-2])
    if len(parts) >= 3:
        candidates.append(parts[-3])
    candidates.append(filename_stem)

    for candidate in candidates:
        candidate_text = str(candidate or "").strip()
        if not candidate_text:
            continue
        if candidate_text in MEDIA_CATEGORY_MAP or candidate_text in MEDIA_CATEGORY_MAP.values():
            continue
        if _is_season_folder(candidate_text):
            continue
        cleaned = _clean_text(candidate_text)
        if cleaned:
            return cleaned

    cleaned_filename = _clean_text(filename_stem)
    if cleaned_filename:
        return cleaned_filename
    return str(filename_stem or "").strip()


def _franchise_from_parts(parts):
    for part in parts:
        text = str(part or "")
        if "合集" in text:
            return _clean_text(text.replace("合集", ""))
    return ""


def _sort_bucket(category):
    mapping = {"动漫": 0, "电视剧": 1, "电影": 2}
    return mapping.get(category, 9)


def _sort_title(name):
    value = re.sub(r"^[0-9]+\.", "", str(name or "")).strip()
    return value.lower()


def parse_video_filename(file_path):
    metadata = file_path if isinstance(file_path, dict) else {}
    raw_path = metadata.get("file_path", file_path)
    decoded_path = unquote(str(raw_path or ""))
    parts = _path_parts(decoded_path)
    filename = parts[-1] if parts else os.path.basename(decoded_path)
    name, ext = os.path.splitext(filename)

    season = _detect_season(name, *(parts[-4:]))
    episode = _detect_episode(name)
    category = _infer_media_category(parts, season)
    clean_name = _pick_title_candidate(parts[:-1], name, season)
    year = _extract_year(name, *(parts[-3:]))
    text_blob = " ".join(parts)

    parsed = {
        "name": clean_name,
        "full_name": clean_name,
        "media_type": "动画" if category == "动漫" else ("剧集" if category == "电视剧" else "电影"),
        "file_path": raw_path,
        "filename": filename,
        "remote_provider": metadata.get("remote_provider", ""),
        "source_label": metadata.get("source_label", ""),
        "category": category,
        "resolution": _extract_resolution(text_blob),
        "video_codec": _extract_codec(text_blob),
        "audio_info": _extract_audio_info(text_blob),
        "subtitle_info": _extract_subtitle_info(text_blob),
        "release_group": _extract_release_group(name, *(parts[-3:])),
        "franchise": _franchise_from_parts(parts),
        "year_hint": year,
        "sort_bucket": _sort_bucket(category),
        "sort_title": _sort_title(clean_name),
        "extension": ext.lower(),
    }

    if season is not None or episode is not None:
        parsed.update(
            {
                "type": "series",
                "season": int(season or 1),
                "episode": int(episode) if episode is not None else None,
            }
        )
        return parsed

    parsed["type"] = "movie"
    return parsed


def build_media_tags(movie):
    tags = []
    category = str(movie.get("category") or "").strip()
    media_type = str(movie.get("type") or "").strip()
    title = str(movie.get("title") or movie.get("name") or "")
    path = str(movie.get("path") or "")
    release_group = str(movie.get("release_group") or "").strip()
    resolution = str(movie.get("resolution") or "").strip()
    codec = str(movie.get("video_codec") or "").strip()
    subtitle_info = str(movie.get("subtitle_info") or "").strip()
    audio_info = str(movie.get("audio_info") or "").strip()
    franchise = str(movie.get("franchise") or "").strip()
    year = int(movie.get("year") or movie.get("year_hint") or 0)

    for value in (category, media_type, release_group, resolution, codec, subtitle_info, audio_info, franchise):
        if value:
            tags.append(value)

    if movie.get("is_series"):
        tags.append("多集")
    else:
        tags.append("单片")

    if "MAI" in release_group.upper() or "MAI" in path.upper() or "MAI" in title.upper():
        tags.append("MAI压制")
    if resolution == "2160p":
        tags.extend(["4K", "超清"])
    if subtitle_info:
        tags.append("外挂/内封字幕")
    if audio_info:
        tags.append("多音轨")
    if year >= 2024:
        tags.append("新作")
    elif 0 < year <= 2015:
        tags.append("经典")
    if "合集" in path:
        tags.append("合集")
    if any(token in path for token in ["/动漫/", "\\动漫\\"]):
        tags.append("动漫库")
    if any(token in path for token in ["/电视剧/", "\\电视剧\\"]):
        tags.append("电视剧库")
    if any(token in path for token in ["/电影/", "\\电影\\"]):
        tags.append("电影库")

    seen = set()
    result = []
    for tag in tags:
        value = str(tag or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


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
                "year": first_ep.get("year_hint") or 2024,
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
                "category": first_ep.get("category", ""),
                "resolution": first_ep.get("resolution", ""),
                "video_codec": first_ep.get("video_codec", ""),
                "audio_info": first_ep.get("audio_info", ""),
                "subtitle_info": first_ep.get("subtitle_info", ""),
                "release_group": first_ep.get("release_group", ""),
                "franchise": first_ep.get("franchise", ""),
                "sort_bucket": first_ep.get("sort_bucket", 9),
                "sort_title": first_ep.get("sort_title", ""),
                "year_hint": first_ep.get("year_hint"),
            }
        )

    for movie in movie_list:
        result.append(
            {
                "title": movie["full_name"],
                "name": movie["name"],
                "type": movie.get("media_type") or "电影",
                "rating": 0.0,
                "year": movie.get("year_hint") or 2024,
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
                "category": movie.get("category", ""),
                "resolution": movie.get("resolution", ""),
                "video_codec": movie.get("video_codec", ""),
                "audio_info": movie.get("audio_info", ""),
                "subtitle_info": movie.get("subtitle_info", ""),
                "release_group": movie.get("release_group", ""),
                "franchise": movie.get("franchise", ""),
                "sort_bucket": movie.get("sort_bucket", 9),
                "sort_title": movie.get("sort_title", ""),
                "year_hint": movie.get("year_hint"),
            }
        )

    return sorted(
        result,
        key=lambda item: (
            int(item.get("sort_bucket") or 9),
            str(item.get("franchise") or ""),
            str(item.get("sort_title") or item.get("title") or ""),
            int(item.get("season") or 0),
        ),
    )
