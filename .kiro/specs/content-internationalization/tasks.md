# Implementation Plan: Content Internationalization

## Overview

Add a `--lang` / `-l` CLI argument that propagates a language preference through the data model to the prompt builder, instructing the LLM to generate all ticket content in the specified language. Default is "English" for backward compatibility.

## Tasks

- [x] 1. Add `language` field to the data model
  - [x] 1.1 Add validated `language` field to `LambdaRequestPayload` in `sprintmaster/models.py`
    - Add `language: str = Field(default="English", max_length=50)` field
    - Add `@field_validator("language")` that rejects empty/whitespace-only strings with a `ValueError`
    - Ensure the field serializes alongside `feature_description`, `team_config`, and `model_id`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 1.2 Write property tests for model language validation
    - **Property 5: Model validation accepts valid language strings**
    - **Property 6: Model whitespace rejection**
    - **Property 7: Model max-length rejection**
    - Create `tests/property/test_language_model.py`
    - Use Hypothesis `text()` strategy filtered for valid/invalid cases
    - **Validates: Requirements 2.3, 2.4, 2.5, 2.6**

  - [x] 1.3 Write unit tests for model language field
    - Add tests in `tests/unit/test_models_language.py`
    - Test default value is "English" when field omitted
    - Test valid strings are accepted and serialized
    - Test empty string and whitespace-only raise `ValidationError`
    - Test strings >50 chars raise `ValidationError`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 2. Implement CLI `--lang` argument and validation
  - [x] 2.1 Add `--lang` / `-l` argument to `parse_args()` in `sprintmaster/cli.py`
    - Add `parser.add_argument("--lang", "-l", default="English", metavar="LANGUAGE", help="Language for generated ticket content (default: English)")` alongside existing arguments
    - _Requirements: 1.1, 1.2, 1.4_

  - [x] 2.2 Add language validation and payload inclusion in `main()` in `sprintmaster/cli.py`
    - After `parse_args()`, strip the `args.lang` value
    - If empty/whitespace-only → print `"Error: --lang value must not be blank"` to stderr, exit with `EXIT_USER_ERROR`
    - If length > 50 → print `"Error: --lang value exceeds maximum length of 50 characters"` to stderr, exit with `EXIT_USER_ERROR`
    - Add `"language": args.lang` to the payload dictionary
    - _Requirements: 1.3, 1.5, 1.6_

  - [x] 2.3 Write property tests for CLI language argument
    - **Property 1: CLI language propagation**
    - **Property 2: CLI non-interference**
    - **Property 3: CLI whitespace rejection**
    - **Property 4: CLI max-length rejection**
    - Create `tests/property/test_language_cli.py`
    - Use Hypothesis strategies to generate valid/invalid language strings
    - **Validates: Requirements 1.3, 1.4, 1.5, 1.6**

  - [x] 2.4 Write unit tests for CLI language argument
    - Add tests in `tests/unit/test_cli_lang.py`
    - Test `--lang` and `-l` are accepted by parser
    - Test default is "English" when omitted
    - Test empty/whitespace values cause exit code 1
    - Test values >50 chars cause exit code 1
    - Test valid language included in payload
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement prompt builder language injection
  - [x] 4.1 Add `LANGUAGE_INSTRUCTION_TEMPLATE` and update `build_messages()` in `lambda/prompt_builder.py`
    - Add the `LANGUAGE_INSTRUCTION_TEMPLATE` constant with placeholders for language name and explicit mention of title, description, and acceptance_criteria fields
    - Add optional `language: str | None = None` parameter to `build_messages()`
    - If `language` is not None and not empty after strip, append the formatted instruction at the end of the system prompt
    - Ensure the instruction is appended after team context or no-team suffix
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 4.2 Write property tests for prompt builder language injection
    - **Property 8: Prompt builder appends correct Language_Instruction**
    - **Property 9: Prompt builder only appends, never modifies**
    - Create `tests/property/test_language_prompt.py`
    - Use Hypothesis to generate various language strings and team_config values
    - Verify system prompt with language is a strict prefix extension of the prompt without language
    - **Validates: Requirements 3.1, 3.2, 3.6, 4.4, 4.5**

  - [x] 4.3 Write unit tests for prompt builder language injection
    - Add tests in `tests/unit/test_prompt_builder_language.py`
    - Test `language=None` → no instruction in prompt
    - Test `language=""` → no instruction in prompt
    - Test `language="English"` → instruction appended
    - Test `language="Spanish"` → instruction contains "Spanish", "title", "description", "acceptance_criteria"
    - Test instruction does not modify existing prompt sections
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 5. Wire language through the Lambda handler
  - [x] 5.1 Update `lambda_handler()` in `lambda/handler.py` to extract and pass language
    - Extract `language` from the event body using `body.get("language")`
    - Pass `language=language` to `build_messages()` call
    - Ensure backward compatibility: if `language` key is absent, `None` is passed
    - _Requirements: 4.1, 4.2, 4.4, 4.5_

  - [x] 5.2 Write integration tests for end-to-end language propagation
    - Add tests in `tests/integration/test_language_propagation.py`
    - Test full flow: `--lang Spanish` → payload contains `"language": "Spanish"` → prompt contains language instruction with "Spanish"
    - Test full flow: no `--lang` → "English" in payload → prompt contains English instruction
    - Test full flow: empty `--lang` → CLI exits with code 1
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 6. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties defined in the design
- Unit tests validate specific examples and edge cases
- The design uses Python directly, matching the existing project language
- Existing test infrastructure (`tests/property/`, `tests/unit/`, `tests/integration/`) is reused

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "5.1"] },
    { "id": 5, "tasks": ["5.2"] }
  ]
}
```
