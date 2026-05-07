from __future__ import annotations

import uvicorn

from backend.app import app
from config.app_config import AppConfig

# 实际监听的端口号，供 services.py 等模块引用
resolved_port: int = 8765


def get_configured_port() -> int:
    config = AppConfig()
    config.load_config()
    return config.SERVER_PORT


def create_server(port: int | None = None) -> tuple[uvicorn.Server, str, int]:
    global resolved_port
    resolved_port = port or get_configured_port()
    url = f"http://127.0.0.1:{resolved_port}"
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=resolved_port,
        log_level="info",
        log_config=None,
        access_log=False,
    )
    return uvicorn.Server(config), url, resolved_port


def run_server() -> dict[str, str | int]:
    server, url, port = create_server()
    print(f"MoviePop API server running at {url}")
    server.run()
    return {"url": url, "port": port}
