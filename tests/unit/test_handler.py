"""Unit tests for lambda/handler.py."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add lambda directory to path so we can import handler
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "lambda"))

from handler import lambda_handler, _parse_event_body, DEFAULT_MODEL_ID


class TestParseEventBody:
    """Tests for _parse_event_body helper."""

    def test_direct_invocation_dict(self):
        """Event body is already a dict with feature_description at top level."""
        event = {"feature_description": "Build login", "team_config": None}
        result = _parse_event_body(event)
        assert result["feature_description"] == "Build login"

    def test_api_gateway_json_string_body(self):
        """Event body is a JSON string (API Gateway proxy format)."""
        payload = {"feature_description": "Build login", "team_config": None}
        event = {"body": json.dumps(payload)}
        result = _parse_event_body(event)
        assert result["feature_description"] == "Build login"

    def test_api_gateway_dict_body(self):
        """Event body key is already a dict."""
        payload = {"feature_description": "Build login", "team_config": None}
        event = {"body": payload}
        result = _parse_event_body(event)
        assert result["feature_description"] == "Build login"

    def test_invalid_json_string_raises(self):
        """Invalid JSON string in body raises JSONDecodeError."""
        event = {"body": "not valid json{{{"}
        with pytest.raises(json.JSONDecodeError):
            _parse_event_body(event)


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    def test_missing_feature_description_returns_400(self):
        """Should return 400 when feature_description is missing."""
        event = {"team_config": None}
        response = lambda_handler(event, None)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "feature_description is required" in body["error"]

    def test_empty_feature_description_returns_400(self):
        """Should return 400 when feature_description is empty."""
        event = {"feature_description": "   ", "team_config": None}
        response = lambda_handler(event, None)
        assert response["statusCode"] == 400

    def test_invalid_body_returns_400(self):
        """Should return 400 when body is invalid JSON."""
        event = {"body": "invalid{json"}
        response = lambda_handler(event, None)
        assert response["statusCode"] == 400

    @patch("handler.boto3.client")
    def test_successful_invocation(self, mock_boto_client):
        """Should return 200 with tickets on successful Bedrock call."""
        # Mock Bedrock response
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        tickets_response = {
            "tickets": [
                {
                    "title": "Implement login",
                    "description": "Create login endpoint",
                    "acceptance_criteria": ["User can log in"],
                    "story_points": 5,
                    "priority": "high",
                    "assignee": "unassigned",
                }
            ]
        }

        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": json.dumps(tickets_response)}]
                }
            },
            "usage": {"inputTokens": 150, "outputTokens": 300},
        }

        event = {
            "feature_description": "Build a user login system",
            "team_config": None,
            "model_id": "us.anthropic.claude-3-haiku-20240307-v1:0",
        }

        response = lambda_handler(event, None)
        assert response["statusCode"] == 200

        body = json.loads(response["body"])
        assert "tickets" in body
        assert len(body["tickets"]) == 1
        assert body["tickets"][0]["title"] == "Implement login"
        assert body["token_usage"] == {"input": 150, "output": 300}
        assert body["model_id"] == "us.anthropic.claude-3-haiku-20240307-v1:0"
        assert "region" in body

    @patch("handler.boto3.client")
    def test_uses_default_model_id(self, mock_boto_client):
        """Should use default model_id when not provided."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"tickets": []}'}]}},
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }

        event = {"feature_description": "Build something"}
        response = lambda_handler(event, None)

        body = json.loads(response["body"])
        assert body["model_id"] == DEFAULT_MODEL_ID

    @patch("handler.boto3.client")
    def test_bedrock_error_returns_500(self, mock_boto_client):
        """Should return 500 when Bedrock call fails."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.converse.side_effect = Exception("Bedrock unavailable")

        event = {"feature_description": "Build something"}
        response = lambda_handler(event, None)
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "Bedrock" in body["error"]

    @patch("handler.boto3.client")
    def test_with_team_config(self, mock_boto_client):
        """Should pass team_config through to prompt_builder."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"tickets": []}'}]}},
            "usage": {"inputTokens": 50, "outputTokens": 100},
        }

        team_config = {
            "team": [
                {"name": "Alice", "role": "Backend Dev", "stack": ["Python", "AWS"]}
            ]
        }
        event = {
            "feature_description": "Build a feature",
            "team_config": team_config,
        }

        response = lambda_handler(event, None)
        assert response["statusCode"] == 200

        # Verify that converse was called with system prompt containing team info
        call_args = mock_client.converse.call_args
        system_prompt_blocks = call_args.kwargs["system"]
        system_text = system_prompt_blocks[0]["text"]
        assert "Alice" in system_text
        assert "Backend Dev" in system_text

    @patch("handler.boto3.client")
    def test_invalid_json_from_bedrock_returns_500(self, mock_boto_client):
        """Should return 500 when Bedrock returns invalid JSON."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "not valid json"}]}},
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }

        event = {"feature_description": "Build something"}
        response = lambda_handler(event, None)
        assert response["statusCode"] == 500
