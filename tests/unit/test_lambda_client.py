"""Unit tests for LambdaClient."""

import argparse
import os
from unittest.mock import patch, MagicMock

import pytest
import requests

from sprintmaster.lambda_client import LambdaClient
from sprintmaster.models import EXIT_SERVICE_ERROR


def make_args(lambda_url=None):
    """Helper to create argparse.Namespace with lambda_url."""
    return argparse.Namespace(lambda_url=lambda_url)


class TestLambdaClientInit:
    """Tests for LambdaClient.__init__."""

    def test_reads_url_from_args(self):
        """URL from args.lambda_url takes priority."""
        client = LambdaClient(make_args(lambda_url="https://example.com/lambda"))
        assert client.url == "https://example.com/lambda"

    def test_reads_url_from_env_var(self, monkeypatch):
        """Falls back to SPRINTMASTER_LAMBDA_URL env var."""
        monkeypatch.setenv("SPRINTMASTER_LAMBDA_URL", "https://env.example.com/lambda")
        client = LambdaClient(make_args(lambda_url=None))
        assert client.url == "https://env.example.com/lambda"

    def test_args_url_overrides_env_var(self, monkeypatch):
        """args.lambda_url overrides env var."""
        monkeypatch.setenv("SPRINTMASTER_LAMBDA_URL", "https://env.example.com/lambda")
        client = LambdaClient(make_args(lambda_url="https://args.example.com/lambda"))
        assert client.url == "https://args.example.com/lambda"

    def test_missing_url_exits_with_service_error(self, monkeypatch):
        """Exits with EXIT_SERVICE_ERROR when no URL is available."""
        monkeypatch.delenv("SPRINTMASTER_LAMBDA_URL", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            LambdaClient(make_args(lambda_url=None))
        assert exc_info.value.code == EXIT_SERVICE_ERROR


class TestLambdaClientSend:
    """Tests for LambdaClient.send."""

    @pytest.fixture
    def client(self):
        """Create a LambdaClient with a test URL."""
        return LambdaClient(make_args(lambda_url="https://test.example.com/lambda"))

    @patch("sprintmaster.lambda_client.requests.post")
    def test_successful_post_returns_json(self, mock_post, client):
        """HTTP 200 returns parsed JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tickets": [], "token_usage": {"input": 10, "output": 20}}
        mock_post.return_value = mock_response

        result = client.send({"feature_description": "test"})
        assert result == {"tickets": [], "token_usage": {"input": 10, "output": 20}}
        mock_post.assert_called_once_with(
            "https://test.example.com/lambda",
            json={"feature_description": "test"},
            timeout=30,
        )

    @patch("sprintmaster.lambda_client.requests.post")
    def test_http_401_exits_with_service_error(self, mock_post, client):
        """HTTP 401 exits with EXIT_SERVICE_ERROR."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        with pytest.raises(SystemExit) as exc_info:
            client.send({"feature_description": "test"})
        assert exc_info.value.code == EXIT_SERVICE_ERROR

    @patch("sprintmaster.lambda_client.requests.post")
    def test_http_403_exits_with_service_error(self, mock_post, client):
        """HTTP 403 exits with EXIT_SERVICE_ERROR."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response

        with pytest.raises(SystemExit) as exc_info:
            client.send({"feature_description": "test"})
        assert exc_info.value.code == EXIT_SERVICE_ERROR

    @patch("sprintmaster.lambda_client.requests.post")
    def test_http_500_exits_with_service_error(self, mock_post, client):
        """HTTP 5xx exits with EXIT_SERVICE_ERROR."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        with pytest.raises(SystemExit) as exc_info:
            client.send({"feature_description": "test"})
        assert exc_info.value.code == EXIT_SERVICE_ERROR

    @patch("sprintmaster.lambda_client.requests.post")
    def test_timeout_exits_with_service_error(self, mock_post, client):
        """Request timeout exits with EXIT_SERVICE_ERROR."""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        with pytest.raises(SystemExit) as exc_info:
            client.send({"feature_description": "test"})
        assert exc_info.value.code == EXIT_SERVICE_ERROR

    @patch("sprintmaster.lambda_client.time.sleep")
    @patch("sprintmaster.lambda_client.requests.post")
    def test_http_429_retries_with_exponential_backoff(self, mock_post, mock_sleep, client):
        """HTTP 429 retries up to 3 times with exponential backoff, then succeeds."""
        mock_429 = MagicMock()
        mock_429.status_code = 429

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"tickets": []}

        # 2 retries with 429, then success
        mock_post.side_effect = [mock_429, mock_429, mock_200]

        result = client.send({"feature_description": "test"})
        assert result == {"tickets": []}
        assert mock_post.call_count == 3
        # Backoff: 1s after first 429, 2s after second 429
        assert mock_sleep.call_args_list[0][0][0] == 1
        assert mock_sleep.call_args_list[1][0][0] == 2

    @patch("sprintmaster.lambda_client.time.sleep")
    @patch("sprintmaster.lambda_client.requests.post")
    def test_http_429_max_retries_exhausted_exits(self, mock_post, mock_sleep, client):
        """HTTP 429 four times (initial + 3 retries) exits with EXIT_SERVICE_ERROR."""
        mock_429 = MagicMock()
        mock_429.status_code = 429

        mock_post.return_value = mock_429

        with pytest.raises(SystemExit) as exc_info:
            client.send({"feature_description": "test"})
        assert exc_info.value.code == EXIT_SERVICE_ERROR
        # 4 total attempts: initial + 3 retries
        assert mock_post.call_count == 4
        # Backoff waits: 1s, 2s, 4s
        assert mock_sleep.call_args_list[0][0][0] == 1
        assert mock_sleep.call_args_list[1][0][0] == 2
        assert mock_sleep.call_args_list[2][0][0] == 4

    @patch("sprintmaster.lambda_client.requests.post")
    def test_malformed_json_response_exits(self, mock_post, client):
        """Non-JSON response body exits with EXIT_SERVICE_ERROR."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("No JSON object")
        mock_post.return_value = mock_response

        with pytest.raises(SystemExit) as exc_info:
            client.send({"feature_description": "test"})
        assert exc_info.value.code == EXIT_SERVICE_ERROR
