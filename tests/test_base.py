"""Tests for services/base.py."""

import logging
import subprocess
from datetime import datetime
from unittest.mock import MagicMock, patch

from services.base import notify, run_command, setup_service_logger, today_weekday


class TestRunCommand:
    def test_successful_command(self):
        with patch("services.base.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["echo", "hi"], returncode=0, stdout="hi\n", stderr=""
            )
            rc, stdout, stderr = run_command(["echo", "hi"])
            assert rc == 0
            assert stdout == "hi\n"
            assert stderr == ""

    def test_failed_command(self):
        with patch("services.base.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["false"], returncode=1, stdout="", stderr="error\n"
            )
            rc, stdout, stderr = run_command(["false"])
            assert rc == 1
            assert stderr == "error\n"

    def test_timeout(self):
        with patch("services.base.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["sleep"], timeout=5)
            logger = MagicMock()
            rc, stdout, stderr = run_command(["sleep", "999"], timeout=5, logger=logger)
            assert rc == -1
            assert "Timed out" in stderr
            logger.error.assert_called_once()

    def test_command_not_found(self):
        with patch("services.base.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            logger = MagicMock()
            rc, stdout, stderr = run_command(["nonexistent"], logger=logger)
            assert rc == -1
            assert "Command not found" in stderr
            logger.error.assert_called_once()

    def test_logger_receives_debug_output(self):
        with patch("services.base.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["cmd"], returncode=0, stdout="out\n", stderr="err\n"
            )
            logger = MagicMock()
            run_command(["cmd"], logger=logger)
            # Should log the command, stdout, and stderr
            assert logger.debug.call_count == 3


class TestTodayWeekday:
    def test_returns_correct_weekday(self):
        # Wednesday = weekday 2
        with patch("services.base.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 11)  # a Wednesday
            assert today_weekday() == 2

    def test_monday(self):
        with patch("services.base.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 9)  # a Monday
            assert today_weekday() == 0


class TestNotify:
    def test_success_path(self):
        with patch("services.base.run_command", return_value=(0, "", "")) as mock_rc:
            logger = MagicMock()
            notify("Title", "Body", logger=logger)
            mock_rc.assert_called_once()
            logger.warning.assert_not_called()

    def test_failure_logs_warning(self):
        with patch("services.base.run_command", return_value=(1, "", "script error")):
            logger = MagicMock()
            notify("Title", "Body", logger=logger)
            logger.warning.assert_called_once()


class TestSetupServiceLogger:
    def test_creates_log_dir_and_returns_logger(self, global_config):
        import os

        logger = setup_service_logger("test-svc", global_config)
        log_dir = os.path.join(global_config["project_root"], "logs", "test-svc")
        assert os.path.isdir(log_dir)
        assert isinstance(logger, logging.Logger)
        assert logger.name == "time-bound.test-svc"
        assert len(logger.handlers) == 2  # file + stream

    def test_no_duplicate_handlers_on_repeat(self, global_config):
        # Use a unique logger name to avoid cross-test pollution
        cfg = dict(global_config)
        logger1 = setup_service_logger("dup-test", cfg)
        handler_count = len(logger1.handlers)
        logger2 = setup_service_logger("dup-test", cfg)
        assert logger1 is logger2
        assert len(logger2.handlers) == handler_count
