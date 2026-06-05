#!/bin/bash
# Install pre-commit hook (clone 後跑一次)
# Usage: bash scripts/hooks/install.sh

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ln -sf "$REPO_ROOT/scripts/hooks/pre-commit" "$REPO_ROOT/.git/hooks/pre-commit"
chmod +x "$REPO_ROOT/.git/hooks/pre-commit"
echo "✓ pre-commit hook 已安裝 (symlink to scripts/hooks/pre-commit)"
echo "  Bypass: git commit --no-verify"
