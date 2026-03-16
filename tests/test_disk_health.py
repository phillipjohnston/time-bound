"""Tests for services/disk_health.py."""

from unittest.mock import call, patch

import pytest

from services.disk_health import _check_volume, run


class TestCheckVolume:
    def _usage(self, free_gb, total_gb):
        free = int(free_gb * 1024 ** 3)
        total = int(total_gb * 1024 ** 3)
        used = total - free
        # shutil.disk_usage returns a named tuple (total, used, free)
        import collections
        Usage = collections.namedtuple("Usage", ["total", "used", "free"])
        return Usage(total=total, used=used, free=free)

    def test_sufficient_space_returns_ok(self, mock_logger):
        with patch("services.disk_health.shutil.disk_usage", return_value=self._usage(50, 100)):
            free_gb, ok = _check_volume("/", 10, mock_logger)
        assert ok is True
        assert abs(free_gb - 50) < 0.1

    def test_insufficient_space_returns_not_ok(self, mock_logger):
        with patch("services.disk_health.shutil.disk_usage", return_value=self._usage(5, 100)):
            free_gb, ok = _check_volume("/", 10, mock_logger)
        assert ok is False
        assert abs(free_gb - 5) < 0.1

    def test_nonexistent_path_returns_none_false(self, mock_logger):
        with patch("services.disk_health.shutil.disk_usage", side_effect=FileNotFoundError):
            free_gb, ok = _check_volume("/no/such/volume", 10, mock_logger)
        assert free_gb is None
        assert ok is False
        mock_logger.error.assert_called_once()


class TestRun:
    def _usage(self, free_gb, total_gb):
        import collections
        Usage = collections.namedtuple("Usage", ["total", "used", "free"])
        total = int(total_gb * 1024 ** 3)
        free = int(free_gb * 1024 ** 3)
        return Usage(total=total, used=total - free, free=free)

    def test_no_alerts_when_space_sufficient(self, mock_logger, global_config):
        with patch("services.disk_health.shutil.disk_usage", return_value=self._usage(50, 100)), \
             patch("services.disk_health.notify") as mock_notify:
            run({"threshold_gb": 10, "volumes": ["/"]}, global_config, mock_logger)
            mock_notify.assert_not_called()

    def test_alert_when_space_low(self, mock_logger, global_config):
        with patch("services.disk_health.shutil.disk_usage", return_value=self._usage(5, 100)), \
             patch("services.disk_health.notify") as mock_notify:
            run({"threshold_gb": 10, "volumes": ["/"]}, global_config, mock_logger)
            mock_notify.assert_called_once()
            assert "Low Disk Space" in mock_notify.call_args[0][0]

    def test_default_volume_is_root(self, mock_logger, global_config):
        with patch("services.disk_health.shutil.disk_usage", return_value=self._usage(50, 100)) as mock_du, \
             patch("services.disk_health.notify"):
            run({}, global_config, mock_logger)
            mock_du.assert_called_once_with("/")

    def test_multiple_volumes_checked(self, mock_logger, global_config):
        with patch("services.disk_health.shutil.disk_usage", return_value=self._usage(50, 100)) as mock_du, \
             patch("services.disk_health.notify"):
            run({"volumes": ["/", "/Volumes/Data"]}, global_config, mock_logger)
            assert mock_du.call_count == 2

    def test_exception_per_volume_is_caught(self, mock_logger, global_config):
        with patch("services.disk_health._check_volume", side_effect=RuntimeError("boom")):
            run({"volumes": ["/"]}, global_config, mock_logger)
            mock_logger.exception.assert_called_once()
