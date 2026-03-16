"""Log cleanup service.

Deletes log files older than a configured number of days from the
time-bound logs directory and any additional configured directories.
Each directory is processed independently — failures don't block others.
"""

import os
from datetime import datetime, timedelta


def _cleanup_dir(log_dir, max_age_days, logger):
    """Delete files older than max_age_days in log_dir (non-recursive)."""
    if not os.path.isdir(log_dir):
        logger.warning("Log directory does not exist, skipping: %s", log_dir)
        return 0

    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted = 0

    for entry in os.scandir(log_dir):
        if not entry.is_file():
            continue
        mtime = datetime.fromtimestamp(entry.stat().st_mtime)
        if mtime < cutoff:
            try:
                os.remove(entry.path)
                logger.debug("Deleted: %s", entry.path)
                deleted += 1
            except OSError as e:
                logger.error("Failed to delete %s: %s", entry.path, e)

    return deleted


def _cleanup_service_logs(project_root, log_dir_name, max_age_days, logger):
    """Walk the per-service log subdirectories under logs/."""
    base = os.path.join(project_root, log_dir_name)
    if not os.path.isdir(base):
        logger.warning("Base log dir does not exist: %s", base)
        return 0

    total = 0
    for entry in os.scandir(base):
        if entry.is_dir():
            deleted = _cleanup_dir(entry.path, max_age_days, logger)
            if deleted:
                logger.info("Cleaned %d file(s) from %s", deleted, entry.path)
            total += deleted

    return total


def run(config, global_config, logger):
    """Entry point called by runner.py."""
    max_age_days = config.get("max_age_days", 30)
    extra_dirs = config.get("extra_dirs", [])

    logger.info("Cleaning log files older than %d days", max_age_days)

    total = 0

    # Always clean this framework's own logs
    project_root = global_config["project_root"]
    log_dir = global_config.get("log_dir", "logs")
    try:
        deleted = _cleanup_service_logs(project_root, log_dir, max_age_days, logger)
        total += deleted
        logger.info("Cleaned %d file(s) from framework logs", deleted)
    except Exception:
        logger.exception("Error cleaning framework logs")

    # Clean any additional configured directories
    for d in extra_dirs:
        try:
            deleted = _cleanup_dir(d, max_age_days, logger)
            total += deleted
            logger.info("Cleaned %d file(s) from %s", deleted, d)
        except Exception:
            logger.exception("Error cleaning %s", d)

    logger.info("Log cleanup complete: %d file(s) deleted total", total)
