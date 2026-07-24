"""Property-based tests for LambdaRequestPayload language field validation.

**Validates: Requirements 2.3, 2.4, 2.5, 2.6**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from sprintmaster.models import LambdaRequestPayload


# Strategy: generate a valid language string (non-empty, non-whitespace-only, length <= 50)
valid_language_string = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Zs")),
).filter(lambda s: s.strip() != "")

# Strategy: generate a whitespace-only string (spaces, tabs, newlines, etc.)
whitespace_only_string = st.one_of(
    st.just(""),
    st.text(
        alphabet=st.sampled_from(" \t\n\r"),
        min_size=1,
        max_size=50,
    ),
)

# Strategy: generate a string with length > 50
over_max_length_string = st.text(
    min_size=51,
    max_size=200,
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
).filter(lambda s: s.strip() != "")


class TestModelValidLanguageStrings:
    """Property 5: Model validation accepts valid language strings.

    For any non-empty, non-whitespace-only string of length <= 50, constructing
    a LambdaRequestPayload with that string as the `language` field SHALL succeed
    without raising a ValidationError, and the serialized output (model_dump())
    SHALL contain the "language" key with that exact string value.

    **Validates: Requirements 2.3, 2.6**
    """

    @given(lang=valid_language_string)
    @settings(max_examples=100)
    def test_valid_language_accepted_and_serialized(self, lang: str) -> None:
        """Model accepts any valid language string and serializes it correctly."""
        payload = LambdaRequestPayload(
            feature_description="Test feature",
            language=lang,
        )
        assert payload.language == lang
        dumped = payload.model_dump()
        assert "language" in dumped
        assert dumped["language"] == lang


class TestModelWhitespaceRejection:
    """Property 6: Model whitespace rejection.

    For any string composed entirely of whitespace characters (or the empty
    string), constructing a LambdaRequestPayload with that string as the
    `language` field SHALL raise a Pydantic ValidationError.

    **Validates: Requirements 2.4**
    """

    @given(lang=whitespace_only_string)
    @settings(max_examples=100)
    def test_whitespace_only_language_rejected(self, lang: str) -> None:
        """Model raises ValidationError for whitespace-only or empty language strings."""
        with pytest.raises(ValidationError):
            LambdaRequestPayload(
                feature_description="Test feature",
                language=lang,
            )


class TestModelMaxLengthRejection:
    """Property 7: Model max-length rejection.

    For any string with length > 50, constructing a LambdaRequestPayload with
    that string as the `language` field SHALL raise a Pydantic ValidationError.

    **Validates: Requirements 2.5**
    """

    @given(lang=over_max_length_string)
    @settings(max_examples=100)
    def test_over_max_length_language_rejected(self, lang: str) -> None:
        """Model raises ValidationError for language strings exceeding 50 characters."""
        with pytest.raises(ValidationError):
            LambdaRequestPayload(
                feature_description="Test feature",
                language=lang,
            )
