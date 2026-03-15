"""Code review service using Claude CLI.

Runs Claude against configured codebases on scheduled days,
saving reports to files or creating GitHub issues/PRs.
"""

import os
import shutil
from datetime import datetime

from services.base import run_command, today_weekday


def _output_to_file(review_text, codebase, config, logger):
    """Write review to reports/{name}/{date}-review.md."""
    reports_dir = config.get("reports_dir", "reports")
    name = codebase["name"]
    output_dir = os.path.join(reports_dir, name)
    os.makedirs(output_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = os.path.join(output_dir, f"{date_str}-review.md")

    with open(output_path, "w") as f:
        f.write(f"# Code Review: {name}\n")
        f.write(f"**Date**: {date_str}\n")
        f.write(f"**Path**: {codebase['path']}\n\n")
        f.write(review_text)

    logger.info("Review written to %s", output_path)
    return output_path


def _output_to_gh_issue(review_text, codebase, logger):
    """Create a GitHub issue with the review."""
    if not shutil.which("gh"):
        logger.warning("gh CLI not found, falling back to file output")
        return None

    name = codebase["name"]
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = f"Code Review: {name} ({date_str})"

    rc, stdout, stderr = run_command(
        ["gh", "issue", "create", "--title", title, "--body", review_text],
        cwd=codebase["path"],
        logger=logger,
    )
    if rc != 0:
        logger.error("Failed to create issue: %s", stderr.strip())
        return None

    issue_url = stdout.strip()
    logger.info("Created issue: %s", issue_url)
    return issue_url


def _output_to_gh_pr(review_text, codebase, logger):
    """Create a branch, commit the review file, push, and open a PR."""
    if not shutil.which("gh"):
        logger.warning("gh CLI not found, falling back to file output")
        return None

    path = codebase["path"]
    name = codebase["name"]
    date_str = datetime.now().strftime("%Y-%m-%d")
    branch_name = f"review/{name}-{date_str}"

    # Create and switch to branch
    rc, _, stderr = run_command(
        ["git", "checkout", "-b", branch_name],
        cwd=path,
        logger=logger,
    )
    if rc != 0:
        logger.error("Failed to create branch: %s", stderr.strip())
        return None

    # Write review file
    review_dir = os.path.join(path, "reviews")
    os.makedirs(review_dir, exist_ok=True)
    review_path = os.path.join(review_dir, f"{date_str}-review.md")

    with open(review_path, "w") as f:
        f.write(f"# Code Review: {name}\n")
        f.write(f"**Date**: {date_str}\n\n")
        f.write(review_text)

    # Commit and push
    run_command(["git", "add", review_path], cwd=path, logger=logger)
    rc, _, stderr = run_command(
        ["git", "commit", "-m", f"Add code review for {date_str}"],
        cwd=path,
        logger=logger,
    )
    if rc != 0:
        logger.error("Commit failed: %s", stderr.strip())
        run_command(["git", "checkout", "-"], cwd=path, logger=logger)
        return None

    rc, _, stderr = run_command(
        ["git", "push", "-u", "origin", branch_name],
        cwd=path,
        logger=logger,
    )
    if rc != 0:
        logger.error("Push failed: %s", stderr.strip())
        run_command(["git", "checkout", "-"], cwd=path, logger=logger)
        return None

    # Create PR
    rc, stdout, stderr = run_command(
        [
            "gh", "pr", "create",
            "--title", f"Code Review: {name} ({date_str})",
            "--body", f"Automated code review for {name}.\n\n{review_text[:2000]}",
        ],
        cwd=path,
        logger=logger,
    )

    # Switch back to previous branch
    run_command(["git", "checkout", "-"], cwd=path, logger=logger)

    if rc != 0:
        logger.error("PR creation failed: %s", stderr.strip())
        return None

    pr_url = stdout.strip()
    logger.info("Created PR: %s", pr_url)
    return pr_url


def _review_codebase(codebase, config, logger):
    """Run Claude CLI against a codebase and handle output."""
    path = codebase["path"]
    name = codebase["name"]
    claude_path = config.get("claude_path", "claude")
    review_focus = codebase.get("review_focus", "Review this codebase for code quality and potential issues.")
    output_method = codebase.get("output_method", "file")

    if not os.path.isdir(path):
        logger.error("Codebase path does not exist: %s", path)
        return False

    logger.info("Reviewing %s (%s)", name, path)

    # Run Claude CLI with 30 minute timeout
    rc, stdout, stderr = run_command(
        [claude_path, "-p", review_focus, "--output-format", "text"],
        cwd=path,
        timeout=1800,
        logger=logger,
    )

    if rc != 0:
        logger.error("Claude review failed for %s: %s", name, stderr.strip())
        return False

    review_text = stdout

    if not review_text.strip():
        logger.warning("Empty review output for %s", name)
        return False

    # Route to output method
    if output_method == "gh-issue":
        result = _output_to_gh_issue(review_text, codebase, logger)
        if result is None:
            # Fallback to file
            _output_to_file(review_text, codebase, config, logger)
    elif output_method == "gh-pr":
        result = _output_to_gh_pr(review_text, codebase, logger)
        if result is None:
            _output_to_file(review_text, codebase, config, logger)
    else:
        _output_to_file(review_text, codebase, config, logger)

    return True


def run(config, global_config, logger):
    """Entry point called by runner.py."""
    codebases = config.get("codebases", [])
    if not codebases:
        logger.warning("No codebases configured for code-review")
        return

    weekday = today_weekday()
    logger.info("Today is weekday %d (0=Mon, 6=Sun)", weekday)

    # Filter to codebases scheduled for today
    scheduled = [
        cb for cb in codebases
        if weekday in cb.get("days", [])
    ]

    if not scheduled:
        logger.info("No codebases scheduled for review today")
        return

    logger.info("Reviewing %d codebase(s)", len(scheduled))

    results = {}
    for codebase in scheduled:
        name = codebase.get("name", "unknown")
        try:
            results[name] = _review_codebase(codebase, config, logger)
        except Exception:
            logger.exception("Unexpected error reviewing %s", name)
            results[name] = False

    succeeded = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    logger.info("Code review complete: %d succeeded, %d failed", succeeded, failed)
