from __future__ import annotations

import os
import re
from collections import defaultdict
from urllib.parse import unquote

from utils.logger import get_logger

logger = get_logger()


VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"}
YEAR_PATTERN = re.compile(r"(?<!\d)(19\d{2}|20\d{2}|21\d{2})(?!\d)")
EPISODE_PATTERNS = [
    re.compile(r"\bS(?P<season>\d{1,2})E(?P<episode>\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\b(?P<season>\d{1,2})x(?P<episode>\d{1,3})\b", re.IGNORECASE),
    re.compile(r"第\s*(?P<episode>\d{1,3})\s*[集话話]", re.IGNORECASE),
    re.compile(r"\bE(?P<episode>\d{1,3})\b", re.IGNORECASE),
    re.compile(r"[\[\s](?P<episode>\d{1,3})(?:v\d)?[\]\s]", re.IGNORECASE),
]
SEASON_PATTERNS = [
    re.compile(r"\b第\s*(?P<season>[0-9一二三四五六七八九十两壹贰叁肆伍陆柒捌玖拾]+)\s*季\b", re.IGNORECASE),
    re.compile(r"\bSeason\s*(?P<season>\d{1,2})\b", re.IGNORECASE),
    # 支持文件名中的 S01E01 格式
    re.compile(r"(?:^|[._])S(?P<season>\d{1,2})E\d{1,3}(?:$|[._])", re.IGNORECASE),
    # 支持单独的 S01, S1 格式
    re.compile(r"(?:^|[._\s])S\s*(?P<season>\d{1,2})(?:$|[._\s]|E)", re.IGNORECASE),
    re.compile(r"\bS\s*(?P<season>\d{1,2})\b", re.IGNORECASE),
    re.compile(r"\bS(?P<season>\d{1,2})\b", re.IGNORECASE),
    re.compile(r"第\s*(?P<season>[0-9一二三四五六七八九十两壹贰叁肆伍陆柒捌玖拾]+)\s*(?:部|期|章)", re.IGNORECASE),
    # 支持带括号的季数，如 (第一季), (第三季上), (第四季#1)
    re.compile(r"\(\s*第\s*(?P<season>[0-9一二三四五六七八九十两壹贰叁肆伍陆柒捌玖拾]+)\s*季[^)]*\)", re.IGNORECASE),
    # 支持罗马数字季数
    re.compile(r"\b(?P<season>Ⅰ|Ⅱ|Ⅲ|Ⅳ|Ⅴ|Ⅵ|Ⅶ|Ⅷ|Ⅸ|Ⅹ|XI|XII|XIII|XIV|XV)\b", re.IGNORECASE),
]
PART_PATTERNS = [
    re.compile(r"#\s*(?P<part>\d{1,2})\b", re.IGNORECASE),  # 支持 #1, #2 格式 - 优先匹配
    re.compile(r"\bPart[\s.]*(?P<part>\d{1,2}|[IVX]+)\b", re.IGNORECASE),  # 支持 Part.2, Part 2 格式
    re.compile(r"第\s*(?P<part>[0-9一二三四五六七八九十两壹贰叁肆伍陆柒捌玖拾]+)\s*部分", re.IGNORECASE),
    # 支持上下篇，使用命名捕获组
    re.compile(r"(?P<part>上|下|前篇|后篇|中篇)\b", re.IGNORECASE),
]
SPECIAL_TYPE_PATTERNS = {
    "OVA": re.compile(r"\b(?:OVA|OAD|OAV)\b", re.IGNORECASE),
    "特别篇": re.compile(r"\bSP\b|特别篇", re.IGNORECASE),
    "剧场版": re.compile(r"剧场版", re.IGNORECASE),
    "外传": re.compile(r"外传", re.IGNORECASE),
    "前传": re.compile(r"前传", re.IGNORECASE),
    "短篇": re.compile(r"短篇", re.IGNORECASE),
    "总集篇": re.compile(r"总集篇", re.IGNORECASE),
    "回顾": re.compile(r"回顾", re.IGNORECASE),
    "龙水篇": re.compile(r"龙水篇", re.IGNORECASE),  # 针对特定命名
}
SEASON_ALIAS_KEYWORDS = {
    "最终季": 4,
    "Final Season": 4,
    "最终章": 4,
    "完结篇": 2,
    "续作": 2,
    "二期": 2,
    "三期": 3,
    "四期": 4,
    "新系列": 3,
    "新篇章": 2,
    "新篇章": 2,
}
MEDIA_CATEGORY_MAP = {
    "动漫": "动漫",
    "动画": "动漫",
    "anime": "动漫",
    "番剧": "动漫",
    "电视剧": "电视剧",
    "剧集": "电视剧",
    "tv": "电视剧",
    "电影": "电影",
    "movie": "电影",
}
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
NOISE_PATTERNS = [
    r"\b(?:WEB[-_. ]?DL|WEB[-_. ]?RIP|BLU[-_. ]?RAY|BDRIP|REMUX|HDRIP|DVDRIP|HDTV|UHD|4K|1080P|720P|2160P)\b",
    r"\b(?:X264|X265|H264|H265|HEVC|AVC|AAC(?:\d\.\d)?|DTS(?:-HD)?|TRUEHD|ATMOS|DDP?\d\.\d|FLAC)\b",
    r"\b(?:NF|NFX|AMZN|DSNP|HMAX|BILI|BILIBILI)\b",
]
BRACKET_CONTENT = re.compile(r"[\[\(（【](.*?)[\]\)）】]")
ROMAN_MAP = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "Ⅰ": 1,
    "Ⅱ": 2,
    "Ⅲ": 3,
    "Ⅳ": 4,
    "Ⅴ": 5,
    "Ⅵ": 6,
    "Ⅶ": 7,
    "Ⅷ": 8,
    "Ⅸ": 9,
    "Ⅹ": 10,
}
CN_NUM_MAP = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "壹": 1,
    "贰": 2,
    "叁": 3,
    "肆": 4,
    "伍": 5,
    "陆": 6,
    "柒": 7,
    "捌": 8,
    "玖": 9,
    "拾": 10,
}


def _path_parts(decoded_path: str) -> list[str]:
    normalized = str(decoded_path or "").replace("\\", "/")
    return [part for part in normalized.split("/") if part]


def _normalize_text(text: str) -> str:
    return unquote(str(text or "")).replace("_", " ").strip()


def _clean_text(text: str) -> str:
    value = _normalize_text(text)
    for pattern in NOISE_PATTERNS:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[国粤英日中韩]{1,4}\d*音轨", " ", value)
    value = re.sub(r"S\d{1,2}E\d{1,3}", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b\d{1,2}x\d{1,3}\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"第\s*\d{1,3}\s*[集话話]", " ", value)
    value = re.sub(r"(?:Season\s*\d+|\bS\d{1,2}\b|第\s*[0-9一二三四五六七八九十两壹贰叁肆伍陆柒捌玖拾]+\s*(?:季|部|期|章))", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\[[0-9]{1,3}\s*-\s*[0-9]{1,3}\]", " ", value)
    value = YEAR_PATTERN.sub(" ", value)
    value = value.replace("/", " ").replace("\\", " ")
    value = re.sub(r"[\[\(（【].*?[\]\)）】]", " ", value)
    value = re.sub(r"[_\-.!]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _parse_number(token: str | None) -> int | None:
    value = str(token or "").strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    upper = value.upper()
    if upper in ROMAN_MAP:
        return ROMAN_MAP[upper]
    if value in CN_NUM_MAP:
        return CN_NUM_MAP[value]
    if len(value) == 2 and value.startswith("十") and value[1] in CN_NUM_MAP:
        return 10 + CN_NUM_MAP[value[1]]
    if len(value) == 2 and value.endswith("十") and value[0] in CN_NUM_MAP:
        return CN_NUM_MAP[value[0]] * 10
    if len(value) == 3 and value[1] in {"十", "拾"} and value[0] in CN_NUM_MAP and value[2] in CN_NUM_MAP:
        return CN_NUM_MAP[value[0]] * 10 + CN_NUM_MAP[value[2]]
    return None


def _extract_year(*parts: str) -> int | None:
    for part in parts:
        match = YEAR_PATTERN.search(str(part or ""))
        if match:
            year = int(match.group(1))
            if 1900 <= year <= 2035:
                return year
    return None


def _extract_resolution(text: str) -> str:
    value = str(text or "")
    if re.search(r"\b(?:2160p|4k|uhd)\b", value, re.IGNORECASE):
        return "2160p"
    if re.search(r"\b1080p\b", value, re.IGNORECASE):
        return "1080p"
    if re.search(r"\b720p\b", value, re.IGNORECASE):
        return "720p"
    return ""


def _extract_codec(text: str) -> str:
    value = str(text or "")
    if re.search(r"\b(?:HEVC|H265|X265)\b", value, re.IGNORECASE):
        return "HEVC"
    if re.search(r"\b(?:AVC|H264|X264)\b", value, re.IGNORECASE):
        return "AVC"
    return ""


def _extract_release_group(*parts: str) -> str:
    values: list[str] = []
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


def _extract_audio_info(text: str) -> str:
    value = str(text or "")
    if any(token in value for token in ["多音轨", "5.1", "7.1", "Atmos", "TRUEHD", "DTS"]):
        return "多音轨"
    if any(token in value for token in ["国粤英", "国语", "粤语", "日语", "英语"]):
        return "多语言音轨"
    return ""


def _extract_subtitle_info(text: str) -> str:
    value = str(text or "").lower()
    if "ass" in value and "srt" in value:
        return "ass+srt"
    if "ass" in value:
        return "ass"
    if "srt" in value:
        return "srt"
    if "字幕" in str(text or ""):
        return "字幕"
    return ""


def _detect_episode(text: str) -> int | None:
    if not text:
        return None
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(str(text))
        if not match:
            continue
        try:
            return int(match.group("episode"))
        except Exception:
            continue
    range_match = re.search(r"\[(\d{1,3})\s*-\s*(\d{1,3})\]", str(text))
    if range_match:
        return int(range_match.group(1))
    return None


def _detect_special_type(*parts: str) -> str:
    text = " ".join([str(part or "") for part in parts])
    for label, pattern in SPECIAL_TYPE_PATTERNS.items():
        if pattern.search(text):
            return label
    return ""


def _detect_part(*parts: str) -> int | None:
    text = " ".join([str(part or "") for part in parts])
    for pattern in PART_PATTERNS:
        match = pattern.search(text)
        if match:
            return _parse_number(match.group("part"))
    return None


def _detect_season(*parts: str) -> tuple[int | None, str]:
    season_title = ""
    for part in parts:
        text = str(part or "")
        for pattern in SEASON_PATTERNS:
            match = pattern.search(text)
            if match:
                season = _parse_number(match.group("season"))
                if season:
                    # 提取季标题信息
                    # 先提取主要副标题（如 NEW WORLD, Stone Wars）
                    main_title = ""
                    if "NEW WORLD" in text:
                        main_title = "NEW WORLD"
                    elif "Stone Wars" in text:
                        main_title = "Stone Wars"
                    elif "科学与未来" in text:
                        main_title = "科学与未来"
                    
                    # 提取部分编号（如 #1, #2）
                    # 注意：Part.N 格式可能出现在季标题中（如 Part.2），应该作为 part 编号而不是标题
                    part_suffix = ""
                    part_match = re.search(r"(#\s*\d+)\b", text)
                    if part_match:
                        part_suffix = part_match.group(1).strip()
                    
                    # 尝试从括号中提取季标题，如 (第三季上) -> "上"
                    bracket_match = re.search(r"\(\s*第\s*[0-9一二三四五六七八九十]+季\s*([^)]+)\)", text)
                    if bracket_match:
                        bracket_title = bracket_match.group(1).strip()
                        # 如果括号标题只是方向（上/下），则与主标题合并
                        if bracket_title in {"上", "下", "前篇", "后篇", "中篇"}:
                            if main_title:
                                season_title = f"{main_title} {bracket_title}"
                            else:
                                season_title = bracket_title
                        else:
                            season_title = bracket_title
                    elif main_title:
                        season_title = main_title
                    
                    # 添加部分编号到季标题
                    if part_suffix and part_suffix not in season_title:
                        if season_title:
                            season_title = f"{season_title} {part_suffix}"
                        else:
                            season_title = part_suffix
                    
                    return season, season_title
        for alias, season in SEASON_ALIAS_KEYWORDS.items():
            if alias.lower() in text.lower():
                return season, alias
    return None, season_title


def _extract_subtitle_from_path(*parts: str) -> tuple[str, int]:
    """从路径中提取副标题和数字前缀，如 OVA 副标题、特别篇副标题等
    
    返回: (subtitle, prefix_number)
    """
    prefix_number = 0
    for part in parts:
        text = str(part or "")
        # 提取文件夹名中的数字前缀，如 "2.Re：从零开始的异世界生活 OVA" -> 2
        prefix_match = re.match(r"^(\d+)\.", text)
        if prefix_match:
            prefix_number = int(prefix_match.group(1))
        
        # 匹配 OVA/SP/剧场版 后面的副标题
        # 如 "Re：从零开始的异世界生活 OVA 雪之回忆" -> "雪之回忆"
        ova_match = re.search(r"\b(OVA|OAD|SP|特别篇|剧场版|外传|前传|短篇|总集篇)\s+(.+?)(?:\s*[-\[\(【#]|$)", text, re.IGNORECASE)
        if ova_match:
            subtitle = ova_match.group(2).strip()
            # 清理副标题中的数字前缀，如 "2.Re：从零开始的异世界生活 OVA" 中的 "2."
            subtitle = re.sub(r"^[0-9]+\.\s*", "", subtitle)
            # 清理副标题中的括号内容
            subtitle = re.sub(r"[\[\(（【].*?[\]\)）】]", "", subtitle).strip()
            # 清理字幕组信息
            for group in KNOWN_GROUPS:
                subtitle = re.sub(rf"\b{re.escape(group)}\b", "", subtitle, flags=re.IGNORECASE)
            subtitle = " ".join(subtitle.split()).strip()
            return subtitle, prefix_number
    return "", prefix_number


def _infer_media_category(parts: list[str], season: int | None, special_type: str) -> str:
    lowered = [str(part or "").lower() for part in parts]
    for part in lowered:
        for key, value in MEDIA_CATEGORY_MAP.items():
            if key in part:
                return value
    if special_type or season is not None:
        return "动漫" if any(token in " ".join(lowered) for token in ["动漫", "动画", "anime", "番剧"]) else "电视剧"
    return "电影"


def _looks_like_season_folder(text: str) -> bool:
    if not text:
        return False
    if _detect_special_type(text):
        return True
    season, _ = _detect_season(text)
    if season:
        return True
    if _detect_part(text):
        return True
    for alias in SEASON_ALIAS_KEYWORDS:
        if alias.lower() in str(text).lower():
            return True
    if re.search(r"(篇|章|期|部分|合集|全集|重制版|新版)$", str(text)):
        return True
    return False


def _pick_title_candidate(parts: list[str], filename_stem: str, season: int | None, special_type: str) -> tuple[str, str]:
    cleaned_parts = [str(part or "").strip() for part in parts if str(part or "").strip()]
    season_label = ""
    if cleaned_parts:
        parent = cleaned_parts[-1]
        grand_parent = cleaned_parts[-2] if len(cleaned_parts) >= 2 else ""
        if _looks_like_season_folder(parent):
            # 提取季标识和副标题
            if special_type:
                season_label = special_type
            elif season:
                # 如果已经识别出季数，尝试从文件夹名中提取副标题
                detected_season, detected_title = _detect_season(parent)
                # 优先使用检测到的副标题
                if detected_title and detected_title not in (f"S{int(season):02d}", f"第{season}季"):
                    season_label = detected_title
                else:
                    # 如果没有检测到副标题，尝试从文件夹名中提取
                    folder_title = _clean_text(parent)
                    # 移除系列标题（如果 grand_parent 是系列标题）
                    if grand_parent:
                        folder_title = folder_title.replace(grand_parent, "").strip()
                    # 移除季数标识
                    folder_title = re.sub(r"(?:^|\s)第\s*[0-9一二三四五六七八九十]+\s*季(?:$|\s)", " ", folder_title)
                    folder_title = re.sub(r"(?:^|\s)S\d{1,2}(?:$|\s)", " ", folder_title)
                    folder_title = re.sub(r"(?:^|\s)Season\s*\d+(?:$|\s)", " ", folder_title)
                    folder_title = folder_title.strip()
                    # 如果提取到了副标题，使用它
                    if folder_title:
                        season_label = folder_title
                    else:
                        season_label = f"S{int(season):02d}"
            else:
                # 尝试从文件夹名中提取季数和副标题
                detected_season, detected_title = _detect_season(parent)
                if detected_season:
                    # 优先使用检测到的副标题
                    if detected_title and detected_title not in (f"S{int(detected_season):02d}", f"第{detected_season}季"):
                        season_label = detected_title
                    else:
                        season_label = f"S{int(detected_season):02d}"
                else:
                    # 如果都没有，保持为空
                    season_label = ""
            
            # 使用 grand_parent 作为标题，如果没有则使用 parent 清理后的版本
            if grand_parent:
                title_candidate = _clean_text(grand_parent)
            else:
                title_candidate = _clean_text(parent)
            
            # 如果标题候选中包含已知的副标题关键词，说明标题提取不正确
            subtitle_keywords = {"Stone Wars", "NEW WORLD", "科学与未来"}
            for keyword in subtitle_keywords:
                if keyword in title_candidate and keyword not in (season_label or ""):
                    title_candidate = title_candidate.replace(keyword, "").strip()
                    if not season_label:
                        season_label = keyword
            
            if title_candidate:
                return title_candidate, season_label
    for candidate in reversed(cleaned_parts[-3:]):
        cleaned = _clean_text(candidate)
        if cleaned and not _looks_like_season_folder(candidate):
            return cleaned, season_label
    cleaned_filename = _clean_text(filename_stem)
    return cleaned_filename or str(filename_stem or "").strip(), season_label


def _franchise_from_parts(parts: list[str], title: str) -> str:
    for part in parts:
        text = str(part or "")
        if "合集" in text or "全集" in text:
            return _clean_text(text.replace("合集", "").replace("全集", ""))
    return title


def _sort_bucket(category: str) -> int:
    mapping = {"动漫": 0, "电视剧": 1, "电影": 2}
    return mapping.get(category, 9)


def _sort_title(name: str) -> str:
    value = re.sub(r"^[0-9]+\.", "", str(name or "")).strip()
    return value.lower()


def _season_display(season: int | None, season_title: str, special_type: str, part: int | None) -> str:
    tokens: list[str] = []
    if special_type:
        tokens.append(special_type)
    elif season:
        # 如果有季标题（如 Stone Wars, NEW WORLD），就不添加季数标识
        if not season_title or season_title in {"全集", "合集"}:
            tokens.append(f"S{int(season):02d}")
    
    # 如果有 season_title，检查是否已经包含特殊类型
    if season_title and season_title not in {"全集", "合集"}:
        # 如果 season_title 已经包含特殊类型，就不再重复添加
        if not (special_type and special_type in season_title):
            tokens.append(season_title)
        elif special_type and special_type in season_title:
            # season_title 包含特殊类型，但我们已经添加了特殊类型，需要添加剩余部分
            remaining = season_title.replace(special_type, "").strip()
            if remaining:
                tokens.append(remaining)
    
    # 只在 part 来自真正的 Part 标识时才显示（不是来自文件夹前缀）
    # 文件夹前缀只用于排序，不显示在标题中
    if part and part > 0:
        # 检查是否是真正的 Part 标识（如 "Part 1" 格式）
        # 如果只是文件夹数字前缀，不显示
        # 这里我们假设如果 part 是从 PART_PATTERNS 匹配来的才显示
        # 暂时先不显示，因为文件夹前缀的情况更多
        pass
    return " ".join(tokens).strip()


def parse_video_filename(file_path):
    metadata = file_path if isinstance(file_path, dict) else {}
    raw_path = metadata.get("file_path", file_path)
    decoded_path = unquote(str(raw_path or ""))
    parts = _path_parts(decoded_path)
    filename = parts[-1] if parts else os.path.basename(decoded_path)
    name, ext = os.path.splitext(filename)

    season, season_alias = _detect_season(name, *(parts[-4:]))
    special_type = _detect_special_type(name, *(parts[-4:]))
    part_number = _detect_part(name, *(parts[-4:]))
    episode = _detect_episode(name)
    
    # 提取副标题和数字前缀（如 OVA 副标题）
    extra_subtitle, folder_prefix = _extract_subtitle_from_path(*parts[-4:])
    
    # 如果 folder_prefix 不为零，使用它作为 part_number
    if folder_prefix > 0 and not part_number:
        part_number = folder_prefix
    
    title, folder_season_title = _pick_title_candidate(parts[:-1], name, season, special_type)
    season_title = season_alias or folder_season_title
    
    # 如果有副标题且不是重复的，添加到 season_title 中
    if extra_subtitle and extra_subtitle not in (season_title or "") and extra_subtitle not in title:
        if season_title:
            season_title = f"{season_title} {extra_subtitle}"
        else:
            season_title = extra_subtitle
    
    category = _infer_media_category(parts, season, special_type)
    year = _extract_year(name, *(parts[-3:]))
    text_blob = " ".join(parts)
    display_suffix = _season_display(season, season_title, special_type, part_number)
    full_name = f"{title} {display_suffix}".strip() if display_suffix else title

    series_hint = (
        season is not None
        or episode is not None
        or bool(special_type)
        or any(_looks_like_season_folder(part) for part in parts[-3:])
    )

    parsed = {
        "title": title,
        "name": title,
        "full_name": full_name,
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
        "franchise": _franchise_from_parts(parts[:-1], title),
        "year_hint": year,
        "sort_bucket": _sort_bucket(category),
        "sort_title": _sort_title(full_name or title),
        "extension": ext.lower(),
        "season_title": season_title,
        "special_type": special_type,
        "part": int(part_number or 0),
        "series_group": _build_series_group(title, season, season_title, special_type, part_number),
    }

    if series_hint:
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


def _build_series_group(title: str, season: int | None, season_title: str, special_type: str, part: int | None) -> str:
    """构建系列分组键，支持同一季的多个部分分开"""
    # 特殊类型（如OVA、特别篇）独立分组
    if special_type:
        # 如果有 season_title（如 OVA 副标题），用它来区分不同的 OVA
        if season_title:
            # 清理 season_title 中的特殊类型前缀，避免重复
            clean_title = season_title.replace(special_type, "").strip() if special_type in season_title else season_title
            if clean_title:
                # 如果有 part 编号，添加到分组中
                if part and part > 0:
                    return f"{title}__{season or 1}__{special_type}_{clean_title}_part{part}"
                return f"{title}__{season or 1}__{special_type}_{clean_title}"
        # 如果有 part 编号，添加到分组中
        if part and part > 0:
            return f"{title}__{season or 1}__{special_type}_part{part}"
        return f"{title}__{season or 1}__{special_type}"
    
    # 如果有 season_title（如 Stone Wars），用它分组
    if season_title:
        # 如果有 part 编号，添加到分组中以区分同一季的不同部分
        if part and part > 0:
            return f"{title}__{season or 1}__{season_title}_part{part}"
        return f"{title}__{season or 1}__{season_title}"
    
    # 如果有 part 编号，添加到分组中
    if part and part > 0:
        return f"{title}__{season or 1}__part{part}"
    
    return f"{title}__{season or 1}__main"


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
    special_type = str(movie.get("special_type") or "").strip()
    season_title = str(movie.get("season_title") or "").strip()
    year = int(movie.get("year") or movie.get("year_hint") or 0)

    for value in (category, media_type, release_group, resolution, codec, subtitle_info, audio_info, franchise, special_type, season_title):
        if value:
            tags.append(value)

    tags.append("多集" if movie.get("is_series") else "单片")

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
    if "合集" in path or "全集" in path:
        tags.append("合集")
    if any(token in path for token in ["/动漫/", "\\动漫\\", "/动画/", "\\动画\\"]):
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


def _is_anime_category(category: str) -> bool:
    return category == "动漫"


def _get_scraper_source(category: str) -> str:
    return "动漫科" if _is_anime_category(category) else "TMDB"


def _get_season_display_text(season: int, special_type: str, episode_count: int) -> str:
    if special_type:
        return "番外"
    if season > 1:
        return f"第{season}季"
    return "单季"


def _get_search_name(series_title: str, season: int, season_title: str, special_type: str) -> str:
    search_parts = [series_title]
    if season > 1:
        search_parts.append(f"第{season}季")
    
    # 如果 season_title 存在且不只是季数标识
    if season_title and season_title.strip():
        # 检查是否只是季数标识
        is_only_season = False
        if re.match(r"^S\d{2}$", season_title):
            is_only_season = True
        # 检查是否只是特殊类型
        if special_type and season_title == special_type:
            is_only_season = True
        # 检查是否只是中文数字季数
        if re.match(r"^第[0-9一二三四五六七八九十]+季$", season_title):
            is_only_season = True
        
        if not is_only_season:
            # 清理 season_title 中的冗余信息（括号等）
            cleaned_season_title = season_title
            # 移除括号内容，如 (第三季上) -> 第三季上
            cleaned_season_title = re.sub(r"\(([^)]+)\)", r"\1", cleaned_season_title)
            # 移除 #1（默认部分不需要显示），保留 #2, #3 等
            cleaned_season_title = re.sub(r"(?<!#)#\s*1\b", "", cleaned_season_title)
            # 移除多余空格
            cleaned_season_title = " ".join(cleaned_season_title.split()).strip()
            
            if cleaned_season_title and cleaned_season_title not in series_title:
                search_parts.append(cleaned_season_title)
    
    # 对于 special_type，只添加类型标识
    if special_type and special_type not in " ".join(search_parts):
        search_parts.append(special_type)
    
    return " ".join(search_parts).strip()


def merge_series_videos(file_list):
    series_dict: dict[str, list[dict]] = defaultdict(list)
    movie_list = []

    for file_path in file_list:
        parsed = parse_video_filename(file_path)
        if parsed["type"] == "series":
            series_dict[parsed["series_group"]].append(parsed)
        else:
            movie_list.append(parsed)

    result = []
    
    if series_dict:
        logger.info("=" * 50)
        logger.info("[识别结果]")

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
        episode_titles = []
        for index, ep in enumerate(ep_list_sorted, start=1):
            episode_number = ep.get("episode") or index
            episode_titles.append(f"第 {episode_number} 集")

        category = first_ep.get("category", "")
        season = int(first_ep.get("season") or 1)
        special_type = first_ep.get("special_type", "")
        series_title = first_ep.get("name", "")
        season_title = first_ep.get("season_title", "")
        episode_count = len(ep_list_sorted)

        is_anime = _is_anime_category(category)
        scraper_source = _get_scraper_source(category)
        season_display = _get_season_display_text(season, special_type, episode_count)
        search_name = _get_search_name(series_title, season, season_title, special_type)

        logger.info(
            "《%s》%s | 集数: %s | 类型: %s | 选择刮削源: %s",
            series_title,
            special_type if special_type else season_display,
            episode_count,
            "番外" if special_type else ("动漫" if is_anime else "电视剧"),
            scraper_source,
        )
        logger.info("搜索名: %s", search_name)

        result.append(
            {
                "title": first_ep["full_name"],
                "name": first_ep["name"],  # 使用主标题，不是 full_name
                "series_title": first_ep["name"],
                "season": int(first_ep.get("season") or 1),
                "season_title": first_ep.get("season_title", ""),
                "special_type": first_ep.get("special_type", ""),
                "part": int(first_ep.get("part") or 0),
                "type": first_ep.get("media_type") or "剧集",
                "rating": 0.0,
                "year": first_ep.get("year_hint") or 2024,
                "duration": "未知",
                "director": "未知",
                "actors": "未知",
                "intro": first_ep["full_name"],
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
        movie_title = movie.get("name", movie.get("full_name", ""))
        movie_category = movie.get("category", "")
        is_anime = _is_anime_category(movie_category)
        scraper_source = _get_scraper_source(movie_category)

        logger.info(
            "扫描到《%s》，判断为%s，开始从%s刮削",
            movie_title,
            "动漫电影" if is_anime else "电影",
            scraper_source,
        )
        logger.info("搜索名：%s", movie_title)

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
                "special_type": movie.get("special_type", ""),
                "season_title": movie.get("season_title", ""),
            }
        )

    return sorted(
        result,
        key=lambda item: (
            int(item.get("sort_bucket") or 9),
            str(item.get("franchise") or ""),
            # 先按系列标题排序，确保同一系列排在一起
            str(item.get("series_title") or item.get("title") or ""),
            # 特别篇（OVA、SP、龙水篇等）排在所有正常季之后
            1 if item.get("special_type") else 0,
            int(item.get("season") or 0),
            # 先按 part 排序（处理文件夹数字前缀），再按 season_title 排序
            int(item.get("part") or 0),
            str(item.get("season_title") or ""),
        ),
    )
