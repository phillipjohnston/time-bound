"""Git synchronization service.

Iterates configured repos, pulling and/or pushing changes.
Each repo is processed independently — failures don't block others.
"""

import os

from services.base import run_command


def _is_dirty(path, logger):
    """Check if the working tree has uncommitted changes."""
    rc, stdout, _ = run_command(["git", "status", "--porcelain"], cwd=path, logger=logger)
    return rc == 0 and stdout.strip() != ""


def _is_ahead(path, remote, branch, logger):
    """Check if local branch is ahead of remote."""
    rc, stdout, _ = run_command(
        ["git", "rev-list", f"{remote}/{branch}..HEAD", "--count"],
        cwd=path,
        logger=logger,
    )
    if rc != 0:
        return False
    return int(stdout.strip()) > 0


def _process_repo(repo, logger):
    """Process a single repository."""
    path = repo["path"]
    remote = repo.get("remote", "origin")
    branch = repo.get("branch", "main")
    do_pull = repo.get("pull", True)
    do_push = repo.get("push", False)
    auto_commit = repo.get("auto_commit", False)

    if not os.path.isdir(path):
        logger.error("Repo path does not exist: %s", path)
        return False

    git_dir = os.path.join(path, ".git")
    if not os.path.exists(git_dir):
        logger.error("Not a git repository: %s", path)
        return False

    logger.info("Processing: %s", path)
    success = True

    # Fetch
    rc, _, stderr = run_command(["git", "fetch", remote], cwd=path, logger=logger)
    if rc != 0:
        logger.error("Fetch failed for %s: %s", path, stderr.strip())
        return False

    dirty = _is_dirty(path, logger)

    # Pull
    if do_pull:
        if dirty and auto_commit:
            # Stash, pull, pop
            logger.info("Stashing changes before pull")
            rc, _, _ = run_command(["git", "stash", "push", "-m", "time-bound auto-stash"], cwd=path, logger=logger)
            if rc != 0:
                logger.error("Stash failed for %s", path)
                return False

            rc, _, stderr = run_command(["git", "pull", "--ff-only", remote, branch], cwd=path, logger=logger)
            if rc != 0:
                logger.error("Pull failed for %s: %s", path, stderr.strip())
                # Try to restore stash even if pull failed
                run_command(["git", "stash", "pop"], cwd=path, logger=logger)
                return False

            rc, _, stderr = run_command(["git", "stash", "pop"], cwd=path, logger=logger)
            if rc != 0:
                logger.warning("Stash pop had conflicts for %s: %s", path, stderr.strip())
                success = False

        elif dirty:
            logger.warning("Skipping pull for %s: dirty working tree (auto_commit=false)", path)
        else:
            rc, _, stderr = run_command(["git", "pull", "--ff-only", remote, branch], cwd=path, logger=logger)
            if rc != 0:
                logger.error("Pull failed for %s: %s", path, stderr.strip())
                success = False

    # Auto-commit
    if do_push and auto_commit and _is_dirty(path, logger):
        logger.info("Auto-committing changes in %s", path)
        rc, _, _ = run_command(["git", "add", "-A"], cwd=path, logger=logger)
        if rc != 0:
            logger.error("git add failed for %s", path)
            return False

        rc, _, stderr = run_command(
            ["git", "commit", "-m", "Auto-commit by time-bound git-sync"],
            cwd=path,
            logger=logger,
        )
        if rc != 0:
            logger.error("Commit failed for %s: %s", path, stderr.strip())
            success = False

    # Push
    if do_push and _is_ahead(path, remote, branch, logger):
        logger.info("Pushing %s to %s/%s", path, remote, branch)
        rc, _, stderr = run_command(["git", "push", remote, branch], cwd=path, logger=logger)
        if rc != 0:
            logger.error("Push failed for %s: %s", path, stderr.strip())
            success = False

    return success


def run(config, global_config, logger):
    """Entry point called by runner.py."""
    repos = config.get("repos", [])
    if not repos:
        logger.warning("No repos configured for git-sync")
        return

    results = {}
    for repo in repos:
        name = repo.get("path", "unknown")
        try:
            results[name] = _process_repo(repo, logger)
        except Exception:
            logger.exception("Unexpected error processing %s", name)
            results[name] = False

    succeeded = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    logger.info("Git sync complete: %d succeeded, %d failed", succeeded, failed)
