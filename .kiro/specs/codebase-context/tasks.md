# Implementation Plan: Codebase Context

## Overview

This plan implements the `--codebase` CLI feature for SprintMaster. The approach starts by creating the `tree_scanner` module with its core scanning logic, then extends the CLI with argument parsing and validation, and finally wires the context through the Lambda payload and prompt builder. Property-based tests validate correctness properties throughout.

## Tasks

- [ ] 1. Create tree_scanner module with core data model and ignore patterns
  - [ ] 1.1 Create `sprintmaster/tree_scanner.py` with `ScanResult` dataclass, default ignore constants, and `_build_default_spec()` helper
    - Define `ScanResult` dataclass with fields: `tree`, `total_entries`, `truncated`, `truncated_count`
    - Define `DEFAULT_IGNORE_DIRS` and `DEFAULT_IGNORE_FILES` constants
    - Implement `_build_default_spec()` using `pathspec.PathSpec.from_lines("gitwildmatch", ...)`
    - Add `pathspec` to project dependencies in `pyproject.toml`
    - _Requirements: 3.1, 3.2_

  - [ ] 1.2 Implement `_load_gitignore(root)` helper in `tree_scanner.py`
    - Read root-level `.gitignore` file if it exists
    - Parse with `pathspec.PathSpec.from_lines("gitwildmatch", ...)`
    - Skip comment lines (starting with `#`) and empty lines
    - Return `None` if file doesn't exist or can't be read
    - Handle permission errors gracefully (log warning, return None)
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6_

  - [ ] 1.3 Implement `_walk()` recursive traversal function in `tree_scanner.py`
    - Accept directory, root, current depth, depth_limit, combined ignore_spec, prefix, lines list, and visited set
    - List directory entries, sort directories first then files, both alphabetically
    - Skip entries matching the combined ignore spec (default + gitignore)
    - Detect circular symlinks using `visited` set of resolved real paths
    - Respect depth_limit: show directory name at limit but don't recurse into it
    - Use tree-drawing characters (`├──`, `└──`, `│`) for hierarchy
    - Handle OS permission denied errors by skipping inaccessible directories
    - Return count of entries added
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6, 3.3, 5.2, 5.3_

  - [ ] 1.4 Implement public `scan()` function in `tree_scanner.py`
    - Combine default patterns with gitignore patterns using `_load_gitignore` and `_build_default_spec`
    - Include root directory name as first line
    - Call `_walk()` to build tree lines
    - Apply character-based truncation at last newline before 10,000 char limit
    - Append truncation indicator line when truncated
    - Return populated `ScanResult`
    - _Requirements: 2.5, 6.1, 6.2, 6.3_

- [ ] 2. Checkpoint - Verify tree_scanner module
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Extend CLI with `--codebase` and `--codebase-depth` arguments
  - [ ] 3.1 Add `--codebase` and `--codebase-depth` arguments to `parse_args()` in `sprintmaster/cli.py`
    - Add `--codebase` with `metavar="PATH"`, `default=None`
    - Add `--codebase-depth` with `metavar="N"`, `type=int`, `default=4`
    - _Requirements: 1.1, 5.1_

  - [ ] 3.2 Add validation logic in CLI `main()` for codebase arguments
    - Resolve `--codebase` to absolute path
    - Check path exists — if not, print error to stderr and exit code 1
    - Check path is a directory — if not, print error to stderr and exit code 1
    - Check `--codebase-depth` >= 1 — if not, print error to stderr and exit code 1
    - _Requirements: 1.2, 1.3, 1.4, 5.4_

  - [ ] 3.3 Integrate tree_scanner call and payload injection in CLI `main()`
    - Call `tree_scanner.scan()` when `--codebase` is provided
    - Log truncation warning in verbose mode if result is truncated
    - Add `codebase_context` field to Lambda payload with the tree string
    - Skip codebase_context field when `--codebase` is not provided
    - _Requirements: 1.5, 6.4, 7.1, 7.2, 7.3_

- [ ] 4. Update Lambda handler and prompt builder
  - [ ] 4.1 Update Lambda handler (`lambda/handler.py`) to extract and pass `codebase_context`
    - Extract `codebase_context` from event body (optional field)
    - Pass it to `build_messages()` as keyword argument
    - _Requirements: 8.1_

  - [ ] 4.2 Update prompt builder (`lambda/prompt_builder.py`) to append codebase context section
    - Add `codebase_context: str | None = None` parameter to `build_messages()`
    - When `codebase_context` is provided and non-empty, append `PROJECT STRUCTURE:` header followed by tree in a code block to user message
    - When not provided, leave user message unchanged
    - _Requirements: 8.2, 8.3, 8.4_

- [ ] 5. Checkpoint - Verify end-to-end integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Write property-based tests for tree_scanner
  - [ ]* 6.1 Write property test for completeness (no silent omissions)
    - **Property 1: Completeness — no silent omissions**
    - Use Hypothesis to generate random directory trees with `tmp_path`
    - Verify every non-ignored file/dir within depth limit appears in output
    - **Validates: Requirements 2.1, 9.2**

  - [ ]* 6.2 Write property test for soundness (no fabricated entries)
    - **Property 2: Soundness — no fabricated entries**
    - Parse tree output names and verify each corresponds to an actual entry on disk
    - **Validates: Requirements 9.1**

  - [ ]* 6.3 Write property test for sorting invariant
    - **Property 3: Sorting invariant**
    - For each directory level, verify directories appear before files and both groups are alphabetically sorted
    - **Validates: Requirements 2.3**

  - [ ]* 6.4 Write property test for root name as first line
    - **Property 4: Root name as first line**
    - Verify first line of output equals the basename of the scanned root directory
    - **Validates: Requirements 2.5**

  - [ ]* 6.5 Write property test for no file contents leaked
    - **Property 5: No file contents leaked**
    - Generate files with random content, verify none of that content appears in tree output
    - **Validates: Requirements 2.4**

  - [ ]* 6.6 Write property test for default ignore exclusion
    - **Property 6: Default ignore exclusion**
    - Create entries matching default patterns, verify they don't appear in output
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 6.7 Write property test for gitignore combined exclusion
    - **Property 7: Gitignore combined exclusion**
    - Generate `.gitignore` with random patterns, verify matching entries are excluded alongside defaults
    - **Validates: Requirements 4.1, 4.4**

  - [ ]* 6.8 Write property test for gitignore comment lines
    - **Property 8: Gitignore comment lines are non-matching**
    - Generate `.gitignore` with comment lines, verify they don't cause any exclusion
    - **Validates: Requirements 4.5**

  - [ ]* 6.9 Write property test for depth limiting
    - **Property 9: Depth limiting**
    - Generate deep trees, verify no entries beyond depth N appear, and directories at depth N show name only
    - **Validates: Requirements 5.2, 5.3**

  - [ ]* 6.10 Write property test for truncation correctness
    - **Property 10: Truncation correctness**
    - Generate large trees that exceed 10,000 chars, verify truncation at line boundary with indicator
    - **Validates: Requirements 6.1, 6.2, 6.3**

- [ ] 7. Write property-based tests for payload and prompt integration
  - [ ]* 7.1 Write property test for payload passthrough
    - **Property 11: Payload passthrough**
    - Verify tree string arrives unmodified in `codebase_context` field
    - **Validates: Requirements 7.1, 7.2**

  - [ ]* 7.2 Write property test for prompt formatting
    - **Property 12: Prompt formatting**
    - Verify `PROJECT STRUCTURE:` header and code block wrapping in user message
    - **Validates: Requirements 8.2, 8.3**

  - [ ]* 7.3 Write property test for invalid path rejection
    - **Property 13: Invalid path rejection**
    - Generate non-existent or non-directory paths, verify exit code 1 and stderr output
    - **Validates: Requirements 1.3, 1.4**

  - [ ]* 7.4 Write property test for invalid depth rejection
    - **Property 14: Invalid depth rejection**
    - Generate integers < 1, verify exit code 1 and stderr output
    - **Validates: Requirements 5.4**

- [ ] 8. Write unit tests for edge cases
  - [ ]* 8.1 Write unit tests for CLI argument parsing and validation
    - Test `--codebase` accepted with valid path
    - Test missing `--codebase` → no codebase_context in payload
    - Test path is a file → exit code 1
    - Test default depth value is 4
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 5.1_

  - [ ]* 8.2 Write unit tests for tree_scanner edge cases
    - Test circular symlink is skipped gracefully
    - Test `.gitignore` not present → defaults only
    - Test empty lines in `.gitignore` don't cause errors
    - Test permission denied directory is skipped
    - _Requirements: 2.6, 4.3, 4.6_

  - [ ]* 8.3 Write unit tests for Lambda handler and prompt builder integration
    - Test handler passes codebase_context to build_messages
    - Test build_messages without codebase_context → message unchanged
    - Test truncation with verbose mode logs warning
    - _Requirements: 8.1, 8.4, 6.4_

- [ ] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The `pathspec` library must be added to `pyproject.toml` dependencies in task 1.1
- All property tests use Hypothesis with `@settings(max_examples=100)`
- Test files: `tests/property/test_tree_scanner.py` (Properties 1–10), `tests/property/test_codebase_payload.py` (Properties 11–14)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3"] },
    { "id": 3, "tasks": ["1.4"] },
    { "id": 4, "tasks": ["3.1", "4.1", "4.2"] },
    { "id": 5, "tasks": ["3.2"] },
    { "id": 6, "tasks": ["3.3"] },
    { "id": 7, "tasks": ["6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "6.7", "6.8", "6.9", "6.10", "7.1", "7.2", "7.3", "7.4"] },
    { "id": 8, "tasks": ["8.1", "8.2", "8.3"] }
  ]
}
```
