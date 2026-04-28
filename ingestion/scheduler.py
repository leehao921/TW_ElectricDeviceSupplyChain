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
import inspect
import logging
import signal
import sys
from typing import Awaitable, Callable, Dict, Tuple, Union

from . import db
from .config import settings

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


def _make_wrapper(name: str, func: JobCallable) -> Callable[[], None]:
    def wrapper() -> None:
        asyncio.run(_run_job_async(name, func))
    wrapper.__name__ = f"wrapped_{name}"
    return wrapper


def build_scheduler():
    """Build a BlockingScheduler with every registered job attached."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler(timezone=settings.tz)
    for name, (cron_expr, func) in JOBS.items():
        trigger = CronTrigger.from_crontab(cron_expr, timezone=settings.tz)
        scheduler.add_job(_make_wrapper(name, func), trigger=trigger, id=name, name=name)
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


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(prog="ingestion.scheduler")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="List registered jobs and exit.")
    group.add_argument("--run-once", metavar="JOB_NAME", help="Run a single job once and exit.")
    args = parser.parse_args(argv)

    if args.dry_run:
        _print_jobs()
        return 0

    if args.run_once:
        return _run_once(args.run_once)

    scheduler = build_scheduler()

    def _graceful_shutdown(*_ignored):
        logger.info("shutdown signal received")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        asyncio.run(db.close())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
