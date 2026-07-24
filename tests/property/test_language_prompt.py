"""Property-based tests for prompt builder language injection.

**Validates: Requirements 3.1, 3.2, 3.6, 4.4, 4.5**
"""

import os
import sys

# Add lambda directory to path so we can import prompt_builder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda"))

from hypothesis import given, settings
from hypothesis import strategies as st

from prompt_builder import (
    BASE_SYSTEM_PROMPT,
    LANGUAGE_INSTRUCTION_TEMPLATE,
    NO_TEAM_SUFFIX,
    build_messages,
)


# Strategy: generate a valid language string (non-empty, non-whitespace-only, length <= 50)
valid_language_string = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Zs")),
).filter(lambda s: s.strip() != "")

# Strategy: generate a feature description (non-empty string)
feature_description_strategy = st.text(
    min_size=1,
    max_size=200,
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Zs")),
).filter(lambda s: s.strip() != "")

# Strategy: generate team_config as either None or a dict with a "team" list
team_member_strategy = st.fixed_dictionaries(
    {
        "name": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L",))).filter(lambda s: s.strip() != ""),
        "role": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L",))).filter(lambda s: s.strip() != ""),
        "stack": st.lists(
            st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("L", "N"))).filter(lambda s: s.strip() != ""),
            min_size=1,
            max_size=3,
        ),
    }
)

team_config_strategy = st.one_of(
    st.none(),
    st.fixed_dictionaries({"team": st.lists(team_member_strategy, min_size=1, max_size=3)}),
)


class TestPromptBuilderAppendsCorrectLanguageInstruction:
    """Property 8: Prompt builder appends correct Language_Instruction.

    For any non-empty, non-whitespace-only language string and any valid team_config
    (including None), calling build_messages(feature_description, team_config, language=lang)
    SHALL produce a system prompt that ends with a Language_Instruction containing the
    language name and the field names "title", "description", and "acceptance_criteria".

    **Validates: Requirements 3.1, 3.2**
    """

    @given(
        lang=valid_language_string,
        feature_desc=feature_description_strategy,
        team_config=team_config_strategy,
    )
    @settings(max_examples=100)
    def test_prompt_ends_with_language_instruction(
        self, lang: str, feature_desc: str, team_config: dict | None
    ) -> None:
        """System prompt ends with a Language_Instruction containing the language and field names."""
        system_prompt, _ = build_messages(feature_desc, team_config, language=lang)

        expected_instruction = LANGUAGE_INSTRUCTION_TEMPLATE.format(language=lang)

        # The system prompt must end with the language instruction
        assert system_prompt.endswith(expected_instruction), (
            f"System prompt does not end with the expected language instruction.\n"
            f"Expected suffix: {expected_instruction!r}\n"
            f"Actual ending: {system_prompt[-len(expected_instruction) - 50:]!r}"
        )

        # The instruction must contain the language name
        assert lang in system_prompt

        # The instruction must reference the required field names
        assert "title" in expected_instruction
        assert "description" in expected_instruction
        assert "acceptance_criteria" in expected_instruction


class TestPromptBuilderOnlyAppendsNeverModifies:
    """Property 9: Prompt builder only appends, never modifies.

    For any valid inputs (feature_description, team_config, language), the system prompt
    produced by build_messages(..., language=lang) SHALL be equal to
    build_messages(..., language=None)[0] concatenated with exactly one Language_Instruction
    suffix. The base prompt content is a strict prefix of the language-augmented prompt.

    **Validates: Requirements 3.6, 4.4, 4.5**
    """

    @given(
        lang=valid_language_string,
        feature_desc=feature_description_strategy,
        team_config=team_config_strategy,
    )
    @settings(max_examples=100)
    def test_language_prompt_is_base_prompt_plus_instruction(
        self, lang: str, feature_desc: str, team_config: dict | None
    ) -> None:
        """System prompt with language = base prompt (no language) + Language_Instruction."""
        # Build prompt without language
        base_prompt, _ = build_messages(feature_desc, team_config, language=None)

        # Build prompt with language
        lang_prompt, _ = build_messages(feature_desc, team_config, language=lang)

        expected_instruction = LANGUAGE_INSTRUCTION_TEMPLATE.format(language=lang)

        # The language-augmented prompt must be exactly: base_prompt + instruction
        expected_full = base_prompt + expected_instruction
        assert lang_prompt == expected_full, (
            f"Language prompt is not base prompt + instruction.\n"
            f"Base prompt length: {len(base_prompt)}\n"
            f"Language prompt length: {len(lang_prompt)}\n"
            f"Expected length: {len(expected_full)}"
        )

        # The base prompt must be a strict prefix of the language-augmented prompt
        assert lang_prompt.startswith(base_prompt), (
            "Base prompt is not a strict prefix of the language-augmented prompt."
        )

        # The suffix after the base prompt is exactly one Language_Instruction
        suffix = lang_prompt[len(base_prompt):]
        assert suffix == expected_instruction, (
            f"Suffix after base prompt is not exactly the Language_Instruction.\n"
            f"Expected: {expected_instruction!r}\n"
            f"Got: {suffix!r}"
        )
