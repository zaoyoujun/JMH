import os
from urllib.parse import quote, unquote, urlparse
from xml.etree import ElementTree as ET

import requests
from requests.auth import HTTPBasicAuth

from config.app_config import AppConfig
from utils.logger import get_logger

logger = get_logger()


class WebDAVClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self.provider = self.config.normalize_remote_provider(self.config.REMOTE_PROVIDER)
        self.host = str(self.config.WEBDAV_HOST or "").strip().rstrip("/")
        self.base_path = urlparse(self.host).path.rstrip("/")
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({"User-Agent": "JimiHua/1.0"})
        if self.config.REMOTE_COOKIE:
            self.session.headers["Cookie"] = self.config.REMOTE_COOKIE
        if self.config.USE_PROXY and self.config.PROXY_URL:
            self.session.proxies.update({
                "http": self.config.PROXY_URL,
                "https": self.config.PROXY_URL,
            })
        self.auth = None
        if self.config.WEBDAV_USER and self.config.WEBDAV_PASS:
            self.auth = HTTPBasicAuth(self.config.WEBDAV_USER, self.config.WEBDAV_PASS)

    def _normalize_path(self, path: str = "/") -> str:
        value = str(path or "/").strip() or "/"
        if not value.startswith("/"):
            value = "/" + value
        return value

    def _encode_path(self, path: str) -> str:
        normalized = self._normalize_path(path)
        segments = [quote(segment) for segment in normalized.lstrip("/").split("/") if segment]
        return "/" + "/".join(segments) if segments else "/"

    def _build_url(self, path: str = "/") -> str:
        if not self.host:
            raise ValueError("Remote host is empty")
        encoded_path = self._encode_path(path)
        return f"{self.host}{encoded_path if encoded_path != '/' else ''}"

    def _request(self, method: str, path: str = "/", *, headers: dict | None = None, data: str | None = None):
        response = self.session.request(
            method.upper(),
            self._build_url(path),
            headers=headers or {},
            data=data,
            timeout=20,
            auth=self.auth,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response

    def _propfind(self, path: str = "/", depth: int = 1):
        body = """<?xml version="1.0" encoding="utf-8" ?><d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype /></d:prop></d:propfind>"""
        return self._request(
            "PROPFIND",
            path,
            headers={
                "Depth": str(depth),
                "Content-Type": "application/xml; charset=utf-8",
            },
            data=body,
        )

    def _href_to_path(self, href: str) -> str:
        parsed = urlparse(str(href or ""))
        href_path = unquote(parsed.path or "/")
        if self.base_path and href_path.startswith(self.base_path):
            href_path = href_path[len(self.base_path):] or "/"
        if not href_path.startswith("/"):
            href_path = "/" + href_path
        return href_path.rstrip("/") or "/"

    def _parse_entries(self, response_text: str, current_path: str) -> list[dict]:
        entries = []
        normalized_current = self._normalize_path(current_path).rstrip("/") or "/"
        try:
            root = ET.fromstring(response_text)
        except ET.ParseError as exc:
            logger.error("WebDAV XML parse failed: %s", exc)
            return entries

        ns = {"d": "DAV:"}
        for item in root.findall("d:response", ns):
            href_text = item.findtext("d:href", default="", namespaces=ns)
            entry_path = self._href_to_path(href_text)
            if (entry_path.rstrip("/") or "/") == normalized_current:
                continue
            prop = item.find("d:propstat/d:prop", ns)
            resource_type = prop.find("d:resourcetype", ns) if prop is not None else None
            is_dir = resource_type is not None and resource_type.find("d:collection", ns) is not None
            # 回退判断：href 以 / 结尾也视为目录（兼容 OpenList 等不返回 collection 标记的 WebDAV 服务）
            if not is_dir and href_text.rstrip().endswith("/"):
                is_dir = True
            name = os.path.basename(entry_path.rstrip("/")) or entry_path.strip("/") or "/"
            entries.append({
                "name": name,
                "full_path": entry_path.rstrip("/") if is_dir else entry_path,
                "is_dir": is_dir,
            })
        return entries

    def list_directories(self, path="/"):
        try:
            response = self._propfind(path, depth=1)
            normalized = self._normalize_path(path).rstrip("/")
            directories = []
            for item in self._parse_entries(response.text, path):
                if not item["is_dir"]:
                    continue
                # 过滤：仅保留直接子目录（部分 WebDAV 服务忽略 Depth 头返回全部嵌套目录）
                item_path = item["full_path"].rstrip("/")
                # 直接子目录：去掉父级前缀后不再包含 /
                if normalized and not item_path.startswith(normalized + "/"):
                    continue
                relative = item_path[len(normalized):] if normalized else item_path
                if relative.count("/") != 1:
                    continue
                directories.append({"name": item["name"], "full_path": item["full_path"]})
            directories.sort(key=lambda d: d["name"].lower())
            logger.info("Listed %s directories under %s", len(directories), path)
            return directories
        except Exception as exc:  # noqa: BLE001
            logger.error("List directories failed for %s: %s", path, exc)
            return []

    def list_directories_recursive(self, path="/", max_depth=5):
        """BFS 递归列出所有嵌套目录，返回扁平列表。"""
        all_dirs = []
        try:
            root = self._normalize_path(path)
            queue = [(root, 0)]
            visited = set()
            while queue:
                current, depth = queue.pop(0)
                if current in visited or depth > max_depth:
                    continue
                visited.add(current)
                try:
                    response = self._propfind(current, depth=1)
                    for item in self._parse_entries(response.text, current):
                        if not item["is_dir"]:
                            continue
                        fp = item["full_path"].rstrip("/") or "/"
                        if fp in visited:
                            continue
                        all_dirs.append({"name": item["name"], "full_path": item["full_path"]})
                        if depth < max_depth:
                            queue.append((fp, depth + 1))
                except Exception as exc:  # noqa: BLE001
                    logger.error("Recursive scan failed for %s: %s", current, exc)
            all_dirs.sort(key=lambda d: d["full_path"].lower())
            logger.info("Recursive scan under %s: found %s directories", path, len(all_dirs))
            return all_dirs
        except Exception as exc:  # noqa: BLE001
            logger.error("Recursive directory scan failed for %s: %s", path, exc)
            return []

    def list_directory(self, path="/", max_depth=2):
        videos = []
        try:
            root_path = self._normalize_path(path)
            scan_queue = [(root_path, 0)]
            processed_dirs = set()

            while scan_queue:
                current_path, current_depth = scan_queue.pop(0)
                if current_path in processed_dirs:
                    continue
                processed_dirs.add(current_path)

                try:
                    response = self._propfind(current_path, depth=1)
                    entries = self._parse_entries(response.text, current_path)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Scan directory failed for %s: %s", current_path, exc)
                    continue

                for item in entries:
                    full_path = item["full_path"]
                    if item["is_dir"]:
                        if current_depth < max_depth:
                            scan_queue.append((full_path, current_depth + 1))
                        continue

                    ext = os.path.splitext(full_path)[1].lower()
                    if ext in self.config.VIDEO_FORMATS:
                        videos.append(full_path)

            logger.info("Remote scan complete, found %s video files", len(videos))
            return videos
        except Exception as exc:  # noqa: BLE001
            logger.error("Remote scan failed: %s", exc)
            return videos

    def get_file_url(self, path):
        play_url = self._build_url(path)
        if self.config.REMOTE_COOKIE:
            return play_url

        if "://" in play_url and self.config.WEBDAV_USER and self.config.WEBDAV_PASS:
            protocol, rest = play_url.split("://", 1)
            encoded_user = quote(self.config.WEBDAV_USER)
            encoded_pass = quote(self.config.WEBDAV_PASS)
            return f"{protocol}://{encoded_user}:{encoded_pass}@{rest}"
        return play_url

    def test_connection(self):
        try:
            response = self._propfind("/", depth=0)
            status = response.status_code
            auth_mode = "cookie" if self.config.REMOTE_COOKIE else "basic"
            return True, f"Connected via {self.provider} ({auth_mode})"
        except Exception as exc:  # noqa: BLE001
            logger.error("Connection test failed: %s", exc)
            return False, f"Connection failed: {exc}"
