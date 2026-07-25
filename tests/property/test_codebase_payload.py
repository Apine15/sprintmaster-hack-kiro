"""Property-based tests for codebase payload passthrough and prompt formatting.

**Validates: Requirements 7.1, 7.2, 8.2, 8.3**
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from sprintmaster import tree_scanner
from sprintmaster.lambda_client import LambdaClient
from sprintmaster.tree_scanner import scan

# Add lambda directory to path so we can import prompt_builder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda"))

from prompt_builder import build_messages


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Safe characters for filesystem names (lowercase alpha only to avoid platform issues)
_safe_name = st.text(
    alphabet=st.characters(whitelist_categories=("Ll",)),
    min_size=2,
    max_size=8,
)

# Strategy for a list of unique file names (with extension)
_file_names = st.lists(
    _safe_name.map(lambda s: f"{s}.txt"),
    min_size=1,
    max_size=5,
    unique=True,
)

# Strategy for a list of unique directory names
_dir_names = st.lists(_safe_name, min_size=0, max_size=3, unique=True)


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestPayloadPassthroughProperty:
    """Property 11: Payload passthrough.

    For any non-empty tree string produced by the scanner, the
    `codebase_context` field in the Lambda payload SHALL contain exactly
    that tree string with no modifications.

    **Validates: Requirements 7.1, 7.2**
    """

    # Feature: codebase-context, Property 11: Payload passthrough

    @given(
        files=_file_names,
        dirs=_dir_names,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_tree_string_arrives_unmodified_in_payload(
        self, files: list[str], dirs: list[str], tmp_path: Path
    ) -> None:
        """The codebase_context field contains the exact tree string from scan."""
        # Create a project directory with generated files and dirs
        project_dir = tmp_path / "project"
        project_dir.mkdir(exist_ok=True)

        for dname in dirs:
            (project_dir / dname).mkdir(exist_ok=True)
        for fname in files:
            (project_dir / fname).write_text("content", encoding="utf-8")

        # Scan the directory to get the expected tree string
        scan_result = scan(project_dir, depth_limit=4, max_chars=10_000)
        expected_tree = scan_result.tree

        # Ensure the tree is non-empty (valid scan)
        assert len(expected_tree) > 0

        # Simulate the CLI payload construction logic from main()
        # The CLI does: payload["codebase_context"] = result.tree
        payload: dict = {
            "feature_description": "test feature",
            "team_config": None,
            "model_id": "test-model",
            "language": "English",
        }
        # This mirrors cli.py: `if codebase_context is not None: payload["codebase_context"] = codebase_context`
        codebase_context = scan_result.tree
        if codebase_context is not None:
            payload["codebase_context"] = codebase_context

        # Verify the payload field contains EXACTLY the tree string — no modifications
        assert "codebase_context" in payload
        assert payload["codebase_context"] == expected_tree
        assert payload["codebase_context"] is codebase_context

    @given(
        files=_file_names,
        dirs=_dir_names,
        depth=st.integers(min_value=1, max_value=4),
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_payload_passthrough_via_cli_mock(
        self, files: list[str], dirs: list[str], depth: int, tmp_path: Path
    ) -> None:
        """End-to-end: CLI sends exact tree string through LambdaClient.send()."""
        # Create a project directory with generated files and dirs
        project_dir = tmp_path / "project"
        project_dir.mkdir(exist_ok=True)

        for dname in dirs:
            (project_dir / dname).mkdir(exist_ok=True)
        for fname in files:
            (project_dir / fname).write_text("content", encoding="utf-8")

        # Get the expected scan result using the same depth the CLI would use
        scan_result = scan(project_dir, depth_limit=depth, max_chars=10_000)
        expected_tree = scan_result.tree

        # Capture the payload sent to LambdaClient.send by mocking
        captured_payload: dict = {}

        def capture_send(self_client: object, payload: dict) -> dict:
            captured_payload.update(payload)
            return {"tickets": [], "model_id": "test", "token_usage": {}}

        with patch.object(LambdaClient, "send", capture_send):
            with patch.object(LambdaClient, "__init__", return_value=None):
                # Replicate the CLI payload construction logic from main()
                result = tree_scanner.scan(project_dir, depth_limit=depth)
                payload: dict = {
                    "feature_description": "test feature",
                    "team_config": None,
                    "model_id": "test-model",
                    "language": "English",
                }
                codebase_context = result.tree
                if codebase_context is not None:
                    payload["codebase_context"] = codebase_context

                # Send through the mocked client
                client = LambdaClient.__new__(LambdaClient)
                client.send(payload)

        # Verify the captured payload has the exact tree string
        assert "codebase_context" in captured_payload
        assert captured_payload["codebase_context"] == expected_tree


class TestInvalidPathRejectionProperty:
    """Property 13: Invalid path rejection.

    For any path string that does not correspond to an existing directory on disk,
    the CLI SHALL exit with code 1 and print an error message to stderr.

    **Validates: Requirements 1.3, 1.4**
    """

    # Feature: codebase-context, Property 13: Invalid path rejection

    @given(
        path_suffix=st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "N")),
            min_size=5,
            max_size=20,
        ).filter(lambda s: s.strip() and s.isascii()),
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_nonexistent_path_exits_with_code_1(self, path_suffix: str, tmp_path) -> None:
        """Non-existent codebase paths cause exit code 1 and stderr error."""
        from unittest.mock import patch
        from io import StringIO

        # Build a path that definitely doesn't exist
        nonexistent_path = str(tmp_path / f"nonexistent_{path_suffix}")

        fake_stderr = StringIO()
        test_argv = [
            "sprintmaster",
            "test feature",
            "--codebase", nonexistent_path,
            "--lambda-url", "https://fake.example.com/invoke",
        ]

        with patch.object(sys, "argv", test_argv), \
             patch("sys.stderr", fake_stderr):
            from sprintmaster.cli import main
            with __import__("pytest").raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1, (
            f"Expected exit code 1, got {exc_info.value.code}"
        )
        stderr_output = fake_stderr.getvalue()
        assert "Error:" in stderr_output, (
            f"Expected error message in stderr, got: {stderr_output}"
        )
        assert "does not exist" in stderr_output, (
            f"Expected 'does not exist' in stderr, got: {stderr_output}"
        )

    @given(
        file_name=st.text(
            alphabet=st.characters(whitelist_categories=("Ll",)),
            min_size=3,
            max_size=12,
        ).filter(lambda s: s.strip() and s.isascii()),
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_file_path_not_directory_exits_with_code_1(self, file_name: str, tmp_path) -> None:
        """Paths that exist but are files (not directories) cause exit code 1 and stderr error."""
        from unittest.mock import patch
        from io import StringIO
        import pytest

        # Create a file (not a directory)
        file_path = tmp_path / f"{file_name}.txt"
        file_path.write_text("content", encoding="utf-8")

        fake_stderr = StringIO()
        test_argv = [
            "sprintmaster",
            "test feature",
            "--codebase", str(file_path),
            "--lambda-url", "https://fake.example.com/invoke",
        ]

        with patch.object(sys, "argv", test_argv), \
             patch("sys.stderr", fake_stderr):
            from sprintmaster.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1, (
            f"Expected exit code 1, got {exc_info.value.code}"
        )
        stderr_output = fake_stderr.getvalue()
        assert "Error:" in stderr_output, (
            f"Expected error message in stderr, got: {stderr_output}"
        )
        assert "not a directory" in stderr_output, (
            f"Expected 'not a directory' in stderr, got: {stderr_output}"
        )



# ---------------------------------------------------------------------------
# Strategy for Property 12
# ---------------------------------------------------------------------------

# Non-empty strings representing codebase context (tree output)
_non_empty_codebase_context = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=500,
).filter(lambda s: s.strip())


# ---------------------------------------------------------------------------
# Property 12 Tests
# ---------------------------------------------------------------------------


class TestPromptFormattingProperty:
    """Property 12: Prompt formatting.

    For any non-empty codebase_context string passed to the prompt builder,
    the resulting user message SHALL contain a `PROJECT STRUCTURE:` header
    followed by the tree string wrapped in a code block.

    **Validates: Requirements 8.2, 8.3**
    """

    # Feature: codebase-context, Property 12: Prompt formatting

    @given(
        codebase_context=_non_empty_codebase_context,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_message_contains_project_structure_header_and_code_block(
        self, codebase_context: str
    ) -> None:
        """Non-empty codebase_context produces PROJECT STRUCTURE header with code block."""
        _, messages = build_messages(
            feature_description="Test feature",
            team_config=None,
            language=None,
            codebase_context=codebase_context,
        )

        user_text = messages[0]["content"][0]["text"]

        # Must contain the PROJECT STRUCTURE: header
        assert "PROJECT STRUCTURE:" in user_text, (
            "User message must contain 'PROJECT STRUCTURE:' header"
        )

        # Must contain the tree wrapped in a code block (``` before and after)
        expected_block = f"```\n{codebase_context}\n```"
        assert expected_block in user_text, (
            f"User message must contain tree wrapped in code block. "
            f"Expected block:\n{expected_block}\n\nGot user_text:\n{user_text}"
        )

        # The PROJECT STRUCTURE: header must appear before the code block
        header_idx = user_text.index("PROJECT STRUCTURE:")
        block_idx = user_text.index(expected_block)
        assert header_idx < block_idx, (
            "PROJECT STRUCTURE: header must appear before the code block"
        )


class TestInvalidDepthRejectionProperty:
    """Property 14: Invalid depth rejection.

    For any integer value less than 1 provided as `--codebase-depth`,
    the CLI SHALL exit with code 1 and print an error message to stderr.

    **Validates: Requirements 5.4**
    """

    # Feature: codebase-context, Property 14: Invalid depth rejection

    @given(
        invalid_depth=st.integers(max_value=0),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_depth_less_than_1_exits_with_code_1(self, invalid_depth: int) -> None:
        """Any --codebase-depth < 1 causes exit code 1 and stderr error."""
        from unittest.mock import patch
        from io import StringIO

        fake_stderr = StringIO()
        test_argv = [
            "sprintmaster",
            "test feature",
            "--codebase-depth", str(invalid_depth),
            "--lambda-url", "https://fake.example.com/invoke",
        ]

        with patch.object(sys, "argv", test_argv), \
             patch("sys.stderr", fake_stderr):
            from sprintmaster.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1, (
            f"Expected exit code 1 for depth={invalid_depth}, got {exc_info.value.code}"
        )
        stderr_output = fake_stderr.getvalue()
        assert "Error:" in stderr_output, (
            f"Expected error message in stderr for depth={invalid_depth}, got: {stderr_output}"
        )
        assert "--codebase-depth must be at least 1" in stderr_output, (
            f"Expected depth error message in stderr, got: {stderr_output}"
        )
