import atexit
import logging
import queue
import threading
import time
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

# Delayed jobs (the 2-minute reply email, retries) wait on timers. They are
# tracked so a shutdown can send them right away instead of dropping them.
_pending: "dict[threading.Timer, EmailJob]" = {}
_pending_lock = threading.Lock()
_shutting_down = False
# How long a stopping server keeps sending before it gives up on the rest.
DEFAULT_SHUTDOWN_SECONDS = 30


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
        if not _started_lanes:
            atexit.register(drain_on_shutdown)
        _started_lanes.add(lane)


def _put_later(job: "EmailJob", delay_seconds: float) -> None:
    with _pending_lock:
        if _shutting_down:
            # Waiting would outlive the process; send it now.
            _QUEUES[job.lane].put(job)
            return

        def fire():
            with _pending_lock:
                if _pending.pop(timer, None) is None:
                    return  # already handed over by drain_on_shutdown
            _QUEUES[job.lane].put(job)

        # Daemon: the timer itself must not hold the process open. Shutdown is
        # handled by drain_on_shutdown, which has a time limit.
        timer = threading.Timer(delay_seconds, fire)
        timer.daemon = True
        _pending[timer] = job
        timer.start()


def drain_on_shutdown(timeout: float | None = None) -> int:
    """Send everything queued or delayed before the process exits.

    Runs at interpreter exit (a normal server stop). Delayed jobs go out
    immediately; the workers keep sending until the queues are empty or the
    time limit passes. Returns how many jobs were left unsent.
    """
    global _shutting_down
    if timeout is None:
        timeout = getattr(settings, "EMAIL_QUEUE_SHUTDOWN_SECONDS", DEFAULT_SHUTDOWN_SECONDS)
    with _pending_lock:
        _shutting_down = True
        waiting = list(_pending.items())
        _pending.clear()
    for timer, job in waiting:
        timer.cancel()
        _QUEUES[job.lane].put(job)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and any(q.unfinished_tasks for q in _QUEUES.values()):
        time.sleep(0.1)
    left = sum(q.unfinished_tasks for q in _QUEUES.values())
    if left:
        logger.error("Server stopping with %s email/push job(s) unsent after %ss.", left, timeout)
    elif waiting:
        logger.info("Sent %s delayed email/push job(s) before stopping.", len(waiting))
    return left


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
