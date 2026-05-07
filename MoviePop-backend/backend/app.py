from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.jobs import job_manager
from backend.runtime_state import get_runtime_state
from backend.services import (
    ConfigService,
    LibraryService,
    OpenListService,
    PlaybackService,
    RecommendationService,
    ReportService,
    ScraperService,
)
from config.app_config import AppConfig
from core.openlist_manager import openlist_manager
from core.remote_source import infer_remote_provider, make_remote_client
from utils.logger import get_logger

logger = get_logger()

BASE_DIR = Path(__file__).resolve().parent.parent
APP_CONFIG = AppConfig()
COVERS_DIR = APP_CONFIG.COVERS_DIR

config_service = ConfigService()
library_service = LibraryService()
playback_service = PlaybackService(library_service)
scraper_service = ScraperService(library_service)
recommendation_service = RecommendationService(library_service)
report_service = ReportService(library_service, recommendation_service)
openlist_service = OpenListService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = AppConfig()
    if config.OPENLIST_ENABLED and config.OPENLIST_AUTO_START:
        try:
            openlist_manager.start()
        except Exception as exc:
            logger.warning("OpenList 自动启动失败: %s", exc)
    yield
    playback_service.stop_vlc_controlled_session()
    openlist_manager.stop()

# \u6d41\u5a92\u4f53 URL \u7f13\u5b58
_stream_url_cache: dict[str, tuple[str, float]] = {}
_STREAM_URL_TTL = 25 * 60  # 25 \u5206\u949f

app = FastAPI(title="\u9e21\u7c73\u82b1", version="2.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if COVERS_DIR.exists():
    app.mount("/covers", StaticFiles(directory=str(COVERS_DIR)), name="covers")

# 前端静态文件 - 支持打包后的路径
import sys
if getattr(sys, 'frozen', False):
    # PyInstaller打包后的路径
    FRONTEND_DIR = Path(sys._MEIPASS) / "frontend"
else:
    FRONTEND_DIR = BASE_DIR.parent / "MoviePop-front"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend-assets")


@app.get("/")
def serve_index():
    from fastapi.responses import FileResponse
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"error": "Frontend not found"}


class ConfigPayload(BaseModel):
    remote_provider: str = "webdav"
    remote_profiles: dict[str, Any] = Field(default_factory=dict)
    webdav_host: str = ""
    webdav_user: str = ""
    webdav_pass: str = ""
    remote_cookie: str = ""
    openlist_source_mode: str = "builtin"
    scan_max_depth: int = 2
    saved_mount_dirs: list[str] = Field(default_factory=list)
    local_scan_max_depth: int = 3
    local_mount_dirs: list[str] = Field(default_factory=list)
    potplayer_path: str = ""
    vlc_path: str = ""
    default_player: str = "potplayer"
    video_formats: list[str] = Field(default_factory=list)
    enable_auto_scrape: bool = True
    scrape_source: str = "auto"
    tmdb_api_key: str = ""
    tmdb_api_base: str = "https://api.themoviedb.org/3"
    tmdb_web_base: str = "https://www.themoviedb.org"
    tmdb_image_base: str = "https://image.tmdb.org/t/p/w500"
    ui_theme: str = "amber"
    interface_theme: str = "amber"
    interface_language: str = "zh"


class MoviePathPayload(BaseModel):
    movie_path: str


class PlayPayload(MoviePathPayload):
    episode_index: int = 0


class VLCControlPayload(BaseModel):
    action: str
    value: str | None = None


class UpdateMoviePayload(MoviePathPayload):
    updates: dict[str, Any]


class CandidateSearchPayload(MoviePathPayload):
    custom_name: str | None = None


class CandidateApplyPayload(MoviePathPayload):
    candidate: dict[str, Any]


class RecommendationRatingPayload(MoviePathPayload):
    rating: float = Field(ge=0, le=5)


class DirectoryBrowsePayload(ConfigPayload):
    path: str = "/"


class PlayerPathPickPayload(BaseModel):
    player: str = "potplayer"
    current_path: str = ""


class OpenListConfigPayload(BaseModel):
    enabled: bool = False
    port: int = 5244
    admin_password: str = ""
    auto_start: bool = True


class OpenListStoragePayload(BaseModel):
    id: int | None = None
    mount_path: str = ""
    driver: str = ""
    addition: dict[str, Any] = Field(default_factory=dict)
    order: int = 0
    cache_expiration: int = 30


def _build_stream_client(provider: str | None, movie_path: str):
    config = AppConfig()
    config.load_config()
    resolved_provider = infer_remote_provider(movie_path, default=provider or config.REMOTE_PROVIDER)
    return resolved_provider, make_remote_client(config, resolved_provider)


def _rewrite_m3u8_playlist(playlist_text: str, base_url: str, provider: str) -> str:
    rewritten_lines: list[str] = []
    for raw_line in playlist_text.splitlines():
        line = raw_line.strip()
        if not line:
            rewritten_lines.append(raw_line)
            continue

        if line.startswith("#") and 'URI="' in line:
            start = line.find('URI="')
            if start >= 0:
                prefix = line[: start + 5]
                rest = line[start + 5 :]
                end = rest.find('"')
                if end >= 0:
                    uri = rest[:end]
                    absolute = urljoin(base_url, uri)
                    proxied = f"/api/stream/segment?provider={quote(provider)}&upstream={quote(absolute, safe='')}"
                    rewritten_lines.append(f'{prefix}{proxied}"{rest[end + 1:]}')
                    continue

        if line.startswith("#"):
            rewritten_lines.append(raw_line)
            continue

        absolute = urljoin(base_url, line)
        proxied = f"/api/stream/segment?provider={quote(provider)}&upstream={quote(absolute, safe='')}"
        rewritten_lines.append(proxied)

    return "\n".join(rewritten_lines)


def _is_m3u8_content_type(content_type: str) -> bool:
    value = str(content_type or "").lower()
    return "mpegurl" in value or "m3u8" in value or "vnd.apple.mpegurl" in value


def _build_passthrough_headers(response) -> dict[str, str]:
    headers: dict[str, str] = {}
    for name in (
        "accept-ranges",
        "cache-control",
        "content-disposition",
        "content-length",
        "content-range",
        "content-type",
        "etag",
        "last-modified",
    ):
        value = response.headers.get(name)
        if value:
            headers[name] = value
    return headers


def _build_content_disposition(file_name: str) -> str:
    safe_name = str(file_name or "").strip() or "media.bin"
    encoded_name = quote(safe_name, safe="")
    return f"inline; filename*=UTF-8''{encoded_name}"


def _pick_player_file(player: str, current_path: str = "") -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"当前环境无法打开文件选择器: {exc}") from exc

    player_name = "VLC" if str(player or "").strip().lower() == "vlc" else "PotPlayer"
    initial_path = str(current_path or "").strip()
    initial_dir = ""
    initial_file = ""
    if initial_path:
        if os.path.isdir(initial_path):
            initial_dir = initial_path
        else:
            initial_dir = os.path.dirname(initial_path)
            initial_file = os.path.basename(initial_path)

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askopenfilename(
            title=f"选择 {player_name} 可执行文件",
            initialdir=initial_dir or None,
            initialfile=initial_file or None,
            filetypes=[
                ("可执行文件", "*.exe"),
                ("所有文件", "*.*"),
            ],
        )
        return str(selected or "").strip()
    finally:
        root.destroy()


def _proxy_upstream_response(
    request: Request,
    *,
    upstream_url: str,
    provider: str,
    client,
    file_name: str = "",
):
    upstream_headers = {"Accept-Encoding": "identity"}
    for header_name in ("range", "if-range"):
        header_value = request.headers.get(header_name)
        if header_value:
            upstream_headers[header_name] = header_value

    response = client.session.get(
        upstream_url,
        headers=upstream_headers,
        timeout=30,
        stream=True,
        allow_redirects=True,
    )
    response.raise_for_status()

    media_type = response.headers.get("content-type", "application/octet-stream")
    if _is_m3u8_content_type(media_type):
        playlist_text = response.text
        base_url = response.url.rsplit("/", 1)[0] + "/"
        rewritten = _rewrite_m3u8_playlist(playlist_text, base_url, provider)
        headers = _build_passthrough_headers(response)
        headers.pop("content-length", None)
        response.close()
        return Response(content=rewritten, media_type="application/vnd.apple.mpegurl", headers=headers)

    headers = _build_passthrough_headers(response)
    if file_name:
        headers["content-disposition"] = _build_content_disposition(file_name)
    if request.method == "HEAD":
        response.close()
        return Response(status_code=response.status_code, media_type=media_type, headers=headers)

    return StreamingResponse(
        response.iter_content(chunk_size=64 * 1024),
        status_code=response.status_code,
        media_type=media_type,
        headers=headers,
        background=BackgroundTask(response.close),
    )


@app.get("/api/bootstrap")
def bootstrap() -> dict[str, Any]:
    config = config_service.get_public_config()
    return {
        "config": config,
        "stats": library_service.get_stats(),
        "has_library": config["has_any_library"],
        "player_runtime": get_runtime_state(),
    }


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return config_service.get_public_config()


@app.get("/api/player/runtime")
def get_player_runtime() -> dict[str, Any]:
    return get_runtime_state()


@app.put("/api/config")
def save_config(payload: ConfigPayload) -> dict[str, Any]:
    return config_service.update_config(payload.dict())


@app.post("/api/config/test")
def test_config_connection(payload: ConfigPayload | None = None) -> dict[str, Any]:
    success, message = config_service.test_connection(payload.dict() if payload else None)
    return {"success": success, "message": message}


@app.get("/api/directories")
def get_webdav_directories(path: str = Query(default="/")) -> list[dict[str, str]]:
    try:
        return config_service.list_directories(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/directories")
def browse_webdav_directories(payload: DirectoryBrowsePayload) -> list[dict[str, str]]:
    try:
        config_payload = payload.dict()
        path = config_payload.pop("path", "/")
        logger.info("目录浏览请求: path=%s, provider=%s", path, config_payload.get("remote_provider"))
        return config_service.list_directories(path, config_payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/local-directories")
def get_local_directories(path: str = Query(default="")) -> list[dict[str, str]]:
    try:
        return config_service.list_local_directories(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/system/pick-player")
def pick_player_file(payload: PlayerPathPickPayload) -> dict[str, str]:
    try:
        return {"path": _pick_player_file(payload.player, payload.current_path)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/library")
def get_library(
    mode: str = Query(default="all"),
    source: str = Query(default="remote"),
    search: str = Query(default=""),
    force_refresh: bool = Query(default=False),
) -> dict[str, Any]:
    movies = library_service.get_movies(
        mode=mode,
        source=source,
        search=search,
        force_refresh=force_refresh,
    )
    return {"items": movies, "stats": library_service.get_stats()}


@app.post("/api/library/refresh")
def refresh_library(
    source: str = Query(default="remote"),
    auto_scrape: bool = Query(default=True),
) -> dict[str, str]:
    def task(update):
        if source == "combined":
            movie_count = 0
            scrape_total = 0
            scrape_updated = 0
            for index, current_source in enumerate(("remote", "local"), start=1):
                update(index - 1, 2, f"Refreshing {current_source} library")
                movies = library_service.refresh_library(source=current_source)
                movie_count += len(movies)
                if auto_scrape and movies:
                    scrape_result = scraper_service.scrape_library(source=current_source, progress=update)
                    scrape_total += scrape_result.get("total", 0)
                    scrape_updated += scrape_result.get("updated", 0)
            return {
                "movie_count": movie_count,
                "scrape": {"total": scrape_total, "updated": scrape_updated},
                "source": source,
            }

        scan_target = "本地目录" if source == "local" else "WebDAV 目录"
        update(0, 1, f"正在扫描{scan_target}")
        movies = library_service.refresh_library(source=source)
        if auto_scrape and movies:
            update(0, len(movies), "扫描完成，开始补全封面和简介")
            scrape_result = scraper_service.scrape_library(source=source, progress=update)
        else:
            scrape_result = {"total": len(movies), "updated": 0}
        return {"movie_count": len(movies), "scrape": scrape_result, "source": source}

    job = job_manager.start(f"refresh-{source}-library", task)
    return {"job_id": job.job_id}


@app.post("/api/library/scrape")
def scrape_library(source: str = Query(default="remote")) -> dict[str, str]:
    def task(update):
        if source != "combined":
            return scraper_service.scrape_library(source=source, progress=update)

        total = 0
        updated = 0
        for index, current_source in enumerate(("remote", "local"), start=1):
            update(index - 1, 2, f"Scraping {current_source} metadata")
            result = scraper_service.scrape_library(source=current_source, progress=update)
            total += result.get("total", 0)
            updated += result.get("updated", 0)
        return {"total": total, "updated": updated, "source": source}

    job = job_manager.start(f"scrape-{source}-library", task)
    return {"job_id": job.job_id}


@app.get("/api/recommendations")
def get_recommendations(
    limit: int = Query(default=18, ge=1, le=48),
    external_limit: int = Query(default=8, ge=0, le=24),
) -> dict[str, Any]:
    return recommendation_service.get_dashboard(limit=limit, external_limit=external_limit)


@app.post("/api/recommendations/refresh")
def refresh_recommendations() -> dict[str, Any]:
    return recommendation_service.refresh()


@app.post("/api/recommendations/rate")
def rate_recommendation_movie(payload: RecommendationRatingPayload) -> dict[str, Any]:
    try:
        return recommendation_service.rate_movie(payload.movie_path, payload.rating)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/report")
def get_report() -> dict[str, Any]:
    return report_service.get_report()


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str) -> dict[str, Any]:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job.snapshot()


@app.post("/api/movies/favorite")
def toggle_favorite(payload: MoviePathPayload) -> dict[str, Any]:
    try:
        movie = library_service.toggle_favorite(payload.movie_path)
        return {"movie": movie, "stats": library_service.get_stats()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/movies/item")
def get_movie_item(movie_path: str = Query(...), source: str | None = Query(default=None)) -> dict[str, Any]:
    movie = library_service.get_movie(movie_path, source=source)
    if not movie:
        raise HTTPException(status_code=404, detail="未找到对应的影视条目")
    return {"movie": movie}


@app.post("/api/movies/recent")
def add_recent(payload: MoviePathPayload) -> dict[str, Any]:
    try:
        movie = library_service.add_recent(payload.movie_path)
        return {"movie": movie, "stats": library_service.get_stats()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/movies/recent")
def clear_recent() -> dict[str, Any]:
    library_service.cache.clear_recent_play()
    return {"success": True, "stats": library_service.get_stats()}


@app.post("/api/movies/play")
def play_movie(payload: PlayPayload) -> dict[str, Any]:
    try:
        result = playback_service.play(payload.movie_path, payload.episode_index)
        return {"success": True, "result": result, "stats": library_service.get_stats()}
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/vlc/session/start")
def start_vlc_controlled_session(payload: PlayPayload) -> dict[str, Any]:
    try:
        result = playback_service.start_vlc_controlled_playback(payload.movie_path, payload.episode_index)
        return {"success": True, "result": result, "stats": library_service.get_stats()}
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/vlc/session")
def get_vlc_controlled_session() -> dict[str, Any]:
    return {"success": True, "result": playback_service.get_vlc_controlled_session()}


@app.post("/api/vlc/session/command")
def control_vlc_controlled_session(payload: VLCControlPayload) -> dict[str, Any]:
    try:
        result = playback_service.control_vlc_controlled_session(payload.action, payload.value)
        return {"success": True, "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/vlc/session")
def stop_vlc_controlled_session() -> dict[str, Any]:
    return playback_service.stop_vlc_controlled_session()


@app.get("/api/stream/playlist.m3u8")
def stream_playlist(
    movie_path: str = Query(...),
    provider: str | None = Query(default=None),
) -> Response:
    try:
        resolved_provider, client = _build_stream_client(provider, movie_path)
        upstream_url = client.get_file_url(movie_path)
        response = client.session.get(upstream_url, timeout=30)
        response.raise_for_status()
        base_url = upstream_url.rsplit("/", 1)[0] + "/"
        rewritten = _rewrite_m3u8_playlist(response.text, base_url, resolved_provider)
        return Response(content=rewritten, media_type="application/vnd.apple.mpegurl")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.api_route("/api/stream/media", methods=["GET", "HEAD"])
@app.api_route("/api/stream/media/{media_name}", methods=["GET", "HEAD"])
def stream_media(
    request: Request,
    media_name: str = "",
    movie_path: str = Query(...),
    provider: str | None = Query(default=None),
) -> Response:
    try:
        resolved_provider, client = _build_stream_client(provider, movie_path)
        cache_key = f"{resolved_provider}:{movie_path}"
        now = time.time()
        cached = _stream_url_cache.get(cache_key)
        if cached and now - cached[1] < _STREAM_URL_TTL:
            upstream_url = cached[0]
        else:
            upstream_url = client.get_file_url(movie_path)
            _stream_url_cache[cache_key] = (upstream_url, now)
        return _proxy_upstream_response(
            request,
            upstream_url=upstream_url,
            provider=resolved_provider,
            client=client,
            file_name=media_name,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.api_route("/api/stream/segment", methods=["GET", "HEAD"])
def stream_segment(
    request: Request,
    upstream: str = Query(...),
    provider: str | None = Query(default=None),
) -> Response:
    try:
        resolved_provider, client = _build_stream_client(provider, "")
        return _proxy_upstream_response(
            request,
            upstream_url=upstream,
            provider=resolved_provider,
            client=client,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/movies/update")
def update_movie(payload: UpdateMoviePayload) -> dict[str, Any]:
    try:
        movie = library_service.save_custom_info(payload.movie_path, payload.updates)
        return {"movie": movie}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/movies/scrape")
def scrape_single_movie(payload: CandidateSearchPayload) -> dict[str, Any]:
    try:
        movie = scraper_service.scrape_single(payload.movie_path, payload.custom_name)
        return {"movie": movie}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/movies/search-candidates")
def search_movie_candidates(payload: CandidateSearchPayload) -> dict[str, Any]:
    try:
        return scraper_service.search_candidates(payload.movie_path, payload.custom_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/movies/apply-candidate")
def apply_movie_candidate(payload: CandidateApplyPayload) -> dict[str, Any]:
    try:
        movie = scraper_service.apply_candidate(payload.movie_path, payload.candidate)
        return {"movie": movie}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/cache/clear")
def clear_library_cache(source: str = Query(default="")) -> dict[str, bool]:
    library_service.clear_library_cache(source or None)
    return {"success": True}


@app.post("/api/cache/clear-all")
def clear_all_cache() -> dict[str, bool]:
    library_service.clear_all_cache()
    return {"success": True}


@app.post("/api/data/clear-all")
def clear_all_data() -> dict[str, bool]:
    library_service.clear_all_data()
    return {"success": True}


@app.get("/api/tags")
def get_all_tags() -> dict[str, Any]:
    tags = library_service.get_all_tags()
    return {"tags": tags}


@app.get("/api/movies/{movie_path}/tags")
def get_movie_tags(movie_path: str) -> dict[str, Any]:
    try:
        tags = library_service.get_movie_tags(movie_path)
        return {"tags": tags}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/movies/{movie_path}/tags")
def add_movie_tag(movie_path: str, tag: str = Body(embed=True)) -> dict[str, Any]:
    try:
        movie = library_service.add_movie_tag(movie_path, tag)
        return {"movie": movie}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/movies/{movie_path}/tags/{tag}")
def remove_movie_tag(movie_path: str, tag: str) -> dict[str, Any]:
    try:
        movie = library_service.remove_movie_tag(movie_path, tag)
        return {"movie": movie}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/tags/{tag}/movies")
def get_movies_by_tag(tag: str, source: str = Query(default="remote")) -> dict[str, Any]:
    movies = library_service.get_movies_by_tag(tag, source=source)
    return {"items": movies}


@app.post("/api/movies/{movie_path}/progress")
def save_playback_progress(
    movie_path: str,
    progress: float = Body(..., embed=True),
    duration: float = Body(..., embed=True),
) -> dict[str, Any]:
    try:
        return library_service.save_playback_progress(movie_path, progress, duration)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/movies/{movie_path}/progress")
def get_playback_progress(movie_path: str) -> dict[str, Any]:
    try:
        return library_service.get_playback_progress(movie_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/movies/{movie_path}/progress")
def clear_playback_progress(movie_path: str) -> dict[str, Any]:
    try:
        return library_service.clear_playback_progress(movie_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---- OpenList 管理接口 ----

@app.get("/api/openlist/status")
def get_openlist_status() -> dict[str, Any]:
    return openlist_service.get_status()


@app.post("/api/openlist/start")
def start_openlist() -> dict[str, Any]:
    return openlist_service.start()


@app.post("/api/openlist/stop")
def stop_openlist() -> dict[str, Any]:
    return openlist_service.stop()


@app.post("/api/openlist/restart")
def restart_openlist() -> dict[str, Any]:
    return openlist_service.restart()


@app.get("/api/openlist/config")
def get_openlist_config() -> dict[str, Any]:
    return openlist_service.get_config()


@app.put("/api/openlist/config")
def save_openlist_config(payload: OpenListConfigPayload) -> dict[str, Any]:
    return openlist_service.update_config(payload.dict())


@app.post("/api/openlist/download")
def download_openlist_binary() -> dict[str, str]:
    job_id = openlist_service.download_binary()
    return {"job_id": job_id}


@app.get("/api/openlist/version")
def check_openlist_version() -> dict[str, Any]:
    return openlist_service.check_binary_update()


@app.post("/api/openlist/reset-password")
def reset_openlist_password(payload: dict[str, str]) -> dict[str, Any]:
    password = payload.get("password", "").strip()
    if not password:
        raise HTTPException(status_code=400, detail="密码不能为空")
    return openlist_service.reset_password(password)


@app.get("/api/openlist/drivers")
def get_openlist_drivers() -> dict[str, Any]:
    return {"items": openlist_service.get_supported_drivers()}


@app.get("/api/openlist/storages")
def list_openlist_storages() -> dict[str, Any]:
    try:
        items = openlist_service.list_storages()
        return {"items": items}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/openlist/directories")
def list_openlist_directories(
    path: str = Query(default="/"),
    recursive: bool = Query(default=False),
) -> list[dict[str, str]]:
    try:
        return openlist_service.list_directories(path, recursive=recursive)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/openlist/storages")
def add_openlist_storage(payload: OpenListStoragePayload) -> dict[str, Any]:
    try:
        return openlist_service.add_storage(payload.dict())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/openlist/storages")
def update_openlist_storage(payload: OpenListStoragePayload) -> dict[str, Any]:
    try:
        return openlist_service.update_storage(payload.dict())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/openlist/storages")
def delete_openlist_storage(storage_id: int = Query(...)) -> dict[str, Any]:
    try:
        return openlist_service.delete_storage(storage_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/openlist/storages/enable")
def enable_openlist_storage(storage_id: int = Query(...)) -> dict[str, Any]:
    try:
        return openlist_service.enable_storage(storage_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/openlist/storages/disable")
def disable_openlist_storage(storage_id: int = Query(...)) -> dict[str, Any]:
    try:
        return openlist_service.disable_storage(storage_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
