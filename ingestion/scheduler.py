"""APScheduler entry point for ingestion collectors.

Other workers extend ``JOBS`` with ``{"job_name": ("cron expr", callable)}``
entries. Every job is wrapped so it logs its outcome (and row count, if the
callable returns an ``int``) to the ``ingest_runs`` table.

CLI:
    python -m ingestion.scheduler --dry-run
    python -m ingestion.scheduler --run-once <job_name>
    python -m ingestion.scheduler        # blocking run
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import inspect
import logging
import signal
import sys
from typing import Awaitable, Callable, Dict, Tuple, Union

from . import db
from .config import settings


def _load_jobs() -> None:
    """Merge :mod:`ingestion.jobs` registrations into ``JOBS``.

    Done lazily so ``python -m ingestion.scheduler --dry-run`` works in
    minimal environments where heavy collector deps are missing — failures
    here are logged but do not abort the CLI. We copy entries explicitly
    rather than relying on shared dict references to dodge the
    ``__main__`` vs ``ingestion.scheduler`` double-import problem.
    """
    try:
        from . import jobs  # populates jobs.JOBS at import time
    except Exception:  # noqa: BLE001
        logging.getLogger("ingestion.scheduler").exception(
            "failed to import ingestion.jobs; JOBS will be empty"
        )
        return
    for name, entry in jobs.JOBS.items():
        JOBS[name] = entry

logger = logging.getLogger("ingestion.scheduler")

# Each entry maps a job name → (cron expression, callable). Callables may be
# sync or async. If they return an int it is recorded as ``rows_written``.
JobCallable = Callable[[], Union[int, None, Awaitable[Union[int, None]]]]
JOBS: Dict[str, Tuple[str, JobCallable]] = {}


async def _invoke(func: JobCallable):
    result = func()
    if inspect.isawaitable(result):
        result = await result
    return result


async def _run_job_async(name: str, func: JobCallable) -> None:
    try:
        result = await _invoke(func)
        rows = result if isinstance(result, int) else None
        await db.log_run(name, "success", rows)
        logger.info("job %s ok (rows=%s)", name, rows)
    except Exception as exc:  # noqa: BLE001 — we want every failure logged
        logger.exception("job %s failed", name)
        try:
            await db.log_run(name, "error", None, error=str(exc))
        except Exception:  # pragma: no cover — logging failure path
            logger.exception("failed to log error for job %s", name)


def build_scheduler():
    """Build an AsyncIOScheduler with every registered job attached.

    Switched from ``BlockingScheduler`` 2026-04-28: the previous design ran
    each fired job on a fresh event loop via ``asyncio.run(...)`` inside a
    thread, but ``ingestion.db`` caches its asyncpg pool as a module-level
    singleton. The pool's connections are bound to the loop that created
    them, so any second loop hitting them raised
    ``InterfaceError: cannot perform operation: another operation is in
    progress``. AsyncIOScheduler runs all jobs on a single shared loop, so
    the pool stays alive forever and the cross-loop bug disappears.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler(timezone=settings.tz)
    for name, (cron_expr, func) in JOBS.items():
        trigger = CronTrigger.from_crontab(cron_expr, timezone=settings.tz)
        scheduler.add_job(
            functools.partial(_run_job_async, name, func),
            trigger=trigger, id=name, name=name,
        )
    return scheduler


def _print_jobs() -> None:
    if not JOBS:
        print("No jobs registered.")
        return
    print(f"Registered jobs ({len(JOBS)}):")
    for name, (cron_expr, _) in sorted(JOBS.items()):
        print(f"  {name:<32} {cron_expr}")


def _run_once(job_name: str) -> int:
    if job_name not in JOBS:
        print(f"error: job {job_name!r} not registered", file=sys.stderr)
        return 2
    _, func = JOBS[job_name]

    async def _go() -> None:
        try:
            await _run_job_async(job_name, func)
        finally:
            await db.close()

    asyncio.run(_go())
    return 0


async def _serve_forever(scheduler) -> None:
    """Run an AsyncIOScheduler until SIGINT/SIGTERM, then close the pool."""
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _graceful_shutdown(*_ignored):
        logger.info("shutdown signal received")
        loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)

    scheduler.start()
    try:
        await stop_event.wait()
    finally:
        scheduler.shutdown(wait=False)
        await db.close()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(prog="ingestion.scheduler")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="List registered jobs and exit.")
    group.add_argument("--run-once", metavar="JOB_NAME", help="Run a single job once and exit.")
    args = parser.parse_args(argv)

    _load_jobs()

    if args.dry_run:
        _print_jobs()
        return 0

    if args.run_once:
        return _run_once(args.run_once)

    scheduler = build_scheduler()
    try:
        asyncio.run(_serve_forever(scheduler))
    except (KeyboardInterrupt, SystemExit):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
