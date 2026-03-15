"""Tests for services/code_review.py."""

import os
from unittest.mock import MagicMock, mock_open, patch

from services.code_review import (
    _output_to_file,
    _output_to_gh_issue,
    _output_to_gh_pr,
    _review_codebase,
    run,
)


class TestRun:
    def test_empty_codebases_logs_warning(self, mock_logger, global_config):
        run({}, global_config, mock_logger)
        mock_logger.warning.assert_called_once()
        assert "No codebases" in mock_logger.warning.call_args[0][0]

    def test_filters_codebases_by_weekday(self, mock_logger, global_config):
        codebases = [
            {"name": "mon-only", "path": "/a", "days": [0]},
            {"name": "wed-only", "path": "/b", "days": [2]},
        ]
        # Pretend today is Wednesday (weekday 2)
        with patch("services.code_review.today_weekday", return_value=2), \
             patch("services.code_review._review_codebase", return_value=True) as mock_rev:
            run({"codebases": codebases}, global_config, mock_logger)
            assert mock_rev.call_count == 1
            assert mock_rev.call_args[0][0]["name"] == "wed-only"

    def test_no_codebases_scheduled_today(self, mock_logger, global_config):
        codebases = [{"name": "x", "path": "/x", "days": [0]}]
        with patch("services.code_review.today_weekday", return_value=4):
            run({"codebases": codebases}, global_config, mock_logger)
            # Should log "No codebases scheduled" but no error
            mock_logger.error.assert_not_called()


class TestReviewCodebase:
    def _codebase(self, **overrides):
        base = {
            "path": "/project",
            "name": "test-project",
            "review_focus": "Review it.",
            "output_method": "file",
        }
        base.update(overrides)
        return base

    def test_nonexistent_path_returns_false(self, mock_logger):
        with patch("services.code_review.os.path.isdir", return_value=False):
            assert _review_codebase(self._codebase(), {}, mock_logger) is False
            mock_logger.error.assert_called_once()

    def test_claude_cli_failure_returns_false(self, mock_logger):
        with patch("services.code_review.os.path.isdir", return_value=True), \
             patch("services.code_review.run_command", return_value=(1, "", "claude error")):
            assert _review_codebase(self._codebase(), {}, mock_logger) is False

    def test_empty_review_output_returns_false(self, mock_logger):
        with patch("services.code_review.os.path.isdir", return_value=True), \
             patch("services.code_review.run_command", return_value=(0, "  \n  ", "")):
            assert _review_codebase(self._codebase(), {}, mock_logger) is False
            mock_logger.warning.assert_called_once()

    def test_successful_review_to_file(self, mock_logger, tmp_path):
        config = {"reports_dir": str(tmp_path / "reports")}
        codebase = self._codebase(output_method="file")
        with patch("services.code_review.os.path.isdir", return_value=True), \
             patch("services.code_review.run_command", return_value=(0, "Good code!", "")):
            assert _review_codebase(codebase, config, mock_logger) is True

    def test_gh_issue_output_method(self, mock_logger):
        codebase = self._codebase(output_method="gh-issue")
        with patch("services.code_review.os.path.isdir", return_value=True), \
             patch("services.code_review.run_command", return_value=(0, "Review text", "")), \
             patch("services.code_review._output_to_gh_issue", return_value="https://gh/1") as mock_issue, \
             patch("services.code_review._output_to_file") as mock_file:
            assert _review_codebase(codebase, {}, mock_logger) is True
            mock_issue.assert_called_once()
            mock_file.assert_not_called()

    def test_gh_issue_fallback_to_file(self, mock_logger, tmp_path):
        """gh-issue returns None (gh not found) => falls back to file."""
        config = {"reports_dir": str(tmp_path / "reports")}
        codebase = self._codebase(output_method="gh-issue")
        with patch("services.code_review.os.path.isdir", return_value=True), \
             patch("services.code_review.run_command", return_value=(0, "Review text", "")), \
             patch("services.code_review._output_to_gh_issue", return_value=None), \
             patch("services.code_review._output_to_file") as mock_file:
            _review_codebase(codebase, config, mock_logger)
            mock_file.assert_called_once()

    def test_gh_pr_output_method(self, mock_logger):
        codebase = self._codebase(output_method="gh-pr")
        with patch("services.code_review.os.path.isdir", return_value=True), \
             patch("services.code_review.run_command", return_value=(0, "Review text", "")), \
             patch("services.code_review._output_to_gh_pr", return_value="https://gh/pr/1") as mock_pr, \
             patch("services.code_review._output_to_file") as mock_file:
            assert _review_codebase(codebase, {}, mock_logger) is True
            mock_pr.assert_called_once()
            mock_file.assert_not_called()

    def test_gh_pr_fallback_to_file(self, mock_logger, tmp_path):
        config = {"reports_dir": str(tmp_path / "reports")}
        codebase = self._codebase(output_method="gh-pr")
        with patch("services.code_review.os.path.isdir", return_value=True), \
             patch("services.code_review.run_command", return_value=(0, "Review text", "")), \
             patch("services.code_review._output_to_gh_pr", return_value=None), \
             patch("services.code_review._output_to_file") as mock_file:
            _review_codebase(codebase, config, mock_logger)
            mock_file.assert_called_once()


class TestOutputToFile:
    def test_writes_correct_content(self, mock_logger, tmp_path):
        config = {"reports_dir": str(tmp_path / "reports")}
        codebase = {"name": "my-proj", "path": "/some/path"}
        with patch("services.code_review.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "2026-03-15"
            result = _output_to_file("Review body", codebase, config, mock_logger)

        assert result.endswith("2026-03-15-review.md")
        content = open(result).read()
        assert "# Code Review: my-proj" in content
        assert "Review body" in content
        assert "/some/path" in content


class TestOutputToGhIssue:
    def test_no_gh_cli_returns_none(self, mock_logger):
        codebase = {"name": "proj", "path": "/p"}
        with patch("services.code_review.shutil.which", return_value=None):
            result = _output_to_gh_issue("text", codebase, mock_logger)
            assert result is None
            mock_logger.warning.assert_called_once()

    def test_successful_issue_creation(self, mock_logger):
        codebase = {"name": "proj", "path": "/p"}
        with patch("services.code_review.shutil.which", return_value="/usr/bin/gh"), \
             patch("services.code_review.run_command", return_value=(0, "https://github.com/o/r/issues/1\n", "")):
            result = _output_to_gh_issue("text", codebase, mock_logger)
            assert result == "https://github.com/o/r/issues/1"


class TestOutputToGhPr:
    def test_no_gh_cli_returns_none(self, mock_logger):
        codebase = {"name": "proj", "path": "/p"}
        with patch("services.code_review.shutil.which", return_value=None):
            result = _output_to_gh_pr("text", codebase, mock_logger)
            assert result is None
            mock_logger.warning.assert_called_once()
