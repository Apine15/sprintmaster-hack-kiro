"""Integration tests for end-to-end language propagation.

Tests the full flow from CLI argument parsing through payload construction
to prompt generation, verifying that the language value propagates correctly
across all layers.

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add lambda directory to path so we can import handler and prompt_builder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "lambda"))

# Mock boto3 before importing handler (boto3 may not be installed locally)
sys.modules.setdefault("boto3", MagicMock())

from handler import lambda_handler
from prompt_builder import LANGUAGE_INSTRUCTION_TEMPLATE
from sprintmaster.cli import parse_args, main


class TestCLIToPayloadPropagation:
    """Test that --lang value propagates from CLI args to the payload dict.

    Validates: Requirements 4.1, 4.2
    """

    def test_lang_spanish_in_payload(self):
        """--lang Spanish → payload contains 'language': 'Spanish'.

        Validates: Requirement 4.1
        """
        args = parse_args(["Build a feature", "--lang", "Spanish"])
        # Replicate what main() does to build the payload
        args.lang = args.lang.strip()
        payload = {
            "feature_description": "Build a feature",
            "team_config": None,
            "model_id": args.model,
            "language": args.lang,
        }
        assert payload["language"] == "Spanish"

    def test_no_lang_defaults_english_in_payload(self):
        """No --lang → payload contains 'language': 'English'.

        Validates: Requirement 4.2
        """
        args = parse_args(["Build a feature"])
        args.lang = args.lang.strip()
        payload = {
            "feature_description": "Build a feature",
            "team_config": None,
            "model_id": args.model,
            "language": args.lang,
        }
        assert payload["language"] == "English"


class TestPayloadToPromptPropagation:
    """Test that language in the Lambda event results in correct prompt injection.

    Validates: Requirements 4.1, 4.2, 4.4, 4.5
    """

    @patch("handler.boto3.client")
    def test_spanish_payload_produces_spanish_prompt(self, mock_boto_client):
        """Payload with 'language': 'Spanish' → prompt contains Spanish instruction.

        Validates: Requirement 4.1
        """
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"tickets": []}'}]}},
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }

        event = {
            "feature_description": "Build a shopping cart",
            "team_config": None,
            "model_id": "us.anthropic.claude-3-haiku-20240307-v1:0",
            "language": "Spanish",
        }

        response = lambda_handler(event, None)
        assert response["statusCode"] == 200

        # Verify the system prompt passed to Bedrock contains the Spanish instruction
        call_args = mock_client.converse.call_args
        system_prompt_blocks = call_args.kwargs["system"]
        system_text = system_prompt_blocks[0]["text"]

        expected_fragment = LANGUAGE_INSTRUCTION_TEMPLATE.format(language="Spanish")
        assert expected_fragment in system_text
        assert "Spanish" in system_text

    @patch("handler.boto3.client")
    def test_english_default_produces_english_prompt(self, mock_boto_client):
        """Payload with 'language': 'English' → prompt contains English instruction.

        Validates: Requirement 4.2
        """
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"tickets": []}'}]}},
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }

        event = {
            "feature_description": "Build a shopping cart",
            "team_config": None,
            "model_id": "us.anthropic.claude-3-haiku-20240307-v1:0",
            "language": "English",
        }

        response = lambda_handler(event, None)
        assert response["statusCode"] == 200

        # Verify the system prompt passed to Bedrock contains the English instruction
        call_args = mock_client.converse.call_args
        system_prompt_blocks = call_args.kwargs["system"]
        system_text = system_prompt_blocks[0]["text"]

        expected_fragment = LANGUAGE_INSTRUCTION_TEMPLATE.format(language="English")
        assert expected_fragment in system_text

    @patch("handler.boto3.client")
    def test_language_does_not_alter_feature_description(self, mock_boto_client):
        """Language propagation does NOT alter feature_description processing.

        Validates: Requirement 4.5
        """
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"tickets": []}'}]}},
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }

        feature_text = "Build a complex microservices architecture"
        event = {
            "feature_description": feature_text,
            "team_config": None,
            "language": "French",
        }

        response = lambda_handler(event, None)
        assert response["statusCode"] == 200

        # Verify the user message still contains the original feature description
        call_args = mock_client.converse.call_args
        messages = call_args.kwargs["messages"]
        user_message_text = messages[0]["content"][0]["text"]
        assert user_message_text == feature_text

    @patch("handler.boto3.client")
    def test_language_does_not_alter_team_config_processing(self, mock_boto_client):
        """Language propagation does NOT alter team_config processing.

        Validates: Requirement 4.5
        """
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"tickets": []}'}]}},
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }

        team_config = {
            "team": [
                {"name": "Alice", "role": "Backend Dev", "stack": ["Python", "AWS"]}
            ]
        }
        event = {
            "feature_description": "Build a feature",
            "team_config": team_config,
            "language": "German",
        }

        response = lambda_handler(event, None)
        assert response["statusCode"] == 200

        # Verify team config info is still in the system prompt
        call_args = mock_client.converse.call_args
        system_prompt_blocks = call_args.kwargs["system"]
        system_text = system_prompt_blocks[0]["text"]
        assert "Alice" in system_text
        assert "Backend Dev" in system_text

    @patch("handler.boto3.client")
    def test_language_instruction_appended_without_modifying_base(self, mock_boto_client):
        """Language instruction appended to system prompt without modifying base content.

        Validates: Requirement 4.4
        """
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"tickets": []}'}]}},
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }

        # Call without language
        event_no_lang = {
            "feature_description": "Build a feature",
            "team_config": None,
        }
        lambda_handler(event_no_lang, None)
        call_args_no_lang = mock_client.converse.call_args
        system_text_no_lang = call_args_no_lang.kwargs["system"][0]["text"]

        mock_client.reset_mock()

        # Call with language
        event_with_lang = {
            "feature_description": "Build a feature",
            "team_config": None,
            "language": "Portuguese",
        }
        lambda_handler(event_with_lang, None)
        call_args_with_lang = mock_client.converse.call_args
        system_text_with_lang = call_args_with_lang.kwargs["system"][0]["text"]

        # The prompt with language should start with the exact same base
        assert system_text_with_lang.startswith(system_text_no_lang)
        # And should have the language instruction appended
        suffix = system_text_with_lang[len(system_text_no_lang):]
        assert "Portuguese" in suffix
        assert "LANGUAGE INSTRUCTION" in suffix


class TestCLIEmptyLangExitsWithError:
    """Test that empty --lang causes CLI to exit with code 1.

    Validates: Requirement 4.3
    """

    def test_empty_lang_exits_with_code_1(self):
        """Empty --lang '' → CLI exits with code 1.

        Validates: Requirement 4.3
        """
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["sprintmaster", "Build a feature", "--lang", ""]):
                main()
        assert exc_info.value.code == 1

    def test_whitespace_only_lang_exits_with_code_1(self):
        """Whitespace-only --lang '   ' → CLI exits with code 1.

        Validates: Requirement 4.3
        """
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["sprintmaster", "Build a feature", "--lang", "   "]):
                main()
        assert exc_info.value.code == 1
