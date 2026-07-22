"""Unit tests for OutputFormatter.

Tests cover: YAML/JSON serialization, stdout/file output,
validation of tickets, error handling for malformed responses.
"""

import argparse
import json
import os
import tempfile

import pytest
import yaml

from sprintmaster.models import EXIT_SERVICE_ERROR
from sprintmaster.output_formatter import OutputFormatter


def make_valid_ticket_dict(**overrides):
    """Helper to create a valid ticket dict."""
    base = {
        "title": "Implement login",
        "description": "Add user authentication flow",
        "acceptance_criteria": ["User can log in", "Errors are shown"],
        "story_points": 5,
        "priority": "high",
        "assignee": "Ana García",
    }
    base.update(overrides)
    return base


@pytest.fixture
def formatter():
    return OutputFormatter()


@pytest.fixture
def valid_raw_response():
    return {"tickets": [make_valid_ticket_dict()]}


class TestParseAndValidate:
    """Tests for parse_and_validate method."""

    def test_valid_tickets_are_returned(self, formatter, valid_raw_response):
        """Requirement 5.3: valid tickets pass validation."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        assert len(tickets) == 1
        assert tickets[0].title == "Implement login"
        assert tickets[0].story_points == 5

    def test_multiple_valid_tickets(self, formatter):
        """Multiple valid tickets are all returned."""
        raw = {
            "tickets": [
                make_valid_ticket_dict(title="Ticket 1"),
                make_valid_ticket_dict(title="Ticket 2", story_points=3),
            ]
        }
        tickets = formatter.parse_and_validate(raw)
        assert len(tickets) == 2

    def test_invalid_ticket_emits_warning_and_is_skipped(self, formatter, capsys):
        """Requirement 5.4: invalid ticket emits warning and is omitted."""
        raw = {
            "tickets": [
                make_valid_ticket_dict(),
                make_valid_ticket_dict(story_points=7),  # not Fibonacci
            ]
        }
        tickets = formatter.parse_and_validate(raw)
        assert len(tickets) == 1
        captured = capsys.readouterr()
        assert "Advertencia" in captured.err

    def test_missing_field_emits_warning(self, formatter, capsys):
        """Requirement 5.4: ticket with missing required field is omitted."""
        incomplete = make_valid_ticket_dict()
        del incomplete["title"]
        raw = {"tickets": [make_valid_ticket_dict(), incomplete]}
        tickets = formatter.parse_and_validate(raw)
        assert len(tickets) == 1
        captured = capsys.readouterr()
        assert "Advertencia" in captured.err

    def test_all_tickets_invalid_exits_with_service_error(self, formatter):
        """When all tickets are invalid, exits with EXIT_SERVICE_ERROR."""
        raw = {"tickets": [make_valid_ticket_dict(story_points=7)]}
        with pytest.raises(SystemExit) as exc_info:
            formatter.parse_and_validate(raw)
        assert exc_info.value.code == EXIT_SERVICE_ERROR

    def test_malformed_response_no_tickets_key(self, formatter):
        """Requirement 5.2: malformed response (no tickets key) exits."""
        with pytest.raises(SystemExit) as exc_info:
            formatter.parse_and_validate({"data": []})
        assert exc_info.value.code == EXIT_SERVICE_ERROR

    def test_malformed_response_tickets_not_list(self, formatter):
        """Requirement 5.2: tickets is not a list → exits."""
        with pytest.raises(SystemExit) as exc_info:
            formatter.parse_and_validate({"tickets": "not a list"})
        assert exc_info.value.code == EXIT_SERVICE_ERROR

    def test_malformed_response_not_dict(self, formatter):
        """Requirement 5.2: raw is not a dict → exits."""
        with pytest.raises(SystemExit) as exc_info:
            formatter.parse_and_validate("not a dict")
        assert exc_info.value.code == EXIT_SERVICE_ERROR

    def test_ticket_item_not_dict_is_skipped(self, formatter, capsys):
        """Non-dict items in tickets list are skipped with warning."""
        raw = {"tickets": [make_valid_ticket_dict(), "invalid_item"]}
        tickets = formatter.parse_and_validate(raw)
        assert len(tickets) == 1
        captured = capsys.readouterr()
        assert "Advertencia" in captured.err

    def test_invalid_priority_skipped(self, formatter, capsys):
        """Requirement 5.6: invalid priority value is skipped."""
        raw = {"tickets": [
            make_valid_ticket_dict(),
            make_valid_ticket_dict(priority="critical"),
        ]}
        tickets = formatter.parse_and_validate(raw)
        assert len(tickets) == 1
        captured = capsys.readouterr()
        assert "Advertencia" in captured.err

    def test_empty_assignee_skipped(self, formatter, capsys):
        """Requirement 5.7: whitespace-only assignee is skipped."""
        raw = {"tickets": [
            make_valid_ticket_dict(),
            make_valid_ticket_dict(assignee="   "),
        ]}
        tickets = formatter.parse_and_validate(raw)
        assert len(tickets) == 1
        captured = capsys.readouterr()
        assert "Advertencia" in captured.err


class TestWrite:
    """Tests for write method."""

    def _make_args(self, fmt="yaml", output=None):
        return argparse.Namespace(format=fmt, output=output)

    def test_default_format_is_yaml(self, formatter, valid_raw_response, capsys):
        """Requirement 4.1: YAML is the default format."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        formatter.write(tickets, self._make_args())
        captured = capsys.readouterr()
        # Should be valid YAML — each ticket is rendered individually
        data = list(yaml.safe_load_all(captured.out))
        assert len(data) == 1
        assert data[0]["title"] == "Implement login"

    def test_format_json_produces_valid_json(self, formatter, valid_raw_response, capsys):
        """Requirement 4.2: --format json produces valid JSON."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        formatter.write(tickets, self._make_args(fmt="json"))
        captured = capsys.readouterr()
        # Each ticket is rendered as an individual JSON object
        data = json.loads(captured.out)
        assert isinstance(data, dict)
        assert data["title"] == "Implement login"

    def test_format_yaml_produces_valid_yaml(self, formatter, valid_raw_response, capsys):
        """Requirement 4.3: --format yaml produces valid YAML."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        formatter.write(tickets, self._make_args(fmt="yaml"))
        captured = capsys.readouterr()
        # Each ticket is rendered individually
        data = list(yaml.safe_load_all(captured.out))
        assert len(data) == 1
        assert data[0]["title"] == "Implement login"

    def test_no_output_flag_writes_to_stdout(self, formatter, valid_raw_response, capsys):
        """Requirement 4.4: no --output → write to stdout."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        formatter.write(tickets, self._make_args(output=None))
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_output_flag_writes_to_file(self, formatter, valid_raw_response):
        """Requirement 4.5: --output → write to specified file."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            path = f.name

        try:
            formatter.write(tickets, self._make_args(output=path))
            with open(path, encoding="utf-8") as f:
                data = list(yaml.safe_load_all(f))
            assert len(data) == 1
            assert data[0]["title"] == "Implement login"
        finally:
            os.unlink(path)

    def test_output_json_to_file(self, formatter, valid_raw_response):
        """JSON format written to file is valid."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        try:
            formatter.write(tickets, self._make_args(fmt="json", output=path))
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, dict)
            assert data["title"] == "Implement login"
        finally:
            os.unlink(path)

    def test_all_fields_present_in_yaml_output(self, formatter, valid_raw_response, capsys):
        """Requirement 4.6: each ticket includes all required fields."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        formatter.write(tickets, self._make_args())
        captured = capsys.readouterr()
        data = list(yaml.safe_load_all(captured.out))
        required_fields = {"title", "description", "acceptance_criteria",
                           "story_points", "priority", "assignee"}
        for ticket in data:
            assert required_fields.issubset(ticket.keys())

    def test_all_fields_present_in_json_output(self, formatter, valid_raw_response, capsys):
        """Requirement 4.6: JSON output also includes all required fields."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        formatter.write(tickets, self._make_args(fmt="json"))
        captured = capsys.readouterr()
        # Single ticket rendered as individual JSON object
        data = json.loads(captured.out)
        required_fields = {"title", "description", "acceptance_criteria",
                           "story_points", "priority", "assignee"}
        assert required_fields.issubset(data.keys())

    def test_format_none_defaults_to_yaml(self, formatter, valid_raw_response, capsys):
        """When format is None, defaults to YAML."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        args = argparse.Namespace(format=None, output=None)
        formatter.write(tickets, args)
        captured = capsys.readouterr()
        data = list(yaml.safe_load_all(captured.out))
        assert len(data) == 1
        assert isinstance(data[0], dict)


class TestRenderPlain:
    """Tests for _render_plain method.

    Validates requirements 6.2, 7.3, 8.3, 8.4.
    """

    def test_single_ticket_yaml_to_stdout_no_ansi(self, formatter, capsys):
        """Req 7.3, 8.3: single ticket to stdout has no ANSI and no leading/trailing blank lines."""
        ticket_data = [make_valid_ticket_dict()]
        formatter._render_plain(ticket_data, "yaml", None)
        captured = capsys.readouterr()
        # No ANSI escape sequences
        assert "\x1b" not in captured.out
        # No leading blank line
        assert not captured.out.startswith("\n")
        # No trailing blank line (only single trailing newline is OK)
        lines = captured.out.split("\n")
        # Strip the final newline added for terminal friendliness
        if lines and lines[-1] == "":
            lines = lines[:-1]
        assert lines[0] != ""  # no leading blank
        assert lines[-1] != ""  # no trailing blank

    def test_single_ticket_json_to_stdout_no_ansi(self, formatter, capsys):
        """Req 7.3: single JSON ticket to stdout has no ANSI."""
        ticket_data = [make_valid_ticket_dict()]
        formatter._render_plain(ticket_data, "json", None)
        captured = capsys.readouterr()
        assert "\x1b" not in captured.out
        parsed = json.loads(captured.out)
        assert parsed["title"] == "Implement login"

    def test_multiple_tickets_yaml_blank_line_separation(self, formatter, capsys):
        """Req 8.1, 8.2, 8.4: multiple tickets separated by exactly one blank line."""
        tickets_data = [
            make_valid_ticket_dict(title="Ticket 1"),
            make_valid_ticket_dict(title="Ticket 2"),
            make_valid_ticket_dict(title="Ticket 3"),
        ]
        formatter._render_plain(tickets_data, "yaml", None)
        captured = capsys.readouterr()
        # Count blank line separators: should be exactly 2 (N-1)
        # A blank line separator is \n\n between blocks
        content = captured.out.rstrip("\n")
        assert content.count("\n\n") == 2
        # No leading blank line
        assert not content.startswith("\n")

    def test_multiple_tickets_json_blank_line_separation(self, formatter, capsys):
        """Req 8.1, 8.4: multiple JSON tickets separated by blank lines."""
        tickets_data = [
            make_valid_ticket_dict(title="Ticket A"),
            make_valid_ticket_dict(title="Ticket B"),
        ]
        formatter._render_plain(tickets_data, "json", None)
        captured = capsys.readouterr()
        content = captured.out.rstrip("\n")
        # Should contain one blank line separator between the two JSON blocks
        parts = content.split("\n\n")
        assert len(parts) == 2
        # Each part should be valid JSON
        parsed_a = json.loads(parts[0])
        parsed_b = json.loads(parts[1])
        assert parsed_a["title"] == "Ticket A"
        assert parsed_b["title"] == "Ticket B"

    def test_yaml_to_file_no_ansi(self, formatter):
        """Req 6.2: YAML written to file has no Rich styling or ANSI."""
        tickets_data = [make_valid_ticket_dict()]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            path = f.name
        try:
            formatter._render_plain(tickets_data, "yaml", path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            assert "\x1b" not in content
            data = yaml.safe_load(content)
            assert data["title"] == "Implement login"
        finally:
            os.unlink(path)

    def test_json_to_file_no_ansi(self, formatter):
        """Req 7.3: JSON written to file has no ANSI escape codes."""
        tickets_data = [make_valid_ticket_dict()]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            formatter._render_plain(tickets_data, "json", path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            assert "\x1b" not in content
            data = json.loads(content)
            assert data["title"] == "Implement login"
        finally:
            os.unlink(path)

    def test_multiple_tickets_to_file_same_spacing_as_stdout(self, formatter, capsys):
        """Req 8.4: file output uses same blank-line separation as stdout."""
        tickets_data = [
            make_valid_ticket_dict(title="File Ticket 1"),
            make_valid_ticket_dict(title="File Ticket 2"),
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            path = f.name
        try:
            formatter._render_plain(tickets_data, "yaml", path)
            with open(path, encoding="utf-8") as f:
                file_content = f.read().rstrip("\n")
            # One blank line separator between two tickets
            assert file_content.count("\n\n") == 1
            assert not file_content.startswith("\n")
        finally:
            os.unlink(path)

    def test_yaml_output_is_parseable(self, formatter, capsys):
        """Req 6.2: plain YAML output is valid YAML parseable by standard libraries."""
        tickets_data = [make_valid_ticket_dict()]
        formatter._render_plain(tickets_data, "yaml", None)
        captured = capsys.readouterr()
        data = yaml.safe_load(captured.out)
        assert data["title"] == "Implement login"
        assert data["story_points"] == 5

    def test_serialization_preserves_all_fields(self, formatter, capsys):
        """All ticket fields are present in plain output."""
        ticket = make_valid_ticket_dict()
        formatter._render_plain([ticket], "yaml", None)
        captured = capsys.readouterr()
        data = yaml.safe_load(captured.out)
        for key in ("title", "description", "acceptance_criteria",
                    "story_points", "priority", "assignee"):
            assert key in data
