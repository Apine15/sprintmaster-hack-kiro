"""Tree scanner module for scanning directory structures.

Produces a textual tree representation of a project's file/folder hierarchy,
respecting default ignore patterns and .gitignore rules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pathspec

logger = logging.getLogger(__name__)


# Default directories to ignore during scanning
DEFAULT_IGNORE_DIRS = [
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    "bin/Debug",
    "bin/Release",
    "obj",
]

# Default files to ignore during scanning
DEFAULT_IGNORE_FILES = [
    ".DS_Store",
    "Thumbs.db",
    "*.pyc",
    "*.pyo",
]


@dataclass
class ScanResult:
    """Result of a directory tree scan."""

    tree: str  # The formatted tree representation
    total_entries: int  # Total files + directories found
    truncated: bool  # Whether output was truncated
    truncated_count: int  # Number of entries not shown due to truncation


def _build_default_spec() -> pathspec.PathSpec:
    """Build a PathSpec from the hardcoded default ignore patterns.

    Directories get a trailing slash pattern so pathspec treats them
    as directory-only matches. File patterns are used as-is.
    """
    patterns: list[str] = []

    # Add directory patterns with trailing slash
    for d in DEFAULT_IGNORE_DIRS:
        patterns.append(f"{d}/")

    # Add file patterns as-is
    for f in DEFAULT_IGNORE_FILES:
        patterns.append(f)

    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def _load_gitignore(root: Path) -> pathspec.PathSpec | None:
    """Load and parse the root .gitignore file if it exists.

    Reads only the root-level .gitignore file. Comment lines (starting
    with '#') and empty lines are skipped before passing to pathspec.

    Args:
        root: The root directory that may contain a .gitignore file.

    Returns:
        A PathSpec compiled from the .gitignore patterns, or None if
        the file doesn't exist or can't be read.
    """
    gitignore_path = root / ".gitignore"

    if not gitignore_path.exists():
        return None

    try:
        content = gitignore_path.read_text(encoding="utf-8")
    except (PermissionError, OSError) as exc:
        logger.warning("Could not read .gitignore at %s: %s", gitignore_path, exc)
        return None

    lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        # Skip empty lines and comment lines
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(line)

    if not lines:
        return None

    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def _walk(
    directory: Path,
    root: Path,
    depth: int,
    depth_limit: int,
    ignore_spec: pathspec.PathSpec,
    prefix: str,
    lines: list[str],
    visited: set[str],
) -> int:
    """Recursively walk the directory, appending tree lines.

    Returns the count of entries added.
    """
    # Try to list directory entries; skip if inaccessible
    try:
        entries = sorted(directory.iterdir(), key=lambda e: e.name)
    except (PermissionError, OSError):
        return 0

    # Separate into directories and files, each sorted alphabetically
    dirs = sorted([e for e in entries if e.is_dir()], key=lambda e: e.name)
    files = sorted([e for e in entries if not e.is_dir()], key=lambda e: e.name)
    combined = dirs + files

    # Filter out ignored entries
    visible: list[Path] = []
    for entry in combined:
        rel_path = entry.relative_to(root).as_posix()
        if entry.is_dir():
            rel_path += "/"
        if ignore_spec.match_file(rel_path):
            continue
        visible.append(entry)

    count = 0
    total = len(visible)

    for index, entry in enumerate(visible):
        is_last = index == total - 1
        connector = "└── " if is_last else "├── "
        child_prefix = prefix + ("    " if is_last else "│   ")

        # Check for circular symlinks
        if entry.is_symlink():
            try:
                real_path = str(entry.resolve())
            except (OSError, ValueError):
                continue
            if real_path in visited:
                continue
            visited.add(real_path)

        if entry.is_dir():
            lines.append(f"{prefix}{connector}{entry.name}/")
            count += 1

            if depth < depth_limit:
                count += _walk(
                    entry, root, depth + 1, depth_limit,
                    ignore_spec, child_prefix, lines, visited,
                )
        else:
            lines.append(f"{prefix}{connector}{entry.name}")
            count += 1

    return count


def scan(
    root: Path,
    depth_limit: int = 4,
    extra_ignore_patterns: list[str] | None = None,
    max_chars: int = 10_000,
) -> ScanResult:
    """Scan a directory tree and return a formatted representation.

    Args:
        root: The root directory to scan.
        depth_limit: Maximum depth of recursion (1 = root only).
        extra_ignore_patterns: Additional pathspec patterns to exclude.
        max_chars: Maximum character count before truncation.

    Returns:
        ScanResult with the tree string and metadata.
    """
    # Build combined ignore spec from default patterns, gitignore, and extras
    all_patterns: list[str] = []

    # Default patterns
    default_spec = _build_default_spec()
    all_patterns.extend(default_spec.patterns)

    # Gitignore patterns
    gitignore_spec = _load_gitignore(root)
    if gitignore_spec is not None:
        all_patterns.extend(gitignore_spec.patterns)

    # Extra ignore patterns
    if extra_ignore_patterns:
        extra_spec = pathspec.PathSpec.from_lines("gitwildmatch", extra_ignore_patterns)
        all_patterns.extend(extra_spec.patterns)

    # Combine all patterns into a single PathSpec
    combined_spec = pathspec.PathSpec(all_patterns)

    # Initialize lines with the root directory name as first line
    lines: list[str] = [root.name]

    # Track visited paths to detect circular symlinks
    visited: set[str] = {str(root.resolve())}

    # Walk the tree starting at depth 1 (root is depth 0)
    total_entries = _walk(root, root, 1, depth_limit, combined_spec, "", lines, visited)

    # Join all lines into the full tree string
    tree_string = "\n".join(lines)

    # Apply truncation if needed
    truncated = False
    truncated_count = 0

    if len(tree_string) > max_chars:
        # Find the last newline before the max_chars position
        cut_pos = tree_string.rfind("\n", 0, max_chars)
        if cut_pos == -1:
            # No newline found before limit; truncate at max_chars
            cut_pos = max_chars

        truncated_tree = tree_string[:cut_pos]

        # Count how many lines were cut
        remaining = tree_string[cut_pos:]
        # Lines cut = number of newlines in the remaining portion
        truncated_count = remaining.count("\n")

        # Append truncation indicator
        tree_string = truncated_tree + f"\n... (truncated, {truncated_count} entries not shown)"
        truncated = True

    return ScanResult(
        tree=tree_string,
        total_entries=total_entries,
        truncated=truncated,
        truncated_count=truncated_count,
    )
