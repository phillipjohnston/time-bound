#!/usr/bin/env bash
# brew-update: Update and upgrade Homebrew packages.
# Runs as a bash service via runner.py (type: bash).

set -euo pipefail

echo "=== brew update ==="
brew update

echo "=== brew upgrade ==="
brew upgrade

echo "=== brew cleanup ==="
brew cleanup

echo "brew-update complete"
