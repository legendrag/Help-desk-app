import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable

from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger(__name__)

# Email and push run on separate lanes so a slow mail server never holds up
# push and a slow push service never holds up email. Push gets a few workers
# so one hung endpoint (each send has a timeout) doesn't stall the rest.
_LANE_WORKERS = {"email": 1, "push": 3}
_QUEUES: "dict[str, queue.Queue[EmailJob]]" = {lane: queue.Queue() for lane in _LANE_WORKERS}
_started_lanes: set[str] = set()
_worker_lock = threading.Lock()


@dataclass
class EmailJob:
    func: Callable[..., Any]
    args: tuple
    kwargs: dict
    attempts: int = 0
    max_attempts: int = 3
    retry_delay: int = 2
    lane: str = "email"


def ensure_worker_started(lane: str = "email") -> None:
    with _worker_lock:
        if lane in _started_lanes:
            return
        for index in range(_LANE_WORKERS[lane]):
            worker = threading.Thread(
                target=_worker_loop, args=(lane,), name=f"{lane}-worker-{index}", daemon=True
            )
            worker.start()
        _started_lanes.add(lane)


def _put_later(job: "EmailJob", delay_seconds: float) -> None:
    # Daemon timer: a pending delay must not keep the process alive on shutdown.
    timer = threading.Timer(delay_seconds, _QUEUES[job.lane].put, args=(job,))
    timer.daemon = True
    timer.start()


def enqueue_email(
    func: Callable[..., Any],
    *args,
    max_attempts: int = 3,
    retry_delay: int = 2,
    delay_seconds: int = 0,
    lane: str = "email",
    **kwargs,
) -> None:
    job = EmailJob(
        func=func, args=args, kwargs=kwargs, max_attempts=max_attempts, retry_delay=retry_delay, lane=lane
    )
    if getattr(settings, "EMAIL_QUEUE_SYNC", False):
        # Tests: a worker thread would open its own connection to the shared
        # test database and race the test's transaction ("table is locked").
        _run_inline(job)
        return
    ensure_worker_started(lane)
    if delay_seconds > 0:
        _put_later(job, delay_seconds)
    else:
        _QUEUES[lane].put(job)


def _run_inline(job: EmailJob) -> None:
    try:
        job.func(*job.args, **job.kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Email job failed (inline): %s", exc)


def _worker_loop(lane: str) -> None:
    jobs = _QUEUES[lane]
    while True:
        job = jobs.get()
        # Background threads skip request middleware, so stale MySQL sockets
        # (CONN_MAX_AGE / server wait_timeout) must be cleared explicitly.
        close_old_connections()
        try:
            try:
                result = job.func(*job.args, **job.kwargs)
                if result is False:
                    logger.debug("Email job returned False (likely no recipients or disabled).")
            except Exception as exc:  # noqa: BLE001
                job.attempts += 1
                logger.exception(
                    "%s job failed (attempt %s/%s): %s",
                    lane,
                    job.attempts,
                    job.max_attempts,
                    exc,
                )
                if job.attempts < job.max_attempts:
                    # Wait off-thread so the lane keeps working meanwhile.
                    _put_later(job, job.retry_delay * job.attempts)
        finally:
            close_old_connections()
            jobs.task_done()
