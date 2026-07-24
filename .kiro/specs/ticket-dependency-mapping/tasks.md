# Implementation Plan: Ticket Dependency Mapping

## Overview

Add a `dependencies` field to the SprintMaster Ticket model to express blocking relationships between generated tickets. The implementation touches four layers: data model, prompt engineering, output formatting, and test suite. All changes are additive and backward-compatible.

## Tasks

- [x] 1. Add `dependencies` field and validator to the Ticket model
  - [x] 1.1 Add `dependencies` field with validator to `sprintmaster/models.py`
    - Import `Field` from pydantic
    - Add `dependencies: list[str] = Field(default_factory=list, max_length=50)` to the `Ticket` class
    - Add `@field_validator("dependencies")` with `@classmethod` that:
      - Iterates elements and raises `ValueError("los elementos de dependencias no pueden ser vacíos")` for any element where `not item.strip()`
      - Raises `ValueError(f"el elemento de dependencia excede 200 caracteres: {item[:50]}...")` for elements longer than 200 chars
      - Raises `ValueError("las dependencias no pueden contener valores repetidos")` if `len(v) != len(set(v))`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 1.2 Write property test: valid dependencies acceptance
    - Create `tests/property/test_ticket_dependencies.py`
    - **Property 1: Valid dependencies acceptance**
    - Generate lists of 0-50 unique strings (1-200 chars, at least one non-whitespace char) and assert Ticket creation succeeds
    - Use `@settings(max_examples=100)`
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [x] 1.3 Write property test: whitespace-only strings are rejected
    - **Property 2: Whitespace-only strings are rejected**
    - Generate lists where at least one element is whitespace-only and assert `ValidationError` is raised
    - Use `@settings(max_examples=100)`
    - **Validates: Requirements 1.5**

  - [x] 1.4 Write property test: duplicate dependencies are rejected
    - **Property 3: Duplicate dependencies are rejected**
    - Generate lists with at least one duplicate valid string and assert `ValidationError` is raised
    - Use `@settings(max_examples=100)`
    - **Validates: Requirements 1.6**

- [x] 2. Update PromptBuilder with dependency instructions
  - [x] 2.1 Extend `BASE_SYSTEM_PROMPT` in `lambda/prompt_builder.py`
    - Add `"dependencies"` to the list of required fields in the prompt text
    - Add instruction paragraph explaining blocking relationships: a ticket B blocks ticket A when A cannot begin until B is finished
    - Instruct LLM to use exact titles of other tickets from the same response, or empty list `[]` if no blockers
    - Instruct LLM to never include a ticket's own title in its dependencies
    - Update the example JSON response to include `"dependencies"` field (one ticket with `[]`, one with a non-empty list)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. Update OutputFormatter to recognize `dependencies`
  - [x] 3.1 Add `"dependencies"` to `TICKET_KEYS` set in `sprintmaster/output_formatter.py`
    - Add the string `"dependencies"` to the existing `TICKET_KEYS` set
    - No other changes needed: `_humanize_key` already handles single-word keys ("dependencies" → "Dependencies"), `_render_yaml_highlighted` already applies bold cyan to any key in `TICKET_KEYS`, and `model_dump(mode="json")` already includes all fields
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [x] 4. Checkpoint - Ensure core implementation is correct
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Write unit tests for the dependencies feature
  - [x] 5.1 Create unit test file `tests/unit/test_ticket_dependencies.py`
    - Add `test_ticket_dependencies_default_empty`: create Ticket without `dependencies` arg, assert `ticket.dependencies == []`
    - Add `test_ticket_with_valid_dependencies`: create Ticket with `dependencies=["Task A", "Task B"]`, assert no error
    - Add `test_ticket_rejects_whitespace_dependency`: create Ticket with `dependencies=["  "]`, assert `ValidationError`
    - Add `test_ticket_rejects_duplicate_dependencies`: create Ticket with `dependencies=["Task A", "Task A"]`, assert `ValidationError`
    - Add `test_ticket_keys_contains_dependencies`: assert `"dependencies" in TICKET_KEYS`
    - Add `test_prompt_contains_dependencies`: assert `"dependencies"` is present in `BASE_SYSTEM_PROMPT`
    - Add `test_yaml_serialization_with_dependencies`: create Ticket with 2+ dependencies, serialize to YAML via `OutputFormatter.write`, parse back with `yaml.safe_load`, assert `dependencies` key is a list matching input
    - Add `test_json_serialization_with_dependencies`: create Ticket with 2+ dependencies, serialize to JSON via `OutputFormatter.write`, parse back with `json.loads`, assert `dependencies` key is a list matching input
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x] 5.2 Write property test: YAML round-trip preserves dependencies
    - Add to `tests/property/test_ticket_dependencies.py`
    - **Property 4: YAML serialization round-trip preserves dependencies**
    - Generate valid Tickets with 0-10 dependency strings (1-100 chars each), serialize to YAML, deserialize, assert `dependencies` list is identical in content and order
    - Use `@settings(max_examples=100)`
    - **Validates: Requirements 5.2, 3.3, 3.5**

  - [x] 5.3 Write property test: JSON round-trip preserves dependencies
    - Add to `tests/property/test_ticket_dependencies.py`
    - **Property 5: JSON serialization round-trip preserves dependencies**
    - Generate valid Tickets with 0-10 dependency strings (1-100 chars each), serialize to JSON, deserialize, assert `dependencies` list is identical in content and order
    - Use `@settings(max_examples=100)`
    - **Validates: Requirements 5.3, 3.3, 3.5**

  - [x] 5.4 Write property test: invalid dependencies cause ticket omission
    - Add to `tests/property/test_ticket_dependencies.py`
    - **Property 6: Invalid dependencies cause ticket omission**
    - Generate ticket dicts with invalid `dependencies` (whitespace-only or duplicates), pass through `OutputFormatter.parse_and_validate` with a second valid ticket, assert the invalid ticket is omitted and a warning is emitted
    - Use `@settings(max_examples=100)`
    - **Validates: Requirements 5.4**

- [-] 6. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The `ValueError` messages in the validator MUST be in Spanish to match existing codebase conventions (e.g., `"los elementos de dependencias no pueden ser vacíos"`, `"las dependencias no pueden contener valores repetidos"`)
- No changes are needed to `lambda/handler.py` — the `dependencies` field flows transparently through the Lambda response

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "5.1"] },
    { "id": 2, "tasks": ["5.2", "5.3", "5.4"] }
  ]
}
```
