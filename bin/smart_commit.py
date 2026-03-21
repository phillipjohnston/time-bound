#!/usr/bin/env python3
"""Generate a commit message via Claude CLI and commit staged changes.

Usage:
    python3 bin/smart_commit.py [--stage-all] [--dry-run] [--claude-path PATH] [-v] [path]
"""

import argparse
import os
import shutil
import sys

# Add project root to sys.path before any local imports
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from services.base import run_command

_PROMPT_TEMPLATE = """\
Generate a git commit message for the following staged diff.

Rules:
- Subject line: 50 characters or fewer, imperative mood (e.g. "Fix bug" not "Fixed bug")
- If the change needs more explanation, add a blank line then a concise body (wrap at 72 chars)
- Focus on WHAT changed and WHY, not HOW
- Do not include any attribution, signature, or mention of AI tools
- Output ONLY the commit message text, no markdown fences, no commentary

Diff:
{diff}"""


def find_claude(claude_path_arg=None):
    """Return the path to the claude binary, or None if not found.

    Resolution order: CLI arg → CLAUDE_PATH env var → shutil.which("claude").
    """
    if claude_path_arg:
        return claude_path_arg
    env_path = os.environ.get("CLAUDE_PATH")
    if env_path:
        return env_path
    return shutil.which("claude")


def get_staged_diff(repo_path):
    """Run `git diff --staged` and return (returncode, diff_text, stderr)."""
    return run_command(["git", "diff", "--staged"], cwd=repo_path)


def stage_all(repo_path):
    """Run `git add -A` and return (returncode, stdout, stderr)."""
    return run_command(["git", "add", "-A"], cwd=repo_path)


def build_prompt(diff_text):
    """Return the full prompt string with the diff embedded."""
    return _PROMPT_TEMPLATE.format(diff=diff_text)


def call_claude(claude_bin, prompt, repo_path):
    """Invoke claude and return (returncode, message, stderr)."""
    return run_command(
        [claude_bin, "-p", prompt, "--output-format", "text"],
        cwd=repo_path,
        timeout=120,
    )


def _strip_fences(text):
    """Remove leading/trailing markdown code fences if present."""
    lines = text.strip().splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
        return "\n".join(lines[1:-1])
    return text


def do_commit(repo_path, message):
    """Run `git commit -m <message>` and return (returncode, stdout, stderr)."""
    return run_command(["git", "commit", "-m", message], cwd=repo_path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a commit message via Claude and commit staged changes."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Git repository path (default: current directory)",
    )
    parser.add_argument(
        "--stage-all",
        action="store_true",
        help="Run `git add -A` before generating the commit message",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated message without committing",
    )
    parser.add_argument(
        "--claude-path",
        default=None,
        metavar="PATH",
        help="Path to the claude binary (overrides CLAUDE_PATH env and PATH lookup)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print the diff sent to Claude and the raw response",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    repo_path = os.path.abspath(args.path) if args.path else os.getcwd()

    claude_bin = find_claude(args.claude_path)
    if not claude_bin:
        print(
            "error: claude not found. Install it or set CLAUDE_PATH / --claude-path.",
            file=sys.stderr,
        )
        return 1

    if args.stage_all:
        rc, _, stderr = stage_all(repo_path)
        if rc != 0:
            print(f"error: git add -A failed:\n{stderr.strip()}", file=sys.stderr)
            return 1

    rc, diff, stderr = get_staged_diff(repo_path)
    if rc != 0:
        print(f"error: git diff failed:\n{stderr.strip()}", file=sys.stderr)
        return 1

    if not diff.strip():
        print("No staged changes to commit.")
        return 0

    if args.verbose:
        print("--- diff ---")
        print(diff)
        print("--- end diff ---\n")

    prompt = build_prompt(diff)
    rc, raw_output, stderr = call_claude(claude_bin, prompt, repo_path)
    if rc != 0:
        print(f"error: claude failed:\n{stderr.strip()}", file=sys.stderr)
        return 1

    if args.verbose:
        print("--- claude output ---")
        print(raw_output)
        print("--- end claude output ---\n")

    message = _strip_fences(raw_output).strip()
    if not message:
        print("error: claude returned an empty message.", file=sys.stderr)
        return 1

    print(f"Commit message:\n{message}\n")

    if args.dry_run:
        print("Dry run — not committing.")
        return 0

    rc, stdout, stderr = do_commit(repo_path, message)
    if rc != 0:
        print(f"error: git commit failed:\n{stderr.strip()}", file=sys.stderr)
        return 1

    print("Committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
