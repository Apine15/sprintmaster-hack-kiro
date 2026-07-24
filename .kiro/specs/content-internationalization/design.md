# Design Document: Content Internationalization

## Overview

This feature adds a `--lang` / `-l` CLI argument that lets users control the language in which the LLM generates ticket content (titles, descriptions, acceptance criteria). The value propagates through three layers:

1. **CLI** – Parses and validates the language argument, includes it in the request payload.
2. **Data Model** – Adds a validated `language` field to `LambdaRequestPayload`.
3. **Prompt Builder** – Appends a `Language_Instruction` to the system prompt instructing the LLM to produce content in the specified language.

Default behavior is "English", preserving full backward compatibility for users who do not supply the flag.

## Architecture

```mermaid
flowchart LR
    A[User CLI] -->|--lang Spanish| B[parse_args]
    B --> C[Payload Dict]
    C -->|language: Spanish| D[LambdaClient.send]
    D --> E[Lambda Handler]
    E -->|extract language| F[build_messages]
    F -->|append Language_Instruction| G[System Prompt]
    G --> H[Bedrock Converse API]
    H --> I[Ticket Content in Spanish]
```

The language value flows linearly through the stack without branching or conditional routing. Each layer validates independently, providing defense-in-depth.

## Components and Interfaces

### 1. CLI Layer (`sprintmaster/cli.py`)

**Change:** Add `--lang` / `-l` argument to `parse_args()`.

```python
parser.add_argument(
    "--lang", "-l",
    default="English",
    metavar="LANGUAGE",
    help="Language for generated ticket content (default: English)",
)
```

**Validation (in `main()` before payload construction):**
- Strip the value; if empty/whitespace-only → print error to stderr, exit with `EXIT_USER_ERROR`.
- If `len(value) > 50` → print error to stderr, exit with `EXIT_USER_ERROR`.

**Payload inclusion:**
```python
payload = {
    "feature_description": feature_description,
    "team_config": team_config.model_dump() if team_config else None,
    "model_id": args.model,
    "language": args.lang,  # new field
}
```

### 2. Data Model Layer (`sprintmaster/models.py`)

**Change:** Add `language` field to `LambdaRequestPayload`.

```python
class LambdaRequestPayload(BaseModel):
    feature_description: str
    team_config: TeamConfig | None = None
    model_id: str = "us.anthropic.claude-3-haiku-20240307-v1:0"
    language: str = Field(default="English", max_length=50)

    @field_validator("language")
    @classmethod
    def language_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("language must not be empty or whitespace-only")
        return v
```

**Behavior:**
- Default: `"English"` when not provided.
- Validation: Non-empty after stripping, max 50 characters.
- Serialization: Included alongside `feature_description`, `team_config`, `model_id`.

### 3. Prompt Builder Layer (`lambda/prompt_builder.py`)

**Change:** Add optional `language` parameter to `build_messages()`.

```python
LANGUAGE_INSTRUCTION_TEMPLATE = (
    "\n\nLANGUAGE INSTRUCTION:\n"
    "You MUST write ALL ticket content in {language}. "
    "This includes the title, description, and acceptance_criteria fields. "
    "Only the JSON keys must remain in English."
)

def build_messages(
    feature_description: str,
    team_config: dict | None,
    language: str | None = None,
) -> tuple[str, list]:
    system_prompt = BASE_SYSTEM_PROMPT

    if team_config:
        system_prompt += build_team_context_section(team_config)
    else:
        system_prompt += NO_TEAM_SUFFIX

    if language and language.strip():
        system_prompt += LANGUAGE_INSTRUCTION_TEMPLATE.format(language=language)

    messages = [{"role": "user", "content": [{"text": feature_description}]}]
    return system_prompt, messages
```

**Design decisions:**
- The `Language_Instruction` is always appended last, after team context or no-team suffix.
- Even when language is "English", the instruction is appended for consistency.
- The instruction explicitly names the JSON fields that must be translated.
- JSON keys remain in English to preserve programmatic parsing.

### 4. Lambda Handler Layer (`lambda/handler.py`)

**Change:** Extract `language` from the event body and pass to `build_messages()`.

```python
language = body.get("language")  # None if not present

system_prompt, messages = build_messages(feature_description, team_config, language=language)
```

**Backward compatibility:** If `language` key is absent from the payload (older CLI versions), `body.get("language")` returns `None`, and `build_messages` skips the language instruction — identical to current behavior.

## Data Models

### LambdaRequestPayload (updated)

| Field               | Type               | Default                                         | Constraints              |
|---------------------|--------------------|-------------------------------------------------|--------------------------|
| feature_description | str                | (required)                                      | Non-empty                |
| team_config         | TeamConfig \| None | None                                            | Valid TeamConfig or None  |
| model_id            | str                | "us.anthropic.claude-3-haiku-20240307-v1:0"     | Non-empty                |
| language            | str                | "English"                                       | Non-empty, max 50 chars  |

### Validation Rules for `language`

1. Must not be empty string or whitespace-only → `ValueError`
2. Must not exceed 50 characters → `ValueError` (enforced by `max_length=50`)
3. Any non-empty string ≤50 chars is accepted (no allowlist; supports arbitrary language names)

### Serialized Payload Example

```json
{
  "feature_description": "Implement shopping cart checkout",
  "team_config": null,
  "model_id": "us.anthropic.claude-3-haiku-20240307-v1:0",
  "language": "Spanish"
}
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: CLI language propagation

*For any* non-empty string of length ≤ 50 that is not purely whitespace, when passed as the `--lang` argument to the CLI, the resulting payload dictionary SHALL contain that exact string under the key `"language"`.

**Validates: Requirements 1.3**

### Property 2: CLI non-interference

*For any* combination of valid existing CLI arguments (`--format`, `--model`, `--verbose`, `--file`, etc.) and any valid `--lang` value, the parsed values for all non-language arguments SHALL be identical regardless of whether `--lang` is provided or what value it holds.

**Validates: Requirements 1.4**

### Property 3: CLI whitespace rejection

*For any* string composed entirely of whitespace characters (spaces, tabs, newlines, or the empty string), when passed as `--lang`, the CLI SHALL exit with code 1 and print an error message to stderr.

**Validates: Requirements 1.5**

### Property 4: CLI max-length rejection

*For any* non-empty string with length > 50, when passed as `--lang`, the CLI SHALL exit with code 1 and print an error message to stderr.

**Validates: Requirements 1.6**

### Property 5: Model validation accepts valid language strings

*For any* non-empty, non-whitespace-only string of length ≤ 50, constructing a `LambdaRequestPayload` with that string as the `language` field SHALL succeed without raising a ValidationError, and the serialized output (`model_dump()`) SHALL contain the `"language"` key with that exact string value.

**Validates: Requirements 2.3, 2.6**

### Property 6: Model whitespace rejection

*For any* string composed entirely of whitespace characters (or the empty string), constructing a `LambdaRequestPayload` with that string as the `language` field SHALL raise a Pydantic ValidationError.

**Validates: Requirements 2.4**

### Property 7: Model max-length rejection

*For any* string with length > 50, constructing a `LambdaRequestPayload` with that string as the `language` field SHALL raise a Pydantic ValidationError.

**Validates: Requirements 2.5**

### Property 8: Prompt builder appends correct Language_Instruction

*For any* non-empty, non-whitespace-only language string and any valid team_config (including None), calling `build_messages(feature_description, team_config, language=lang)` SHALL produce a system prompt that ends with a Language_Instruction containing the language name and the field names "title", "description", and "acceptance_criteria".

**Validates: Requirements 3.1, 3.2**

### Property 9: Prompt builder only appends, never modifies

*For any* valid inputs (feature_description, team_config, language), the system prompt produced by `build_messages(..., language=lang)` SHALL be equal to `build_messages(..., language=None)[0]` concatenated with exactly one Language_Instruction suffix. The base prompt content is a strict prefix of the language-augmented prompt.

**Validates: Requirements 3.6, 4.4, 4.5**

## Error Handling

### CLI Layer

| Condition                          | Action                                      | Exit Code |
|------------------------------------|---------------------------------------------|-----------|
| `--lang` value is empty/whitespace | Print error to stderr                       | 1         |
| `--lang` value exceeds 50 chars    | Print error to stderr                       | 1         |
| `--lang` not provided              | Default to "English", continue normally     | —         |

Error messages follow the existing pattern in `cli.py`:
```
Error: --lang value must not be blank
Error: --lang value exceeds maximum length of 50 characters
```

### Data Model Layer

| Condition                          | Action                           |
|------------------------------------|----------------------------------|
| Empty/whitespace `language`        | Raise `ValidationError`          |
| `language` exceeds 50 chars        | Raise `ValidationError`          |
| `language` field absent            | Default to "English"             |

### Prompt Builder Layer

| Condition                          | Action                           |
|------------------------------------|----------------------------------|
| `language` is None                 | Skip Language_Instruction        |
| `language` is empty string         | Skip Language_Instruction        |
| `language` is valid non-empty      | Append Language_Instruction      |

### Lambda Handler Layer

| Condition                          | Action                           |
|------------------------------------|----------------------------------|
| `language` key missing from body   | Pass `None` to `build_messages`  |
| `language` key present             | Pass value to `build_messages`   |

No new HTTP error codes are introduced. Validation happens at the CLI layer before the request reaches Lambda.

## Testing Strategy

### Unit Tests (Example-Based)

| Test                                         | Requirement |
|----------------------------------------------|-------------|
| `--lang` and `-l` are accepted by parser     | 1.1         |
| Default language is "English" when omitted   | 1.2, 2.2    |
| `build_messages` accepts optional `language`  | 3.4         |
| `language=None` → no instruction in prompt   | 3.5         |
| `language=""` → no instruction in prompt     | 3.5         |
| `language="English"` → instruction appended  | 3.3         |

### Property-Based Tests (Hypothesis)

The project already uses Hypothesis (`hypothesis>=6.0` in dev dependencies). Each property test runs a minimum of 100 iterations.

| Property | Test Description                                      | Tag                                                    |
|----------|-------------------------------------------------------|--------------------------------------------------------|
| 1        | Valid lang → payload contains it                      | Feature: content-internationalization, Property 1      |
| 2        | --lang doesn't alter other parsed args                | Feature: content-internationalization, Property 2      |
| 3        | Whitespace strings rejected by CLI                    | Feature: content-internationalization, Property 3      |
| 4        | Strings >50 chars rejected by CLI                     | Feature: content-internationalization, Property 4      |
| 5        | Model accepts valid strings & serializes them         | Feature: content-internationalization, Property 5      |
| 6        | Model rejects whitespace strings                      | Feature: content-internationalization, Property 6      |
| 7        | Model rejects strings >50 chars                       | Feature: content-internationalization, Property 7      |
| 8        | Prompt instruction contains language + field names    | Feature: content-internationalization, Property 8      |
| 9        | Prompt with language = prefix + instruction suffix    | Feature: content-internationalization, Property 9      |

**Configuration:**
- Library: `hypothesis` (already in dev dependencies)
- Minimum iterations: 100 per property (`@settings(max_examples=100)`)
- Generators: `hypothesis.strategies.text`, filtered for non-empty/whitespace constraints

### Integration Tests

| Test                                                       | Requirement |
|------------------------------------------------------------|-------------|
| Full flow: `--lang Spanish` → payload → prompt contains instruction | 4.1    |
| Full flow: no `--lang` → "English" instruction in prompt   | 4.2         |
| Full flow: empty `--lang` → CLI exits with code 1          | 4.3         |
