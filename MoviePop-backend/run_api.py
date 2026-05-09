"""启动 MoviePop：生成 nginx.conf 并启动后端 API 服务"""
from __future__ import annotations

import atexit
import socket
import subprocess
import time
from pathlib import Path

from backend.server import create_server
from config.app_config import AppConfig


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0

NGINX_CONF_TEMPLATE = """\
worker_processes  1;

events {{
    worker_connections  1024;
}}

http {{
    include       "{nginx_dir}/conf/mime.types";
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout  65;

    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer"';

    server {{
        listen       {nginx_port};
        server_name  localhost;

        access_log  "{log_dir}/moviepop_access.log"  main;
        error_log   "{log_dir}/moviepop_error.log";

        # ---- 前端静态文件 ----

        location /assets/ {{
            alias "{frontend_dir}/";
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            add_header Pragma "no-cache";
            add_header Expires "0";
        }}

        location = / {{
            root "{frontend_dir}";
            try_files /index.html =404;
        }}

        # ---- 后端 API 反向代理 ----

        location /api/ {{
            proxy_pass http://127.0.0.1:{api_port};
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

            proxy_buffering off;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }}

        # ---- 封面图片代理 ----

        location /covers/ {{
            proxy_pass http://127.0.0.1:{api_port};
            proxy_set_header Host $host;
        }}
    }}
}}
"""


def generate_nginx_conf(api_port: int, nginx_port: int = 80) -> Path:
    project_root = Path(__file__).resolve().parent.parent
    nginx_dir = (project_root / "nginx-1.30.0").as_posix()
    frontend_dir = (project_root / "MoviePop-front").as_posix()
    log_dir = (project_root / "logs").as_posix()
    conf_path = project_root / "nginx.conf"

    # 确保 logs 目录存在
    (project_root / "logs").mkdir(exist_ok=True)

    content = NGINX_CONF_TEMPLATE.format(
        nginx_dir=nginx_dir,
        frontend_dir=frontend_dir,
        api_port=api_port,
        nginx_port=nginx_port,
        log_dir=log_dir,
    )
    conf_path.write_text(content, encoding="utf-8")
    return conf_path


def find_nginx() -> str | None:
    """查找 nginx 可执行文件"""
    project_root = Path(__file__).resolve().parent.parent
    local_nginx = project_root / "nginx-1.30.0" / "nginx.exe"
    if local_nginx.exists():
        return str(local_nginx)
    # 尝试 PATH 中的 nginx
    import shutil
    return shutil.which("nginx")


def stop_existing_nginx() -> None:
    """强制停止所有 nginx 进程，释放端口"""
    try:
        subprocess.run(
            ["taskkill", "/f", "/im", "nginx.exe"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        pass


def start_nginx(conf_path: Path) -> bool:
    """启动 nginx，返回是否成功"""
    nginx_exe = find_nginx()
    if not nginx_exe:
        print("错误: 未找到 nginx，请确保 nginx-1.30.0 目录存在或 nginx 已安装并在 PATH 中")
        return False
    try:
        # 先停止已有的 nginx 实例
        stop_existing_nginx()
        time.sleep(1)

        result = subprocess.run(
            [nginx_exe, "-t", "-c", str(conf_path)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            print(f"nginx 配置检测失败:\n{result.stderr}")
            return False

        subprocess.Popen(
            [nginx_exe, "-c", str(conf_path)],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        print("nginx 已启动")
        return True
    except Exception as exc:
        print(f"启动 nginx 失败: {exc}")
        return False


def main() -> None:
    config = AppConfig()
    config.load_config()
    api_port = config.SERVER_PORT
    nginx_port = config.NGINX_PORT

    # 检查端口，如果被占用先尝试停止已有的 nginx
    if not is_port_free(nginx_port):
        print(f"端口 {nginx_port} 被占用，尝试停止已有 nginx...")
        stop_existing_nginx()
        time.sleep(2)
        if not is_port_free(nginx_port):
            print(f"错误: 端口 {nginx_port} 仍被占用，请手动关闭占用该端口的程序")
            return
        print("已释放端口")

    if not is_port_free(api_port):
        print(f"错误: API 端口 {api_port} 已被占用，请关闭占用该端口的程序")
        return

    conf_path = generate_nginx_conf(api_port, nginx_port)
    print(f"nginx.conf 已生成: {conf_path}")
    print(f"后端 API 端口: {api_port}")
    print(f"nginx 监听端口: {nginx_port}")
    print()

    if not start_nginx(conf_path):
        print(f"nginx 启动失败，后端 API 仍会启动（可直接访问 http://127.0.0.1:{api_port}）")
        print()

    # 注册退出钩子：无论以何种方式退出都停止 nginx
    atexit.register(stop_existing_nginx)

    print(f"浏览器访问 http://localhost:{nginx_port}")
    print("按 Ctrl+C 停止")
    print()

    server, url, _ = create_server(port=api_port)
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n正在停止 nginx...")
        stop_existing_nginx()
        print("已停止")


if __name__ == "__main__":
    main()
