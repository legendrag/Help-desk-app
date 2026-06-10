import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

_QUEUE: "queue.Queue[EmailJob]" = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()


@dataclass
class EmailJob:
    func: Callable[..., Any]
    args: tuple
    kwargs: dict
    attempts: int = 0
    max_attempts: int = 3
    retry_delay: int = 2


def ensure_worker_started() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        worker = threading.Thread(target=_worker_loop, name="email-worker", daemon=True)
        worker.start()
        _worker_started = True


def enqueue_email(func: Callable[..., Any], *args, max_attempts: int = 3, retry_delay: int = 2, **kwargs) -> None:
    ensure_worker_started()
    _QUEUE.put(EmailJob(func=func, args=args, kwargs=kwargs, max_attempts=max_attempts, retry_delay=retry_delay))


def _worker_loop() -> None:
    while True:
        job = _QUEUE.get()
        try:
            try:
                result = job.func(*job.args, **job.kwargs)
                if result is False:
                    logger.debug("Email job returned False (likely no recipients or disabled).")
            except Exception as exc:  # noqa: BLE001
                job.attempts += 1
                logger.exception(
                    "Email job failed (attempt %s/%s): %s",
                    job.attempts,
                    job.max_attempts,
                    exc,
                )
                if job.attempts < job.max_attempts:
                    time.sleep(job.retry_delay)
                    _QUEUE.put(job)
        finally:
            _QUEUE.task_done()
