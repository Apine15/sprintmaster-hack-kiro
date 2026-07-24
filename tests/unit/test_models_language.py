"""Unit tests for the LambdaRequestPayload language field.

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import pytest
from pydantic import ValidationError

from sprintmaster.models import LambdaRequestPayload


class TestLanguageDefault:
    """Test default value behavior for the language field."""

    def test_default_is_english_when_omitted(self):
        """Requirement 2.2: Default value is 'English' when field not provided."""
        payload = LambdaRequestPayload(feature_description="Build a REST API")
        assert payload.language == "English"


class TestLanguageValidStrings:
    """Test that valid language strings are accepted and serialized."""

    @pytest.mark.parametrize("lang", ["Spanish", "French", "日本語", "Português", "中文"])
    def test_valid_strings_accepted(self, lang: str):
        """Requirement 2.3: Valid non-empty strings ≤50 chars are accepted."""
        payload = LambdaRequestPayload(
            feature_description="Build a REST API",
            language=lang,
        )
        assert payload.language == lang

    @pytest.mark.parametrize("lang", ["Spanish", "French", "日本語"])
    def test_valid_strings_in_model_dump(self, lang: str):
        """Requirement 2.6: Language appears correctly in serialized output."""
        payload = LambdaRequestPayload(
            feature_description="Build a REST API",
            language=lang,
        )
        data = payload.model_dump()
        assert data["language"] == lang


class TestLanguageEmptyRejection:
    """Test that empty strings raise ValidationError."""

    def test_empty_string_raises_validation_error(self):
        """Requirement 2.4: Empty string raises ValidationError."""
        with pytest.raises(ValidationError):
            LambdaRequestPayload(
                feature_description="Build a REST API",
                language="",
            )


class TestLanguageWhitespaceRejection:
    """Test that whitespace-only strings raise ValidationError."""

    @pytest.mark.parametrize("whitespace", ["   ", "\t", "\n", " \t\n "])
    def test_whitespace_only_raises_validation_error(self, whitespace: str):
        """Requirement 2.4: Whitespace-only strings raise ValidationError."""
        with pytest.raises(ValidationError):
            LambdaRequestPayload(
                feature_description="Build a REST API",
                language=whitespace,
            )


class TestLanguageMaxLength:
    """Test that strings exceeding 50 characters raise ValidationError."""

    def test_51_chars_raises_validation_error(self):
        """Requirement 2.5: String >50 chars raises ValidationError."""
        long_string = "a" * 51
        with pytest.raises(ValidationError):
            LambdaRequestPayload(
                feature_description="Build a REST API",
                language=long_string,
            )

    def test_50_chars_is_accepted(self):
        """Boundary: exactly 50 chars should be valid."""
        valid_string = "a" * 50
        payload = LambdaRequestPayload(
            feature_description="Build a REST API",
            language=valid_string,
        )
        assert payload.language == valid_string


class TestLanguageSerialization:
    """Test that language key appears in serialized output alongside other fields."""

    def test_language_in_serialized_output(self):
        """Requirement 2.6: language key present in model_dump alongside other fields."""
        payload = LambdaRequestPayload(
            feature_description="Build a REST API",
            team_config=None,
            model_id="us.anthropic.claude-3-haiku-20240307-v1:0",
            language="Spanish",
        )
        data = payload.model_dump()
        assert "feature_description" in data
        assert "team_config" in data
        assert "model_id" in data
        assert "language" in data
        assert data["language"] == "Spanish"
