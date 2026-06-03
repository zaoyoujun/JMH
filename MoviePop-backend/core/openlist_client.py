from __future__ import annotations

import json
import time
from typing import Any

import requests

from utils.logger import get_logger

logger = get_logger()


SUPPORTED_DRIVERS = [
    {
        "driver": "Quark",
        "label": "夸克网盘",
        "fields": [
            {"key": "cookie", "label": "Cookie", "type": "textarea", "required": True, "placeholder": "从浏览器 F12 → Network → Request Headers 复制，不含 \"Cookie:\" 前缀", "help": "登录 drive.quark.cn 后，按 F12 打开开发者工具，在 Network 标签页找到任意请求，复制 Request Headers 中的 Cookie 值"},
            {"key": "root_folder_id", "label": "根目录 ID", "placeholder": "默认为 0 表示根目录"},
        ],
    },
    {
        "driver": "AliyundriveOpen",
        "label": "阿里云盘 (Open)",
        "fields": [
            {"key": "refresh_token", "label": "Refresh Token", "required": True, "help": "通过阿里云盘 OAuth 授权获取"},
            {"key": "root_folder_id", "label": "根目录文件 ID", "placeholder": "root"},
            {"key": "drive_type", "label": "云盘类型", "placeholder": "default", "type": "hidden"},
        ],
    },
    {
        "driver": "115 Cloud",
        "label": "115网盘",
        "fields": [
            {"key": "cookie", "label": "Cookie", "type": "textarea", "required": True, "placeholder": "从浏览器 F12 复制，不含 \"Cookie:\" 前缀", "help": "登录 115.com 后，从浏览器开发者工具复制 Cookie"},
            {"key": "root_folder_id", "label": "根目录 ID", "placeholder": "默认为 0 表示根目录"},
        ],
    },
    {
        "driver": "BaiduNetdisk",
        "label": "百度网盘",
        "fields": [
            {"key": "refresh_token", "label": "Refresh Token", "required": True},
            {"key": "root_folder_path", "label": "根目录路径", "placeholder": "/"},
        ],
    },
    {
        "driver": "AList V3",
        "label": "AList V3 挂载",
        "fields": [
            {"key": "base_url", "label": "AList 地址", "required": True, "placeholder": "http://example.com:5244"},
            {"key": "token", "label": "Token", "required": True},
            {"key": "root_folder_path", "label": "根目录路径", "placeholder": "/"},
        ],
    },
    {
        "driver": "WebDav",
        "label": "WebDAV",
        "fields": [
            {"key": "address", "label": "地址", "required": True, "placeholder": "http://example.com/dav"},
            {"key": "username", "label": "用户名"},
            {"key": "password", "label": "密码", "type": "password"},
            {"key": "root_folder_path", "label": "根目录路径", "placeholder": "/"},
        ],
    },
]


class OpenListAdminClient:
    """OpenList 管理后台 API 客户端"""

    def __init__(self, base_url: str = "http://127.0.0.1:5244"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._token: str = ""
        self._token_expires: float = 0

    def login(self, password: str) -> str:
        resp = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"username": "admin", "password": password},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise RuntimeError(f"OpenList 登录失败: {data.get('message', '未知错误')}")
        self._token = data["data"]["token"]
        self._token_expires = time.time() + 3600
        return self._token

    def _ensure_token(self, password: str) -> None:
        if not self._token or time.time() > self._token_expires - 60:
            self.login(password)

    def _auth_headers(self, password: str) -> dict[str, str]:
        self._ensure_token(password)
        return {"Authorization": self._token}

    def _check_response(self, resp: requests.Response) -> dict[str, Any]:
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise RuntimeError(f"OpenList API 错误: {data.get('message', '未知错误')}")
        return data

    def list_storages(self, password: str) -> list[dict[str, Any]]:
        resp = self.session.get(
            f"{self.base_url}/api/admin/storage/list",
            headers=self._auth_headers(password),
            timeout=10,
        )
        data = self._check_response(resp)
        items = data.get("data", {}).get("content", [])
        result = []
        for item in items or []:
            addition = item.get("addition", "{}")
            if isinstance(addition, str):
                try:
                    addition = json.loads(addition)
                except (json.JSONDecodeError, TypeError):
                    addition = {}
            result.append({
                "id": item.get("id"),
                "mount_path": item.get("mount_path", ""),
                "order": item.get("order", 0),
                "driver": item.get("driver", ""),
                "cache_expiration": item.get("cache_expiration", 30),
                "status": item.get("status", "work"),
                "addition": addition,
                "modified": item.get("modified", ""),
            })
        return result

    def add_storage(self, password: str, storage_config: dict[str, Any]) -> dict[str, Any]:
        # 检查是否已存在相同的挂载路径
        mount_path = storage_config.get("mount_path", "")
        existing_storages = self.list_storages(password)
        for storage in existing_storages:
            if storage.get("mount_path") == mount_path:
                # 已存在，更新而不是创建
                storage_config["id"] = storage.get("id")
                return self.update_storage(password, storage_config)

        addition = storage_config.get("addition", {})
        if isinstance(addition, dict):
            addition = json.dumps(addition, ensure_ascii=False)
        payload = {
            "mount_path": mount_path,
            "order": storage_config.get("order", 0),
            "driver": storage_config.get("driver", ""),
            "cache_expiration": storage_config.get("cache_expiration", 30),
            "status": "work",
            "addition": addition,
        }
        resp = self.session.post(
            f"{self.base_url}/api/admin/storage/create",
            headers=self._auth_headers(password),
            json=payload,
            timeout=15,
        )
        return self._check_response(resp)

    def update_storage(self, password: str, storage_config: dict[str, Any]) -> dict[str, Any]:
        addition = storage_config.get("addition", {})
        if isinstance(addition, dict):
            addition = json.dumps(addition, ensure_ascii=False)
        payload = {
            "id": storage_config.get("id"),
            "mount_path": storage_config.get("mount_path", ""),
            "order": storage_config.get("order", 0),
            "driver": storage_config.get("driver", ""),
            "cache_expiration": storage_config.get("cache_expiration", 30),
            "status": storage_config.get("status", "work"),
            "addition": addition,
        }
        resp = self.session.post(
            f"{self.base_url}/api/admin/storage/update",
            headers=self._auth_headers(password),
            json=payload,
            timeout=15,
        )
        return self._check_response(resp)

    def delete_storage(self, password: str, storage_id: int) -> dict[str, Any]:
        resp = self.session.post(
            f"{self.base_url}/api/admin/storage/delete",
            headers=self._auth_headers(password),
            json={"id": storage_id},
            timeout=10,
        )
        return self._check_response(resp)

    def enable_storage(self, password: str, storage_id: int) -> dict[str, Any]:
        resp = self.session.post(
            f"{self.base_url}/api/admin/storage/enable",
            headers=self._auth_headers(password),
            json={"id": storage_id},
            timeout=10,
        )
        return self._check_response(resp)

    def disable_storage(self, password: str, storage_id: int) -> dict[str, Any]:
        resp = self.session.post(
            f"{self.base_url}/api/admin/storage/disable",
            headers=self._auth_headers(password),
            json={"id": storage_id},
            timeout=10,
        )
        return self._check_response(resp)

    def get_me(self, password: str) -> dict[str, Any]:
        resp = self.session.get(
            f"{self.base_url}/api/me",
            headers=self._auth_headers(password),
            timeout=10,
        )
        return self._check_response(resp)

    @staticmethod
    def get_supported_drivers() -> list[dict[str, Any]]:
        return SUPPORTED_DRIVERS

    def list_files(
        self,
        password: str,
        path: str = "/",
        page: int = 1,
        per_page: int = 0,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """列目录，返回当前层级的子项（OpenList /api/fs/list）"""
        import urllib.parse
        encoded_path = urllib.parse.quote(path, safe='/')
        resp = self.session.post(
            f"{self.base_url}/api/fs/list",
            headers=self._auth_headers(password),
            json={"path": encoded_path, "password": "", "page": page, "per_page": per_page, "refresh": bool(refresh)},
            timeout=15,
        )
        return self._check_response(resp)
