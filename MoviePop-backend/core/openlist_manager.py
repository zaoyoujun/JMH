from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import tarfile
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Callable

import requests
import urllib3

from config.app_config import AppConfig

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from utils.logger import get_logger

logger = get_logger()

OPENLIST_GITHUB_REPO = "OpenListTeam/OpenList"
OPENLIST_FALLBACK_VERSION = "v3.42.0"
OPENLIST_CHECK_URL = "http://127.0.0.1:{port}/api/public/settings"
OPENLIST_HEALTH_INTERVAL = 10
OPENLIST_MAX_RESTARTS = 3
OPENLIST_PORT_RANGE = range(5244, 5265)
OPENLIST_DOWNLOAD_TIMEOUT = 300  # 下载总超时 5 分钟
OPENLIST_DOWNLOAD_CHUNK_SIZE = 8192
OPENLIST_MIRRORS = [
    "https://ghfast.top",
    "https://ghproxy.cn",
    "https://github.moeyy.xyz",
]


class OpenListManager:
    """OpenList 子进程管理器"""

    STATUS_STOPPED = "stopped"
    STATUS_STARTING = "starting"
    STATUS_RUNNING = "running"
    STATUS_ERROR = "error"

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._status: str = self.STATUS_STOPPED
        self._error_message: str = ""
        self._lock = threading.Lock()
        self._health_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._restart_count: int = 0
        self._start_time: float = 0
        self._config = AppConfig()
        self._active_port: int = 0  # 实际运行的端口

    def reload_config(self) -> None:
        """重新加载配置（清除数据后调用）"""
        self._config = AppConfig()

    def get_binary_path(self) -> Path:
        ext = ".exe" if platform.system() == "Windows" else ""
        return self._get_openlist_dir() / f"openlist{ext}"

    def is_binary_available(self) -> bool:
        return self.get_binary_path().is_file()

    def get_binary_version(self) -> str | None:
        binary = self.get_binary_path()
        if not binary.is_file():
            return None
        try:
            result = subprocess.run(
                [str(binary), "version"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
            )
            output = (result.stdout or result.stderr or "").strip()
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("v") or line.startswith("Version"):
                    return line.split()[-1].strip()
            return output.splitlines()[0].strip() if output else None
        except Exception:
            return None

    def _get_openlist_dir(self) -> Path:
        path = self._config.DATA_DIR / "openlist"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_openlist_data_dir(self) -> Path:
        path = self._get_openlist_dir() / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _find_available_port(self) -> int:
        preferred = self._config.OPENLIST_PORT or 5244
        # 优先使用用户配置的端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", preferred)) != 0:
                return preferred
        # 首选端口被占用，扫描备选端口
        for port in OPENLIST_PORT_RANGE:
            if port == preferred:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
        return preferred

    def _generate_openlist_config(self, port: int) -> None:
        data_dir = self._get_openlist_data_dir()
        config_file = data_dir / "config.json"
        db_path = data_dir / "data.db"
        log_path = data_dir / "log.log"

        config = {
            "force": False,
            "site_url": "",
            "cdn": "",
            "login_expiration": 48,
            "database": {
                "type": "sqlite3",
                "host": "",
                "port": 0,
                "user": "",
                "password": "",
                "name": "",
                "db_file": str(db_path).replace("\\", "/"),
                "table_prefix": "x_",
                "ssl_mode": "",
                "dsn": "",
            },
            "scheme": {
                "address": "127.0.0.1",
                "http_port": port,
                "disable_http": False,
                "unix_file": "",
                "unix_file_perm": "",
                "enable_tls": False,
                "cert_file": "",
                "key_file": "",
            },
            "temp_dir": str(data_dir / "temp").replace("\\", "/"),
            "bleve_dir": str(data_dir / "bleve").replace("\\", "/"),
            "dist_dir": "",
            "log": {
                "enable": True,
                "name": str(log_path).replace("\\", "/"),
                "max_size": 10,
                "max_backups": 5,
                "max_age": 28,
                "compress": False,
            },
            "delayed_start": 0,
            "max_connections": 0,
            "tls_insecure_skip_verify": True,
            "tasks": {
                "download": {"workers": 5, "max_retry": 1, "task_persistant": True},
                "transfer": {"workers": 5, "max_retry": 2, "task_persistant": True},
                "upload": {"workers": 5, "max_retry": 1, "task_persistant": False},
                "copy": {"workers": 5, "max_retry": 2, "task_persistant": True},
            },
        }
        config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._process and self._process.poll() is None:
                return {"success": True, "message": "OpenList 已在运行中", "status": self._status}

            if not self.is_binary_available():
                self._status = self.STATUS_ERROR
                self._error_message = "OpenList 二进制文件不存在，请先下载"
                return {"success": False, "message": self._error_message, "status": self._status}

            self._status = self.STATUS_STARTING
            self._error_message = ""
            port = self._find_available_port()

            try:
                self._generate_openlist_config(port)
                binary = self.get_binary_path()
                data_dir = self._get_openlist_data_dir()

                startupinfo = None
                creation_flags = 0
                if platform.system() == "Windows":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    creation_flags = subprocess.CREATE_NO_WINDOW

                # 准备环境变量，包含 admin 密码
                env = os.environ.copy()
                admin_password = self._config.OPENLIST_ADMIN_PASSWORD
                if admin_password:
                    env["OPENLIST_ADMIN_PASSWORD"] = admin_password

                self._process = subprocess.Popen(
                    [str(binary), "server", "--data", str(data_dir)],
                    cwd=str(self._get_openlist_dir()),
                    startupinfo=startupinfo,
                    creationflags=creation_flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                )
                self._start_time = time.time()

                if self._wait_for_ready(port):
                    self._status = self.STATUS_RUNNING
                    self._restart_count = 0
                    self._active_port = port
                    self._stop_event.clear()
                    self._start_health_thread()
                    logger.info("OpenList 启动成功，端口: %d, PID: %d", port, self._process.pid)
                    return {"success": True, "message": "OpenList 启动成功", "status": self._status, "port": port}
                else:
                    self._status = self.STATUS_ERROR
                    self._error_message = "OpenList 启动超时"
                    self._force_kill()
                    return {"success": False, "message": self._error_message, "status": self._status}

            except Exception as exc:
                self._status = self.STATUS_ERROR
                self._error_message = f"启动失败: {exc}"
                logger.error("OpenList 启动失败: %s", exc)
                return {"success": False, "message": self._error_message, "status": self._status}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if not self._process or self._process.poll() is not None:
                self._status = self.STATUS_STOPPED
                self._process = None
                return {"success": True, "message": "OpenList 已停止", "status": self._status}

            self._stop_event.set()
            pid = self._process.pid
            try:
                if platform.system() == "Windows":
                    # taskkill /T 终止整个进程树（包括子进程）
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True, timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=3)
            except Exception as exc:
                logger.warning("停止 OpenList 进程异常: %s", exc)

            self._process = None
            self._status = self.STATUS_STOPPED
            self._error_message = ""
            self._active_port = 0
            logger.info("OpenList 已停止")
            return {"success": True, "message": "OpenList 已停止", "status": self._status}

    def restart(self) -> dict[str, Any]:
        self.stop()
        time.sleep(1)
        return self.start()

    def reset_admin_password(self, password: str) -> dict[str, Any]:
        """重置 OpenList admin 密码"""
        binary = self.get_binary_path()
        if not binary.is_file():
            return {"success": False, "message": "OpenList 二进制文件不存在"}

        try:
            data_dir = self._get_openlist_data_dir()
            result = subprocess.run(
                [str(binary), "admin", "set", password, "--data", str(data_dir)],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
            )
            if result.returncode == 0:
                self._config.OPENLIST_ADMIN_PASSWORD = password
                self._config.save_config()
                return {"success": True, "message": "密码重置成功"}
            else:
                return {"success": False, "message": f"密码重置失败: {result.stderr or result.stdout}"}
        except Exception as exc:
            return {"success": False, "message": f"密码重置失败: {exc}"}

    def get_status(self) -> dict[str, Any]:
        pid = None
        uptime = 0
        if self._process and self._process.poll() is not None:
            pass
        elif self._process:
            pid = self._process.pid
            uptime = int(time.time() - self._start_time)

        return {
            "status": self._status,
            "port": self._active_port or self._config.OPENLIST_PORT or 5244,
            "pid": pid,
            "uptime_seconds": uptime,
            "error_message": self._error_message,
            "version": self.get_binary_version(),
            "binary_available": self.is_binary_available(),
            "auto_start": self._config.OPENLIST_AUTO_START,
            "enabled": self._config.OPENLIST_ENABLED,
        }

    def _wait_for_ready(self, port: int, timeout: float = 15.0) -> bool:
        url = OPENLIST_CHECK_URL.format(port=port)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    return True
            except requests.RequestException:
                pass
            time.sleep(0.5)
        return False

    def _start_health_thread(self):
        if self._health_thread and self._health_thread.is_alive():
            return
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_thread.start()

    def _health_check_loop(self):
        fail_count = 0
        while not self._stop_event.is_set():
            self._stop_event.wait(OPENLIST_HEALTH_INTERVAL)
            if self._stop_event.is_set():
                break
            if not self._process or self._process.poll() is not None:
                fail_count += 1
                if fail_count >= OPENLIST_MAX_RESTARTS:
                    logger.error("OpenList 进程异常退出，已达到最大重启次数")
                    with self._lock:
                        self._status = self.STATUS_ERROR
                        self._error_message = "OpenList 进程异常退出"
                        self._process = None
                    break
                logger.warning("OpenList 进程异常退出，尝试重启 (%d/%d)", fail_count, OPENLIST_MAX_RESTARTS)
                with self._lock:
                    self._status = self.STATUS_STARTING
                result = self.start()
                if result.get("success"):
                    fail_count = 0
                continue

            port = self._active_port or self._config.OPENLIST_PORT or 5244
            try:
                resp = requests.get(OPENLIST_CHECK_URL.format(port=port), timeout=5)
                if resp.status_code == 200:
                    fail_count = 0
                    continue
            except requests.RequestException:
                pass

            fail_count += 1
            if fail_count >= OPENLIST_MAX_RESTARTS:
                logger.error("OpenList 健康检查连续失败 %d 次，标记为错误状态", fail_count)
                with self._lock:
                    self._status = self.STATUS_ERROR
                    self._error_message = "OpenList 健康检查失败"
                break

    def _force_kill(self):
        if self._process:
            try:
                self._process.kill()
                self._process.wait(timeout=3)
            except Exception:
                pass
            self._process = None


class OpenListBinaryManager:
    """OpenList 二进制下载与版本管理"""

    def __init__(self):
        self._config = AppConfig()
        self._openlist_dir = self._config.DATA_DIR / "openlist"
        self._openlist_dir.mkdir(parents=True, exist_ok=True)
        self._version_cache: dict[str, Any] = {}

    def _ensure_openlist_dir(self) -> Path:
        self._openlist_dir.mkdir(parents=True, exist_ok=True)
        return self._openlist_dir

    def _download_archive(
        self,
        url: str,
        target_file: Path,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> None:
        start_time = time.time()
        with requests.get(
            url,
            stream=True,
            timeout=(10, 30),
            allow_redirects=True,
            proxies=self._get_proxies(),
            verify=False,
        ) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(target_file, "wb") as f:
                for chunk in resp.iter_content(chunk_size=OPENLIST_DOWNLOAD_CHUNK_SIZE):
                    if not chunk:
                        continue
                    if time.time() - start_time > OPENLIST_DOWNLOAD_TIMEOUT:
                        raise TimeoutError("下载超时，请检查网络连接或代理配置")
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total > 0:
                        progress_cb(downloaded, total)

    @staticmethod
    def _extract_binary_from_zip(archive_path: Path, target_binary: Path) -> None:
        candidates = {target_binary.name, "openlist.exe", "openlist"}
        with zipfile.ZipFile(archive_path, "r") as zf:
            for name in zf.namelist():
                basename = name.replace("\\", "/").split("/")[-1]
                if basename not in candidates:
                    continue
                with zf.open(name) as src, open(target_binary, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                return
        raise FileNotFoundError(f"压缩包中未找到 {target_binary.name}")

    @staticmethod
    def _extract_binary_from_tar(archive_path: Path, target_binary: Path) -> None:
        candidates = {target_binary.name, "openlist"}
        with tarfile.open(archive_path, "r:gz") as tf:
            for member in tf.getmembers():
                basename = member.name.replace("\\", "/").split("/")[-1]
                if basename not in candidates:
                    continue
                src = tf.extractfile(member)
                if src is None:
                    continue
                with src, open(target_binary, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                return
        raise FileNotFoundError(f"压缩包中未找到 {target_binary.name}")

    def _extract_binary(self, archive_path: Path, ext: str, target_binary: Path) -> None:
        if ext == "zip":
            self._extract_binary_from_zip(archive_path, target_binary)
            return
        self._extract_binary_from_tar(archive_path, target_binary)

    @staticmethod
    def _install_binary(extracted_binary: Path, target_binary: Path) -> None:
        target_binary.parent.mkdir(parents=True, exist_ok=True)
        temp_target = target_binary.with_suffix(target_binary.suffix + ".new")
        backup_target = target_binary.with_suffix(target_binary.suffix + ".bak")

        temp_target.unlink(missing_ok=True)
        backup_target.unlink(missing_ok=True)

        shutil.copy2(extracted_binary, temp_target)
        if platform.system() != "Windows":
            temp_target.chmod(temp_target.stat().st_mode | 0o755)

        try:
            if target_binary.exists():
                os.replace(target_binary, backup_target)
            os.replace(temp_target, target_binary)
            backup_target.unlink(missing_ok=True)
        except Exception:
            temp_target.unlink(missing_ok=True)
            if backup_target.exists() and not target_binary.exists():
                os.replace(backup_target, target_binary)
            raise

    def _get_proxies(self) -> dict[str, str] | None:
        if self._config.USE_PROXY and self._config.PROXY_URL:
            proxy = self._config.PROXY_URL.strip()
            return {"http": proxy, "https": proxy}
        return None

    def get_platform_info(self) -> tuple[str, str]:
        system = platform.system().lower()
        machine = platform.machine().lower()
        os_map = {"windows": "windows", "linux": "linux", "darwin": "darwin"}
        arch_map = {"amd64": "amd64", "x86_64": "amd64", "x64": "amd64", "arm64": "arm64", "aarch64": "arm64"}
        os_name = os_map.get(system, system)
        arch = arch_map.get(machine, "amd64")
        return os_name, arch

    def get_latest_version(self) -> str:
        cache_key = "latest_version"
        cached = self._version_cache.get(cache_key)
        if cached and time.time() - cached["time"] < 3600:
            return cached["version"]

        try:
            resp = requests.get(
                f"https://api.github.com/repos/{OPENLIST_GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=15,
                proxies=self._get_proxies(),
                verify=False,
            )
            resp.raise_for_status()
            version = resp.json()["tag_name"]
            self._version_cache[cache_key] = {"version": version, "time": time.time()}
            return version
        except Exception as exc:
            logger.warning("获取 OpenList 最新版本失败: %s，使用兜底版本", exc)
            return OPENLIST_FALLBACK_VERSION

    def get_download_url(self, version: str = "") -> str:
        if not version:
            version = self.get_latest_version()
        os_name, arch = self.get_platform_info()
        ext = "zip" if os_name == "windows" else "tar.gz"
        # OpenList 使用 openlist-{os}-{arch}.{ext} 格式
        filename = f"openlist-{os_name}-{arch}.{ext}"
        return f"https://github.com/{OPENLIST_GITHUB_REPO}/releases/download/{version}/{filename}"

    def _get_download_urls(self, version: str = "") -> list[str]:
        """返回所有可用的下载 URL（主站 + 镜像源）"""
        if not version:
            version = self.get_latest_version()
        os_name, arch = self.get_platform_info()
        ext = "zip" if os_name == "windows" else "tar.gz"
        filename = f"openlist-{os_name}-{arch}.{ext}"
        github_url = f"https://github.com/{OPENLIST_GITHUB_REPO}/releases/download/{version}/{filename}"

        urls = []
        # 如果配置了代理，优先使用 GitHub 直连
        if self._get_proxies():
            urls.append(github_url)

        # 添加镜像源
        for mirror in OPENLIST_MIRRORS:
            mirror = mirror.rstrip("/")
            urls.append(f"{mirror}/{github_url}")

        # 如果没有代理，GitHub 直连作为最后备选
        if not self._get_proxies():
            urls.append(github_url)

        return urls

    def download_binary(self, version: str = "", progress_cb: Callable[[int, int], None] | None = None) -> Path:
        if not version:
            version = self.get_latest_version()

        urls = self._get_download_urls(version)
        ext = "zip" if urls[0].endswith(".zip") else "tar.gz"
        binary_name = "openlist.exe" if platform.system() == "Windows" else "openlist"
        target = self._ensure_openlist_dir() / binary_name

        last_error = None
        with tempfile.TemporaryDirectory(prefix="openlist-download-", dir=str(self._ensure_openlist_dir())) as temp_dir:
            archive_path = Path(temp_dir) / f"openlist_download.{ext}"
            extracted_binary = Path(temp_dir) / binary_name

            for url in urls:
                try:
                    logger.info("尝试下载 OpenList: %s", url)
                    self._download_archive(url, archive_path, progress_cb)
                    self._extract_binary(archive_path, ext, extracted_binary)
                    self._install_binary(extracted_binary, target)
                    logger.info("OpenList 下载并安装成功: %s", url)
                    break
                except Exception as exc:
                    last_error = exc
                    logger.warning("下载失败 %s: %s", url, exc)
                    archive_path.unlink(missing_ok=True)
                    extracted_binary.unlink(missing_ok=True)
                    continue
            else:
                raise RuntimeError(f"所有下载源均失败，最后错误: {last_error}")

        self._config.OPENLIST_BINARY_VERSION = version
        self._config.save_config()

        logger.info("OpenList %s 下载完成: %s", version, target)
        return target

    def is_update_available(self) -> tuple[bool, str, str]:
        current = self._config.OPENLIST_BINARY_VERSION or ""
        latest = self.get_latest_version()
        if not current:
            return (True, "", latest)
        current_clean = current.lstrip("v")
        latest_clean = latest.lstrip("v")
        return (current_clean != latest_clean, current, latest)


openlist_manager = OpenListManager()
openlist_binary_manager = OpenListBinaryManager()
