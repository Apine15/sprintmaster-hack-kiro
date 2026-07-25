"""Unit tests for Lambda handler and prompt builder integration.

Tests the integration between the handler's extraction of codebase_context
from the event payload, the prompt builder's conditional appending of
PROJECT STRUCTURE, and CLI verbose truncation logging.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add lambda directory to path so we can import handler and prompt_builder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "lambda"))

from handler import lambda_handler
from prompt_builder import build_messages, CODEBASE_CONTEXT_TEMPLATE


class TestHandlerPassesCodebaseContext:
    """Tests that the Lambda handler correctly passes codebase_context to build_messages."""

    @patch("handler.boto3.client")
    def test_codebase_context_in_payload_reaches_user_message(self, mock_boto_client):
        """When codebase_context is in the event payload, it appears in the user message sent to Bedrock."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"tickets": []}'}]}},
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }

        tree_content = "my-project\n├── src/\n│   └── main.py\n└── README.md"
        event = {
            "feature_description": "Build a login page",
            "team_config": None,
            "codebase_context": tree_content,
        }

        response = lambda_handler(event, None)
        assert response["statusCode"] == 200

        # Verify the user message sent to Bedrock contains the PROJECT STRUCTURE section
        call_args = mock_client.converse.call_args
        messages = call_args.kwargs["messages"]
        user_text = messages[0]["content"][0]["text"]
        assert "PROJECT STRUCTURE:" in user_text
        assert tree_content in user_text

    @patch("handler.boto3.client")
    def test_no_codebase_context_leaves_message_unchanged(self, mock_boto_client):
        """When codebase_context is NOT in the event, user message is just feature_description."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"tickets": []}'}]}},
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }

        feature = "Build a login page"
        event = {
            "feature_description": feature,
            "team_config": None,
        }

        response = lambda_handler(event, None)
        assert response["statusCode"] == 200

        # Verify the user message is just the feature description (no PROJECT STRUCTURE)
        call_args = mock_client.converse.call_args
        messages = call_args.kwargs["messages"]
        user_text = messages[0]["content"][0]["text"]
        assert user_text == feature
        assert "PROJECT STRUCTURE:" not in user_text


class TestBuildMessagesCodebaseContext:
    """Tests for build_messages behavior with and without codebase_context."""

    def test_without_codebase_context_returns_feature_only(self):
        """Calling build_messages without codebase_context returns user message equal to feature_description."""
        feature = "Implement password reset"
        _, messages = build_messages(feature, team_config=None)

        user_text = messages[0]["content"][0]["text"]
        assert user_text == feature
        assert "PROJECT STRUCTURE:" not in user_text

    def test_with_codebase_context_appends_project_structure(self):
        """Calling build_messages with codebase_context appends the PROJECT STRUCTURE section."""
        feature = "Implement password reset"
        tree = "project\n├── app.py\n└── tests/"

        _, messages = build_messages(feature, team_config=None, codebase_context=tree)

        user_text = messages[0]["content"][0]["text"]
        assert user_text.startswith(feature)
        assert "PROJECT STRUCTURE:" in user_text
        assert tree in user_text

    def test_empty_codebase_context_does_not_modify_message(self):
        """Empty string codebase_context does not append anything."""
        feature = "Build API"
        _, messages = build_messages(feature, team_config=None, codebase_context="")

        user_text = messages[0]["content"][0]["text"]
        assert user_text == feature
        assert "PROJECT STRUCTURE:" not in user_text

    def test_whitespace_only_codebase_context_does_not_modify_message(self):
        """Whitespace-only codebase_context does not append anything."""
        feature = "Build API"
        _, messages = build_messages(feature, team_config=None, codebase_context="   \n  ")

        user_text = messages[0]["content"][0]["text"]
        assert user_text == feature
        assert "PROJECT STRUCTURE:" not in user_text


class TestCLITruncationVerboseLogging:
    """Tests that CLI logs truncation warning in verbose mode."""

    @patch("sprintmaster.cli.LambdaClient")
    @patch("sprintmaster.cli.tree_scanner")
    @patch("sprintmaster.cli.resolve_input")
    @patch("sprintmaster.cli.load_team_config")
    @patch("sprintmaster.cli.parse_args")
    @patch("sprintmaster.cli.Logger")
    def test_truncation_verbose_logs_warning(
        self,
        mock_logger_cls,
        mock_parse_args,
        mock_load_team,
        mock_resolve_input,
        mock_tree_scanner,
        mock_lambda_client,
        tmp_path,
    ):
        """When scan result is truncated and verbose is active, logger.verbose is called with truncation message."""
        from sprintmaster.tree_scanner import ScanResult
        from sprintmaster.cli import main

        # Setup args
        mock_args = MagicMock()
        mock_args.codebase = str(tmp_path)
        mock_args.codebase_depth = 4
        mock_args.verbose = True
        mock_args.quiet = False
        mock_args.lang = "English"
        mock_args.model = "test-model"
        mock_args.format = "terminal"
        mock_args.output = None
        mock_parse_args.return_value = mock_args

        # Setup logger
        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger

        # Setup tree_scanner to return truncated result
        mock_scan_result = ScanResult(
            tree="truncated tree...",
            total_entries=100,
            truncated=True,
            truncated_count=42,
        )
        mock_tree_scanner.scan.return_value = mock_scan_result

        # Setup other mocks
        mock_resolve_input.return_value = "Some feature"
        mock_load_team.return_value = None

        # Mock the LambdaClient to prevent actual invocation
        mock_client_instance = MagicMock()
        mock_lambda_client.return_value = mock_client_instance
        mock_client_instance.invoke.return_value = {
            "tickets": [],
            "token_usage": {"input": 0, "output": 0},
            "model_id": "test",
            "region": "us-east-1",
        }

        # Run main - it may raise SystemExit or other exceptions after our point of interest
        # We only care that the truncation warning was logged
        try:
            main()
        except (SystemExit, Exception):
            pass

        # Verify verbose was called with the truncation warning
        mock_logger.verbose.assert_any_call(
            "Tree output truncated: 42 entries not shown"
        )

    @patch("sprintmaster.cli.LambdaClient")
    @patch("sprintmaster.cli.tree_scanner")
    @patch("sprintmaster.cli.resolve_input")
    @patch("sprintmaster.cli.load_team_config")
    @patch("sprintmaster.cli.parse_args")
    @patch("sprintmaster.cli.Logger")
    def test_no_truncation_no_verbose_log(
        self,
        mock_logger_cls,
        mock_parse_args,
        mock_load_team,
        mock_resolve_input,
        mock_tree_scanner,
        mock_lambda_client,
        tmp_path,
    ):
        """When scan result is not truncated, logger.verbose is NOT called with truncation message."""
        from sprintmaster.tree_scanner import ScanResult
        from sprintmaster.cli import main

        # Setup args
        mock_args = MagicMock()
        mock_args.codebase = str(tmp_path)
        mock_args.codebase_depth = 4
        mock_args.verbose = True
        mock_args.quiet = False
        mock_args.lang = "English"
        mock_args.model = "test-model"
        mock_args.format = "terminal"
        mock_args.output = None
        mock_parse_args.return_value = mock_args

        # Setup logger
        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger

        # Setup tree_scanner to return NON-truncated result
        mock_scan_result = ScanResult(
            tree="small tree",
            total_entries=5,
            truncated=False,
            truncated_count=0,
        )
        mock_tree_scanner.scan.return_value = mock_scan_result

        # Setup other mocks
        mock_resolve_input.return_value = "Some feature"
        mock_load_team.return_value = None

        mock_client_instance = MagicMock()
        mock_lambda_client.return_value = mock_client_instance
        mock_client_instance.invoke.return_value = {
            "tickets": [],
            "token_usage": {"input": 0, "output": 0},
            "model_id": "test",
            "region": "us-east-1",
        }

        try:
            main()
        except (SystemExit, Exception):
            pass

        # Verify verbose was NOT called with any truncation message
        for call in mock_logger.verbose.call_args_list:
            assert "truncated" not in str(call).lower()
