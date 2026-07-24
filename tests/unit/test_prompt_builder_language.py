"""Unit tests for Prompt Builder language injection logic.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

import sys
import os

# Add lambda directory to path so we can import prompt_builder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda"))

from prompt_builder import (
    BASE_SYSTEM_PROMPT,
    LANGUAGE_INSTRUCTION_TEMPLATE,
    NO_TEAM_SUFFIX,
    build_messages,
)


SAMPLE_TEAM_CONFIG = {
    "team": [
        {
            "name": "Ana García",
            "role": "Backend Developer",
            "stack": ["Python", "FastAPI", "PostgreSQL"],
        },
    ]
}


class TestLanguageNoneSkipsInstruction:
    """When language=None, no Language_Instruction is appended. (Req 3.5)"""

    def test_no_language_instruction_with_none_no_team(self):
        system_prompt, _ = build_messages("Build a feature", None, language=None)
        assert "LANGUAGE INSTRUCTION" not in system_prompt

    def test_no_language_instruction_with_none_with_team(self):
        system_prompt, _ = build_messages("Build a feature", SAMPLE_TEAM_CONFIG, language=None)
        assert "LANGUAGE INSTRUCTION" not in system_prompt


class TestLanguageEmptyStringSkipsInstruction:
    """When language="", no Language_Instruction is appended. (Req 3.5)"""

    def test_no_language_instruction_with_empty_string_no_team(self):
        system_prompt, _ = build_messages("Build a feature", None, language="")
        assert "LANGUAGE INSTRUCTION" not in system_prompt

    def test_no_language_instruction_with_empty_string_with_team(self):
        system_prompt, _ = build_messages("Build a feature", SAMPLE_TEAM_CONFIG, language="")
        assert "LANGUAGE INSTRUCTION" not in system_prompt


class TestLanguageEnglishAppendsInstruction:
    """When language="English", Language_Instruction is appended. (Req 3.3)"""

    def test_instruction_appended_with_english_no_team(self):
        system_prompt, _ = build_messages("Build a feature", None, language="English")
        assert "LANGUAGE INSTRUCTION" in system_prompt
        assert "English" in system_prompt.split("LANGUAGE INSTRUCTION")[1]

    def test_instruction_appended_with_english_with_team(self):
        system_prompt, _ = build_messages("Build a feature", SAMPLE_TEAM_CONFIG, language="English")
        assert "LANGUAGE INSTRUCTION" in system_prompt
        assert "English" in system_prompt.split("LANGUAGE INSTRUCTION")[1]


class TestLanguageSpanishContainsRequiredFields:
    """When language="Spanish", instruction contains language name and field names. (Req 3.1, 3.2)"""

    def test_instruction_contains_spanish(self):
        system_prompt, _ = build_messages("Build a feature", None, language="Spanish")
        instruction_section = system_prompt.split("LANGUAGE INSTRUCTION")[1]
        assert "Spanish" in instruction_section

    def test_instruction_contains_title_field(self):
        system_prompt, _ = build_messages("Build a feature", None, language="Spanish")
        instruction_section = system_prompt.split("LANGUAGE INSTRUCTION")[1]
        assert "title" in instruction_section

    def test_instruction_contains_description_field(self):
        system_prompt, _ = build_messages("Build a feature", None, language="Spanish")
        instruction_section = system_prompt.split("LANGUAGE INSTRUCTION")[1]
        assert "description" in instruction_section

    def test_instruction_contains_acceptance_criteria_field(self):
        system_prompt, _ = build_messages("Build a feature", None, language="Spanish")
        instruction_section = system_prompt.split("LANGUAGE INSTRUCTION")[1]
        assert "acceptance_criteria" in instruction_section

    def test_instruction_with_spanish_and_team_config(self):
        system_prompt, _ = build_messages("Build a feature", SAMPLE_TEAM_CONFIG, language="Spanish")
        instruction_section = system_prompt.split("LANGUAGE INSTRUCTION")[1]
        assert "Spanish" in instruction_section
        assert "title" in instruction_section
        assert "description" in instruction_section
        assert "acceptance_criteria" in instruction_section


class TestLanguageInstructionDoesNotModifyExistingSections:
    """Language_Instruction must not modify existing prompt sections. (Req 3.6)"""

    def test_base_prompt_preserved_no_team(self):
        prompt_without_lang, _ = build_messages("Build a feature", None, language=None)
        prompt_with_lang, _ = build_messages("Build a feature", None, language="French")
        # The prompt with language should start with the same content as without
        assert prompt_with_lang.startswith(prompt_without_lang)

    def test_base_prompt_preserved_with_team(self):
        prompt_without_lang, _ = build_messages("Build a feature", SAMPLE_TEAM_CONFIG, language=None)
        prompt_with_lang, _ = build_messages("Build a feature", SAMPLE_TEAM_CONFIG, language="French")
        # The prompt with language should start with the same content as without
        assert prompt_with_lang.startswith(prompt_without_lang)

    def test_json_rules_intact(self):
        system_prompt, _ = build_messages("Build a feature", None, language="German")
        assert "valid JSON" in system_prompt
        assert '"tickets"' in system_prompt

    def test_story_points_rules_intact(self):
        system_prompt, _ = build_messages("Build a feature", None, language="German")
        assert "1, 2, 3, 5, 8, 13" in system_prompt

    def test_priority_rules_intact(self):
        system_prompt, _ = build_messages("Build a feature", None, language="German")
        assert '"high"' in system_prompt
        assert '"medium"' in system_prompt
        assert '"low"' in system_prompt

    def test_no_team_suffix_intact_when_no_team(self):
        system_prompt, _ = build_messages("Build a feature", None, language="German")
        assert NO_TEAM_SUFFIX in system_prompt

    def test_team_context_intact_when_team_provided(self):
        system_prompt, _ = build_messages("Build a feature", SAMPLE_TEAM_CONFIG, language="German")
        assert "Ana García" in system_prompt
        assert "Backend Developer" in system_prompt
        assert "TEAM CONFIGURATION" in system_prompt

    def test_language_instruction_comes_after_no_team_suffix(self):
        system_prompt, _ = build_messages("Build a feature", None, language="Japanese")
        no_team_pos = system_prompt.find("unassigned")
        lang_pos = system_prompt.find("LANGUAGE INSTRUCTION")
        assert lang_pos > no_team_pos

    def test_language_instruction_comes_after_team_context(self):
        system_prompt, _ = build_messages("Build a feature", SAMPLE_TEAM_CONFIG, language="Japanese")
        team_pos = system_prompt.find("TEAM CONFIGURATION")
        lang_pos = system_prompt.find("LANGUAGE INSTRUCTION")
        assert lang_pos > team_pos
