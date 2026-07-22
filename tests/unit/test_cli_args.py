"""Unit tests for CLI argument parsing, input resolution, and team config loading."""

import argparse
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from sprintmaster.cli import (
    FileNotFoundInputError,
    InputError,
    TeamConfigFileNotFoundError,
    TeamConfigInvalidYAMLError,
    TeamConfigValidationError,
    load_team_config,
    parse_args,
    resolve_input,
)
from sprintmaster.models import TeamConfig


class TestParseArgs:
    """Tests for the parse_args function."""

    def test_positional_feature_description(self):
        args = parse_args(["Build a REST API"])
        assert args.feature_description == "Build a REST API"

    def test_file_flag(self):
        args = parse_args(["--file", "spec.txt"])
        assert args.file == "spec.txt"

    def test_team_config_flag(self):
        args = parse_args(["--team-config", "team.yaml"])
        assert args.team_config == "team.yaml"

    def test_format_default_yaml(self):
        args = parse_args([])
        assert args.format == "yaml"

    def test_format_json(self):
        args = parse_args(["--format", "json"])
        assert args.format == "json"

    def test_format_yaml_explicit(self):
        args = parse_args(["--format", "yaml"])
        assert args.format == "yaml"

    def test_output_flag(self):
        args = parse_args(["--output", "tickets.yaml"])
        assert args.output == "tickets.yaml"

    def test_lambda_url_flag(self):
        args = parse_args(["--lambda-url", "https://example.com/invoke"])
        assert args.lambda_url == "https://example.com/invoke"

    def test_lambda_url_from_env(self):
        with patch.dict("os.environ", {"SPRINTMASTER_LAMBDA_URL": "https://env.example.com"}):
            args = parse_args([])
            assert args.lambda_url == "https://env.example.com"

    def test_lambda_url_flag_overrides_env(self):
        with patch.dict("os.environ", {"SPRINTMASTER_LAMBDA_URL": "https://env.example.com"}):
            args = parse_args(["--lambda-url", "https://flag.example.com"])
            assert args.lambda_url == "https://flag.example.com"

    def test_model_default(self):
        args = parse_args([])
        assert args.model == "us.anthropic.claude-3-haiku-20240307-v1:0"

    def test_model_override(self):
        args = parse_args(["--model", "us.anthropic.claude-3-sonnet-20240229-v1:0"])
        assert args.model == "us.anthropic.claude-3-sonnet-20240229-v1:0"

    def test_verbose_flag(self):
        args = parse_args(["--verbose"])
        assert args.verbose is True

    def test_quiet_flag(self):
        args = parse_args(["--quiet"])
        assert args.quiet is True

    def test_verbose_default_false(self):
        args = parse_args([])
        assert args.verbose is False

    def test_quiet_default_false(self):
        args = parse_args([])
        assert args.quiet is False

    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out

    def test_no_args_no_error(self):
        # parse_args itself doesn't error on missing input; resolve_input handles that
        args = parse_args([])
        assert args.feature_description is None

    def test_all_flags_together(self):
        args = parse_args([
            "Build API",
            "--file", "spec.txt",
            "--team-config", "team.yaml",
            "--format", "json",
            "--output", "out.json",
            "--lambda-url", "https://example.com",
            "--model", "custom-model",
            "--verbose",
        ])
        assert args.feature_description == "Build API"
        assert args.file == "spec.txt"
        assert args.team_config == "team.yaml"
        assert args.format == "json"
        assert args.output == "out.json"
        assert args.lambda_url == "https://example.com"
        assert args.model == "custom-model"
        assert args.verbose is True


class TestResolveInput:
    """Tests for the resolve_input function."""

    def test_positional_arg_priority(self):
        args = argparse.Namespace(feature_description="Hello", file=None)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = resolve_input(args)
        assert result == "Hello"

    def test_file_input(self, tmp_path):
        test_file = tmp_path / "feature.txt"
        test_file.write_text("Feature from file", encoding="utf-8")
        args = argparse.Namespace(feature_description=None, file=str(test_file))
        result = resolve_input(args)
        assert result == "Feature from file"

    def test_file_not_found_error(self):
        args = argparse.Namespace(feature_description=None, file="/nonexistent/path.txt")
        with pytest.raises(FileNotFoundInputError, match="file not found"):
            resolve_input(args)

    def test_stdin_input(self):
        args = argparse.Namespace(feature_description=None, file=None)
        with patch("sys.stdin", new=StringIO("Piped feature description")):
            with patch("sys.stdin.isatty", return_value=False):
                # StringIO doesn't have isatty, so we patch it at module level
                pass
        # Better approach: patch sys.stdin properly
        mock_stdin = StringIO("Piped feature description")
        mock_stdin.isatty = lambda: False
        with patch("sprintmaster.cli.sys.stdin", mock_stdin):
            result = resolve_input(args)
        assert result == "Piped feature description"

    def test_no_input_raises_error(self):
        args = argparse.Namespace(feature_description=None, file=None)
        mock_stdin = StringIO("")
        mock_stdin.isatty = lambda: True
        with patch("sprintmaster.cli.sys.stdin", mock_stdin):
            with pytest.raises(InputError, match="no feature description provided"):
                resolve_input(args)

    def test_positional_takes_priority_over_file(self, tmp_path):
        test_file = tmp_path / "feature.txt"
        test_file.write_text("From file", encoding="utf-8")
        args = argparse.Namespace(feature_description="From positional", file=str(test_file))
        result = resolve_input(args)
        assert result == "From positional"

    def test_file_takes_priority_over_stdin(self, tmp_path):
        test_file = tmp_path / "feature.txt"
        test_file.write_text("From file", encoding="utf-8")
        args = argparse.Namespace(feature_description=None, file=str(test_file))
        mock_stdin = StringIO("From stdin")
        mock_stdin.isatty = lambda: False
        with patch("sprintmaster.cli.sys.stdin", mock_stdin):
            result = resolve_input(args)
        assert result == "From file"

    def test_whitespace_only_positional_falls_through(self, tmp_path):
        test_file = tmp_path / "feature.txt"
        test_file.write_text("From file", encoding="utf-8")
        args = argparse.Namespace(feature_description="   ", file=str(test_file))
        result = resolve_input(args)
        assert result == "From file"

    def test_strips_whitespace(self):
        args = argparse.Namespace(feature_description="  Build API  ", file=None)
        mock_stdin = StringIO("")
        mock_stdin.isatty = lambda: True
        with patch("sprintmaster.cli.sys.stdin", mock_stdin):
            result = resolve_input(args)
        assert result == "Build API"


class TestLoadTeamConfig:
    """Tests for the load_team_config function."""

    def test_no_team_config_returns_none(self):
        args = argparse.Namespace(team_config=None)
        result = load_team_config(args)
        assert result is None

    def test_valid_team_config(self, tmp_path):
        config_file = tmp_path / "team.yaml"
        config_file.write_text(
            "team:\n"
            "  - name: Alice\n"
            "    role: Backend Developer\n"
            "    stack: [Python, FastAPI]\n"
            "  - name: Bob\n"
            "    role: Frontend Developer\n"
            "    stack: [React, TypeScript]\n",
            encoding="utf-8",
        )
        args = argparse.Namespace(team_config=str(config_file))
        result = load_team_config(args)
        assert isinstance(result, TeamConfig)
        assert len(result.team) == 2
        assert result.team[0].name == "Alice"
        assert result.team[1].stack == ["React", "TypeScript"]

    def test_file_not_found_error(self):
        args = argparse.Namespace(team_config="/nonexistent/team.yaml")
        with pytest.raises(TeamConfigFileNotFoundError, match="team config file not found"):
            load_team_config(args)

    def test_invalid_yaml_error(self, tmp_path):
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("{\ninvalid: yaml: [broken", encoding="utf-8")
        args = argparse.Namespace(team_config=str(config_file))
        with pytest.raises(TeamConfigInvalidYAMLError, match="invalid YAML"):
            load_team_config(args)

    def test_empty_file_error(self, tmp_path):
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("", encoding="utf-8")
        args = argparse.Namespace(team_config=str(config_file))
        with pytest.raises(TeamConfigInvalidYAMLError, match="team config file is empty"):
            load_team_config(args)

    def test_schema_validation_error(self, tmp_path):
        config_file = tmp_path / "invalid_schema.yaml"
        config_file.write_text(
            "team:\n"
            "  - name: Alice\n"
            "    missing_role: true\n",
            encoding="utf-8",
        )
        args = argparse.Namespace(team_config=str(config_file))
        with pytest.raises(TeamConfigValidationError, match="team config validation failed"):
            load_team_config(args)

    def test_error_hierarchy_file_not_found_over_yaml(self):
        """File not found error takes priority over YAML parsing."""
        args = argparse.Namespace(team_config="/nonexistent/team.yaml")
        with pytest.raises(TeamConfigFileNotFoundError):
            load_team_config(args)
