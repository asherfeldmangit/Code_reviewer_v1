#!/usr/bin/env bash
# Installs the version-controlled Git hooks.

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

echo "[AI Reviewer] Installing git hooks..."

git config core.hooksPath .githooks
chmod +x .githooks/*

echo "[AI Reviewer] Hooks installed." 