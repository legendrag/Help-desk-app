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

    # Outbox email is in the database and goes out after the restart; just
    # stop taking new rows and let the ones being sent finish.
    _outbox_stop.set()
    _outbox_wake.set()

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and (
        any(q.unfinished_tasks for q in _QUEUES.values()) or _outbox_busy()
    ):
        time.sleep(0.1)
    left = sum(q.unfinished_tasks for q in _QUEUES.values()) + _outbox_busy_count
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
    if lane == "email" and _store_in_outbox(job, delay_seconds):
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


# ── Email outbox ────────────────────────────────────────────────────────────
# Email jobs are saved in the EmailOutbox table and sent from there, so a
# crash or forced kill can't lose them: whatever is still in the table is sent
# once the server is back. Rows are claimed with a conditional update, so two
# server processes never send the same row.

# How often the workers look for due rows (delayed replies, retries) when
# nothing has woken them.
OUTBOX_POLL_SECONDS = 5
# A row still "sending" this long after it was claimed belongs to a process
# that died mid-send; it is picked up again. Recipients already recorded as
# sent are skipped, so at most the one being sent at the crash gets it twice.
OUTBOX_STUCK_SECONDS = 15 * 60
OUTBOX_BATCH = 20
# Several workers, so one slow mail server conversation doesn't hold up every
# email behind it. Rows are claimed one at a time, so they never double up.
OUTBOX_WORKERS = 3
# Rows that failed every attempt are kept this long for an admin, then removed.
OUTBOX_FAILED_KEEP_DAYS = 30
_PRUNE_EVERY_SECONDS = 3600

_outbox_wake = threading.Event()
_outbox_stop = threading.Event()
_outbox_busy_lock = threading.Lock()
_outbox_busy_count = 0
_outbox_started = False
_last_prune = 0.0
# The row this worker thread is sending, for per-recipient bookkeeping.
_current = threading.local()


def _outbox_busy() -> bool:
    return _outbox_busy_count > 0


def _set_outbox_busy(delta: int) -> None:
    global _outbox_busy_count
    with _outbox_busy_lock:
        _outbox_busy_count += delta


def _delivery_key(subject: str, recipient: str) -> str:
    import hashlib

    return hashlib.sha1(f"{subject}\x00{recipient}".encode()).hexdigest()[:16]


def already_delivered(subject: str, recipient: str) -> bool:
    """True if this outbox row sent this message to this recipient before a
    crash or retry. Always False outside an outbox row."""
    row = getattr(_current, "row", None)
    return row is not None and _delivery_key(subject, recipient) in row.sent_keys


def mark_delivered(subject: str, recipient: str) -> None:
    """Record a sent message on the current outbox row, so a crash right after
    doesn't send it again."""
    row = getattr(_current, "row", None)
    if row is None:
        return
    from notifications.models import EmailOutbox

    from django.utils import timezone

    row.sent_keys.append(_delivery_key(subject, recipient))
    try:
        # updated_at doubles as a heartbeat: a long send (many recipients, a
        # slow server) is not mistaken for a dead process and sent again.
        EmailOutbox.objects.filter(pk=row.pk).update(sent_keys=row.sent_keys, updated_at=timezone.now())
    except Exception:  # noqa: BLE001 - worst case it goes out twice after a crash
        logger.warning("Could not record a sent email on outbox row %s", row.pk, exc_info=True)


def _job_path(func) -> str:
    """Dotted path of a module-level function, checked to resolve back to it."""
    from django.utils.module_loading import import_string

    path = f"{func.__module__}.{func.__qualname__}"
    if "<" in path or import_string(path) is not func:
        raise ValueError(f"{path} is not a module-level function")
    return path


def _store_in_outbox(job: EmailJob, delay_seconds: float) -> bool:
    """Save the job; False (use the in-memory queue) if it can't be saved."""
    from datetime import timedelta

    from django.db import transaction
    from django.utils import timezone

    from notifications.models import EmailOutbox

    try:
        path = _job_path(job.func)
        EmailOutbox.objects.create(
            func=path,
            args=list(job.args),
            kwargs=job.kwargs,
            max_attempts=job.max_attempts,
            retry_delay=job.retry_delay,
            next_attempt_at=timezone.now() + timedelta(seconds=max(delay_seconds, 0)),
        )
    except Exception as exc:  # noqa: BLE001 - unsaveable args, missing table during migrate...
        logger.warning("Email job not saved to the outbox, queued in memory instead: %s", exc)
        return False
    ensure_outbox_worker()
    # Inside a transaction the row is invisible to the worker until commit.
    transaction.on_commit(_outbox_wake.set)
    return True


def ensure_outbox_worker() -> None:
    global _outbox_started
    with _worker_lock:
        if _outbox_started:
            return
        for index in range(OUTBOX_WORKERS):
            threading.Thread(target=_outbox_loop, name=f"email-outbox-{index}", daemon=True).start()
        if not _started_lanes:
            atexit.register(drain_on_shutdown)
        _started_lanes.add("outbox")
        _outbox_started = True


def _outbox_loop() -> None:
    while not _outbox_stop.is_set():
        close_old_connections()
        try:
            worked = run_due_outbox_jobs()
        except Exception:  # noqa: BLE001 - e.g. the database is briefly unreachable
            logger.exception("Email outbox pass failed")
            worked = False
        finally:
            close_old_connections()
        if not worked:
            _outbox_wake.wait(OUTBOX_POLL_SECONDS)
            _outbox_wake.clear()


def run_due_outbox_jobs() -> int:
    """Send the outbox rows that are due. Returns how many were attempted."""
    from datetime import timedelta

    from django.utils import timezone

    from notifications.models import EmailOutbox

    now = timezone.now()
    # Rows a dead process claimed and never finished.
    EmailOutbox.objects.filter(
        status=EmailOutbox.Status.SENDING,
        updated_at__lt=now - timedelta(seconds=OUTBOX_STUCK_SECONDS),
    ).update(status=EmailOutbox.Status.PENDING, updated_at=now)
    _prune_failed_rows(now)

    due = list(
        EmailOutbox.objects.filter(status=EmailOutbox.Status.PENDING, next_attempt_at__lte=now)
        .order_by("next_attempt_at", "id")
        .values_list("pk", flat=True)[:OUTBOX_BATCH]
    )
    attempted = 0
    for pk in due:
        if _outbox_stop.is_set():
            break
        claimed = EmailOutbox.objects.filter(pk=pk, status=EmailOutbox.Status.PENDING).update(
            status=EmailOutbox.Status.SENDING, updated_at=timezone.now()
        )
        if not claimed:
            continue  # another process took it
        attempted += 1
        _set_outbox_busy(1)
        try:
            _run_outbox_row(EmailOutbox.objects.get(pk=pk))
        finally:
            _set_outbox_busy(-1)
    return attempted


def _prune_failed_rows(now) -> None:
    """Remove rows that failed for good long ago (at most once an hour)."""
    global _last_prune
    from datetime import timedelta

    from notifications.models import EmailOutbox

    if _last_prune and time.monotonic() - _last_prune < _PRUNE_EVERY_SECONDS:
        return
    _last_prune = time.monotonic()
    keep_days = getattr(settings, "EMAIL_OUTBOX_FAILED_KEEP_DAYS", OUTBOX_FAILED_KEEP_DAYS)
    removed, _ = EmailOutbox.objects.filter(
        status=EmailOutbox.Status.FAILED, updated_at__lt=now - timedelta(days=keep_days)
    ).delete()
    if removed:
        logger.info("Removed %s failed outbox email(s) older than %s days.", removed, keep_days)


def _run_outbox_row(row) -> None:
    from datetime import timedelta

    from django.utils import timezone
    from django.utils.module_loading import import_string

    from notifications.models import EmailOutbox

    _current.row = row
    try:
        func = import_string(row.func)
        result = func(*row.args, **row.kwargs)
        if result is False:
            logger.debug("Email job returned False (likely no recipients or disabled).")
    except Exception as exc:  # noqa: BLE001
        row.attempts += 1
        row.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        row.updated_at = timezone.now()
        if row.attempts < row.max_attempts:
            row.status = EmailOutbox.Status.PENDING
            row.next_attempt_at = timezone.now() + timedelta(seconds=row.retry_delay * row.attempts)
            logger.warning("Email job %s failed (attempt %s/%s): %s", row.func, row.attempts, row.max_attempts, exc)
        else:
            row.status = EmailOutbox.Status.FAILED
            logger.error("Email job %s failed for good after %s attempts: %s", row.func, row.attempts, exc)
        row.save()
        return
    finally:
        _current.row = None
    row.delete()


def start_outbox_on_first_request(**_kwargs) -> None:
    """request_started hook: send email left in the outbox by a crash, without
    waiting for the next new email. Tests run with EMAIL_QUEUE_SYNC and skip it."""
    if getattr(settings, "EMAIL_QUEUE_SYNC", False) or _outbox_started:
        return
    ensure_outbox_worker()
