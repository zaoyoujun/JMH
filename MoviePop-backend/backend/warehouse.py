from __future__ import annotations

import datetime as dt
from typing import Any

from config.app_config import AppConfig
from utils.logger import get_logger

logger = get_logger()

try:
    import clickhouse_connect
except Exception:  # noqa: BLE001
    clickhouse_connect = None


class ClickHouseWarehouse:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.config.load_config()

    def get_status(self) -> dict[str, Any]:
        if not self.config.CLICKHOUSE_ENABLED:
            return {
                "enabled": False,
                "connected": False,
                "database": self.config.CLICKHOUSE_DATABASE,
                "reason": "当前未连接 ClickHouse，正在使用应用内数据",
            }
        if clickhouse_connect is None:
            return {
                "enabled": True,
                "connected": False,
                "database": self.config.CLICKHOUSE_DATABASE,
                "reason": "缺少 clickhouse-connect 依赖",
            }
        try:
            client = self._get_client()
            client.command("SELECT 1")
            return {
                "enabled": True,
                "connected": True,
                "database": self.config.CLICKHOUSE_DATABASE,
                "reason": "",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "enabled": True,
                "connected": False,
                "database": self.config.CLICKHOUSE_DATABASE,
                "reason": str(exc),
            }

    def sync_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        status = self.get_status()
        if not status.get("enabled"):
            return status
        if not status.get("connected"):
            return status

        client = self._get_client()
        self._ensure_schema(client)
        self._truncate_tables(client)
        self._insert_rows(client, "dim_time", snapshot.get("dim_time_rows", []))
        self._insert_rows(client, "dim_media", snapshot.get("dim_media_rows", []))
        self._insert_rows(client, "bridge_media_tag", snapshot.get("bridge_media_tag_rows", []))
        self._insert_rows(client, "fact_scan_snapshot", snapshot.get("fact_scan_rows", []))
        self._insert_rows(client, "fact_user_behavior", snapshot.get("fact_behavior_rows", []))
        return {
            "enabled": True,
            "connected": True,
            "database": self.config.CLICKHOUSE_DATABASE,
            "reason": "",
            "rows": {
                "dim_time": len(snapshot.get("dim_time_rows", [])),
                "dim_media": len(snapshot.get("dim_media_rows", [])),
                "bridge_media_tag": len(snapshot.get("bridge_media_tag_rows", [])),
                "fact_scan_snapshot": len(snapshot.get("fact_scan_rows", [])),
                "fact_user_behavior": len(snapshot.get("fact_behavior_rows", [])),
            },
        }

    def _get_client(self):
        if clickhouse_connect is None:
            raise RuntimeError("clickhouse-connect not installed")
        return clickhouse_connect.get_client(
            host=self.config.CLICKHOUSE_HOST,
            port=self.config.CLICKHOUSE_PORT,
            username=self.config.CLICKHOUSE_USER,
            password=self.config.CLICKHOUSE_PASSWORD,
            database=self.config.CLICKHOUSE_DATABASE,
        )

    def _ensure_schema(self, client) -> None:
        client.command(f"CREATE DATABASE IF NOT EXISTS {self.config.CLICKHOUSE_DATABASE}")
        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS dim_time (
                date_key Date,
                year UInt16,
                month UInt8,
                day UInt8,
                week UInt8,
                quarter UInt8,
                weekday UInt8
            ) ENGINE = ReplacingMergeTree
            ORDER BY date_key
            """,
            """
            CREATE TABLE IF NOT EXISTS dim_media (
                media_path String,
                title String,
                media_type String,
                year UInt16,
                year_bucket String,
                source String,
                provider String,
                is_series UInt8,
                favorite UInt8,
                has_intro UInt8,
                has_cover UInt8,
                updated_at DateTime
            ) ENGINE = ReplacingMergeTree(updated_at)
            ORDER BY media_path
            """,
            """
            CREATE TABLE IF NOT EXISTS bridge_media_tag (
                media_path String,
                tag String,
                tag_source String,
                updated_at DateTime
            ) ENGINE = ReplacingMergeTree(updated_at)
            ORDER BY (media_path, tag, tag_source)
            """,
            """
            CREATE TABLE IF NOT EXISTS fact_scan_snapshot (
                snapshot_date Date,
                media_path String,
                source String,
                provider String,
                tag_count UInt16,
                playback_percent Float32,
                rating Float32,
                updated_at DateTime
            ) ENGINE = MergeTree
            ORDER BY (snapshot_date, media_path)
            """,
            """
            CREATE TABLE IF NOT EXISTS fact_user_behavior (
                event_date Date,
                media_path String,
                favorite UInt8,
                recent UInt8,
                playback_percent Float32,
                progress_seconds Float64,
                duration_seconds Float64,
                rating Float32,
                watch_seconds Float64,
                updated_at DateTime
            ) ENGINE = MergeTree
            ORDER BY (event_date, media_path)
            """,
        ]
        for statement in ddl_statements:
            client.command(statement)

    def _truncate_tables(self, client) -> None:
        for table_name in (
            "dim_time",
            "dim_media",
            "bridge_media_tag",
            "fact_scan_snapshot",
            "fact_user_behavior",
        ):
            client.command(f"TRUNCATE TABLE IF EXISTS {table_name}")

    def _insert_rows(self, client, table_name: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        column_names = list(rows[0].keys())
        values = [list(row.get(column) for column in column_names) for row in rows]
        client.insert(table_name, values, column_names=column_names)


def build_time_dimension_rows(dates: set[dt.date]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in sorted(dates):
        iso_week = value.isocalendar().week
        rows.append(
            {
                "date_key": value,
                "year": value.year,
                "month": value.month,
                "day": value.day,
                "week": iso_week,
                "quarter": ((value.month - 1) // 3) + 1,
                "weekday": value.weekday() + 1,
            }
        )
    return rows
