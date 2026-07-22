# Implementation Plan: SprintMaster

## Overview

SprintMaster es una CLI en Python que descompone descripciones de funcionalidades en tickets ágiles estructurados usando AWS Lambda + Bedrock (Claude 3 Haiku). La implementación se divide en: modelos de datos y validación, cliente Lambda con reintentos, formateador de salida, constructor de prompts (Lambda), CLI entry point y wiring final.

## Tasks

- [x] 1. Set up project structure, dependencies and core data models
  - [x] 1.1 Create project structure with pyproject.toml and directory layout
    - Create `sprintmaster/` package with `__init__.py`, `cli.py`, `lambda_client.py`, `output_formatter.py`, `models.py`, `logger.py`
    - Create `lambda/` directory with `handler.py`, `prompt_builder.py`
    - Create `tests/unit/`, `tests/property/`, `tests/integration/` directories
    - Configure `pyproject.toml` with dependencies (pydantic, requests, pyyaml, hypothesis for dev) and `console_scripts` entry point `sprintmaster = sprintmaster.cli:main`
    - _Requirements: 1.1, 7.1_

  - [-] 1.2 Implement Pydantic data models and validation logic
    - Implement `Ticket`, `TeamMember`, `TeamConfig`, `LambdaRequestPayload`, `LambdaResponse`, `TokenUsage` models in `sprintmaster/models.py`
    - Implement `Priority` enum with values high, medium, low
    - Add `field_validator` for `story_points` (must be in Fibonacci set {1,2,3,5,8,13})
    - Add `field_validator` for `assignee` (must be non-empty/non-whitespace string)
    - Define exit code constants: `EXIT_SUCCESS=0`, `EXIT_USER_ERROR=1`, `EXIT_SERVICE_ERROR=2`
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ]* 1.3 Write property test for Ticket schema validation (Property 4)
    - **Property 4: Validación completa del Ticket_Schema**
    - Generate dicts with fields present/missing, valid/invalid values using Hypothesis strategies
    - Verify: valid dicts pass validation, dicts with missing fields or whitespace-only assignee raise ValidationError
    - **Validates: Requirements 5.3, 5.4, 5.7**

  - [ ]* 1.4 Write property test for invalid story_points rejection (Property 2)
    - **Property 2: Valores inválidos de story_points son rechazados**
    - `@given(st.integers().filter(lambda n: n not in FIBONACCI))`
    - Verify: Ticket with non-Fibonacci story_points raises ValidationError
    - **Validates: Requirements 5.5**

  - [ ]* 1.5 Write property test for invalid priority rejection (Property 3)
    - **Property 3: Valores inválidos de priority son rechazados**
    - `@given(st.text(min_size=1).filter(lambda s: s not in {"high","medium","low"}))`
    - Verify: Ticket with invalid priority value raises ValidationError
    - **Validates: Requirements 5.6**

- [x] 2. Implement Output Formatter with serialization and validation
  - [x] 2.1 Implement OutputFormatter class in `sprintmaster/output_formatter.py`
    - Implement `parse_and_validate(raw: dict) -> list[Ticket]` that parses raw response, validates each ticket, emits warnings to stderr for invalid tickets, and returns only valid tickets
    - Implement `write(tickets: list[Ticket], args) -> None` that serializes to YAML (default) or JSON and writes to stdout or file (--output flag)
    - Handle case where all tickets are invalid (exit with EXIT_SERVICE_ERROR)
    - Handle malformed JSON response (exit with EXIT_SERVICE_ERROR)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4_

  - [ ]* 2.2 Write property test for serialization round-trip (Property 1)
    - **Property 1: Round-trip de serialización (YAML y JSON)**
    - `@given(st.sampled_from(["yaml","json"]), st.lists(valid_ticket_strategy(), min_size=1))`
    - Verify: serialize then deserialize produces equivalent list of tickets
    - **Validates: Requirements 4.2, 4.3, 5.1**

  - [ ]* 2.3 Write property test for required fields in serialized output (Property 5)
    - **Property 5: Todos los campos requeridos están presentes en la salida serializada**
    - `@given(st.lists(valid_ticket_strategy(), min_size=1))`
    - Verify: each serialized ticket contains all six fields (title, description, acceptance_criteria, story_points, priority, assignee)
    - **Validates: Requirements 4.6**

- [x] 3. Implement Lambda Client with retries and error handling
  - [x] 3.1 Implement LambdaClient class in `sprintmaster/lambda_client.py`
    - Implement `__init__` reading URL from args.lambda_url or `SPRINTMASTER_LAMBDA_URL` env var
    - Implement `send(payload: dict) -> dict` with HTTP POST, 30s timeout
    - Implement exponential backoff retry for HTTP 429 (max 3 retries, base 1s)
    - Handle HTTP 401/403 → error message + EXIT_SERVICE_ERROR
    - Handle HTTP 5xx → error message + EXIT_SERVICE_ERROR
    - Handle timeout → error message + EXIT_SERVICE_ERROR
    - Handle missing SPRINTMASTER_LAMBDA_URL → error message + EXIT_SERVICE_ERROR
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]* 3.2 Write property test for retry backoff timing (Property 6)
    - **Property 6: Reintentos con backoff exponencial**
    - `@given(st.integers(min_value=1, max_value=3))`
    - Mock HTTP responses to return 429 n times, verify retry count and that wait time >= BASE_BACKOFF_SECONDS × 2^(i-1)
    - **Validates: Requirements 2.5**

  - [ ]* 3.3 Write unit tests for Lambda Client error scenarios
    - Test: SPRINTMASTER_LAMBDA_URL not defined → Exit_Code 2
    - Test: HTTP 429 × 4 times → Exit_Code 2 after retries exhausted
    - Test: HTTP 5xx → Exit_Code 2
    - Test: HTTP 401/403 → Exit_Code 2
    - Test: 30s timeout → Exit_Code 2
    - Test: Malformed JSON response → Exit_Code 2
    - _Requirements: 2.3, 2.5, 2.6, 2.7, 2.8_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement CLI argument parsing and input resolution
  - [x] 5.1 Implement argument parser in `sprintmaster/cli.py`
    - Configure argparse with: positional `feature_description` (optional), `--file`, `--team-config`, `--format` (yaml/json, default yaml), `--output`, `--lambda-url`, `--model`, `--verbose`, `--quiet`, `--version`
    - Add usage examples in epilog for --help output
    - Implement `resolve_input(args)` to handle: positional arg > --file > stdin priority
    - Implement `load_team_config(args)` to parse and validate team YAML file
    - Implement error hierarchy: file not found > invalid YAML > generic usage error
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3_

  - [ ]* 5.2 Write property test for error priority ordering (Property 7)
    - **Property 7: Prioridad del error más específico**
    - Generate combinations of simultaneous error conditions
    - Verify: displayed error corresponds to most specific error per defined hierarchy
    - **Validates: Requirements 1.8**

  - [ ]* 5.3 Write unit tests for CLI argument parsing
    - Test: --help shows usage and exits with code 0
    - Test: --version shows version and exits with code 0
    - Test: --file with non-existent file → Exit_Code 1
    - Test: --team-config with invalid YAML → Exit_Code 1
    - Test: no input provided → Exit_Code 1
    - Test: --format with invalid value → Exit_Code 1
    - _Requirements: 1.4, 1.5, 1.7, 7.1, 7.2_

- [x] 6. Implement Logger and verbosity modes
  - [-] 6.1 Implement Logger class in `sprintmaster/logger.py`
    - Implement `progress(msg)` for standard mode indicator
    - Implement `verbose(msg)` shown only with --verbose flag
    - Implement `warning(msg)` always to stderr
    - Implement `error(msg)` always to stderr
    - Respect --quiet flag: suppress progress/verbose, show only errors
    - With --verbose: show model_id, AWS region, token usage, processing time
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ] 7. Implement Lambda function with Prompt Builder
  - [x] 7.1 Implement Prompt Builder in `lambda/prompt_builder.py`
    - Implement `build_messages(feature_description, team_config)` returning (system_prompt, messages)
    - BASE_SYSTEM_PROMPT instructs model to return JSON with `tickets` array, Fibonacci story points, priority levels
    - When team_config provided: inject team members context into system prompt for intelligent assignment
    - When no team_config: instruct model to set assignee to "unassigned"
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [ ] 7.2 Implement Lambda handler in `lambda/handler.py`
    - Implement `lambda_handler(event, context)` that:
      - Parses request body (feature_description, team_config, model_id)
      - Calls Prompt_Builder to get system_prompt and messages
      - Invokes Bedrock Converse API with boto3
      - Extracts and returns JSON response with tickets, token_usage, model_id, region
    - _Requirements: 2.1, 3.1, 3.3_

  - [ ]* 7.3 Write unit tests for Prompt Builder
    - Test: prompt without team_config includes "unassigned" instruction
    - Test: prompt with team_config includes member names, roles, stacks
    - Test: system prompt instructs Fibonacci story points and priority values
    - _Requirements: 3.1, 3.2, 3.5, 3.6, 3.7, 3.8_

- [ ] 8. Wire CLI entry point and integrate all components
  - [ ] 8.1 Implement main() entry point in `sprintmaster/cli.py`
    - Wire together: parse_args → resolve_input → load_team_config → build_request_payload → LambdaClient.send → OutputFormatter.parse_and_validate → OutputFormatter.write
    - Integrate Logger for progress/verbose/quiet modes
    - Handle all exit codes appropriately
    - Include model_id in request payload (default or --model value)
    - _Requirements: 1.1, 2.1, 4.4, 4.5, 6.3, 6.4, 8.4_

  - [ ]* 8.2 Write integration tests for end-to-end CLI flow
    - Test: full flow with mocked Lambda returning valid tickets → YAML output
    - Test: full flow with --format json → JSON output
    - Test: full flow with --output file → file created with content
    - Test: full flow with --verbose → additional info on stderr
    - Test: full flow with --quiet → only tickets on stdout
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.1, 8.2_

- [ ] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using Hypothesis
- Unit tests validate specific examples and edge cases
- The Lambda function (`lambda/` directory) is deployed independently from the CLI package
- All stderr output (warnings, progress, verbose info) is separated from stdout (ticket output)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "1.4", "1.5", "2.1", "3.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "3.2", "3.3", "5.1", "6.1", "7.1"] },
    { "id": 4, "tasks": ["5.2", "5.3", "7.2", "7.3"] },
    { "id": 5, "tasks": ["8.1"] },
    { "id": 6, "tasks": ["8.2"] }
  ]
}
```
