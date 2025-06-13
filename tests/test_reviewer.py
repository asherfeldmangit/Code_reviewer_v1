import builtins
import types
from pathlib import Path
import sys

import tempfile
import textwrap

import pytest

# Import the module under test
import importlib

# Ensure project root is on path so `import scripts` works when running tests from any location.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ai_reviewer = importlib.import_module("scripts.ai_code_reviewer")


def test_collect_repo_context_excludes(tmp_path: Path):
    """collect_repo_context should skip excluded dirs and non-text files."""
    # Create structure
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "dummy.pyc").write_bytes(b"binary")

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "readme.md").write_text("# docs\n")

    # Create binary image file at root
    (tmp_path / "logo.png").write_bytes(b"binarydata")

    context = ai_reviewer.collect_repo_context(tmp_path, max_chars=10_000)

    # The context should include docs/readme.md but not logo.png nor __pycache__
    assert "docs/readme.md" in context
    assert "logo.png" not in context
    assert "__pycache__" not in context


def test_build_messages_structure():
    diff = "diff --git a/foo.py b/foo.py\n+print('hi')"
    context = "# File: foo.py\nprint('hi')"
    messages = ai_reviewer.build_messages(diff, context)

    # Should return a list with system and user message
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert diff in messages[1]["content"]
    assert context in messages[1]["content"]


def test_get_commit_diff(monkeypatch: pytest.MonkeyPatch):
    """get_commit_diff should surface diff from git show wrapper."""
    fake_diff = "diff --git a/x b/x\n"

    def fake_run(cmd, cwd=None):  # noqa: D401
        assert cmd[:2] == ["git", "show"]
        return fake_diff

    monkeypatch.setattr(ai_reviewer, "run", fake_run)

    result = ai_reviewer.get_commit_diff("HEAD")
    assert result == fake_diff 