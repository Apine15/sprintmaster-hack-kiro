"""Unit tests for the Ticket dependencies feature.

Tests cover: default value, valid dependencies, validation rejection,
TICKET_KEYS membership, prompt content, and YAML/JSON serialization.
"""

import argparse
import json
import os
import sys

import pytest
import yaml
from pydantic import ValidationError

# Add lambda directory to path so we can import prompt_builder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda"))

from prompt_builder import BASE_SYSTEM_PROMPT

from sprintmaster.models import Ticket
from sprintmaster.output_formatter import TICKET_KEYS, OutputFormatter


def make_valid_ticket(**overrides):
    """Helper to create a valid Ticket with sensible defaults."""
    kwargs = {
        "title": "Implement login",
        "description": "Add user authentication flow",
        "acceptance_criteria": ["User can log in", "Errors are shown"],
        "story_points": 5,
        "priority": "high",
        "assignee": "Ana García",
    }
    kwargs.update(overrides)
    return Ticket(**kwargs)


class TestTicketDependenciesModel:
    """Tests for the dependencies field on the Ticket model."""

    def test_ticket_dependencies_default_empty(self):
        """Req 4.1: Ticket without dependencies arg defaults to []."""
        ticket = make_valid_ticket()
        assert ticket.dependencies == []

    def test_ticket_with_valid_dependencies(self):
        """Req 4.2: Ticket with valid dependency strings is accepted."""
        ticket = make_valid_ticket(dependencies=["Task A", "Task B"])
        assert ticket.dependencies == ["Task A", "Task B"]

    def test_ticket_rejects_whitespace_dependency(self):
        """Req 4.3: Ticket with whitespace-only dependency raises ValidationError."""
        with pytest.raises(ValidationError):
            make_valid_ticket(dependencies=["  "])

    def test_ticket_rejects_duplicate_dependencies(self):
        """Req 4.8: Ticket with duplicate dependencies raises ValidationError."""
        with pytest.raises(ValidationError):
            make_valid_ticket(dependencies=["Task A", "Task A"])


class TestTicketKeysAndPrompt:
    """Tests for TICKET_KEYS and BASE_SYSTEM_PROMPT integration."""

    def test_ticket_keys_contains_dependencies(self):
        """Req 4.4: TICKET_KEYS set includes 'dependencies'."""
        assert "dependencies" in TICKET_KEYS

    def test_prompt_contains_dependencies(self):
        """Req 4.5: BASE_SYSTEM_PROMPT mentions 'dependencies'."""
        assert "dependencies" in BASE_SYSTEM_PROMPT


class TestDependenciesSerialization:
    """Tests for YAML and JSON serialization of dependencies."""

    def test_yaml_serialization_with_dependencies(self, capsys):
        """Req 4.6: YAML output includes dependencies as a parseable list."""
        ticket = make_valid_ticket(dependencies=["Set up DB", "Create API"])
        formatter = OutputFormatter()
        args = argparse.Namespace(format="yaml", output=None)
        formatter.write([ticket], args)

        captured = capsys.readouterr()
        data = yaml.safe_load(captured.out)
        assert "dependencies" in data
        assert isinstance(data["dependencies"], list)
        assert data["dependencies"] == ["Set up DB", "Create API"]

    def test_json_serialization_with_dependencies(self, capsys):
        """Req 4.7: JSON output includes dependencies as a parseable list."""
        ticket = make_valid_ticket(dependencies=["Set up DB", "Create API"])
        formatter = OutputFormatter()
        args = argparse.Namespace(format="json", output=None)
        formatter.write([ticket], args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "dependencies" in data
        assert isinstance(data["dependencies"], list)
        assert data["dependencies"] == ["Set up DB", "Create API"]
