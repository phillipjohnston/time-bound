"""Tests for bin/install.py."""

import os
import subprocess
from unittest.mock import MagicMock, mock_open, patch

from bin.install import generate_plist, install_service, schedule_to_xml


class TestScheduleToXml:
    def test_single_entry(self):
        schedule = [{"Hour": 9, "Minute": 0}]
        xml = schedule_to_xml(schedule)
        assert "<dict>" in xml
        assert "<key>Hour</key>" in xml
        assert "<integer>9</integer>" in xml
        assert "<key>Minute</key>" in xml
        assert "<integer>0</integer>" in xml
        # Single entry should NOT be wrapped in <array>
        assert "<array>" not in xml

    def test_multiple_entries(self):
        schedule = [
            {"Hour": 9, "Minute": 0},
            {"Hour": 17, "Minute": 30},
        ]
        xml = schedule_to_xml(schedule)
        assert "<array>" in xml
        assert "</array>" in xml
        assert xml.count("<dict>") == 2
        assert "<integer>17</integer>" in xml
        assert "<integer>30</integer>" in xml


class TestGeneratePlist:
    def test_renders_template_with_substitutions(self, tmp_path, global_config):
        # Set up a template file
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template_file = template_dir / "launchagent.plist.template"
        template_file.write_text(
            "<plist><label>${label}</label>"
            "<python>${python_path}</python>"
            "<root>${project_root}</root>"
            "<svc>${service_name}</svc>"
            "<path>${path}</path>"
            "<home>${home}</home>"
            "<logdir>${log_dir}</logdir>"
            "${schedule_xml}</plist>"
        )

        service_def = {
            "schedule": [{"Hour": 12, "Minute": 0}],
        }

        label, content = generate_plist("git-sync", service_def, global_config)

        assert label == "com.test.time-bound.git-sync"
        assert "com.test.time-bound.git-sync" in content
        assert global_config["python_path"] in content
        assert str(tmp_path) in content
        assert "git-sync" in content
        assert "<integer>12</integer>" in content


class TestInstallService:
    def test_writes_plist_and_bootstraps(self, tmp_path, global_config):
        service_def = {
            "schedule": [{"Hour": 8, "Minute": 0}],
        }
        # Create template
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "launchagent.plist.template").write_text(
            "<plist>${label} ${python_path} ${project_root} "
            "${service_name} ${path} ${home} ${log_dir} ${schedule_xml}</plist>"
        )

        plist_dir = tmp_path / "LaunchAgents"

        with patch("bin.install.os.path.expanduser", return_value=str(plist_dir)), \
             patch("bin.install.subprocess.run") as mock_run:
            # First call = bootout (ignored), second = bootstrap (success)
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 0, "", ""),
            ]
            result = install_service("git-sync", service_def, global_config)

        assert result is True
        plist_path = plist_dir / "com.test.time-bound.git-sync.plist"
        assert plist_path.exists()

    def test_bootstrap_failure_returns_false(self, tmp_path, global_config):
        service_def = {
            "schedule": [{"Hour": 8, "Minute": 0}],
        }
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "launchagent.plist.template").write_text(
            "<plist>${label} ${python_path} ${project_root} "
            "${service_name} ${path} ${home} ${log_dir} ${schedule_xml}</plist>"
        )

        plist_dir = tmp_path / "LaunchAgents"

        with patch("bin.install.os.path.expanduser", return_value=str(plist_dir)), \
             patch("bin.install.subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),    # bootout
                subprocess.CompletedProcess([], 1, "", "err"), # bootstrap fails
            ]
            result = install_service("git-sync", service_def, global_config)

        assert result is False
