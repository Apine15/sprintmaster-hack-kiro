"""Unit tests for the Prompt Builder module."""

import sys
import os

# Add lambda directory to path so we can import prompt_builder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda"))

from prompt_builder import (
    BASE_SYSTEM_PROMPT,
    NO_TEAM_SUFFIX,
    build_messages,
    build_team_context_section,
)


class TestBaseSystemPrompt:
    """Tests for the BASE_SYSTEM_PROMPT content."""

    def test_instructs_json_response(self):
        assert "valid JSON" in BASE_SYSTEM_PROMPT

    def test_instructs_tickets_array(self):
        assert '"tickets"' in BASE_SYSTEM_PROMPT

    def test_instructs_fibonacci_story_points(self):
        assert "1, 2, 3, 5, 8, 13" in BASE_SYSTEM_PROMPT

    def test_instructs_priority_levels(self):
        assert '"high"' in BASE_SYSTEM_PROMPT
        assert '"medium"' in BASE_SYSTEM_PROMPT
        assert '"low"' in BASE_SYSTEM_PROMPT

    def test_instructs_required_fields(self):
        assert '"title"' in BASE_SYSTEM_PROMPT
        assert '"description"' in BASE_SYSTEM_PROMPT
        assert '"acceptance_criteria"' in BASE_SYSTEM_PROMPT
        assert '"story_points"' in BASE_SYSTEM_PROMPT
        assert '"priority"' in BASE_SYSTEM_PROMPT
        assert '"assignee"' in BASE_SYSTEM_PROMPT


class TestBuildMessagesWithoutTeamConfig:
    """Tests for build_messages when no team_config is provided."""

    def test_returns_tuple_of_two_elements(self):
        result = build_messages("Build a login page", None)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_system_prompt_contains_base_prompt(self):
        system_prompt, _ = build_messages("Build a login page", None)
        assert BASE_SYSTEM_PROMPT in system_prompt

    def test_system_prompt_contains_unassigned_instruction(self):
        system_prompt, _ = build_messages("Build a login page", None)
        assert "unassigned" in system_prompt

    def test_system_prompt_includes_no_team_suffix(self):
        system_prompt, _ = build_messages("Build a login page", None)
        assert NO_TEAM_SUFFIX in system_prompt

    def test_messages_contain_feature_description(self):
        _, messages = build_messages("Build a login page", None)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == [{"text": "Build a login page"}]

    def test_feature_description_passed_as_user_message(self):
        description = "Implement OAuth2 authentication with Google provider"
        _, messages = build_messages(description, None)
        assert messages[0]["content"][0]["text"] == description


class TestBuildMessagesWithTeamConfig:
    """Tests for build_messages when team_config is provided."""

    SAMPLE_TEAM_CONFIG = {
        "team": [
            {
                "name": "Ana García",
                "role": "Backend Developer",
                "stack": ["Python", "FastAPI", "PostgreSQL"],
            },
            {
                "name": "Luis Pérez",
                "role": "Frontend Developer",
                "stack": ["React", "TypeScript", "Tailwind"],
            },
        ]
    }

    def test_system_prompt_contains_team_members(self):
        system_prompt, _ = build_messages("Build a feature", self.SAMPLE_TEAM_CONFIG)
        assert "Ana García" in system_prompt
        assert "Luis Pérez" in system_prompt

    def test_system_prompt_contains_roles(self):
        system_prompt, _ = build_messages("Build a feature", self.SAMPLE_TEAM_CONFIG)
        assert "Backend Developer" in system_prompt
        assert "Frontend Developer" in system_prompt

    def test_system_prompt_contains_tech_stacks(self):
        system_prompt, _ = build_messages("Build a feature", self.SAMPLE_TEAM_CONFIG)
        assert "Python" in system_prompt
        assert "React" in system_prompt
        assert "TypeScript" in system_prompt

    def test_system_prompt_does_not_contain_no_team_suffix(self):
        system_prompt, _ = build_messages("Build a feature", self.SAMPLE_TEAM_CONFIG)
        assert NO_TEAM_SUFFIX not in system_prompt

    def test_system_prompt_instructs_intelligent_assignment(self):
        system_prompt, _ = build_messages("Build a feature", self.SAMPLE_TEAM_CONFIG)
        assert "most suitable" in system_prompt.lower() or "best match" in system_prompt.lower()

    def test_messages_still_contain_feature_description(self):
        _, messages = build_messages("Build a feature", self.SAMPLE_TEAM_CONFIG)
        assert messages[0]["content"][0]["text"] == "Build a feature"


class TestBuildTeamContextSection:
    """Tests for the build_team_context_section helper."""

    def test_includes_team_member_name(self):
        config = {"team": [{"name": "María Torres", "role": "DevOps", "stack": ["AWS"]}]}
        section = build_team_context_section(config)
        assert "María Torres" in section

    def test_includes_role(self):
        config = {"team": [{"name": "Test", "role": "DevOps Engineer", "stack": []}]}
        section = build_team_context_section(config)
        assert "DevOps Engineer" in section

    def test_includes_stack_items(self):
        config = {"team": [{"name": "Test", "role": "Dev", "stack": ["Terraform", "Docker"]}]}
        section = build_team_context_section(config)
        assert "Terraform" in section
        assert "Docker" in section

    def test_handles_empty_team(self):
        config = {"team": []}
        section = build_team_context_section(config)
        assert "TEAM CONFIGURATION" in section

    def test_handles_missing_stack(self):
        config = {"team": [{"name": "Test", "role": "Dev"}]}
        section = build_team_context_section(config)
        assert "Not specified" in section

    def test_handles_empty_stack(self):
        config = {"team": [{"name": "Test", "role": "Dev", "stack": []}]}
        section = build_team_context_section(config)
        assert "Not specified" in section
