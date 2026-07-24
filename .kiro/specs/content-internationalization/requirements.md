# Requirements Document

## Introduction

This feature enables users to specify the language in which the LLM generates ticket content (titles, descriptions, acceptance criteria, and all other ticket fields). The implementation spans three layers: CLI argument parsing, the data model payload, and the prompt builder's language injection logic. By default, tickets are generated in English, preserving backward compatibility.

## Glossary

- **CLI**: The command-line interface module (`cli.py`) that parses user arguments and orchestrates the application flow.
- **LambdaRequestPayload**: The Pydantic data model (`models.py`) representing the JSON payload sent to the AWS Lambda backend.
- **Prompt_Builder**: The module (`prompt_builder.py`) responsible for constructing the system prompt and user messages for the Bedrock Converse API.
- **Language_Argument**: The `--lang` / `-l` CLI flag that accepts a language name string (e.g., "Spanish", "French", "English").
- **Language_Instruction**: A dynamic text block appended to the end of the system prompt that instructs the LLM to produce all ticket content strictly in the specified language.
- **Ticket_Content**: All textual fields within a generated ticket, including title, description, and acceptance_criteria.

## Requirements

### Requirement 1: CLI Language Argument

**User Story:** As a user, I want to specify a target language via the command line, so that generated tickets are written in my preferred language.

#### Acceptance Criteria

1. THE CLI SHALL accept a `--lang` argument with a short alias `-l` that takes a single string value representing the target language name, with a maximum length of 50 characters.
2. WHEN the `--lang` argument is not provided, THE CLI SHALL default the language value to "English".
3. WHEN the `--lang` argument is provided, THE CLI SHALL include the specified language value under the key `language` in the request payload sent to the Lambda backend.
4. THE CLI SHALL place the `--lang` argument in the argument parser alongside existing arguments (`--format`, `--model`, `--verbose`) without altering their behavior.
5. IF the `--lang` argument value is an empty string or contains only whitespace characters, THEN THE CLI SHALL print an error message indicating that the language value must not be blank to stderr and exit with exit code 1 (EXIT_USER_ERROR).
6. IF the `--lang` argument value exceeds 50 characters, THEN THE CLI SHALL print an error message indicating that the language value exceeds the maximum allowed length to stderr and exit with exit code 1 (EXIT_USER_ERROR).

### Requirement 2: Data Model Language Field

**User Story:** As a developer, I want the request payload schema to include a language field, so that the backend receives the user's language preference in a validated structure.

#### Acceptance Criteria

1. THE LambdaRequestPayload SHALL include a `language` field of type `str`.
2. WHEN the `language` field is not provided during payload construction, THE LambdaRequestPayload SHALL default the field value to "English".
3. THE LambdaRequestPayload SHALL accept any non-empty, non-whitespace-only string with a maximum length of 50 characters as a valid value for the `language` field.
4. IF the `language` field receives an empty string or a whitespace-only string, THEN THE LambdaRequestPayload SHALL raise a Pydantic ValidationError indicating that the language value is invalid.
5. IF the `language` field receives a string exceeding 50 characters, THEN THE LambdaRequestPayload SHALL raise a Pydantic ValidationError indicating that the language value exceeds the maximum length.
6. THE LambdaRequestPayload SHALL serialize the `language` field in the JSON payload alongside `feature_description`, `team_config`, and `model_id`.

### Requirement 3: Prompt Builder Language Injection

**User Story:** As a user, I want the LLM to receive an explicit instruction to write in my chosen language, so that all ticket content is produced in that language.

#### Acceptance Criteria

1. WHEN a non-empty `language` string is provided, THE Prompt_Builder SHALL append a Language_Instruction as a newline-separated section at the end of the system prompt, after the team context section or the no-team suffix.
2. THE Language_Instruction SHALL contain the language name and explicitly reference the Ticket_Content fields (title, description, acceptance_criteria) that must be written in that language.
3. WHEN the language value is "English", THE Prompt_Builder SHALL still append the Language_Instruction to maintain consistent behavior.
4. THE Prompt_Builder `build_messages` function SHALL accept an optional `language` parameter (string or None) in addition to the existing `feature_description` and `team_config` parameters.
5. IF the `language` parameter is None or an empty string, THEN THE Prompt_Builder SHALL not append any Language_Instruction to the system prompt.
6. THE Language_Instruction SHALL NOT modify or remove any existing section of the system prompt (JSON structure rules, story points rules, priority rules, assignee rules, or dependency rules); it SHALL only be appended after all other sections.

### Requirement 4: End-to-End Language Propagation

**User Story:** As a user, I want the language preference to flow seamlessly from the CLI to the generated prompt, so that specifying `--lang Spanish` produces tickets in Spanish without additional configuration.

#### Acceptance Criteria

1. WHEN the user provides `--lang Spanish` on the command line, THE CLI SHALL include a `"language": "Spanish"` key-value pair in the payload dictionary sent to the Lambda backend, and the Lambda handler SHALL pass this value to `build_messages`, resulting in a system prompt that contains an instruction directing the LLM to produce all ticket content in Spanish.
2. WHEN the user does not provide `--lang`, THE CLI SHALL include `"language": "English"` in the payload dictionary sent to the Lambda backend, and the Lambda handler SHALL pass this value to `build_messages`, resulting in a system prompt that contains an instruction directing the LLM to produce all ticket content in English.
3. IF the user provides `--lang` with an empty or whitespace-only value, THEN THE CLI SHALL exit with exit code 1 (EXIT_USER_ERROR) and print an error message indicating that a non-empty language value is required.
4. WHEN the `language` field is present in the payload, THE `build_messages` function SHALL append exactly one language instruction to the system prompt that references the provided language name, without modifying the base system prompt content, the team context section, or the no-team suffix.
5. THE language propagation path SHALL NOT alter the output of feature_description, team_config, or model_id processing; given identical values for these fields, the tickets structure, token_usage, and response format SHALL remain unchanged regardless of the language value.
