import hashlib
import os
import re
import time
from http.cookies import SimpleCookie
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator  # 新增：翻译库
from config.app_config import AppConfig
from utils.logger import get_logger

logger = get_logger()

# ==================== 全局配置与请求头 ====================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive"
}
ANIBK_BASE = "https://www.anibk.com"
ANIBK_SEARCH = f"{ANIBK_BASE}/list/---------?order=20&kw="
BANGUMI_API = "https://api.bgm.tv"
TMDB_BASE = "https://www.themoviedb.org"
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/w500"
DOUBAN_BASE = "https://movie.douban.com"
IMDB_BASE = "https://www.imdb.com"


# ==================== 新增：翻译辅助函数 ====================
def is_chinese(text):
    """判断文本是否主要为中文（避免重复翻译）"""
    if not text:
        return True
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    # 中文字符占比 > 30% 则认为是中文
    return len(chinese_chars) / len(text) > 0.3


def translate_to_chinese(text):
    """自动翻译非中文文本为中文"""
    if not text or is_chinese(text):
        return text  # 空文本或已是中文直接返回
    try:
        # 使用 Google 翻译（源语言自动检测，目标语言简体中文）
        translated = GoogleTranslator(source='auto', target='zh-CN').translate(text)
        logger.info(f"简介翻译成功: {text[:30]}... → {translated[:30]}...")
        return translated
    except Exception as e:
        logger.error(f"简介翻译失败: {e}")
        return text  # 翻译失败时返回原文


# ==================== 原有辅助函数（保留） ====================
def normalize_chinese_punctuation(text):
    if not text:
        return text
    text = text.replace("：", ":")
    text = text.replace("（", "(")
    text = text.replace("）", ")")
    text = text.replace("【", "[")
    text = text.replace("】", "]")
    text = text.replace("，", ",")
    text = text.replace("。", ".")
    text = text.replace("、", " ")
    return text


def clean_title_for_search(title):
    title = normalize_chinese_punctuation(title)
    season_num = None
    year = None
    season_match = re.search(r'第(\d+)季|Season\s*(\d+)|S(\d{1,2})', title, re.IGNORECASE)
    if season_match:
        season_num = next((g for g in season_match.groups() if g), None)
        if season_num:
            season_num = int(season_num)
    year_match = re.search(r'[(（](\d{4})[)）]', title)
    if year_match:
        year = year_match.group(1)
    clean_name = re.sub(r'第\d+季|Season\s*\d+|S\d{1,2}', '', title, flags=re.IGNORECASE)
    clean_name = re.sub(r'[(（]\d{4}[)）]', '', clean_name)
    clean_name = re.sub(r'[_\-\[\]().]', ' ', clean_name)
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()
    return {
        "clean_name": clean_name,
        "season": season_num,
        "year": year,
        "original_title": title
    }


# ==================== 核心刮削类 ====================
class CoverScraper:
    def __init__(self):
        self.config = AppConfig()
        self.config.load_config()
        self.save_dir = self.config.COVERS_DIR
        self.tmdb_api_base = getattr(self.config, "TMDB_API_BASE", "https://api.themoviedb.org/3")
        self.tmdb_image_base = getattr(self.config, "TMDB_IMAGE_BASE", "https://image.tmdb.org/t/p/w500")
        self._last_candidate_diagnostics = []
        self._tmdb_disabled_until = 0
        self._tmdb_failure_reason = ""

    def _build_douban_headers(self):
        headers = HEADERS.copy()
        headers["Referer"] = DOUBAN_BASE
        headers["Origin"] = DOUBAN_BASE
        headers["Sec-Fetch-Dest"] = "document"
        headers["Sec-Fetch-Mode"] = "navigate"
        headers["Sec-Fetch-Site"] = "same-site"
        headers["Upgrade-Insecure-Requests"] = "1"
        cookie = str(getattr(self.config, "DOUBAN_COOKIE", "") or "").strip()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def _apply_douban_cookie(self, session, cookie_value):
        raw_cookie = str(cookie_value or "").strip()
        if not raw_cookie:
            return
        try:
            parsed = SimpleCookie()
            parsed.load(raw_cookie)
            for morsel in parsed.values():
                session.cookies.set(
                    morsel.key,
                    morsel.value,
                    domain=".douban.com",
                    path=morsel["path"] or "/",
                )
        except Exception as exc:
            logger.warning(f"豆瓣 Cookie 解析失败: {exc}")

    def _tmdb_is_temporarily_disabled(self):
        return time.time() < float(self._tmdb_disabled_until or 0)

    def _disable_tmdb_temporarily(self, reason, cooldown=180):
        self._tmdb_disabled_until = time.time() + cooldown
        self._tmdb_failure_reason = str(reason or "")

    def _reset_tmdb_availability(self):
        self._tmdb_disabled_until = 0
        self._tmdb_failure_reason = ""

    def _is_probably_valid_cover(self, file_path):
        try:
            if not file_path or not os.path.exists(file_path):
                return False
            if os.path.getsize(file_path) < 2048:
                return False
            with open(file_path, "rb") as fh:
                header = fh.read(32)
            return (
                header.startswith(b"\xff\xd8\xff")
                or header.startswith(b"\x89PNG\r\n\x1a\n")
                or header.startswith(b"RIFF")
                or header.startswith(b"WEBP", 8)
            )
        except Exception:
            return False

    def _solve_douban_challenge(self, session, response):
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            form = soup.find("form", id="sec")
            if not form:
                return False

            tok_input = form.find("input", {"name": "tok"})
            cha_input = form.find("input", {"name": "cha"})
            red_input = form.find("input", {"name": "red"})
            if not tok_input or not cha_input or not red_input:
                return False

            difficulty = 4
            difficulty_match = re.search(r"process\(data,\s*difficulty\s*=\s*(\d+)\)", response.text)
            if difficulty_match:
                difficulty = int(difficulty_match.group(1))

            tok = tok_input.get("value", "")
            cha = cha_input.get("value", "")
            red = red_input.get("value", "")
            nonce = 0
            prefix = "0" * difficulty
            while True:
                nonce += 1
                digest = hashlib.sha512(f"{cha}{nonce}".encode("utf-8")).hexdigest()
                if digest.startswith(prefix):
                    break

            challenge_headers = dict(session.headers)
            challenge_headers.update({
                "Referer": response.url,
                "Origin": "https://sec.douban.com",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
            })
            challenge_url = urljoin(response.url, form.get("action") or "/c")
            challenge_response = session.post(
                challenge_url,
                data={"tok": tok, "cha": cha, "sol": str(nonce), "red": red},
                headers=challenge_headers,
                timeout=20,
                allow_redirects=False,
            )
            return challenge_response.status_code in {200, 302, 303}
        except Exception as exc:
            logger.warning(f"豆瓣验证页求解失败: {exc}")
            return False

    def _douban_get(self, url):
        session = requests.Session()
        headers = self._build_douban_headers()
        if "/j/subject_suggest" in str(url):
            headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["Sec-Fetch-Dest"] = "empty"
            headers["Sec-Fetch-Mode"] = "cors"
            headers["Sec-Fetch-Site"] = "same-origin"
            headers["Referer"] = f"{DOUBAN_BASE}/"
        session.headers.update(headers)
        cookie = str(getattr(self.config, "DOUBAN_COOKIE", "") or "").strip()
        self._apply_douban_cookie(session, cookie)
        response = session.get(url, timeout=15, allow_redirects=True)
        if "sec.douban.com" in response.url or 'id="sec"' in response.text:
            logger.warning("豆瓣请求命中风控校验: %s", response.url)
            solved = self._solve_douban_challenge(session, response)
            if solved:
                response = session.get(url, timeout=15, allow_redirects=True)
        return session, response

    def _get_douban_detail_soup(self, detail_url):
        try:
            _session, response = self._douban_get(detail_url)
            response.raise_for_status()
            response.encoding = "utf-8"
            return BeautifulSoup(response.text, "html.parser")
        except Exception as exc:
            logger.error(f"提取豆瓣详情页失败: {exc}")
            return None

    def _fallback_cover_from_tmdb(self, candidate, movie_data, name):
        title = str(candidate.get("title") or movie_data.get("title") or movie_data.get("name") or "").strip()
        if not title:
            return None

        queries = [title]
        year = candidate.get("year") or movie_data.get("year")
        if year:
            queries.append(f"{title} {year}")

        is_series = bool(movie_data.get("is_series", False))
        for query in queries:
            try:
                tmdb_items = self._fetch_tmdb_list(query, is_series=is_series) or []
            except Exception as exc:
                logger.warning(f"豆瓣封面回退到 TMDB 失败: {exc}")
                continue
            for item in tmdb_items:
                cover_url = self._get_tmdb_cover(item.get("url", ""))
                cover_path = self._download_cover(cover_url, name) if cover_url else None
                if cover_path:
                    logger.info(f"豆瓣封面已回退到 TMDB: {title}")
                    return cover_path
        return None

    def _is_anime_content(self, movie_data):
        haystacks = [
            str(movie_data.get("type", "") or "").strip().lower(),
            str(movie_data.get("title", "") or "").strip().lower(),
            str(movie_data.get("name", "") or "").strip().lower(),
            str(movie_data.get("path", "") or "").strip().lower(),
        ]
        keywords = ["动画", "动漫", "anime", "anibk", "番剧", "/动漫/", "/动画/"]
        return any(keyword in haystack for haystack in haystacks for keyword in keywords)

    def _has_tmdb_api_key(self):
        return bool(getattr(self.config, "TMDB_API_KEY", "").strip())

    def _tmdb_media_type(self, is_series):
        return "tv" if is_series else "movie"

    def _build_tmdb_locator(self, media_type, item_id):
        return f"tmdb://{media_type}/{item_id}"

    def _parse_tmdb_locator(self, detail_url):
        if not isinstance(detail_url, str) or not detail_url.startswith("tmdb://"):
            return None, None
        parts = detail_url.replace("tmdb://", "", 1).split("/", 1)
        if len(parts) != 2:
            return None, None
        media_type, item_id = parts
        if media_type not in {"movie", "tv"} or not item_id.isdigit():
            return None, None
        return media_type, item_id

    def _tmdb_api_get(self, path, params=None):
        if self._tmdb_is_temporarily_disabled():
            raise RuntimeError(self._tmdb_failure_reason or "TMDB is temporarily unavailable")
        api_key = getattr(self.config, "TMDB_API_KEY", "").strip()
        if not api_key:
            raise ValueError("TMDB API key is not configured")
        query = {"api_key": api_key, "language": "zh-CN"}
        if params:
            query.update(params)
        try:
            response = requests.get(f"{self.tmdb_api_base}{path}", params=query, timeout=4)
            response.raise_for_status()
            self._reset_tmdb_availability()
            return response.json()
        except Exception as exc:
            self._disable_tmdb_temporarily(exc)
            raise

    def _tmdb_api_detail(self, detail_url):
        media_type, item_id = self._parse_tmdb_locator(detail_url)
        if not media_type or not item_id:
            return None
        try:
            return self._tmdb_api_get(f"/{media_type}/{item_id}")
        except Exception as exc:
            logger.warning(f"TMDB API详情获取失败: {exc}")
            return None

    def search_cover(self, movie_data, custom_name=None, force_update_meta=False):
        """
        增强版：刮削封面 + 剧情简介（自动翻译） + 年份
        """
        name = custom_name or movie_data.get("name", movie_data.get("title", ""))
        is_anime = self._is_anime_content(movie_data)
        target_season = movie_data.get("season", 0)
        is_movie = not movie_data.get("is_series", False) and target_season == 0
        current_year = movie_data.get("year", 2024)
        current_intro = movie_data.get("intro", "")

        # 检查本地已有封面
        valid_name = "".join([c for c in name if c.isalnum() or c in (" ", "-", "_")])
        local_cover_path = None
        for suffix in ["jpg", "png", "webp"]:
            local_path = os.path.join(self.save_dir, f"{valid_name}.{suffix}")
            local_path_season = os.path.join(self.save_dir, f"{valid_name}_S{target_season}.{suffix}")
            if os.path.exists(local_path):
                local_cover_path = local_path
                break
            if os.path.exists(local_path_season):
                local_cover_path = local_path_season
                break

        # 如果有本地封面，且不需要强制更新元数据，直接返回
        if local_cover_path and not self._is_probably_valid_cover(local_cover_path):
            try:
                os.remove(local_cover_path)
                logger.warning(f"已移除无效本地封面: {local_cover_path}")
            except OSError:
                pass
            local_cover_path = None

        if local_cover_path and not force_update_meta:
            logger.info(f"使用本地封面: {name}")
            return local_cover_path, None, None

        logger.info("[刮削详情] 目标: %s | 季数: %s | 类型: %s", name, target_season, 'movie' if is_movie else 'series')
        parsed = clean_title_for_search(movie_data.get("title", ""))
        clean_base = parsed["clean_name"] or name
        year = movie_data.get("year", "")

        cover_path = local_cover_path
        intro_text = current_intro
        scraped_year = current_year

        # 先走统一候选搜索，避免自动刮削只命中单一来源，且能感知季数
        candidates = self.search_candidates(movie_data, custom_name=custom_name)
        for candidate in candidates[:6]:
            candidate_score = float(candidate.get("match_score") or 0)
            candidate_source = str(candidate.get("source") or "")
            if candidate_score < 20:
                continue
            if candidate_source == "AniBK" and not is_anime:
                continue
            new_cover, new_intro, new_year = self.download_by_candidate(candidate, movie_data)
            if new_cover:
                cover_path = new_cover
            if new_intro:
                intro_text = new_intro
            if new_year:
                scraped_year = new_year
            if new_cover or new_intro or new_year:
                logger.info(
                    "匹配成功 | 来源: %s | 标题: %s",
                    candidate_source,
                    candidate.get("title", ""),
                )
                return cover_path, intro_text, scraped_year

        # 情况1：电影/无季数内容
        if is_movie:
            logger.info("[判定] 电影/无季数内容")
            new_cover, new_intro, new_year = self._movie_flow(clean_base, year, is_anime, valid_name)
            if new_cover: cover_path = new_cover
            if new_intro: intro_text = new_intro
            if new_year: scraped_year = new_year
            return cover_path, intro_text, scraped_year

        # 情况2：第二季及以上
        elif target_season >= 2:
            logger.info(f"[判定] 目标季S{target_season}>=2")
            new_cover, new_intro, new_year = None, None, None
            if is_anime:
                new_cover, new_intro, new_year = self._season_specific_search_anibk(clean_base, target_season,
                                                                                    valid_name)
            if not new_cover and not is_anime:
                new_cover, new_intro, new_year = self._season_specific_search_tmdb(clean_base, target_season,
                                                                                   movie_data.get("is_series", False),
                                                                                   valid_name)
            if not new_cover:
                logger.warning(f"精准季数搜索无结果，降级到纯剧名搜索")
                new_cover, new_intro, new_year = self._s1_flow(clean_base, year, target_season, is_anime, valid_name,
                                                               movie_data)

            if new_cover: cover_path = new_cover
            if new_intro: intro_text = new_intro
            if new_year: scraped_year = new_year
            return cover_path, intro_text, scraped_year

        # 情况3：第一季/季数为0
        elif target_season <= 1:
            logger.info(f"[判定] 目标季S{target_season}")
            new_cover, new_intro, new_year = self._s1_flow(clean_base, year, target_season, is_anime, valid_name,
                                                           movie_data)
            if new_cover: cover_path = new_cover
            if new_intro: intro_text = new_intro
            if new_year: scraped_year = new_year
            return cover_path, intro_text, scraped_year

        logger.warning(f" 所有搜索流程均无结果: {name}")
        return cover_path, intro_text, scraped_year

    # ==================== 分场景流程引擎 ====================
    def _movie_flow(self, clean_base, year, is_anime, valid_name):
        queries = [clean_base]
        if year: queries.append(f"{clean_base} {year}")
        if is_anime:
            for q in queries:
                candidates = self._fetch_anibk_list(q)
                if candidates:
                    logger.info(f"[动漫科 电影] 命中: {candidates[0]['title']}")
                    cover_url = self._get_anibk_cover(candidates[0]['url'])
                    intro_text = self._get_anibk_intro(candidates[0]['url'])  # 已含翻译
                    scraped_year = self._fetch_anibk_year(candidates[0]['url'])
                    cover_path = self._download_cover(cover_url, valid_name) if cover_url else None
                    return cover_path, intro_text, scraped_year
            return None, None, None
        # TMDB兜底
        for q in queries:
            candidates = self._fetch_tmdb_list(q, is_series=False)
            if candidates:
                logger.info(f"[TMDB 电影] 命中: {candidates[0]['title']}")
                cover_url = self._get_tmdb_cover(candidates[0]['url'])
                intro_text = self._get_tmdb_intro(candidates[0]['url'])  # 已含翻译
                scraped_year = self._fetch_tmdb_year(candidates[0]['url'])
                cover_path = self._download_cover(cover_url, valid_name) if cover_url else None
                return cover_path, intro_text, scraped_year
        return None, None, None

    def _s1_flow(self, clean_base, year, target_season, is_anime, valid_name, movie_data):
        base_queries = [clean_base]
        if year: base_queries.append(f"{clean_base} {year}")
        if is_anime:
            for q in base_queries:
                candidates = self._fetch_anibk_list(q)
                if not candidates: continue
                titles = [c['title'] for c in candidates]
                is_multi = self._is_likely_multi_season(titles, clean_base)
                logger.info(f"[动漫科 S1] 试探结果: {len(candidates)} 条 | 疑似多季: {is_multi}")
                selected_idx = 0
                if is_multi:
                    selected_idx = self._pick_s1_from_results(titles)
                if 0 <= selected_idx < len(candidates):
                    cover_url = self._get_anibk_cover(candidates[selected_idx]['url'])
                    intro_text = self._get_anibk_intro(candidates[selected_idx]['url'])  # 已含翻译
                    scraped_year = self._fetch_anibk_year(candidates[selected_idx]['url'])
                    cover_path = self._download_cover(cover_url,
                                                      f"{valid_name}_S{target_season}") if cover_url else None
                    return cover_path, intro_text, scraped_year
            return None, None, None
        # TMDB兜底
        for q in base_queries:
            candidates = self._fetch_tmdb_list(q, is_series=movie_data.get("is_series", False))
            if not candidates: continue
            titles = [c['title'] for c in candidates]
            is_multi = self._is_likely_multi_season(titles, clean_base)
            logger.info(f"[TMDB S1] 试探结果: {len(candidates)} 条 | 疑似多季: {is_multi}")
            selected_idx = 0
            if is_multi:
                selected_idx = self._pick_s1_from_results(titles)
            if 0 <= selected_idx < len(candidates):
                cover_url = self._get_tmdb_cover(candidates[selected_idx]['url'])
                intro_text = self._get_tmdb_intro(candidates[selected_idx]['url'])  # 已含翻译
                scraped_year = self._fetch_tmdb_year(candidates[selected_idx]['url'])
                cover_path = self._download_cover(cover_url, f"{valid_name}_S{target_season}") if cover_url else None
                return cover_path, intro_text, scraped_year
        return None, None, None

    def _season_specific_search_anibk(self, clean_base, season, valid_name):
        season_queries = [
            f"{clean_base} 第{season}季",
            f"{clean_base} 第{season}期",
            f"{clean_base} 第二季" if season == 2 else "",
            f"{clean_base} 第三季" if season == 3 else "",
            f"{clean_base} Season {season}",
            f"{clean_base} S{season:02d}"
        ]
        season_queries = [q for q in season_queries if q]
        logger.info(f"[动漫科 精准] 搜索词: {season_queries}")
        for q in season_queries:
            candidates = self._fetch_anibk_list(q)
            if candidates:
                logger.info(f"[动漫科 精准] 命中: {candidates[0]['title']}")
                cover_url = self._get_anibk_cover(candidates[0]['url'])
                intro_text = self._get_anibk_intro(candidates[0]['url'])  # 已含翻译
                scraped_year = self._fetch_anibk_year(candidates[0]['url'])
                cover_path = self._download_cover(cover_url, f"{valid_name}_S{season}") if cover_url else None
                return cover_path, intro_text, scraped_year
        return None, None, None

    def _season_specific_search_tmdb(self, clean_base, season, is_series, valid_name):
        season_queries = [
            f"{clean_base} Season {season}",
            f"{clean_base} S{season:02d}",
            f"{clean_base} 第{season}季"
        ]
        logger.info(f"[TMDB 精准] 搜索词: {season_queries}")
        for q in season_queries:
            candidates = self._fetch_tmdb_list(q, is_series=is_series)
            if candidates:
                logger.info(f"[TMDB 精准] 命中: {candidates[0]['title']}")
                cover_url = self._get_tmdb_cover(candidates[0]['url'])
                intro_text = self._get_tmdb_intro(candidates[0]['url'])  # 已含翻译
                scraped_year = self._fetch_tmdb_year(candidates[0]['url'])
                cover_path = self._download_cover(cover_url, f"{valid_name}_S{season}") if cover_url else None
                return cover_path, intro_text, scraped_year
        return None, None, None

    # ==================== 核心提取函数（含翻译） ====================
    def _get_anibk_intro(self, detail_url):
        """提取动漫科简介 + 自动翻译"""
        try:
            headers = HEADERS.copy()
            headers["Referer"] = ANIBK_BASE
            res = requests.get(detail_url, headers=headers, timeout=12)
            res.raise_for_status()
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
            intro_container = soup.find("div", class_="bkir-content")
            if not intro_container:
                return ""
            full_intro = []
            for p in intro_container.find_all("p"):
                text = p.get_text(strip=True)
                if text:
                    full_intro.append(text)
            intro = "".join(full_intro) if full_intro else ""
            # 自动翻译为中文
            return translate_to_chinese(intro)
        except Exception as e:
            logger.error(f"提取动漫科简介失败: {e}")
            return ""

    def _get_tmdb_intro(self, detail_url):
        """提取TMDB简介 + 自动翻译"""
        try:
            detail_data = self._tmdb_api_detail(detail_url)
            if detail_data:
                intro = detail_data.get("overview", "").strip()
                return translate_to_chinese(intro)
            headers = HEADERS.copy()
            headers["Referer"] = TMDB_BASE
            res = requests.get(detail_url, headers=headers, timeout=12)
            res.raise_for_status()
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                intro = og_desc["content"].strip()
                return translate_to_chinese(intro)  # 自动翻译
            overview_div = soup.find("div", class_="overview")
            if overview_div:
                intro_p = overview_div.find("p")
                if intro_p:
                    intro = intro_p.get_text(strip=True)
                    return translate_to_chinese(intro)  # 自动翻译
            return ""
        except Exception as e:
            logger.error(f"提取TMDB简介失败: {e}")
            return ""

    def _fetch_anibk_year(self, detail_url):
        """强化版：动漫科年份提取"""
        try:
            headers = HEADERS.copy()
            headers["Referer"] = ANIBK_BASE
            res = requests.get(detail_url, headers=headers, timeout=12)
            res.raise_for_status()
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")

            # 1. 优先找页面里的上映/发行日期
            page_text = soup.get_text()
            date_match = re.search(r'(上映时间|发行时间|首播时间|播出时间)\s*[：:]\s*(\d{4})', page_text)
            if date_match:
                year = int(date_match.group(2))
                logger.info(f"动漫科精准提取年份: {year}")
                return year

            # 2. 找完整日期格式 YYYY-MM-DD
            full_date_match = re.search(r'(\d{4})-\d{2}-\d{2}', page_text)
            if full_date_match:
                year = int(full_date_match.group(1))
                logger.info(f"动漫科日期提取年份: {year}")
                return year

            # 3. 找标题里的年份
            title_elem = soup.find("h1", class_="bk-title") or soup.find("h1")
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                title_year_match = re.search(r'[(（](\d{4})[)）]', title_text)
                if title_year_match:
                    year = int(title_year_match.group(1))
                    logger.info(f"动漫科标题提取年份: {year}")
                    return year

            # 4. 简介里的年份
            intro_text = self._get_anibk_intro(detail_url)
            intro_year_match = re.search(r'(\d{4})年', intro_text)
            if intro_year_match:
                year = int(intro_year_match.group(1))
                logger.info(f"动漫科简介提取年份: {year}")
                return year

            # 5. 兜底：整个页面找4位数字年份
            all_year_match = re.search(r'(\d{4})', page_text)
            if all_year_match:
                year = int(all_year_match.group(1))
                if 1900 <= year <= 2030:
                    logger.info(f"动漫科兜底提取年份: {year}")
                    return year

            logger.warning(f"动漫科未提取到有效年份")
            return None
        except Exception as e:
            logger.error(f"提取动漫科年份失败: {e}")
            return None

    def _fetch_tmdb_year(self, detail_url):
        """强化版：TMDB年份提取"""
        try:
            detail_data = self._tmdb_api_detail(detail_url)
            if detail_data:
                release_date = detail_data.get("release_date") or detail_data.get("first_air_date") or ""
                year_match = re.search(r'(\d{4})', release_date)
                if year_match:
                    return int(year_match.group(1))
            headers = HEADERS.copy()
            headers["Referer"] = TMDB_BASE
            res = requests.get(detail_url, headers=headers, timeout=12)
            res.raise_for_status()
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")

            # 1. 优先找官方发布日期meta标签
            release_meta = soup.find("meta", property="og:release_date")
            if release_meta and release_meta.get("content"):
                release_date = release_meta["content"]
                year_match = re.search(r'(\d{4})', release_date)
                if year_match:
                    year = int(year_match.group(1))
                    logger.info(f"TMDB官方meta提取年份: {year}")
                    return year

            # 2. 找页面里的发布日期标签
            release_elem = soup.find("span", class_="release_date")
            if release_elem:
                release_text = release_elem.get_text(strip=True)
                year_match = re.search(r'(\d{4})', release_text)
                if year_match:
                    year = int(year_match.group(1))
                    logger.info(f"TMDB页面标签提取年份: {year}")
                    return year

            # 3. 找标题meta里的年份
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title_text = og_title.get("content", "")
                year_match = re.search(r'[(（](\d{4})[)）]', title_text)
                if year_match:
                    year = int(year_match.group(1))
                    logger.info(f"TMDB标题提取年份: {year}")
                    return year

            # 4. 兜底：简介里的年份
            intro_text = self._get_tmdb_intro(detail_url)
            intro_year_match = re.search(r'(\d{4})年', intro_text)
            if intro_year_match:
                year = int(intro_year_match.group(1))
                logger.info(f"TMDB简介提取年份: {year}")
                return year

            logger.warning(f"TMDB未提取到有效年份")
            return None
        except Exception as e:
            logger.error(f"提取TMDB年份失败: {e}")
            return None

    def _get_anibk_cover(self, detail_url):
        """提取动漫科封面"""
        try:
            headers = HEADERS.copy()
            headers["Referer"] = ANIBK_BASE
            res = requests.get(detail_url, headers=headers, timeout=12)
            res.raise_for_status()
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
            cover_box = soup.find("div", class_="bk-main-pic") or soup.find("div", class_="rbox-pic")
            if cover_box:
                img = cover_box.find("img", src=True)
                if img and img["src"]:
                    return img["src"]
            return None
        except Exception as e:
            logger.error(f"提取动漫科封面失败: {e}")
            return None

    def _get_tmdb_cover(self, detail_url):
        """提取TMDB封面"""
        try:
            detail_data = self._tmdb_api_detail(detail_url)
            if detail_data:
                poster_path = detail_data.get("poster_path")
                if poster_path:
                    return f"{self.tmdb_image_base.rstrip('/')}/{poster_path.lstrip('/')}"
            headers = HEADERS.copy()
            headers["Referer"] = TMDB_BASE
            res = requests.get(detail_url, headers=headers, timeout=12)
            res.raise_for_status()
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                return og_img["content"]
            poster_img = soup.find("img", class_="poster")
            if poster_img:
                src = poster_img.get("src") or poster_img.get("data-src")
                if src:
                    if src.startswith("http://") or src.startswith("https://"):
                        return src
                    return f"{self.tmdb_image_base.rstrip('/')}/{src.lstrip('/')}"
            return None
        except Exception as e:
            logger.error(f"提取TMDB封面失败: {e}")
            return None

    def _get_douban_cover(self, detail_url):
        """提取豆瓣封面"""
        try:
            soup = self._get_douban_detail_soup(detail_url)
            if not soup:
                return None

            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                return og_img["content"]

            cover_root = soup.find("div", id="mainpic")
            if cover_root:
                cover_link = cover_root.find("a", href=True)
                if cover_link and cover_link.get("href"):
                    return cover_link["href"]
                img = cover_root.find("img", src=True)
                if img and img.get("src"):
                    return img["src"]
            return None
        except Exception as e:
            logger.error(f"提取豆瓣封面失败: {e}")
            return None

    def _get_douban_intro(self, detail_url):
        """提取豆瓣简介并优先返回中文内容"""
        try:
            soup = self._get_douban_detail_soup(detail_url)
            if not soup:
                return ""
            intro_block = soup.find("span", property="v:summary")
            if intro_block:
                intro = intro_block.get_text(" ", strip=True)
                return normalize_chinese_punctuation(intro)
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                return normalize_chinese_punctuation(meta_desc["content"].strip())
            return ""
        except Exception as e:
            logger.error(f"提取豆瓣简介失败: {e}")
            return ""

    def _fetch_douban_year(self, detail_url):
        """提取豆瓣年份"""
        try:
            soup = self._get_douban_detail_soup(detail_url)
            if not soup:
                return None
            year_tag = soup.find("span", class_="year")
            if year_tag:
                year_match = re.search(r"(\d{4})", year_tag.get_text(" ", strip=True))
                if year_match:
                    return int(year_match.group(1))
            page_text = soup.get_text(" ", strip=True)
            year_match = re.search(r"(\d{4})", page_text)
            if year_match:
                year = int(year_match.group(1))
                if 1900 <= year <= 2035:
                    return year
            return None
        except Exception as e:
            logger.error(f"提取豆瓣年份失败: {e}")
            return None

    def _bangumi_subject_id(self, detail_url):
        match = re.search(r"/subject/(\d+)", str(detail_url or ""))
        return match.group(1) if match else ""

    def _bangumi_subject_payload(self, detail_url):
        subject_id = self._bangumi_subject_id(detail_url)
        if not subject_id:
            return None
        try:
            response = requests.get(
                f"{BANGUMI_API}/v0/subjects/{subject_id}",
                headers={"User-Agent": "JMH/1.0"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.warning("Bangumi detail failed for %s: %s", detail_url, exc)
            return None

    def _get_bangumi_cover(self, detail_url):
        payload = self._bangumi_subject_payload(detail_url)
        images = (payload or {}).get("images") or {}
        return images.get("large") or images.get("common") or images.get("medium") or ""

    def _get_bangumi_intro(self, detail_url):
        payload = self._bangumi_subject_payload(detail_url)
        summary = str((payload or {}).get("summary") or "").strip()
        return translate_to_chinese(summary)

    def _fetch_bangumi_year(self, detail_url):
        payload = self._bangumi_subject_payload(detail_url)
        date_value = str((payload or {}).get("date") or "").strip()
        year_match = re.search(r"(\d{4})", date_value)
        if year_match:
            return int(year_match.group(1))
        return None

    def _get_imdb_detail_soup(self, detail_url):
        try:
            headers = HEADERS.copy()
            headers["Referer"] = IMDB_BASE
            response = requests.get(detail_url, headers=headers, timeout=12)
            response.raise_for_status()
            response.encoding = "utf-8"
            return BeautifulSoup(response.text, "html.parser")
        except Exception as exc:
            logger.error(f"提取 IMDb 详情页失败: {exc}")
            return None

    def _get_imdb_cover(self, detail_url):
        try:
            soup = self._get_imdb_detail_soup(detail_url)
            if not soup:
                return None
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                return og_img["content"]
            return None
        except Exception as exc:
            logger.error(f"提取 IMDb 封面失败: {exc}")
            return None

    def _get_imdb_intro(self, detail_url):
        try:
            soup = self._get_imdb_detail_soup(detail_url)
            if not soup:
                return ""
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                return translate_to_chinese(og_desc["content"].strip())
            return ""
        except Exception as exc:
            logger.error(f"提取 IMDb 简介失败: {exc}")
            return ""

    def _fetch_imdb_year(self, detail_url):
        try:
            soup = self._get_imdb_detail_soup(detail_url)
            if not soup:
                return None
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                year_match = re.search(r"\((\d{4})\)", og_title["content"])
                if year_match:
                    return int(year_match.group(1))
            page_text = soup.get_text(" ", strip=True)
            year_match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", page_text)
            if year_match:
                return int(year_match.group(1))
            return None
        except Exception as exc:
            logger.error(f"提取 IMDb 年份失败: {exc}")
            return None

    def _download_cover(self, cover_url, name):
        """下载封面到本地"""
        try:
            if not cover_url:
                return None
            headers = HEADERS.copy()
            if ANIBK_BASE in cover_url:
                headers["Referer"] = ANIBK_BASE
            elif "doubanio.com" in cover_url or "douban.com" in cover_url:
                headers["Referer"] = DOUBAN_BASE
            else:
                headers["Referer"] = TMDB_BASE
            res = requests.get(cover_url, headers=headers, timeout=20, stream=True)
            res.raise_for_status()
            content_type = (res.headers.get("content-type") or "").lower()
            if not content_type.startswith("image/"):
                logger.warning(f"封面响应不是图片: {cover_url} ({content_type or 'unknown'})")
                return None
            img_suffix = "jpg"
            if "image/webp" in content_type or ".webp" in cover_url:
                img_suffix = "webp"
            elif "image/png" in content_type or ".png" in cover_url:
                img_suffix = "png"
            save_path = os.path.join(self.save_dir, f"{name}.{img_suffix}")
            with open(save_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=1024 * 8):
                    f.write(chunk)
            logger.info(f"封面下载成功: {name}")
            return save_path
        except Exception as e:
            logger.error(f"[error] cover download failed {name}: {e}")
            return None

    # ==================== 手动刮削兼容函数 ====================
    def search_candidates(self, movie_data, custom_name=None):
        name = custom_name or movie_data.get("name", movie_data.get("title", ""))
        queries = self._build_base_queries(movie_data, custom_name)
        candidates = []
        diagnostics = []
        seen = set()
        logger.info(f"开始匹配候选: {name}")
        is_series = movie_data.get("is_series", False)
        is_anime = self._is_anime_content(movie_data)
        
        # 检查是否有豆瓣 cookie
        has_douban_cookie = bool((getattr(self.config, "DOUBAN_COOKIE", "") or "").strip())
        
        if is_anime:
            source_fetchers = [
                ("AniBK", lambda q: self._fetch_anibk_list(q)),
            ]
            # 如果有豆瓣 cookie，添加豆瓣作为备选
            if has_douban_cookie:
                source_fetchers.append(("Douban", lambda q: self._fetch_douban_list(q)))
            # TMDB 作为最后备选
            source_fetchers.append(("TMDB", lambda q: self._fetch_tmdb_list(q, is_series=is_series)))
        else:
            source_fetchers = []
            # 如果有豆瓣 cookie，优先使用豆瓣
            if has_douban_cookie:
                source_fetchers.append(("Douban", lambda q: self._fetch_douban_list(q)))
            # TMDB 作为主要源
            source_fetchers.append(("TMDB", lambda q: self._fetch_tmdb_list(q, is_series=is_series)))
            # AniBK 作为最后备选
            source_fetchers.append(("AniBK", lambda q: self._fetch_anibk_list(q)))

        for source_name, fetcher in source_fetchers:
            if source_name == "TMDB" and self._tmdb_is_temporarily_disabled():
                diagnostics.append({
                    "source": source_name,
                    "queries": 0,
                    "hits": 0,
                    "status": "failed",
                    "error": self._tmdb_failure_reason or "TMDB is temporarily unavailable",
                })
                continue
            source_hits = 0
            source_queries = 0
            source_error = ""
            for q in queries:
                source_queries += 1
                try:
                    result_items = fetcher(q) or []
                except Exception as exc:
                    source_error = str(exc)
                    continue

                for item in result_items:
                    title = str(item.get("title", "")).strip()
                    url = str(item.get("url", "")).strip()
                    if not title or not url:
                        continue
                    dedupe_key = f"{source_name}::{self._normalize_candidate_url(source_name, url)}"
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    year = item.get("year")
                    if isinstance(year, str) and year.isdigit():
                        year = int(year)
                    if not isinstance(year, int):
                        year_match = re.search(r'(\d{4})', title)
                        if year_match:
                            year = int(year_match.group(1))
                        else:
                            year = None
                    candidate = {
                        "title": title,
                        "url": url,
                        "source": source_name,
                        "year": year,
                        "matched_query": q,
                    }
                    candidate["match_score"] = self._score_candidate(movie_data, candidate)
                    candidates.append(candidate)
                    source_hits += 1

            diagnostics.append({
                "source": source_name,
                "queries": source_queries,
                "hits": source_hits,
                "status": "success" if source_hits else ("failed" if source_error else "empty"),
                "error": source_error,
            })

        candidates.sort(
            key=lambda item: (
                float(item.get("match_score") or 0),
                1 if item.get("source") == "Bangumi" else 0,
                1 if item.get("source") == "Douban" else 0,
                1 if item.get("source") == "TMDB" else 0,
                1 if item.get("source") == "IMDb" else 0,
                int(item.get("year") or 0),
            ),
            reverse=True,
        )
        self._last_candidate_diagnostics = diagnostics
        return candidates

    def download_by_candidate(self, candidate, movie_data):
        """增强版：下载封面+提取简介（翻译）+刮削年份"""
        try:
            source = candidate.get("source")
            if source == "TMDB":
                parse_func = self._get_tmdb_cover
            elif source == "Douban":
                parse_func = self._get_douban_cover
            elif source == "Bangumi":
                parse_func = self._get_bangumi_cover
            elif source == "IMDb":
                parse_func = self._get_imdb_cover
            else:
                parse_func = self._get_anibk_cover
            cover_url = parse_func(candidate["url"])

            name = movie_data.get("name", "cover")
            season = movie_data.get("season", 0)
            valid_name = "".join([c for c in name if c.isalnum() or c in (" ", "-", "_")])
            cover_path = self._download_cover(cover_url, f"{valid_name}_S{season}") if cover_url else None
            if source == "Douban" and not cover_path:
                cover_path = self._fallback_cover_from_tmdb(candidate, movie_data, f"{valid_name}_S{season}")

            intro_text = ""
            if source == "AniBK":
                intro_text = self._get_anibk_intro(candidate["url"])
            elif source == "TMDB":
                intro_text = self._get_tmdb_intro(candidate["url"])
            elif source == "Douban":
                intro_text = self._get_douban_intro(candidate["url"])
            elif source == "Bangumi":
                intro_text = self._get_bangumi_intro(candidate["url"])
            elif source == "IMDb":
                intro_text = self._get_imdb_intro(candidate["url"])

            scraped_year = None
            if source == "AniBK":
                scraped_year = self._fetch_anibk_year(candidate["url"])
            elif source == "TMDB":
                scraped_year = self._fetch_tmdb_year(candidate["url"])
            elif source == "Douban":
                scraped_year = self._fetch_douban_year(candidate["url"])
            elif source == "Bangumi":
                scraped_year = self._fetch_bangumi_year(candidate["url"])
            elif source == "IMDb":
                scraped_year = self._fetch_imdb_year(candidate["url"])

            if not scraped_year and candidate.get("year"):
                scraped_year = candidate["year"]

            return cover_path, intro_text, scraped_year

        except Exception as e:
            logger.error(f"下载指定封面/简介/年份失败: {e}")
            return None, None, None

    # ==================== 其他工具函数 ====================
    def _build_base_queries(self, movie_data, custom_name):
        title = str(movie_data.get("title", "") or "")
        name = str(movie_data.get("name", "") or "")
        series_title = str(movie_data.get("series_title", "") or "")
        season_title = str(movie_data.get("season_title", "") or "")
        special_type = str(movie_data.get("special_type", "") or "")
        year = movie_data.get("year", "")
        season = int(movie_data.get("season") or 0)
        parsed = clean_title_for_search(title)
        clean_base = parsed["clean_name"] or name or title
        seasonless_base = self._strip_season_tokens(clean_base)
        queries = []

        for value in (custom_name, title, name, series_title, clean_base, seasonless_base):
            normalized = str(value or "").strip()
            if normalized:
                queries.append(normalized)

        if season > 0 and seasonless_base:
            queries.extend(
                [
                    f"{seasonless_base} {self._season_label_cn(season)}",
                    f"{seasonless_base} 第{season}季",
                    f"{seasonless_base} Season {season}",
                    f"{seasonless_base} S{season:02d}",
                ]
            )
        if season_title and seasonless_base:
            queries.extend(
                [
                    f"{seasonless_base} {season_title}",
                    season_title if len(season_title) > 1 else "",
                ]
            )
        if special_type and seasonless_base:
            queries.append(f"{seasonless_base} {special_type}")
        if year:
            base_for_year = seasonless_base or clean_base
            if base_for_year:
                queries.append(f"{base_for_year} {year}")
        return list(dict.fromkeys([q for q in queries if q]))

    def _season_label_cn(self, season):
        season_map = {
            1: "第一季",
            2: "第二季",
            3: "第三季",
            4: "第四季",
            5: "第五季",
            6: "第六季",
            7: "第七季",
            8: "第八季",
            9: "第九季",
            10: "第十季",
        }
        return season_map.get(int(season or 0), f"第{season}季")

    def _strip_season_tokens(self, text):
        value = str(text or "").strip()
        patterns = [
            r"第\s*[一二三四五六七八九十\d]+\s*季",
            r"Season\s*\d+",
            r"\bS\d{1,2}\b",
            r"#\d+",
        ]
        for pattern in patterns:
            value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", value).strip()

    def _extract_candidate_season(self, text):
        value = str(text or "")
        match = re.search(r"第\s*([一二三四五六七八九十\d]+)\s*季", value, re.IGNORECASE)
        if match:
            season_token = match.group(1)
            if season_token.isdigit():
                return int(season_token)
            cn_map = {
                "一": 1,
                "二": 2,
                "三": 3,
                "四": 4,
                "五": 5,
                "六": 6,
                "七": 7,
                "八": 8,
                "九": 9,
                "十": 10,
            }
            return cn_map.get(season_token)
        match = re.search(r"\bS(\d{1,2})\b", value, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"Season\s*(\d{1,2})", value, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _score_candidate(self, movie_data, candidate):
        target_title = str(movie_data.get("title") or movie_data.get("name") or "").strip().lower()
        candidate_title = str(candidate.get("title") or "").strip().lower()
        target_year = int(movie_data.get("year") or 0)
        target_season = int(movie_data.get("season") or 0)
        candidate_season = self._extract_candidate_season(candidate.get("title"))
        candidate_year = int(candidate.get("year") or 0) if str(candidate.get("year") or "").isdigit() else 0
        score = 0.0
        if target_title and candidate_title:
            if target_title == candidate_title:
                score += 70
            elif target_title in candidate_title or candidate_title in target_title:
                score += 54
            else:
                target_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+", target_title))
                candidate_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+", candidate_title))
                if target_tokens and candidate_tokens:
                    score += 45 * (len(target_tokens & candidate_tokens) / max(len(target_tokens | candidate_tokens), 1))
        if target_year and candidate_year:
            gap = abs(target_year - candidate_year)
            score += max(0, 20 - min(gap, 20))
        if target_season:
            if candidate_season == target_season:
                score += 26
            elif candidate_season is not None:
                score -= min(18, abs(candidate_season - target_season) * 8)
        if movie_data.get("is_series"):
            score += 5
        source_bonus = {"Douban": 6, "TMDB": 4, "Bangumi": 5, "IMDb": 4, "AniBK": 3}
        score += source_bonus.get(candidate.get("source"), 0)
        return round(score, 2)

    def _normalize_candidate_url(self, source_name, url):
        value = str(url or "").strip()
        if source_name == "Douban":
            return value.split("?", 1)[0].rstrip("/")
        return value

    def _is_likely_multi_season(self, result_titles, base_name):
        if len(result_titles) < 2:
            return False
        lower_titles = [t.lower() for t in result_titles]
        base_name_lower = base_name.lower()
        multi_season_keywords = [
            "第2季", "第3季", "第4季", "season 2", "season 3", "s2", "s3", "s02", "s03",
            "第二季", "第三季", "第四季", "第二期", "第三期",
            "part 2", "part ii", "part2", "下半篇", "续篇", "最终季", "2nd season", "3rd season"
        ]
        multi_season_keywords_lower = [k.lower() for k in multi_season_keywords]
        hit_count = 0
        for title in lower_titles:
            if any(keyword in title for keyword in multi_season_keywords_lower):
                hit_count += 1
            elif base_name_lower in title and len(title) > len(base_name_lower) * 1.2:
                hit_count += 0.5
        if hit_count >= 1:
            return True
        valid_count = 0
        for title in lower_titles:
            if base_name_lower in title:
                valid_count += 1
        if valid_count >= 3:
            return True
        return False

    def _pick_s1_from_results(self, titles):
        for i, t in enumerate(titles):
            t_lower = t.lower()
            if any(k in t_lower for k in ["第1季", "第一季", "第一期", "season 1", "s1", "s01"]):
                return i
        min_len = 9999
        min_idx = 0
        for i, t in enumerate(titles):
            if len(t) < min_len:
                min_len = len(t)
                min_idx = i
        return min_idx

    def _fetch_anibk_list(self, query):
        try:
            search_url = f"{ANIBK_SEARCH}{quote(query)}"
            res = requests.get(search_url, headers=HEADERS, timeout=10)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
            candidates = []
            seen = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/bk/") and href.split("/")[-1].isdigit():
                    title = a.get_text(strip=True)
                    full_url = urljoin(ANIBK_BASE, href)
                    if title and full_url not in seen:
                        seen.add(full_url)
                        candidates.append({"title": title, "url": full_url})
            return candidates
        except Exception as e:
            logger.warning(f"动漫科搜索失败: {e}")
            return []

    def _fetch_bangumi_list(self, query):
        try:
            response = requests.post(
                f"{BANGUMI_API}/v0/search/subjects",
                params={"limit": 6, "offset": 0},
                json={"keyword": query, "sort": "match", "filter": {"type": [2]}},
                headers={"User-Agent": "JMH/1.0"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            candidates = []
            for item in payload.get("data", [])[:6]:
                title = str(item.get("name_cn") or item.get("name") or "").strip()
                subject_id = item.get("id")
                if not title or not subject_id:
                    continue
                air_date = str(item.get("date") or "").strip()
                candidates.append(
                    {
                        "title": title,
                        "url": f"https://bgm.tv/subject/{subject_id}",
                        "year": air_date[:4] if re.match(r"\d{4}", air_date) else "",
                    }
                )
            return candidates
        except Exception as exc:
            logger.warning("Bangumi search failed for %s: %s", query, exc)
            return []

    def _fetch_imdb_list(self, query):
        if not query:
            return []
        safe_term = re.sub(r"[^a-z0-9]+", "", query.lower())[:2] or "a"
        try:
            response = requests.get(
                f"https://v3.sg.media-imdb.com/suggestion/{safe_term}/{quote(query)}.json",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("IMDb search failed for %s: %s", query, exc)
            return []

        candidates = []
        for item in payload.get("d", [])[:6]:
            title = str(item.get("l") or "").strip()
            imdb_id = str(item.get("id") or "").strip()
            year = item.get("y")
            if not title or not imdb_id:
                continue
            candidates.append(
                {
                    "title": title,
                    "url": f"{IMDB_BASE}/title/{imdb_id}/",
                    "year": str(year) if year else "",
                }
            )
        return candidates

    def _fetch_douban_list(self, query):
        candidates = []
        try:
            _session, res = self._douban_get(f"{DOUBAN_BASE}/j/subject_suggest?q={quote(query)}")
            res.raise_for_status()
            payload = res.json()
            for item in payload[:10]:
                title = str(item.get("title") or "").strip()
                url = str(item.get("url") or "").strip()
                if title and url:
                    candidates.append({
                        "title": title,
                        "url": url,
                        "year": str(item.get("year") or "").strip(),
                    })
        except Exception as e:
            logger.warning(f"豆瓣 suggest 搜索失败: {e}")

        if candidates:
            return candidates

        try:
            _session, res = self._douban_get(f"{DOUBAN_BASE}/search?q={quote(query)}")
            res.raise_for_status()
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
            for card in soup.select(".result"):
                title_link = card.select_one(".title a")
                if not title_link:
                    continue
                title = title_link.get_text(" ", strip=True)
                url = title_link.get("href") or ""
                year_match = re.search(r"(\d{4})", card.get_text(" ", strip=True))
                candidates.append({
                    "title": title,
                    "url": url,
                    "year": year_match.group(1) if year_match else "",
                })
                if len(candidates) >= 10:
                    break
        except Exception as e:
            logger.warning(f"豆瓣页面搜索失败: {e}")
        return candidates

    def _fetch_tmdb_list(self, query, is_series):
        if self._tmdb_is_temporarily_disabled():
            logger.warning(f"TMDB search skipped during cooldown: {self._tmdb_failure_reason}")
            return []
        try:
            if self._has_tmdb_api_key():
                media_type = self._tmdb_media_type(is_series)
                payload = self._tmdb_api_get(f"/search/{media_type}", {"query": query, "include_adult": "false"})
                candidates = []
                for item in payload.get("results", [])[:10]:
                    item_id = item.get("id")
                    title = item.get("name") or item.get("title") or ""
                    if not item_id or not title:
                        continue
                    candidates.append(
                        {
                            "title": title,
                            "url": self._build_tmdb_locator(media_type, item_id),
                            "year": (item.get("first_air_date") or item.get("release_date") or "")[:4],
                        }
                    )
                self._reset_tmdb_availability()
                return candidates
            base_url = f"{TMDB_BASE}/search/tv?query=" if is_series else f"{TMDB_BASE}/search/movie?query="
            search_url = f"{base_url}{quote(query)}&language=zh-CN"
            headers = HEADERS.copy()
            headers["Referer"] = TMDB_BASE
            res = requests.get(search_url, headers=headers, timeout=4)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
            candidates = []
            cards = soup.find_all("div", class_="card")
            for card in cards:
                a_tag = card.find("a", href=True)
                title_elem = card.find("h2")
                if a_tag and title_elem:
                    candidates.append({
                        "title": title_elem.get_text(strip=True),
                        "url": urljoin(TMDB_BASE, a_tag["href"])
                    })
            self._reset_tmdb_availability()
            return candidates
        except Exception as e:
            self._disable_tmdb_temporarily(e)
            logger.warning(f"TMDB搜索失败: {e}")
            return []


