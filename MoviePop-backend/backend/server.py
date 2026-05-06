from __future__ import annotations

import socket
import threading
import time
import webbrowser
from typing import Any

import uvicorn

from backend.app import app

# 实际监听的端口号，由 create_server 设置
resolved_port: int = 8765


def find_free_port(start: int = 8765, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("未找到可用端口")


def open_browser_when_ready(url: str, delay_seconds: float = 1.0) -> None:
    def opener() -> None:
        time.sleep(delay_seconds)
        webbrowser.open(url)

    threading.Thread(target=opener, name="open-browser", daemon=True).start()


def create_server(port: int | None = None) -> tuple[uvicorn.Server, str, int]:
    global resolved_port
    resolved_port = port or find_free_port()
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


def start_server_in_thread(port: int | None = None) -> tuple[uvicorn.Server, str, int, threading.Thread]:
    server, url, actual_port = create_server(port=port)
    thread = threading.Thread(target=server.run, name="jimihua-api", daemon=True)
    thread.start()
    return server, url, actual_port, thread


def run_server(open_browser: bool = True) -> dict[str, Any]:
    server, url, port = create_server()
    if open_browser:
        open_browser_when_ready(url)
    server.run()
    return {"url": url, "port": port}
