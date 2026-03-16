"""Tests for services/log_cleanup.py."""

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.log_cleanup import _cleanup_dir, _cleanup_service_logs, run


class TestCleanupDir:
    def test_nonexistent_dir_logs_warning(self, mock_logger):
        _cleanup_dir("/nonexistent/path", 30, mock_logger)
        mock_logger.warning.assert_called_once()

    def test_deletes_old_files(self, tmp_path, mock_logger):
        old_file = tmp_path / "old.log"
        old_file.write_text("old")
        old_mtime = (datetime.now() - timedelta(days=31)).timestamp()
        os.utime(old_file, (old_mtime, old_mtime))

        new_file = tmp_path / "new.log"
        new_file.write_text("new")

        deleted = _cleanup_dir(str(tmp_path), 30, mock_logger)

        assert deleted == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_keeps_files_within_threshold(self, tmp_path, mock_logger):
        recent = tmp_path / "recent.log"
        recent.write_text("data")

        deleted = _cleanup_dir(str(tmp_path), 30, mock_logger)

        assert deleted == 0
        assert recent.exists()

    def test_skips_subdirectories(self, tmp_path, mock_logger):
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        deleted = _cleanup_dir(str(tmp_path), 30, mock_logger)
        assert deleted == 0
        assert subdir.exists()


class TestCleanupServiceLogs:
    def test_nonexistent_base_dir_logs_warning(self, mock_logger):
        _cleanup_service_logs("/nonexistent", "logs", 30, mock_logger)
        mock_logger.warning.assert_called_once()

    def test_cleans_each_service_subdir(self, tmp_path, mock_logger):
        svc_dir = tmp_path / "logs" / "my-service"
        svc_dir.mkdir(parents=True)
        old_file = svc_dir / "2020-01-01.log"
        old_file.write_text("old")
        old_mtime = (datetime.now() - timedelta(days=60)).timestamp()
        os.utime(old_file, (old_mtime, old_mtime))

        total = _cleanup_service_logs(str(tmp_path), "logs", 30, mock_logger)

        assert total == 1
        assert not old_file.exists()


class TestRun:
    def test_empty_config_uses_defaults(self, tmp_path, mock_logger):
        global_config = {"project_root": str(tmp_path), "log_dir": "logs"}
        (tmp_path / "logs").mkdir()

        run({}, global_config, mock_logger)

        mock_logger.info.assert_called()

    def test_extra_dirs_are_cleaned(self, tmp_path, mock_logger):
        global_config = {"project_root": str(tmp_path), "log_dir": "logs"}
        (tmp_path / "logs").mkdir()

        extra = tmp_path / "extra_logs"
        extra.mkdir()
        old_file = extra / "old.log"
        old_file.write_text("x")
        old_mtime = (datetime.now() - timedelta(days=31)).timestamp()
        os.utime(old_file, (old_mtime, old_mtime))

        run({"max_age_days": 30, "extra_dirs": [str(extra)]}, global_config, mock_logger)

        assert not old_file.exists()

    def test_exception_in_extra_dir_is_caught(self, tmp_path, mock_logger):
        global_config = {"project_root": str(tmp_path), "log_dir": "logs"}
        (tmp_path / "logs").mkdir()

        with patch("services.log_cleanup._cleanup_dir", side_effect=RuntimeError("boom")):
            run({"extra_dirs": ["/some/dir"]}, global_config, mock_logger)
            mock_logger.exception.assert_called()
