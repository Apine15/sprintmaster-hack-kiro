"""Property-based tests for Ticket dependency mapping.

**Validates: Requirements 1.1, 1.2, 1.3, 1.5, 1.6**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from sprintmaster.models import Ticket


# Strategy: generate a valid dependency string (1-200 chars, at least one non-whitespace char)
valid_dependency_string = st.text(
    min_size=1,
    max_size=200,
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Zs")),
).filter(lambda s: s.strip() != "")

# Strategy: generate a list of 0-50 unique valid dependency strings
valid_dependencies_list = st.lists(
    valid_dependency_string,
    min_size=0,
    max_size=50,
    unique=True,
)


class TestValidDependenciesAcceptance:
    """Property 1: Valid dependencies acceptance.

    For any list of 0 to 50 unique strings where each string contains at least
    one non-whitespace character and is at most 200 characters long, creating a
    Ticket with that list as `dependencies` SHALL succeed without validation errors.

    **Validates: Requirements 1.1, 1.2, 1.3**
    """

    @given(deps=valid_dependencies_list)
    @settings(max_examples=100)
    def test_valid_dependencies_accepted(self, deps: list[str]) -> None:
        """Ticket creation succeeds for any valid dependencies list."""
        ticket = Ticket(
            title="Test Ticket",
            description="A test ticket for property testing",
            acceptance_criteria=["criterion 1"],
            story_points=5,
            priority="high",
            assignee="developer",
            dependencies=deps,
        )
        assert ticket.dependencies == deps


# Feature: ticket-dependency-mapping, Property 2: Whitespace-only strings are rejected


# Strategy: generate a whitespace-only string (spaces, tabs, newlines)
whitespace_only_string = st.text(
    alphabet=st.sampled_from(" \t\n\r"),
    min_size=1,
    max_size=50,
)

# Strategy: generate a dependencies list where at least one element is whitespace-only
deps_with_whitespace_element = st.lists(
    valid_dependency_string,
    min_size=0,
    max_size=10,
).flatmap(
    lambda valid_deps: whitespace_only_string.flatmap(
        lambda ws: st.integers(min_value=0, max_value=len(valid_deps)).map(
            lambda idx: valid_deps[:idx] + [ws] + valid_deps[idx:]
        )
    )
)


class TestWhitespaceOnlyRejected:
    """Property 2: Whitespace-only strings are rejected.

    For any list of strings where at least one element is composed entirely of
    whitespace characters (spaces, tabs, newlines), creating a Ticket with that
    list as `dependencies` SHALL raise a `ValidationError`.

    **Validates: Requirements 1.5**
    """

    @given(deps=deps_with_whitespace_element)
    @settings(max_examples=100)
    def test_whitespace_only_dependency_rejected(self, deps: list[str]) -> None:
        """Ticket creation raises ValidationError when a dependency is whitespace-only."""
        with pytest.raises(ValidationError):
            Ticket(
                title="Test Ticket",
                description="A test ticket for property testing",
                acceptance_criteria=["criterion 1"],
                story_points=5,
                priority="high",
                assignee="developer",
                dependencies=deps,
            )


# Feature: ticket-dependency-mapping, Property 3: Duplicate dependencies are rejected


# Strategy: generate a dependencies list with at least one duplicate valid string
deps_with_duplicate_element = valid_dependency_string.flatmap(
    lambda dup: st.lists(
        valid_dependency_string.filter(lambda s: s != dup),
        min_size=0,
        max_size=10,
        unique=True,
    ).flatmap(
        lambda unique_deps: st.integers(
            min_value=0, max_value=len(unique_deps)
        ).flatmap(
            lambda idx1: st.integers(
                min_value=idx1, max_value=len(unique_deps) + 1
            ).map(
                lambda idx2: (
                    unique_deps[:idx1] + [dup] + unique_deps[idx1:idx2] + [dup] + unique_deps[idx2:]
                )
            )
        )
    )
)


class TestDuplicateDependenciesRejected:
    """Property 3: Duplicate dependencies are rejected.

    For any list of valid dependency strings that contains at least one duplicate
    value, creating a Ticket with that list as `dependencies` SHALL raise a
    `ValidationError`.

    **Validates: Requirements 1.6**
    """

    @given(deps=deps_with_duplicate_element)
    @settings(max_examples=100)
    def test_duplicate_dependencies_rejected(self, deps: list[str]) -> None:
        """Ticket creation raises ValidationError when dependencies contain duplicates."""
        with pytest.raises(ValidationError):
            Ticket(
                title="Test Ticket",
                description="A test ticket for property testing",
                acceptance_criteria=["criterion 1"],
                story_points=5,
                priority="high",
                assignee="developer",
                dependencies=deps,
            )
