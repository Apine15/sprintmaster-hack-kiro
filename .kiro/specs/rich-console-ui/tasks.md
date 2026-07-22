# Implementation Plan: Rich Console UI

## Overview

Integrate the Rich library into SprintMaster's CLI to replace plain `print()` calls with styled, color-aware terminal output. The implementation modifies `Logger` and `OutputFormatter` modules to use Rich's `Console` object while preserving backward compatibility with non-TTY environments and existing verbosity contracts.

## Tasks

- [x] 1. Add Rich dependency and set up infrastructure
  - [x] 1.1 Add `rich>=13.0` to pyproject.toml dependencies
    - Add `"rich>=13.0"` to the `[project] dependencies` list in `pyproject.toml`
    - Run `pip install -e .` to install the dependency
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 2. Implement Rich-based Logger
  - [x] 2.1 Refactor Logger to use Rich Console for stderr output
    - Replace `import sys` print calls with `rich.console.Console(stderr=True)`
    - Add `_console` attribute initialized in `__init__`
    - Add `_status` attribute (initially None) for spinner tracking
    - Preserve existing `is_verbose` and `is_quiet` properties unchanged
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 2.2 Implement startup banner method
    - Add `banner()` method that prints "SprintMaster" with `style="bold cyan"`
    - Suppress banner output when `quiet=True`
    - Rich handles non-TTY degradation automatically (plain text without ANSI)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 2.3 Implement styled error messages
    - Modify `error()` method to use `self._console.print(f"❌ Error: {msg}", style="bold red")`
    - Error messages always shown regardless of verbosity mode
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 2.4 Implement styled warning messages
    - Modify `warning()` method to use `self._console.print(f"⚠️ Warning: {msg}", style="yellow")`
    - Warning messages always shown regardless of verbosity mode
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 2.5 Implement animated spinner for progress
    - Add `start_progress(msg)` method using `self._console.status(msg)` with `.start()`
    - Add `stop_progress()` method that calls `.stop()` on active status and resets to None
    - Modify `progress()` method to use spinner display via `console.status()`
    - Suppress spinner and message when `quiet=True`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 2.6 Update verbose method with dim styling
    - Modify `verbose()` to use `self._console.print(msg, style="dim")`
    - Preserve existing logic: show only when verbose=True and quiet=False
    - _Requirements: 1.2_

  - [ ]* 2.7 Write property test for verbosity mode controls (Property 1)
    - **Property 1: Verbosity mode controls message visibility**
    - Generate random (verbose, quiet, message) triples using hypothesis
    - Assert progress suppressed when quiet=True, verbose shown only when verbose=True and quiet=False, warning/error always shown
    - **Validates: Requirements 1.2, 4.4**

  - [ ]* 2.8 Write property test for error message format (Property 2)
    - **Property 2: Error message format preservation**
    - Generate random strings via `hypothesis.strategies.text()`
    - Assert output contains `❌ Error: {input}` with exact input string unmodified
    - **Validates: Requirements 3.2**

  - [ ]* 2.9 Write property test for warning message format (Property 3)
    - **Property 3: Warning message format preservation**
    - Generate random strings via `hypothesis.strategies.text()`
    - Assert output contains `⚠️ Warning: {input}` with exact input string unmodified
    - **Validates: Requirements 4.3**

- [ ] 3. Checkpoint - Verify Logger implementation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement Rich-based OutputFormatter
  - [ ] 4.1 Add Rich Console instance to OutputFormatter
    - Import `Console` from `rich.console` and `Syntax` from `rich.syntax`
    - Add `_stdout_console = Console(file=sys.stdout)` in `__init__`
    - Define `TICKET_KEYS` constant: `{"title", "description", "acceptance_criteria", "story_points", "priority", "assignee"}`
    - _Requirements: 6.1, 7.1_

  - [ ] 4.2 Implement syntax-highlighted YAML rendering
    - Add `_render_yaml_highlighted()` method using `rich.syntax.Syntax` with "yaml" lexer
    - Apply bold cyan styling to the six ticket keys
    - Insert one blank line between consecutive ticket blocks
    - Only used when stdout is connected to a TTY
    - Wrap `Syntax()` in try/except to fall back to plain text on failure
    - _Requirements: 6.1, 7.1, 7.2, 8.1, 8.2_

  - [ ] 4.3 Implement plain text rendering for file and non-TTY output
    - Add `_render_plain()` method for file output and piped stdout
    - Write plain YAML/JSON without Rich styling or ANSI escape sequences
    - Apply same blank-line separation rules between tickets
    - _Requirements: 6.2, 7.3, 8.3, 8.4_

  - [ ] 4.4 Modify write() method to route between styled and plain rendering
    - Detect TTY via `self._stdout_console.is_terminal` (or `sys.stdout.isatty()`)
    - Route to `_render_yaml_highlighted()` for YAML + TTY
    - Route to `_render_plain()` for file output, JSON, or non-TTY
    - Ensure no blank line before first ticket or after last ticket
    - _Requirements: 6.1, 6.2, 7.3, 8.1, 8.2, 8.3_

  - [ ]* 4.5 Write property test for file output plain text (Property 4)
    - **Property 4: File output contains no ANSI escape sequences**
    - Generate random valid tickets using hypothesis Ticket strategy
    - Write to temp file via OutputFormatter, assert no `\x1b` bytes and content is parseable YAML
    - **Validates: Requirements 6.2, 7.3**

  - [ ]* 4.6 Write property test for ticket spacing (Property 5)
    - **Property 5: Ticket spacing invariant**
    - Generate lists of 1-10 valid tickets, render to string
    - Assert separator count equals len(tickets) - 1, no leading/trailing blank lines
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**

  - [ ]* 4.7 Write property test for serialization round-trip (Property 6)
    - **Property 6: Serialization round-trip through formatting**
    - Generate random Ticket objects, serialize via OutputFormatter plain mode
    - Parse back with yaml.safe_load, assert equality with ticket.model_dump(mode="json")
    - **Validates: Requirements 6.2, 8.1**

- [ ] 5. Checkpoint - Verify OutputFormatter implementation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Integration and wiring
  - [ ] 6.1 Update cli.py to use new Logger features
    - Add `logger.banner()` call immediately after Logger initialization (before any other output)
    - Replace `logger.progress("Generating tickets...")` with `logger.start_progress("Generating tickets...")`
    - Add `logger.stop_progress()` after Lambda response is received
    - Replace second `logger.progress("Processing response...")` with `logger.start_progress("Processing response...")`
    - Add `logger.stop_progress()` after processing completes
    - Keep final `logger.progress(f"Done! ...")` as-is (non-spinner message)
    - _Requirements: 2.1, 5.1, 5.2_

  - [ ]* 6.2 Write unit tests for Logger styled output
    - Test banner prints "SprintMaster" and is suppressed in quiet mode
    - Test error/warning contain ❌/⚠️ icons in formatted output
    - Test non-TTY degradation using `Console(no_color=True)` or StringIO
    - Test spinner lifecycle: mock `console.status()` to verify start/stop
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 4.1, 4.3, 5.1, 5.2_

  - [ ]* 6.3 Write unit tests for OutputFormatter styled output
    - Test file output produces valid YAML/JSON with no ANSI sequences
    - Test single ticket has no leading/trailing blank lines
    - Test multiple tickets have exactly one blank line between each
    - Test YAML stdout rendering calls Syntax with "yaml" lexer
    - _Requirements: 6.1, 6.2, 7.3, 8.1, 8.2, 8.3, 8.4_

- [ ] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The Rich library handles TTY detection automatically — no manual ANSI stripping needed
- The existing public API of Logger and OutputFormatter remains unchanged; callers (cli.py) need minimal updates

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6"] },
    { "id": 3, "tasks": ["2.7", "2.8", "2.9", "4.2", "4.3"] },
    { "id": 4, "tasks": ["4.4"] },
    { "id": 5, "tasks": ["4.5", "4.6", "4.7"] },
    { "id": 6, "tasks": ["6.1"] },
    { "id": 7, "tasks": ["6.2", "6.3"] }
  ]
}
```
