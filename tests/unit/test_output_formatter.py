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
        # Should be valid YAML
        data = yaml.safe_load(captured.out)
        assert isinstance(data, list)
        assert data[0]["title"] == "Implement login"

    def test_format_json_produces_valid_json(self, formatter, valid_raw_response, capsys):
        """Requirement 4.2: --format json produces valid JSON."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        formatter.write(tickets, self._make_args(fmt="json"))
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["title"] == "Implement login"

    def test_format_yaml_produces_valid_yaml(self, formatter, valid_raw_response, capsys):
        """Requirement 4.3: --format yaml produces valid YAML."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        formatter.write(tickets, self._make_args(fmt="yaml"))
        captured = capsys.readouterr()
        data = yaml.safe_load(captured.out)
        assert isinstance(data, list)
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
                data = yaml.safe_load(f)
            assert isinstance(data, list)
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
            assert isinstance(data, list)
            assert data[0]["title"] == "Implement login"
        finally:
            os.unlink(path)

    def test_all_fields_present_in_yaml_output(self, formatter, valid_raw_response, capsys):
        """Requirement 4.6: each ticket includes all required fields."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        formatter.write(tickets, self._make_args())
        captured = capsys.readouterr()
        data = yaml.safe_load(captured.out)
        required_fields = {"title", "description", "acceptance_criteria",
                           "story_points", "priority", "assignee"}
        for ticket in data:
            assert required_fields.issubset(ticket.keys())

    def test_all_fields_present_in_json_output(self, formatter, valid_raw_response, capsys):
        """Requirement 4.6: JSON output also includes all required fields."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        formatter.write(tickets, self._make_args(fmt="json"))
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        required_fields = {"title", "description", "acceptance_criteria",
                           "story_points", "priority", "assignee"}
        for ticket in data:
            assert required_fields.issubset(ticket.keys())

    def test_format_none_defaults_to_yaml(self, formatter, valid_raw_response, capsys):
        """When format is None, defaults to YAML."""
        tickets = formatter.parse_and_validate(valid_raw_response)
        args = argparse.Namespace(format=None, output=None)
        formatter.write(tickets, args)
        captured = capsys.readouterr()
        data = yaml.safe_load(captured.out)
        assert isinstance(data, list)
