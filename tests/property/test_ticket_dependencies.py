"""Property-based tests for Ticket dependency mapping.

**Validates: Requirements 1.1, 1.2, 1.3, 1.5, 1.6, 5.2, 3.3, 3.5**
"""

import json

import yaml
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


# Feature: ticket-dependency-mapping, Property 4: YAML serialization round-trip preserves dependencies

# Strategy: generate a valid dependency string of 1-100 chars for round-trip tests
roundtrip_dependency_string = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Zs")),
).filter(lambda s: s.strip() != "")

# Strategy: generate a list of 0-10 unique valid dependency strings for round-trip tests
roundtrip_dependencies_list = st.lists(
    roundtrip_dependency_string,
    min_size=0,
    max_size=10,
    unique=True,
)


class TestYamlRoundTripPreservesDependencies:
    """Property 4: YAML serialization round-trip preserves dependencies.

    For any valid Ticket with a `dependencies` list of 0 to 10 elements
    (each 1-100 characters), serializing to YAML and deserializing back
    SHALL produce a list identical to the original in both content and order.

    **Validates: Requirements 5.2, 3.3, 3.5**
    """

    @given(deps=roundtrip_dependencies_list)
    @settings(max_examples=100)
    def test_yaml_roundtrip_preserves_dependencies(self, deps: list[str]) -> None:
        """YAML round-trip preserves dependencies list content and order."""
        ticket = Ticket(
            title="Test Ticket",
            description="A test ticket for round-trip testing",
            acceptance_criteria=["criterion 1"],
            story_points=5,
            priority="high",
            assignee="developer",
            dependencies=deps,
        )

        # Serialize to dict (same as OutputFormatter does)
        ticket_data = ticket.model_dump(mode="json")

        # Serialize to YAML (same settings as _render_plain)
        yaml_str = yaml.dump(
            ticket_data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        # Deserialize back from YAML
        loaded_data = yaml.safe_load(yaml_str)

        # Assert dependencies are identical in content and order
        assert loaded_data["dependencies"] == deps


# Feature: ticket-dependency-mapping, Property 5: JSON serialization round-trip preserves dependencies


class TestJsonRoundTripPreservesDependencies:
    """Property 5: JSON serialization round-trip preserves dependencies.

    For any valid Ticket with a `dependencies` list of 0 to 10 elements
    (each 1-100 characters), serializing to JSON and deserializing back
    SHALL produce a list identical to the original in both content and order.

    **Validates: Requirements 5.3, 3.3, 3.5**
    """

    @given(deps=roundtrip_dependencies_list)
    @settings(max_examples=100)
    def test_json_roundtrip_preserves_dependencies(self, deps: list[str]) -> None:
        """JSON round-trip preserves dependencies list content and order."""
        ticket = Ticket(
            title="Test Ticket",
            description="A test ticket for round-trip testing",
            acceptance_criteria=["criterion 1"],
            story_points=5,
            priority="high",
            assignee="developer",
            dependencies=deps,
        )

        # Serialize to dict (same as OutputFormatter does)
        ticket_data = ticket.model_dump(mode="json")

        # Serialize to JSON
        json_str = json.dumps(ticket_data)

        # Deserialize back from JSON
        loaded_data = json.loads(json_str)

        # Assert dependencies are identical in content and order
        assert loaded_data["dependencies"] == deps


# Feature: ticket-dependency-mapping, Property 6: Invalid dependencies cause ticket omission


from sprintmaster.output_formatter import OutputFormatter


# Strategy: generate a valid ticket dict (always passes validation)
def _make_valid_ticket_dict(title: str = "Valid Ticket") -> dict:
    """Create a valid ticket dict that passes Ticket model validation."""
    return {
        "title": title,
        "description": "A valid ticket for testing",
        "acceptance_criteria": ["criterion 1"],
        "story_points": 5,
        "priority": "high",
        "assignee": "developer",
        "dependencies": [],
    }


# Strategy: generate an invalid ticket dict with whitespace-only dependencies
invalid_ticket_with_whitespace_deps = st.builds(
    lambda ws_dep, valid_deps: {
        "title": "Invalid Ticket WS",
        "description": "Ticket with whitespace-only dependency",
        "acceptance_criteria": ["criterion 1"],
        "story_points": 5,
        "priority": "high",
        "assignee": "developer",
        "dependencies": valid_deps + [ws_dep],
    },
    ws_dep=whitespace_only_string,
    valid_deps=st.lists(valid_dependency_string, min_size=0, max_size=3, unique=True),
)

# Strategy: generate an invalid ticket dict with duplicate dependencies
invalid_ticket_with_duplicate_deps = valid_dependency_string.flatmap(
    lambda dup: st.lists(
        valid_dependency_string.filter(lambda s: s != dup),
        min_size=0,
        max_size=3,
        unique=True,
    ).map(
        lambda others: {
            "title": "Invalid Ticket Dup",
            "description": "Ticket with duplicate dependencies",
            "acceptance_criteria": ["criterion 1"],
            "story_points": 5,
            "priority": "high",
            "assignee": "developer",
            "dependencies": [dup] + others + [dup],
        }
    )
)

# Combined strategy: either whitespace-only or duplicate invalid dependencies
invalid_ticket_strategy = st.one_of(
    invalid_ticket_with_whitespace_deps,
    invalid_ticket_with_duplicate_deps,
)


class TestInvalidDependenciesCauseTicketOmission:
    """Property 6: Invalid dependencies cause ticket omission.

    For any ticket dictionary where the `dependencies` field contains invalid
    values (whitespace-only strings or duplicate entries), passing through
    `OutputFormatter.parse_and_validate` SHALL omit that ticket from the result
    and emit a warning.

    **Validates: Requirements 5.4**
    """

    @given(invalid_ticket=invalid_ticket_strategy)
    @settings(max_examples=100)
    def test_invalid_dependencies_cause_ticket_omission(
        self, invalid_ticket: dict
    ) -> None:
        """Invalid dependency tickets are omitted and a warning is emitted."""
        import io
        from contextlib import redirect_stderr

        valid_ticket = _make_valid_ticket_dict()
        raw = {"tickets": [invalid_ticket, valid_ticket]}

        stderr_capture = io.StringIO()
        formatter = OutputFormatter()

        with redirect_stderr(stderr_capture):
            result = formatter.parse_and_validate(raw)

        # The invalid ticket should be omitted, only the valid ticket remains
        assert len(result) == 1
        assert result[0].title == "Valid Ticket"

        # A warning should be emitted to stderr
        warning_output = stderr_capture.getvalue()
        assert "Advertencia" in warning_output or "inválido" in warning_output
