"""Property-based tests for the tree_scanner module.

**Validates: Requirements 2.1, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 4.1, 4.4, 4.5, 5.2, 5.3, 6.1, 6.2, 6.3, 9.1, 9.2**
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from sprintmaster.tree_scanner import (
    DEFAULT_IGNORE_DIRS,
    DEFAULT_IGNORE_FILES,
    scan,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Safe characters for filesystem names (lowercase alpha only to avoid platform issues)
_safe_name = st.text(
    alphabet=st.characters(whitelist_categories=("Ll",)),
    min_size=2,
    max_size=8,
)

# Strategy for a list of unique directory names
_dir_names = st.lists(_safe_name, min_size=1, max_size=4, unique=True)

# Strategy for a list of unique file names (with extension)
_file_names = st.lists(
    _safe_name.map(lambda s: f"{s}.txt"),
    min_size=1,
    max_size=4,
    unique=True,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _parse_entry_names(tree_output: str) -> list[str]:
    """Extract entry names from tree output lines (skipping the root line).

    Returns names without trailing '/' for directories.
    """
    names: list[str] = []
    lines = tree_output.split("\n")
    for line in lines[1:]:  # skip root line
        # Skip truncation indicator
        if line.startswith("... (truncated"):
            continue
        # Extract the name after the connector
        match = re.search(r"[├└]── (.+)$", line)
        if match:
            name = match.group(1)
            # Remove trailing / for directories
            if name.endswith("/"):
                name = name[:-1]
            names.append(name)
    return names


def _make_temp_dir() -> Path:
    """Create a fresh temporary directory for each hypothesis example."""
    return Path(tempfile.mkdtemp())


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestCompletenessProperty:
    """Property 1: Completeness — no silent omissions.

    For any directory tree and depth limit, every file and directory within
    the depth limit that does not match any ignore pattern SHALL appear in
    the Tree_Representation output.

    **Validates: Requirements 2.1, 9.2**
    """

    # Feature: codebase-context, Property 1: Completeness — no silent omissions

    @given(
        dirs=_dir_names,
        files=_file_names,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_entries_within_depth_appear_in_output(self, dirs: list[str], files: list[str], tmp_path: Path) -> None:
        """Every non-ignored entry within depth limit appears in tree output."""
        root = tmp_path / "root"
        root.mkdir(exist_ok=True)

        for dname in dirs:
            (root / dname).mkdir(exist_ok=True)
        for fname in files:
            (root / fname).write_text("x", encoding="utf-8")

        result = scan(root, depth_limit=2, max_chars=50_000)
        output_names = _parse_entry_names(result.tree)

        for dname in dirs:
            assert dname in output_names, f"Directory '{dname}' missing from output"
        for fname in files:
            assert fname in output_names, f"File '{fname}' missing from output"


class TestSoundnessProperty:
    """Property 2: Soundness — no fabricated entries.

    For any directory scanned, every name in the Tree_Representation
    SHALL correspond to an actual entry on disk.

    **Validates: Requirements 9.1**
    """

    # Feature: codebase-context, Property 2: Soundness — no fabricated entries

    @given(
        dirs=st.lists(_safe_name, min_size=0, max_size=4, unique=True),
        files=st.lists(
            _safe_name.map(lambda s: f"{s}.txt"),
            min_size=0,
            max_size=4,
            unique=True,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_output_entries_exist_on_disk(self, dirs: list[str], files: list[str], tmp_path: Path) -> None:
        """Every entry in tree output corresponds to a real file/dir on disk."""
        root = tmp_path / "root"
        root.mkdir(exist_ok=True)

        for dname in dirs:
            (root / dname).mkdir(exist_ok=True)
        for fname in files:
            (root / fname).write_text("x", encoding="utf-8")

        result = scan(root, depth_limit=2, max_chars=50_000)
        output_names = _parse_entry_names(result.tree)

        # Collect all real entry names on disk (recursive)
        real_names: set[str] = set()

        def _collect(d: Path) -> None:
            try:
                for child in d.iterdir():
                    real_names.add(child.name)
                    if child.is_dir():
                        _collect(child)
            except (PermissionError, OSError):
                pass

        _collect(root)

        for name in output_names:
            assert name in real_names, f"Entry '{name}' in output but not on disk"


class TestSortingInvariantProperty:
    """Property 3: Sorting invariant.

    For each directory level, directories appear before files and both
    groups are alphabetically sorted.

    **Validates: Requirements 2.3**
    """

    # Feature: codebase-context, Property 3: Sorting invariant

    @given(
        dirs=st.lists(_safe_name, min_size=2, max_size=6, unique=True),
        files=st.lists(
            _safe_name.map(lambda s: f"{s}.txt"),
            min_size=2,
            max_size=6,
            unique=True,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_dirs_before_files_both_sorted(self, dirs: list[str], files: list[str], tmp_path: Path) -> None:
        """Directories appear before files, both sorted alphabetically at each level."""
        root = tmp_path / "root"
        root.mkdir(exist_ok=True)

        for dname in dirs:
            (root / dname).mkdir(exist_ok=True)
        for fname in files:
            (root / fname).write_text("x", encoding="utf-8")

        result = scan(root, depth_limit=2, max_chars=50_000)
        lines = result.tree.split("\n")

        # Parse first-level entries (lines with single connector, no nested prefix)
        first_level_dirs: list[str] = []
        first_level_files: list[str] = []

        for line in lines[1:]:  # skip root
            if line.startswith("... (truncated"):
                continue
            # First-level entries have connector at the start (no │ prefix)
            match = re.match(r"^[├└]── (.+)$", line)
            if match:
                name = match.group(1)
                if name.endswith("/"):
                    first_level_dirs.append(name[:-1])
                else:
                    first_level_files.append(name)

        # Verify dirs come before files in the output order
        all_first_level: list[str] = []
        for line in lines[1:]:
            if line.startswith("... (truncated"):
                continue
            match = re.match(r"^[├└]── (.+)$", line)
            if match:
                all_first_level.append(match.group(1).rstrip("/"))

        expected_order = sorted(first_level_dirs) + sorted(first_level_files)
        # The output list should match dirs-first-then-files, each sorted
        assert first_level_dirs == sorted(first_level_dirs), "Dirs should be alphabetically sorted"
        assert first_level_files == sorted(first_level_files), "Files should be alphabetically sorted"
        assert all_first_level == expected_order, "Dirs should precede files in output"


class TestRootNameFirstLineProperty:
    """Property 4: Root name as first line.

    The first line of the Tree_Representation SHALL be exactly the
    root directory name (basename of the scanned path).

    **Validates: Requirements 2.5**
    """

    # Feature: codebase-context, Property 4: Root name as first line

    @given(
        root_name=_safe_name,
        files=st.lists(
            _safe_name.map(lambda s: f"{s}.txt"),
            min_size=0,
            max_size=3,
            unique=True,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_first_line_is_root_name(self, root_name: str, files: list[str], tmp_path: Path) -> None:
        """First line of output equals the basename of the scanned root."""
        root_dir = tmp_path / root_name
        root_dir.mkdir(exist_ok=True)
        for fname in files:
            (root_dir / fname).write_text("x", encoding="utf-8")

        result = scan(root_dir, depth_limit=2, max_chars=50_000)
        first_line = result.tree.split("\n")[0]

        assert first_line == root_name, f"Expected '{root_name}', got '{first_line}'"


class TestNoFileContentsLeakedProperty:
    """Property 5: No file contents leaked.

    The Tree_Representation SHALL not contain any substring matching
    any file's content (only names appear).

    **Validates: Requirements 2.4**
    """

    # Feature: codebase-context, Property 5: No file contents leaked

    @given(
        file_content=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=15,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_file_content_not_in_tree_output(self, file_content: str, tmp_path: Path) -> None:
        """File contents never appear in the tree output."""
        root = tmp_path / "proj"
        root.mkdir(exist_ok=True)

        # Ensure content is meaningfully distinct from any filename
        assume(len(file_content.strip()) >= 15)

        test_file = root / "datafile.txt"
        test_file.write_text(file_content, encoding="utf-8")

        result = scan(root, depth_limit=2, max_chars=50_000)

        assert file_content not in result.tree, "File content leaked into tree output"


class TestDefaultIgnoreExclusionProperty:
    """Property 6: Default ignore exclusion.

    Entries matching default ignore patterns SHALL NOT appear
    in the Tree_Representation.

    **Validates: Requirements 3.1, 3.2, 3.3**
    """

    # Feature: codebase-context, Property 6: Default ignore exclusion

    @given(
        ignored_dir=st.sampled_from([
            d for d in DEFAULT_IGNORE_DIRS if "/" not in d
        ]),
        visible_file=_safe_name.map(lambda s: f"{s}.txt"),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_default_ignored_dirs_excluded(self, ignored_dir: str, visible_file: str, tmp_path: Path) -> None:
        """Directories matching default ignore patterns are excluded from output."""
        root = tmp_path / "proj"
        root.mkdir(exist_ok=True)

        # Create an ignored directory with content inside
        ignored_path = root / ignored_dir
        ignored_path.mkdir(exist_ok=True)
        (ignored_path / "inner.txt").write_text("hidden", encoding="utf-8")

        # Create a visible file
        (root / visible_file).write_text("visible", encoding="utf-8")

        result = scan(root, depth_limit=4, max_chars=50_000)
        output_names = _parse_entry_names(result.tree)

        assert ignored_dir not in output_names, f"Ignored dir '{ignored_dir}' should not appear"
        assert "inner" not in result.tree, "Contents of ignored dir should not appear"
        assert visible_file in output_names, f"Visible file '{visible_file}' should appear"


class TestGitignoreCombinedExclusionProperty:
    """Property 7: Gitignore combined exclusion.

    Entries matching gitignore patterns SHALL be excluded from output,
    and this exclusion is applied in addition to default patterns.

    **Validates: Requirements 4.1, 4.4**
    """

    # Feature: codebase-context, Property 7: Gitignore combined exclusion

    @given(
        gitignored_name=_safe_name,
        visible_name=_safe_name,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_gitignore_patterns_exclude_entries(self, gitignored_name: str, visible_name: str, tmp_path: Path) -> None:
        """Entries matching .gitignore patterns are excluded alongside defaults."""
        # Ensure the names are different
        assume(gitignored_name != visible_name)
        assume(f"{gitignored_name}.log" != f"{visible_name}.txt")

        root = tmp_path / "proj"
        root.mkdir(exist_ok=True)

        # Create .gitignore that excludes the target file
        gitignore_content = f"{gitignored_name}.log\n"
        (root / ".gitignore").write_text(gitignore_content, encoding="utf-8")

        # Create the file that should be ignored by gitignore
        (root / f"{gitignored_name}.log").write_text("ignored", encoding="utf-8")

        # Create a visible file
        (root / f"{visible_name}.txt").write_text("visible", encoding="utf-8")

        # Also create a default-ignored directory to verify combined behavior
        (root / "node_modules").mkdir(exist_ok=True)
        (root / "node_modules" / "pkg.json").write_text("{}", encoding="utf-8")

        result = scan(root, depth_limit=4, max_chars=50_000)
        output_names = _parse_entry_names(result.tree)

        assert f"{gitignored_name}.log" not in output_names, "Gitignored file should be excluded"
        assert "node_modules" not in output_names, "Default ignored dir should still be excluded"
        assert f"{visible_name}.txt" in output_names, "Non-ignored file should appear"


class TestGitignoreCommentLinesProperty:
    """Property 8: Gitignore comment lines are non-matching.

    Lines starting with '#' in .gitignore SHALL NOT cause any file
    or directory to be excluded.

    **Validates: Requirements 4.5**
    """

    # Feature: codebase-context, Property 8: Gitignore comment lines are non-matching

    @given(
        file_name=_safe_name.map(lambda s: f"{s}.txt"),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_comment_lines_do_not_exclude(self, file_name: str, tmp_path: Path) -> None:
        """Comment lines in .gitignore do not cause exclusions."""
        root = tmp_path / "proj"
        root.mkdir(exist_ok=True)

        # Create .gitignore with the filename as a comment (should NOT exclude it)
        gitignore_content = f"# {file_name}\n# some other comment\n"
        (root / ".gitignore").write_text(gitignore_content, encoding="utf-8")

        # Create the file that the comment mentions
        (root / file_name).write_text("content", encoding="utf-8")

        result = scan(root, depth_limit=4, max_chars=50_000)
        output_names = _parse_entry_names(result.tree)

        assert file_name in output_names, (
            f"File '{file_name}' should appear (comment line should not exclude it)"
        )


class TestDepthLimitingProperty:
    """Property 9: Depth limiting.

    No entries beyond depth N SHALL appear, and directories at depth N
    SHALL appear by name but their contents are not listed.

    **Validates: Requirements 5.2, 5.3**
    """

    # Feature: codebase-context, Property 9: Depth limiting

    @given(
        depth_limit=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_entries_beyond_depth_limit(self, depth_limit: int, tmp_path: Path) -> None:
        """No entries beyond depth N appear; dirs at depth N show name only."""
        root = tmp_path / f"proj_{depth_limit}"
        root.mkdir(exist_ok=True)

        # Create a tree of known depth 5:
        # depth 1: root/level1/
        # depth 2: root/level1/level2/
        # depth 3: root/level1/level2/level3/
        # depth 4: root/level1/level2/level3/level4/
        # depth 5: root/level1/level2/level3/level4/level5/
        level_names = ["level1", "level2", "level3", "level4", "level5"]
        current = root
        for name in level_names:
            current = current / name
            current.mkdir(exist_ok=True)
            # Add a marker file at each level
            (current / f"file_at_{name}.txt").write_text("x", encoding="utf-8")

        result = scan(root, depth_limit=depth_limit, max_chars=50_000)
        output_names = _parse_entry_names(result.tree)

        # Directories and files at depth <= depth_limit should appear
        for i in range(min(depth_limit, len(level_names))):
            dir_name = level_names[i]
            assert dir_name in output_names, (
                f"Dir '{dir_name}' at depth {i+1} should appear (limit={depth_limit})"
            )

        # Files beyond depth_limit should NOT appear
        for i in range(depth_limit, len(level_names)):
            file_name = f"file_at_{level_names[i]}.txt"
            assert file_name not in output_names, (
                f"File '{file_name}' at depth {i+1} should not appear (limit={depth_limit})"
            )

        # The directory at exactly depth_limit should appear (its name is shown)
        # but its CONTENTS (the file inside + sub-dir) should NOT appear
        at_limit_dir = level_names[depth_limit - 1]
        assert at_limit_dir in output_names, (
            f"Dir '{at_limit_dir}' at depth {depth_limit} should appear"
        )
        # The file inside that directory is at depth depth_limit (inside it),
        # so the file at that level IS shown (it's within the dir at depth_limit).
        # Actually: _walk is called with depth=1 for root's children.
        # level1 is at depth 1. _walk recurses into level1 with depth=2.
        # If depth_limit=1, _walk won't recurse into level1 because depth(1) >= depth_limit(1).
        # Wait: the code checks `if depth < depth_limit` before recursing.
        # So at depth=1, if depth_limit=1, it does NOT recurse. level1/ is shown but not entered.
        # That means file_at_level1.txt (inside level1) should NOT appear when depth_limit=1.
        file_inside_limit_dir = f"file_at_{at_limit_dir}.txt"
        assert file_inside_limit_dir not in output_names, (
            f"File '{file_inside_limit_dir}' inside dir at depth limit should not appear"
        )


class TestTruncationCorrectnessProperty:
    """Property 10: Truncation correctness.

    When output exceeds max_chars, it SHALL be truncated at the last
    newline before the limit (no partial lines) with a truncation indicator.

    **Validates: Requirements 6.1, 6.2, 6.3**
    """

    # Feature: codebase-context, Property 10: Truncation correctness

    @given(
        num_files=st.integers(min_value=50, max_value=80),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_truncation_at_line_boundary_with_indicator(self, num_files: int, tmp_path: Path) -> None:
        """When truncated, output ends at a line boundary with truncation indicator."""
        root = tmp_path / "proj"
        root.mkdir(exist_ok=True)

        # Create many files to force truncation with small max_chars
        for i in range(num_files):
            (root / f"file_{i:04d}_longname.txt").write_text("x", encoding="utf-8")

        # Use a small max_chars to guarantee truncation
        max_chars = 300
        result = scan(root, depth_limit=4, max_chars=max_chars)

        # With this many files and small max_chars, truncation should occur
        assert result.truncated, "Expected truncation with many files and small max_chars"

        # Output should end with the truncation indicator
        assert "... (truncated," in result.tree, "Truncation indicator missing"
        assert "entries not shown)" in result.tree, "Truncation indicator incomplete"

        # The content before the truncation indicator should not exceed max_chars
        lines = result.tree.split("\n")
        # Last line is the indicator
        content_lines = lines[:-1]
        content_without_indicator = "\n".join(content_lines)
        assert len(content_without_indicator) <= max_chars, (
            f"Content before indicator ({len(content_without_indicator)}) exceeds max_chars ({max_chars})"
        )

        # No partial lines — each line should be a valid tree line or root name
        for line in content_lines:
            if line == content_lines[0]:
                continue  # root line has no connector
            # Each non-root line should contain a connector
            assert "── " in line, f"Partial or invalid line detected: '{line}'"

        # truncated_count should be positive
        assert result.truncated_count > 0, "truncated_count should be > 0 when truncated"
