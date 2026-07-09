"""Add worktree root to sys.path so `from scripts.X import ...` works in tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
