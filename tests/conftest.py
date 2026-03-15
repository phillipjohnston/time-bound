"""Shared fixtures for time-bound tests."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def global_config(tmp_path):
    """Sample global config pointing at a tmpdir for logs."""
    return {
        "project_root": str(tmp_path),
        "log_dir": "logs",
        "label_prefix": "com.test.time-bound",
        "python_path": "/usr/bin/python3",
        "path": "/usr/bin:/bin",
    }


@pytest.fixture
def mock_logger():
    """A MagicMock standing in for a logging.Logger."""
    return MagicMock()


@pytest.fixture
def sample_repo_config():
    """A typical git-sync repo config dict."""
    return {
        "path": "/tmp/fake-repo",
        "remote": "origin",
        "branch": "main",
        "pull": True,
        "push": False,
        "auto_commit": False,
    }


@pytest.fixture
def sample_codebase_config():
    """A typical code-review codebase config dict."""
    return {
        "path": "/tmp/fake-project",
        "name": "fake-project",
        "review_focus": "Review for quality.",
        "days": [0, 2, 4],
        "output_method": "file",
    }
