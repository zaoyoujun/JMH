from __future__ import annotations

import socket

from backend.server import create_server
from config.app_config import AppConfig


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def main() -> None:
    config = AppConfig()
    config.load_config()
    api_port = config.SERVER_PORT

    if not is_port_free(api_port):
        print(f"错误: API 端口 {api_port} 已被占用，请先关闭占用该端口的程序。")
        return

    server, url, _ = create_server(port=api_port)
    print(f"MoviePop backend API running at {url}")
    print("按 Ctrl+C 停止")
    print()
    server.run()


if __name__ == "__main__":
    main()
