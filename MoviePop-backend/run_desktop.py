from __future__ import annotations

import atexit
import socket
import threading
import time
from contextlib import closing

import webview

from backend.runtime_state import mark_browser_runtime, set_desktop_window
from backend.server import create_server
from config.app_config import AppConfig
from core.openlist_manager import openlist_manager
from run_api import generate_nginx_conf, is_port_free, start_nginx, stop_existing_nginx


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.2)
    return False


def main() -> None:
    config = AppConfig()
    config.load_config()
    api_port = config.SERVER_PORT
    nginx_port = config.NGINX_PORT

    if not is_port_free(nginx_port):
        print(f"端口 {nginx_port} 已被占用，尝试停止现有 nginx...")
        stop_existing_nginx()
        time.sleep(1.5)
        if not is_port_free(nginx_port):
            print(f"错误: nginx 端口 {nginx_port} 仍被占用，请先关闭对应程序。")
            return

    if not is_port_free(api_port):
        print(f"错误: API 端口 {api_port} 已被占用，请先关闭对应程序。")
        return

    conf_path = generate_nginx_conf(api_port, nginx_port)
    if not start_nginx(conf_path):
        print("错误: 桌面模式依赖 nginx 提供前端页面，nginx 启动失败。")
        return

    atexit.register(stop_existing_nginx)

    server, _, _ = create_server(port=api_port)
    server_thread = threading.Thread(target=server.run, name="moviepop-api-server", daemon=True)
    server_thread.start()

    if not wait_for_port(api_port):
        print(f"错误: 后端 API 未能在端口 {api_port} 上成功启动。")
        stop_existing_nginx()
        return

    url = f"http://127.0.0.1:{nginx_port}"
    window = webview.create_window("MoviePop Desktop", url=url, width=1440, height=920)

    def on_webview_ready() -> None:
        set_desktop_window(window, "MoviePop Desktop")

    try:
        webview.start(on_webview_ready)
    finally:
        mark_browser_runtime()
        server.should_exit = True
        server_thread.join(timeout=10)
        openlist_manager.stop()
        stop_existing_nginx()


if __name__ == "__main__":
    main()
