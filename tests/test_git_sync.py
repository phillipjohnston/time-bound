"""Tests for services/git_sync.py."""

from unittest.mock import MagicMock, call, patch

from services.git_sync import _process_repo, run


class TestRun:
    def test_empty_repos_logs_warning(self, mock_logger, global_config):
        run({}, global_config, mock_logger)
        mock_logger.warning.assert_called_once()
        assert "No repos" in mock_logger.warning.call_args[0][0]

    def test_calls_process_repo_per_repo(self, mock_logger, global_config):
        repos = [{"path": "/a"}, {"path": "/b"}]
        with patch("services.git_sync._process_repo") as mock_pr:
            mock_pr.return_value = True
            run({"repos": repos}, global_config, mock_logger)
            assert mock_pr.call_count == 2

    def test_exception_in_process_repo_is_caught(self, mock_logger, global_config):
        repos = [{"path": "/bad"}]
        with patch("services.git_sync._process_repo", side_effect=RuntimeError("boom")):
            run({"repos": repos}, global_config, mock_logger)
            mock_logger.exception.assert_called_once()


class TestProcessRepo:
    def _repo(self, **overrides):
        base = {
            "path": "/repo",
            "remote": "origin",
            "branch": "main",
            "pull": True,
            "push": False,
            "auto_commit": False,
        }
        base.update(overrides)
        return base

    def test_nonexistent_path_returns_false(self, mock_logger):
        with patch("services.git_sync.os.path.isdir", return_value=False):
            assert _process_repo(self._repo(), mock_logger) is False
            mock_logger.error.assert_called_once()

    def test_not_a_git_repo_returns_false(self, mock_logger):
        with patch("services.git_sync.os.path.isdir", return_value=True), \
             patch("services.git_sync.os.path.exists", return_value=False):
            assert _process_repo(self._repo(), mock_logger) is False
            mock_logger.error.assert_called_once()

    def test_fetch_failure_returns_false(self, mock_logger):
        with patch("services.git_sync.os.path.isdir", return_value=True), \
             patch("services.git_sync.os.path.exists", return_value=True), \
             patch("services.git_sync.run_command", return_value=(1, "", "fetch error")):
            assert _process_repo(self._repo(), mock_logger) is False

    def test_clean_pull_ff_only(self, mock_logger):
        """Clean working tree: fetch succeeds, pull --ff-only succeeds."""
        call_results = [
            (0, "", ""),       # fetch
            (0, "", ""),       # status --porcelain (clean)
            (0, "", ""),       # pull --ff-only
        ]
        with patch("services.git_sync.os.path.isdir", return_value=True), \
             patch("services.git_sync.os.path.exists", return_value=True), \
             patch("services.git_sync.run_command", side_effect=call_results):
            assert _process_repo(self._repo(), mock_logger) is True

    def test_dirty_tree_auto_commit_stash_pull_pop(self, mock_logger):
        """Dirty tree + auto_commit: stash, pull, pop."""
        call_results = [
            (0, "", ""),             # fetch
            (0, "M file.txt\n", ""), # status --porcelain (dirty)
            (0, "", ""),             # stash push
            (0, "", ""),             # pull --ff-only
            (0, "", ""),             # stash pop
        ]
        repo = self._repo(auto_commit=True)
        with patch("services.git_sync.os.path.isdir", return_value=True), \
             patch("services.git_sync.os.path.exists", return_value=True), \
             patch("services.git_sync.run_command", side_effect=call_results):
            assert _process_repo(repo, mock_logger) is True

    def test_dirty_tree_without_auto_commit_skips_pull(self, mock_logger):
        """Dirty tree + auto_commit=False: skip pull with warning."""
        call_results = [
            (0, "", ""),             # fetch
            (0, "M file.txt\n", ""), # status --porcelain (dirty)
        ]
        repo = self._repo(auto_commit=False, push=False)
        with patch("services.git_sync.os.path.isdir", return_value=True), \
             patch("services.git_sync.os.path.exists", return_value=True), \
             patch("services.git_sync.run_command", side_effect=call_results):
            assert _process_repo(repo, mock_logger) is True
            mock_logger.warning.assert_called_once()
            assert "dirty" in mock_logger.warning.call_args[0][0].lower() or \
                   "dirty" in str(mock_logger.warning.call_args)

    def test_auto_commit_and_push_when_dirty(self, mock_logger):
        """push=True, auto_commit=True, tree dirty after pull: add, commit, push."""
        call_results = [
            (0, "", ""),             # fetch
            (0, "", ""),             # status --porcelain (clean — no stash needed)
            (0, "", ""),             # pull --ff-only
            (0, "M f\n", ""),        # _is_dirty check for auto-commit
            (0, "", ""),             # git add -A
            (0, "", ""),             # git commit
            (0, "1\n", ""),          # rev-list count (ahead by 1)
            (0, "", ""),             # git push
        ]
        repo = self._repo(push=True, auto_commit=True)
        with patch("services.git_sync.os.path.isdir", return_value=True), \
             patch("services.git_sync.os.path.exists", return_value=True), \
             patch("services.git_sync.run_command", side_effect=call_results):
            assert _process_repo(repo, mock_logger) is True

    def test_push_when_ahead(self, mock_logger):
        """push=True, clean tree, ahead of remote: push."""
        call_results = [
            (0, "", ""),       # fetch
            (0, "", ""),       # status --porcelain (clean)
            (0, "", ""),       # pull --ff-only
            (0, "", ""),       # _is_dirty for auto_commit check (clean)
            (0, "2\n", ""),    # rev-list count (ahead by 2)
            (0, "", ""),       # git push
        ]
        repo = self._repo(push=True, auto_commit=True)
        with patch("services.git_sync.os.path.isdir", return_value=True), \
             patch("services.git_sync.os.path.exists", return_value=True), \
             patch("services.git_sync.run_command", side_effect=call_results):
            assert _process_repo(repo, mock_logger) is True

    def test_no_push_when_not_ahead(self, mock_logger):
        """push=True but not ahead of remote: no push attempted."""
        call_results = [
            (0, "", ""),       # fetch
            (0, "", ""),       # status --porcelain (clean)
            (0, "", ""),       # pull --ff-only
            (0, "", ""),       # _is_dirty for auto_commit check (clean)
            (0, "0\n", ""),    # rev-list count (not ahead)
        ]
        repo = self._repo(push=True, auto_commit=True)
        with patch("services.git_sync.os.path.isdir", return_value=True), \
             patch("services.git_sync.os.path.exists", return_value=True), \
             patch("services.git_sync.run_command", side_effect=call_results) as mock_rc:
            assert _process_repo(repo, mock_logger) is True
            # Should NOT have a 6th call (push)
            assert mock_rc.call_count == 5
