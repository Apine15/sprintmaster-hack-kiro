# Design Document: Ticket Dependency Mapping

## Overview

This feature adds a `dependencies` field to the SprintMaster Ticket model, enabling the LLM to express blocking relationships between generated tickets. The change touches four system layers:

1. **Data Model** (`sprintmaster/models.py`) — new optional `dependencies` field with validation
2. **Prompt Engineering** (`lambda/prompt_builder.py`) — instructions for the LLM to analyze and populate blocking relationships
3. **Output Formatting** (`sprintmaster/output_formatter.py`) — serialization and rendering of the new field
4. **Test Suite** (`tests/`) — unit tests and property-based tests covering the integration

The design preserves backward compatibility: tickets without a `dependencies` field default to an empty list, and existing serialization/parsing pipelines continue to work unchanged.

## Architecture

The dependency mapping integrates into the existing linear pipeline:

```mermaid
flowchart LR
    A[User Input] --> B[PromptBuilder]
    B --> C[Bedrock / Claude 3 Haiku]
    C --> D[Lambda Handler]
    D --> E[OutputFormatter.parse_and_validate]
    E --> F[Ticket Model Validation]
    F --> G[OutputFormatter.write]
    G --> H[YAML/JSON Output]
```

The `dependencies` field flows through each stage:
- **PromptBuilder**: instructs the LLM to populate `dependencies` with exact ticket titles
- **LLM Response**: returns JSON with `dependencies: [...]` per ticket
- **parse_and_validate**: validates each ticket through the Pydantic model (rejects invalid dependencies)
- **write**: serializes the field in YAML or JSON output with proper formatting

No new services, APIs, or infrastructure are required. The change is purely additive to existing modules.

## Components and Interfaces

### 1. Ticket Model (`sprintmaster/models.py`)

**Changes:**
- Add `dependencies: list[str] = Field(default_factory=list, max_length=50)` to the `Ticket` class
- Add a `@field_validator("dependencies")` that:
  - Rejects any element that is empty or whitespace-only (raises `ValueError`)
  - Rejects duplicate elements (raises `ValueError`)
  - Validates each element is ≤ 200 characters

```python
class Ticket(BaseModel):
    # ... existing fields ...
    dependencies: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("dependencies")
    @classmethod
    def validate_dependencies(cls, v: list[str]) -> list[str]:
        for item in v:
            if not item.strip():
                raise ValueError("los elementos de dependencias no pueden ser vacíos")
            if len(item) > 200:
                raise ValueError(f"el elemento de dependencia excede 200 caracteres: {item[:50]}...")
        if len(v) != len(set(v)):
            raise ValueError("las dependencias no pueden contener valores repetidos")
        return v
```

### 2. PromptBuilder (`lambda/prompt_builder.py`)

**Changes:**
- Extend `BASE_SYSTEM_PROMPT` to:
  - Add `"dependencies"` to the list of required fields per ticket
  - Add a blocking-relationship instruction paragraph
  - Update the example JSON response to include `dependencies` (one ticket with dependencies, one without)

The dependency instruction will be placed after the existing field definitions:

```
- "dependencies": A list of exact titles of other tickets in this response that MUST be completed
  before this ticket can start. If a ticket has no blockers, use an empty list [].
  A ticket B blocks ticket A when A cannot begin until B is finished.
  Never include the ticket's own title in its dependencies list.
```

### 3. OutputFormatter (`sprintmaster/output_formatter.py`)

**Changes:**
- Add `"dependencies"` to the `TICKET_KEYS` set
- No changes needed to `parse_and_validate` — it already uses `Ticket(**ticket_data)` which will validate dependencies through the model
- No changes needed to `_render_plain` — it uses `ticket.model_dump(mode="json")` which automatically includes the new field
- No changes needed to `_render_yaml_highlighted` — it already handles any key in `TICKET_KEYS` with bold cyan styling and humanized label ("Dependencies")

The `_humanize_key` method already handles single-word keys correctly: `"dependencies"` → `"Dependencies"`.

### 4. Lambda Handler (`lambda/handler.py`)

**No changes required.** The handler passes raw JSON through to the client, and the client's `OutputFormatter` handles validation. The `dependencies` field flows transparently through the Lambda response.

## Data Models

### Updated Ticket Schema

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| title | `str` | required | — |
| description | `str` | required | — |
| acceptance_criteria | `list[str]` | required | — |
| story_points | `int` | required | Must be Fibonacci: {1, 2, 3, 5, 8, 13} |
| priority | `Priority` | required | "high", "medium", "low" |
| assignee | `str` | required | Non-empty after strip |
| **dependencies** | **`list[str]`** | **`[]`** | **Max 50 elements; each 1-200 chars, non-whitespace; no duplicates** |

### Validation Rules for `dependencies`

1. **Type**: Must be a `list` of `str`
2. **Length**: 0 ≤ len ≤ 50
3. **Element format**: Each string must have ≥ 1 non-whitespace character and ≤ 200 total characters
4. **Uniqueness**: No duplicate values allowed
5. **Default**: Empty list `[]` when field is omitted

### Example LLM Response (Updated)

```json
{
  "tickets": [
    {
      "title": "Set up database schema",
      "description": "Create the initial PostgreSQL schema...",
      "acceptance_criteria": ["Tables exist", "Migrations run"],
      "story_points": 5,
      "priority": "high",
      "assignee": "unassigned",
      "dependencies": []
    },
    {
      "title": "Implement user registration",
      "description": "Create registration endpoint...",
      "acceptance_criteria": ["User can register", "Email validation works"],
      "story_points": 8,
      "priority": "high",
      "assignee": "unassigned",
      "dependencies": ["Set up database schema"]
    }
  ]
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Valid dependencies acceptance

*For any* list of 0 to 50 unique strings where each string contains at least one non-whitespace character and is at most 200 characters long, creating a Ticket with that list as `dependencies` SHALL succeed without validation errors.

**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Whitespace-only strings are rejected

*For any* list of strings where at least one element is composed entirely of whitespace characters (spaces, tabs, newlines), creating a Ticket with that list as `dependencies` SHALL raise a `ValidationError`.

**Validates: Requirements 1.5**

### Property 3: Duplicate dependencies are rejected

*For any* list of valid dependency strings that contains at least one duplicate value, creating a Ticket with that list as `dependencies` SHALL raise a `ValidationError`.

**Validates: Requirements 1.6**

### Property 4: YAML serialization round-trip preserves dependencies

*For any* valid Ticket with a `dependencies` list of 0 to 10 elements (each 1-100 characters), serializing to YAML and deserializing back SHALL produce a list identical to the original in both content and order.

**Validates: Requirements 5.2, 3.3, 3.5**

### Property 5: JSON serialization round-trip preserves dependencies

*For any* valid Ticket with a `dependencies` list of 0 to 10 elements (each 1-100 characters), serializing to JSON and deserializing back SHALL produce a list identical to the original in both content and order.

**Validates: Requirements 5.3, 3.3, 3.5**

### Property 6: Invalid dependencies cause ticket omission

*For any* ticket dictionary where the `dependencies` field contains invalid values (whitespace-only strings or duplicate entries), passing through `OutputFormatter.parse_and_validate` SHALL omit that ticket from the result and emit a warning.

**Validates: Requirements 5.4**

## Error Handling

| Scenario | Handler | Behavior |
|----------|---------|----------|
| `dependencies` field missing from LLM response | Pydantic default | Defaults to `[]`, ticket is valid |
| `dependencies` contains empty/whitespace string | `Ticket.validate_dependencies` | Raises `ValidationError` |
| `dependencies` contains duplicates | `Ticket.validate_dependencies` | Raises `ValidationError` |
| `dependencies` has > 50 elements | Pydantic `max_length` | Raises `ValidationError` |
| Element > 200 characters | `Ticket.validate_dependencies` | Raises `ValidationError` |
| `dependencies` is not a list (e.g., string, int) | Pydantic type coercion | Raises `ValidationError` |
| `dependencies` contains non-string elements | Pydantic type validation | Raises `ValidationError` |
| Ticket fails validation in `parse_and_validate` | `OutputFormatter` | Emits warning to stderr, skips ticket |
| All tickets fail validation | `OutputFormatter` | Exits with `EXIT_SERVICE_ERROR` |

Error messages will be in Spanish to match existing conventions in the codebase (e.g., "dependency elements cannot be empty" → "los elementos de dependencias no pueden ser vacíos").

## Testing Strategy

### Property-Based Tests (Hypothesis)

The project already uses `hypothesis>=6.0` for property-based testing. Each correctness property will be implemented as a Hypothesis test with a minimum of 100 examples.

**Library**: Hypothesis (already in `[project.optional-dependencies] dev`)
**Location**: `tests/property/test_ticket_dependencies.py`
**Configuration**: `@settings(max_examples=100)` minimum per property

Each test will be tagged with a comment referencing the design property:
```python
# Feature: ticket-dependency-mapping, Property 1: Valid dependencies acceptance
```

**Generators needed:**
- `valid_dependency_string()`: `st.text(min_size=1, max_size=200, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S', 'Z')))` filtered to ensure at least one non-space char
- `valid_dependencies_list()`: `st.lists(valid_dependency_string(), max_size=50, unique=True)`
- `valid_ticket_strategy()`: builds a complete valid Ticket dict with random dependencies

### Unit Tests

**Location**: `tests/unit/test_ticket_dependencies.py`

| Test | Validates |
|------|-----------|
| `test_ticket_dependencies_default_empty` | Req 4.1 — default is `[]` |
| `test_ticket_with_valid_dependencies` | Req 4.2 — list of valid strings accepted |
| `test_ticket_rejects_whitespace_dependency` | Req 4.3 — whitespace string → `ValidationError` |
| `test_ticket_rejects_duplicate_dependencies` | Req 4.8 — duplicates → `ValidationError` |
| `test_ticket_keys_contains_dependencies` | Req 4.4 — `"dependencies"` in `TICKET_KEYS` |
| `test_prompt_contains_dependencies` | Req 4.5 — `"dependencies"` in `BASE_SYSTEM_PROMPT` |
| `test_yaml_serialization_with_dependencies` | Req 4.6 — YAML output includes parseable dependencies |
| `test_json_serialization_with_dependencies` | Req 4.7 — JSON output includes parseable dependencies |

### Integration Tests

**Location**: `tests/integration/` (if needed)

- End-to-end test with mock LLM response containing dependencies → verify formatted output includes dependencies correctly
- Test that the full pipeline (raw dict → parse_and_validate → write) handles dependencies without regression

### Test Balance

- **Property tests** verify universal correctness (round-trips, validation boundaries) — run 100+ iterations each
- **Unit tests** verify specific examples, edge cases, and integration points — concrete assertions
- Together they provide comprehensive coverage without excessive redundancy
