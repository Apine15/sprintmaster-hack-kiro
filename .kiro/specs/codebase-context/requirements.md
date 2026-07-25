# Requirements Document

## Introduction

The Codebase Context feature adds a `--codebase <PATH>` CLI flag to SprintMaster that scans a project's directory structure (file and folder names only, not file contents) and injects the resulting tree representation into the user message sent to the LLM backend. This enables the model to reference real file paths, modules, and architectural patterns from the user's project when generating agile tickets, producing more specific and actionable output.

## Glossary

- **CLI**: The SprintMaster command-line interface entry point (`sprintmaster.cli`)
- **Tree_Scanner**: The module responsible for traversing a directory and producing a textual tree representation of its structure
- **Tree_Representation**: A text string showing the hierarchical directory structure using indentation and tree-drawing characters (e.g., `├──`, `└──`)
- **Ignore_Pattern**: A glob or path pattern specifying files and directories to exclude from scanning (e.g., `node_modules`, `.git`)
- **Depth_Limit**: The maximum number of directory levels to traverse during scanning
- **Codebase_Context_Section**: The formatted text block injected into the user message containing the project structure
- **Lambda_Payload**: The JSON object sent from the CLI to the Lambda backend containing the feature description and metadata
- **Pathspec_Library**: The `pathspec` Python package used to match file paths against `.gitignore`-style patterns with full syntax support

## Requirements

### Requirement 1: CLI Flag Registration

**User Story:** As a developer, I want to specify a project directory via a `--codebase` flag, so that SprintMaster can understand my project structure.

#### Acceptance Criteria

1. THE CLI SHALL accept an optional `--codebase` argument with a `PATH` metavar
2. WHEN the `--codebase` flag is provided with a valid directory path, THE CLI SHALL store the resolved absolute path in the parsed arguments
3. WHEN the `--codebase` flag is provided with a path that does not exist, THE CLI SHALL print an error message to stderr and exit with code 1
4. WHEN the `--codebase` flag is provided with a path that is not a directory, THE CLI SHALL print an error message to stderr and exit with code 1
5. WHEN the `--codebase` flag is not provided, THE CLI SHALL proceed without codebase context

### Requirement 2: Directory Tree Scanning

**User Story:** As a developer, I want SprintMaster to scan my project's directory structure, so that the AI can reference my actual file layout.

#### Acceptance Criteria

1. WHEN a valid directory path is provided, THE Tree_Scanner SHALL produce a Tree_Representation containing all file and folder names within the directory hierarchy
2. THE Tree_Scanner SHALL use tree-drawing characters to indicate hierarchy (indentation with `├──`, `└──`, and `│` connectors)
3. THE Tree_Scanner SHALL list directories before files at each level, both sorted alphabetically
4. THE Tree_Scanner SHALL not read or include file contents in the Tree_Representation
5. THE Tree_Scanner SHALL include the root directory name as the first line of the Tree_Representation
6. WHEN a circular symbolic link is encountered during traversal, THE Tree_Scanner SHALL skip the link and continue scanning the remaining entries to prevent infinite loops

### Requirement 3: Default Ignore Patterns

**User Story:** As a developer, I want common non-essential directories excluded by default, so that the tree output stays focused on meaningful project files.

#### Acceptance Criteria

1. THE Tree_Scanner SHALL exclude directories matching these default patterns: `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `.env`, `.tox`, `.mypy_cache`, `.pytest_cache`, `dist`, `build`, `.next`, `.nuxt`, `target`, `bin/Debug`, `bin/Release`, `obj`
2. THE Tree_Scanner SHALL exclude files matching these default patterns: `.DS_Store`, `Thumbs.db`, `*.pyc`, `*.pyo`
3. WHEN a directory matches an Ignore_Pattern, THE Tree_Scanner SHALL skip the directory and all its contents

### Requirement 4: Gitignore Integration

**User Story:** As a developer, I want SprintMaster to respect my `.gitignore` file, so that excluded files do not appear in the project tree.

#### Acceptance Criteria

1. WHEN a `.gitignore` file exists at the root of the scanned directory, THE Tree_Scanner SHALL read only that root-level `.gitignore` file and exclude matching files and directories (nested `.gitignore` files in subdirectories SHALL be ignored — this is a deliberate simplification for the initial version)
2. THE Tree_Scanner SHALL use the `pathspec` Python library to match `.gitignore` patterns instead of custom regex-based parsing, ensuring full compatibility with gitignore syntax (negations, nested wildcards, etc.)
3. WHEN a `.gitignore` file does not exist in the scanned directory, THE Tree_Scanner SHALL proceed using only the default Ignore_Patterns
4. THE Tree_Scanner SHALL apply `.gitignore` patterns in addition to the default Ignore_Patterns
5. THE Tree_Scanner SHALL treat lines starting with `#` in `.gitignore` as comments and ignore them
6. THE Tree_Scanner SHALL treat empty lines in `.gitignore` as non-matching and skip them

### Requirement 5: Depth Limiting

**User Story:** As a developer, I want the tree scan to have a configurable depth limit, so that deeply nested projects do not produce excessively large output.

#### Acceptance Criteria

1. THE CLI SHALL accept an optional `--codebase-depth` argument with a default value of 4
2. WHEN scanning directories, THE Tree_Scanner SHALL not traverse beyond the configured Depth_Limit levels from the root
3. WHEN a directory exceeds the Depth_Limit, THE Tree_Scanner SHALL display the directory name but not recurse into its contents
4. WHEN the `--codebase-depth` argument is provided with a value less than 1, THE CLI SHALL print an error message to stderr and exit with code 1

### Requirement 6: Output Size Truncation

**User Story:** As a developer, I want the tree output to be truncated if it exceeds a safe size, so that it fits within the LLM's token limits.

#### Acceptance Criteria

1. THE Tree_Scanner SHALL enforce a maximum output size of 10,000 characters for the Tree_Representation
2. WHEN the Tree_Representation exceeds the maximum size, THE Tree_Scanner SHALL truncate the output at the last newline character (`\n`) occurring before the 10,000 character limit, ensuring no filename or tree line is cut in half
3. WHEN truncation occurs, THE Tree_Scanner SHALL append a line indicating truncation (e.g., `... (truncated, X files/directories not shown)`)
4. WHEN truncation occurs and verbose mode is active, THE CLI SHALL log a warning message indicating the tree was truncated

### Requirement 7: Context Injection into User Message

**User Story:** As a developer, I want the project tree to be included in the message sent to the AI, so that generated tickets reference my real project files.

#### Acceptance Criteria

1. WHEN codebase context is available, THE CLI SHALL include a `codebase_context` field in the Lambda_Payload
2. THE `codebase_context` field SHALL contain the Tree_Representation as a plain text string
3. WHEN codebase context is not available, THE CLI SHALL not include the `codebase_context` field in the Lambda_Payload

### Requirement 8: Lambda and Prompt Builder Integration

**User Story:** As a developer, I want the backend to use the codebase context when constructing prompts, so that the model generates project-aware tickets.

#### Acceptance Criteria

1. WHEN the Lambda handler receives a payload with a `codebase_context` field, THE handler SHALL pass the codebase context to the prompt builder
2. WHEN codebase context is provided, THE prompt builder SHALL append a clearly labeled section to the user message containing the project structure
3. THE prompt builder SHALL format the codebase context section with a header (e.g., `PROJECT STRUCTURE:`) followed by the Tree_Representation wrapped in a code block
4. WHEN codebase context is not provided, THE prompt builder SHALL not modify the user message

### Requirement 9: Tree Representation Round-Trip Integrity

**User Story:** As a developer, I want the tree representation to faithfully reflect the scanned directory, so that I can trust the context provided to the AI.

#### Acceptance Criteria

1. FOR ALL directories scanned by the Tree_Scanner, every file and directory included in the Tree_Representation SHALL correspond to an actual file or directory on disk (no fabricated entries)
2. FOR ALL files and directories within the Depth_Limit that do not match any Ignore_Pattern, the Tree_Representation SHALL include them (no silent omissions)
