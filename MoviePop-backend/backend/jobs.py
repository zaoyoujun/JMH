from __future__ import annotations

import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


JobFunc = Callable[[Callable[[int, int, str], None]], Any]


@dataclass
class JobRecord:
    job_id: str
    name: str
    status: str = "queued"
    current: int = 0
    total: int = 0
    message: str = ""
    error: str = ""
    result: Any = None
    thread: threading.Thread | None = field(default=None, repr=False)

    def snapshot(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "status": self.status,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "error": self.error,
            "result": self.result,
        }


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def start(self, name: str, target: JobFunc) -> JobRecord:
        job = JobRecord(job_id=uuid.uuid4().hex, name=name)
        with self._lock:
            self._jobs[job.job_id] = job

        def update(current: int, total: int, message: str) -> None:
            with self._lock:
                job.current = current
                job.total = total
                job.message = message
                if job.status == "queued":
                    job.status = "running"

        def runner() -> None:
            try:
                with self._lock:
                    job.status = "running"
                job.result = target(update)
                with self._lock:
                    job.status = "completed"
                    if not job.message:
                        job.message = "任务完成"
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    job.status = "failed"
                    job.error = f"{exc}\n{traceback.format_exc()}"
                    if not job.message:
                        job.message = "任务失败"

        thread = threading.Thread(target=runner, name=f"job-{job.job_id}", daemon=True)
        job.thread = thread
        thread.start()
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)


job_manager = JobManager()
