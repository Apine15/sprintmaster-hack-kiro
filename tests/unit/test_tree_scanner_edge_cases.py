"""Unit tests for tree_scanner edge cases.

Covers: circular symlinks, missing .gitignore, empty lines in .gitignore,
and permission-denied directories.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from sprintmaster.tree_scanner import scan


class TestCircularSymlink:
    """Tests that circular symlinks are skipped gracefully (Req 2.6)."""

    @pytest.mark.skipif(
        os.name == "nt",
        reason="Symlink creation may require elevated privileges on Windows",
    )
    def test_circular_symlink_is_skipped(self, tmp_path: Path):
        """A symlink pointing back to a parent directory does not cause infinite recursion."""
        # Create: root/subdir/link -> root
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        link = subdir / "link_to_root"
        link.symlink_to(tmp_path, target_is_directory=True)

        # Also add a regular file so we can verify the scan produces output
        (tmp_path / "hello.txt").write_text("hi")

        result = scan(tmp_path, depth_limit=4)

        # Scan completes without error
        assert result.tree is not None
        assert "hello.txt" in result.tree
        # The symlink should not cause the tree to recurse infinitely
        # The result should be finite and not contain repeated patterns
        assert result.total_entries >= 2  # subdir + hello.txt at minimum


class TestGitignoreNotPresent:
    """Tests that missing .gitignore falls back to defaults only (Req 4.3)."""

    def test_no_gitignore_uses_default_patterns(self, tmp_path: Path):
        """Without .gitignore, default ignore patterns are still applied."""
        # Create entries that should be excluded by default patterns
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "module.cpython-311.pyc").write_text("")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main")

        # Create a regular file that should appear
        (tmp_path / "main.py").write_text("print('hello')")

        # No .gitignore file exists
        assert not (tmp_path / ".gitignore").exists()

        result = scan(tmp_path, depth_limit=4)

        # Default-ignored directories should NOT appear
        assert "__pycache__" not in result.tree
        assert ".git" not in result.tree

        # Regular files should appear
        assert "main.py" in result.tree


class TestEmptyLinesInGitignore:
    """Tests that empty lines in .gitignore don't cause errors (Req 4.6)."""

    def test_gitignore_with_empty_and_comment_lines(self, tmp_path: Path):
        """A .gitignore with empty lines, comments, and valid patterns works correctly."""
        # Create .gitignore with mixed content
        gitignore_content = "\n".join([
            "",
            "# This is a comment",
            "",
            "*.log",
            "",
            "# Another comment",
            "temp/",
            "",
            "",
        ])
        (tmp_path / ".gitignore").write_text(gitignore_content)

        # Create files that match valid patterns
        (tmp_path / "debug.log").write_text("log data")
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        (temp_dir / "cache.txt").write_text("cached")

        # Create files that should NOT be excluded
        (tmp_path / "app.py").write_text("code")
        (tmp_path / "README.md").write_text("readme")

        result = scan(tmp_path, depth_limit=4)

        # Scan completes without errors
        assert result.tree is not None

        # Files matching valid patterns are excluded
        assert "debug.log" not in result.tree
        assert "temp" not in result.tree

        # Files not matching any pattern are included
        assert "app.py" in result.tree
        assert "README.md" in result.tree


class TestPermissionDeniedDirectory:
    """Tests that a permission-denied directory is skipped gracefully (Req 2.6, error handling)."""

    def test_permission_denied_is_skipped(self, tmp_path: Path):
        """A directory that raises PermissionError when listed is skipped."""
        # Create a normal directory with a file
        (tmp_path / "accessible").mkdir()
        (tmp_path / "accessible" / "file.txt").write_text("ok")

        # Create the restricted directory
        restricted = tmp_path / "restricted"
        restricted.mkdir()

        # Mock iterdir to raise PermissionError for the restricted directory
        original_iterdir = Path.iterdir

        def patched_iterdir(self):
            if self == restricted:
                raise PermissionError("Permission denied")
            return original_iterdir(self)

        with patch.object(Path, "iterdir", patched_iterdir):
            result = scan(tmp_path, depth_limit=4)

        # Scan completes without crashing
        assert result.tree is not None

        # The accessible directory and its contents appear
        assert "accessible" in result.tree
        assert "file.txt" in result.tree

        # The restricted directory name appears (it's listed by the parent)
        # but its contents are not listed (iterdir fails inside it)
        assert "restricted" in result.tree
