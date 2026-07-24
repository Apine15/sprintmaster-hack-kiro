"""Unit tests for CLI --lang / -l argument parsing and validation."""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from sprintmaster.cli import parse_args, main


class TestParseLangArg:
    """Tests for --lang / -l argument parsing via parse_args()."""

    def test_lang_flag_accepted(self):
        """--lang Spanish → args.lang == 'Spanish'. Validates: Requirements 1.1"""
        args = parse_args(["--lang", "Spanish"])
        assert args.lang == "Spanish"

    def test_short_alias_l_accepted(self):
        """-l French → args.lang == 'French'. Validates: Requirements 1.1"""
        args = parse_args(["-l", "French"])
        assert args.lang == "French"

    def test_lang_default_english(self):
        """No --lang → args.lang == 'English'. Validates: Requirements 1.2"""
        args = parse_args([])
        assert args.lang == "English"

    def test_exactly_50_chars_accepted(self):
        """A 50-char string is accepted by parser (boundary). Validates: Requirements 1.1"""
        value = "a" * 50
        args = parse_args(["--lang", value])
        assert args.lang == value


class TestMainLangValidation:
    """Tests for language validation in main() — error paths."""

    def test_empty_lang_exits_with_error(self):
        """--lang '' → exit code 1 + error on stderr. Validates: Requirements 1.5"""
        with patch("sys.argv", ["sprintmaster", "test feature", "--lang", ""]):
            with patch("sprintmaster.cli.Logger"):
                with pytest.raises(SystemExit) as exc_info:
                    with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                        main()
                assert exc_info.value.code == 1

    def test_whitespace_only_lang_exits_with_error(self):
        """--lang '   ' → exit code 1 + 'blank' in error. Validates: Requirements 1.5"""
        with patch("sys.argv", ["sprintmaster", "test feature", "--lang", "   "]):
            with patch("sprintmaster.cli.Logger"):
                stderr_capture = StringIO()
                with patch("sys.stderr", stderr_capture):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                assert exc_info.value.code == 1
                assert "blank" in stderr_capture.getvalue()

    def test_tab_whitespace_lang_exits_with_error(self):
        """--lang '\\t' → exit code 1. Validates: Requirements 1.5"""
        with patch("sys.argv", ["sprintmaster", "test feature", "--lang", "\t"]):
            with patch("sprintmaster.cli.Logger"):
                with pytest.raises(SystemExit) as exc_info:
                    with patch("sys.stderr", new_callable=StringIO):
                        main()
                assert exc_info.value.code == 1

    def test_over_50_chars_exits_with_error(self):
        """--lang 'x'*51 → exit code 1 + 'exceeds' in error. Validates: Requirements 1.6"""
        long_value = "x" * 51
        with patch("sys.argv", ["sprintmaster", "test feature", "--lang", long_value]):
            with patch("sprintmaster.cli.Logger"):
                stderr_capture = StringIO()
                with patch("sys.stderr", stderr_capture):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                assert exc_info.value.code == 1
                assert "exceeds" in stderr_capture.getvalue()


class TestMainLangInPayload:
    """Tests for valid language value inclusion in the request payload."""

    def test_valid_lang_in_payload(self):
        """--lang Spanish → payload has 'language': 'Spanish'. Validates: Requirements 1.3"""
        captured_payload = {}

        def capture_send(payload):
            captured_payload.update(payload)
            return {"tickets": [], "token_usage": {"input": 0, "output": 0}, "model_id": "m", "region": "r"}

        with patch("sys.argv", ["sprintmaster", "test feature", "--lang", "Spanish"]):
            with patch("sprintmaster.cli.Logger"):
                with patch("sprintmaster.cli.LambdaClient") as MockClient:
                    mock_instance = MagicMock()
                    mock_instance.send.side_effect = capture_send
                    MockClient.return_value = mock_instance
                    with patch("sprintmaster.cli.OutputFormatter") as MockFormatter:
                        mock_fmt = MagicMock()
                        mock_fmt.parse_and_validate.return_value = []
                        MockFormatter.return_value = mock_fmt
                        with pytest.raises(SystemExit) as exc_info:
                            main()
                        assert exc_info.value.code == 0

        assert captured_payload["language"] == "Spanish"
