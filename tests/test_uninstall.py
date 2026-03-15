"""Tests for bin/uninstall.py."""

import os
import subprocess
from unittest.mock import patch

from bin.uninstall import uninstall_service


class TestUninstallService:
    def _global_config(self):
        return {"label_prefix": "com.test.time-bound"}

    def test_removes_plist_and_calls_bootout(self, tmp_path):
        label = "com.test.time-bound.git-sync"
        plist_path = tmp_path / f"{label}.plist"
        plist_path.write_text("<plist/>")

        with patch("bin.uninstall.os.path.expanduser", return_value=str(plist_path)), \
             patch("bin.uninstall.os.path.exists", return_value=True), \
             patch("bin.uninstall.os.remove") as mock_rm, \
             patch("bin.uninstall.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, "", "")
            result = uninstall_service("git-sync", self._global_config())

        assert result is True
        mock_run.assert_called_once()
        mock_rm.assert_called_once()

    def test_plist_not_found_already_removed(self, tmp_path):
        with patch("bin.uninstall.os.path.exists", return_value=False), \
             patch("bin.uninstall.subprocess.run") as mock_run:
            result = uninstall_service("git-sync", self._global_config())

        assert result is True
        mock_run.assert_not_called()

    def test_bootout_error_code_3_is_tolerated(self, tmp_path):
        """Error code 3 means 'no such process' — already unloaded."""
        with patch("bin.uninstall.os.path.exists", return_value=True), \
             patch("bin.uninstall.os.remove") as mock_rm, \
             patch("bin.uninstall.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                [], 1, "", "3: No such process"
            )
            result = uninstall_service("git-sync", self._global_config())

        assert result is True
        mock_rm.assert_called_once()
