"""Shared utilities for time-bound services."""

import logging
import os
import subprocess
from datetime import datetime


def run_command(cmd, cwd=None, timeout=300, logger=None):
    """Run a shell command, returning (returncode, stdout, stderr).

    Args:
        cmd: Command as a list of strings.
        cwd: Working directory.
        timeout: Timeout in seconds (default 5 minutes).
        logger: Optional logger for debug output.
    """
    if logger:
        logger.debug("Running: %s (cwd=%s)", " ".join(cmd), cwd or os.getcwd())

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if logger:
            if result.stdout.strip():
                logger.debug("stdout: %s", result.stdout.strip())
            if result.stderr.strip():
                logger.debug("stderr: %s", result.stderr.strip())
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        if logger:
            logger.error("Command timed out after %ds: %s", timeout, " ".join(cmd))
        return -1, "", f"Timed out after {timeout}s"
    except FileNotFoundError:
        msg = f"Command not found: {cmd[0]}"
        if logger:
            logger.error(msg)
        return -1, "", msg


def today_weekday():
    """Return today's weekday as an integer (0=Monday, 6=Sunday)."""
    return datetime.now().weekday()


def notify(title, message, logger=None):
    """Send a macOS notification via osascript.

    This is best-effort; failures are logged but not raised.
    """
    script = f'display notification "{message}" with title "{title}"'
    rc, _, stderr = run_command(["osascript", "-e", script], logger=logger)
    if rc != 0 and logger:
        logger.warning("Notification failed: %s", stderr.strip())


def setup_service_logger(service_name, global_config):
    """Create a logger that writes to a per-service daily log file and stderr.

    Returns a configured logging.Logger.
    """
    project_root = global_config["project_root"]
    log_dir = os.path.join(project_root, global_config["log_dir"], service_name)
    os.makedirs(log_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"{date_str}.log")

    logger = logging.getLogger(f"time-bound.{service_name}")
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers on repeated calls
    if not logger.handlers:
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    return logger
