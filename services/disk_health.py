"""Disk health monitoring service.

Checks free space on configured volumes and sends a macOS notification
when any volume falls below the configured threshold.
Each volume is checked independently — failures don't block others.
"""

import shutil

from services.base import notify


def _check_volume(path, threshold_gb, logger):
    """Check free space on a volume. Returns (free_gb, ok)."""
    try:
        usage = shutil.disk_usage(path)
    except FileNotFoundError:
        logger.error("Volume path does not exist: %s", path)
        return None, False

    free_gb = usage.free / (1024 ** 3)
    total_gb = usage.total / (1024 ** 3)
    used_pct = 100 * usage.used / usage.total

    logger.info(
        "%s: %.1f GB free of %.1f GB (%.0f%% used)",
        path, free_gb, total_gb, used_pct,
    )

    return free_gb, free_gb >= threshold_gb


def run(config, global_config, logger):
    """Entry point called by runner.py."""
    threshold_gb = config.get("threshold_gb", 10)
    volumes = config.get("volumes", ["/"])

    logger.info("Checking disk health (threshold: %d GB free)", threshold_gb)

    alerts = []
    for vol in volumes:
        try:
            free_gb, ok = _check_volume(vol, threshold_gb, logger)
            if free_gb is not None and not ok:
                alerts.append((vol, free_gb))
        except Exception:
            logger.exception("Error checking volume %s", vol)

    if alerts:
        for vol, free_gb in alerts:
            msg = f"{vol}: only {free_gb:.1f} GB free"
            logger.warning("LOW DISK SPACE — %s", msg)
            notify("Low Disk Space", msg, logger)
    else:
        logger.info("All volumes have sufficient free space")
