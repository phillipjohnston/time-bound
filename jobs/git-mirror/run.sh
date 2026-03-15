#!/bin/bash
set -euo pipefail
cd /Users/buildbot/src/git-mirror
exec venv/bin/python -m git_mirror.cli
