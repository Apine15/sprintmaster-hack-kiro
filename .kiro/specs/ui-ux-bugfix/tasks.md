# Implementation Plan

## Overview

Bugfix implementation for UI/UX visual defects in SprintMaster CLI. Follows the exploratory bugfix workflow: write tests to confirm bugs exist, write preservation tests for non-bug behavior, implement fixes, then verify all tests pass.

## Tasks

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - UI/UX Visual Defects in Logger and Output
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate all five bugs exist
  - **Scoped PBT Approach**: Scope the property to concrete failing cases for each bug condition
  - Test file: `tests/property/test_bug_condition_ui_ux.py`
  - **Bug 1 - Banner single-line**: Call `Logger(quiet=False).banner()` and capture stderr output. Assert output contains multiple lines (>= 5 lines of ASCII art). On unfixed code, banner is only 1 line.
  - **Bug 2 - Validation warnings bypass logger**: Create `OutputFormatter` with a mock logger, call `parse_and_validate()` with invalid ticket data, assert `logger.warning()` was called. On unfixed code, print() is used directly instead.
  - **Bug 3 - Spinner overlap**: Inspect the sequence in `cli.py main()` — assert `stop_progress()` is called BEFORE `formatter.write()`. On unfixed code, stop_progress is called AFTER write.
  - **Bug 4 - Warning emoji**: Call `Logger().warning("test msg")` and capture stderr. Assert output does NOT contain ⚠️ emoji and DOES contain "[!] Warning:". On unfixed code, output contains ⚠️.
  - **Bug 5 - Error emoji**: Call `Logger().error("test msg")` and capture stderr. Assert output does NOT contain ❌ emoji and DOES contain "[x] Error:". On unfixed code, output contains ❌.
  - Use `hypothesis` with `@given(st.text(min_size=1, max_size=100))` for property-based tests on warning/error messages to verify no emoji appears for ANY message input
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bugs exist)
  - Document counterexamples found to understand root cause
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Unchanged CLI Behavior for Non-Bug Inputs
  - **IMPORTANT**: Follow observation-first methodology
  - Test file: `tests/property/test_preservation_ui_ux.py`
  - **Observe behavior on UNFIXED code** for non-buggy inputs, then write property-based tests:
  - **Quiet mode suppresses banner (3.1)**: Create `Logger(quiet=True)`, call `banner()`, assert no output to stderr. Observe: quiet mode already works correctly.
  - **Valid tickets produce no warnings (3.2)**: Call `parse_and_validate()` with all-valid ticket data, assert no warning output. Observe: valid tickets produce clean output.
  - **First spinner stops cleanly (3.3)**: Verify the "Generating tickets..." spinner calls `stop_progress()` before verbose metadata. Observe: first spinner sequence is correct in current code.
  - **Verbose mode (3.4)**: Create `Logger(verbose=True)`, call `verbose("msg")`, assert output contains "msg" in dim style. Create `Logger(verbose=False)`, assert verbose messages suppressed.
  - **Non-TTY plain text (3.5)**: Create OutputFormatter with non-TTY console, call `write()`, assert stdout output has no ANSI escape sequences.
  - **Stderr routing (3.6)**: Call `Logger().warning("x")` and `Logger().error("y")`, assert output goes to stderr not stdout.
  - **Quiet shows warnings/errors (3.7)**: Create `Logger(quiet=True)`, call `warning("x")` and `error("y")`, assert they still produce output.
  - Use `hypothesis` with `@given(st.text(min_size=1, max_size=200))` for property-based tests on message content to verify preservation holds for all inputs
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [x] 3. Fix for UI/UX visual defects in SprintMaster CLI

  - [x] 3.1 Replace single-line banner with ASCII art multi-line in logger.py
    - In `sprintmaster/logger.py`, define a `BANNER_ART` constant with multi-line ASCII art text for "SprintMaster" (block or slant style, at least 5 lines)
    - Replace the single `self._console.print("SprintMaster", style="bold cyan")` line in `banner()` with iteration over `BANNER_ART` lines, applying gradient style (bold cyan/magenta)
    - Keep the `if not self._quiet` guard unchanged
    - _Bug_Condition: isBugCondition(input) where input.action == "banner" AND NOT input.quietMode_
    - _Expected_Behavior: banner output has >= 5 lines of ASCII art with gradient colors_
    - _Preservation: --quiet suppresses banner entirely (Requirement 3.1)_
    - _Requirements: 1.1, 2.1, 3.1_

  - [x] 3.2 Replace emoji prefixes with text prefixes in logger.py
    - In `Logger.warning()`: change `f"⚠️ Warning: {msg}"` to `f"[!] Warning: {msg}"`, keep `style="yellow"`
    - In `Logger.error()`: change `f"❌ Error: {msg}"` to `f"[x] Error: {msg}"`, keep `style="bold red"`
    - _Bug_Condition: isBugCondition(input) where input.action IN ["warning", "error"] AND outputContainsEmoji_
    - _Expected_Behavior: output uses "[!]" for warnings and "[x]" for errors, no emoji characters_
    - _Preservation: warning/error still write to stderr, still shown in quiet mode (Requirements 3.6, 3.7)_
    - _Requirements: 1.4, 1.5, 2.4, 2.5, 3.6, 3.7_

  - [x] 3.3 Add logger parameter to OutputFormatter and route validation warnings
    - In `sprintmaster/output_formatter.py`:
      - Modify `OutputFormatter.__init__()` to accept optional `logger` parameter: `def __init__(self, logger=None) -> None`
      - Store as `self._logger = logger`
      - In `parse_and_validate()`, replace `print(f"Advertencia: ticket '{title}' es inválido...", file=sys.stderr)` with `self._logger.warning(...)` when `self._logger` is not None
      - Also replace `print(f"Advertencia: ticket #{i + 1} no es un objeto válido...", file=sys.stderr)` similarly
      - Keep fallback to `print(..., file=sys.stderr)` when no logger is available for backward compatibility
    - _Bug_Condition: isBugCondition(input) where ValidationError occurs and warning routed via print()_
    - _Expected_Behavior: validation warnings route through logger.warning() with yellow styling_
    - _Preservation: Valid tickets produce no warnings (Requirement 3.2)_
    - _Requirements: 1.2, 2.2, 3.2_

  - [x] 3.4 Reorder stop_progress/write in cli.py and pass logger to OutputFormatter
    - In `sprintmaster/cli.py` `main()` function:
      - Move `logger.stop_progress()` to BEFORE `formatter.write(tickets, args)`:
        ```python
        tickets = formatter.parse_and_validate(raw_response)
        logger.stop_progress()          # moved here
        formatter.write(tickets, args)
        # logger.stop_progress()        # removed from here
        ```
      - Change `OutputFormatter()` to `OutputFormatter(logger=logger)` to enable warning routing
    - _Bug_Condition: isBugCondition(input) where spinnerActive AND write invoked before stop_progress_
    - _Expected_Behavior: stop_progress() called before write(), no visual overlap_
    - _Preservation: First spinner "Generating tickets..." still stops cleanly (Requirement 3.3)_
    - _Requirements: 1.3, 2.3, 3.3_

  - [x] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - UI/UX Visual Defects Fixed
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1: `pytest tests/property/test_bug_condition_ui_ux.py -v`
    - **EXPECTED OUTCOME**: Test PASSES (confirms all 5 bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Unchanged CLI Behavior Confirmed
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2: `pytest tests/property/test_preservation_ui_ux.py -v`
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - Run full test suite: `pytest tests/ -v`
  - Verify all property-based tests pass (both bug condition and preservation)
  - Verify existing unit tests in `tests/unit/` still pass (no regressions to existing test_logger.py, test_output_formatter.py, test_cli_args.py)
  - Ensure all tests pass, ask the user if questions arise.


## Task Dependencies

```json
{"dependencies": {"1": [], "2": [], "3.1": ["1", "2"], "3.2": ["1", "2"], "3.3": ["1", "2"], "3.4": ["3.3"], "3.5": ["3.1", "3.2", "3.3", "3.4"], "3.6": ["3.5"], "4": ["3.6"]}}
```

## Notes

- Tasks 1 and 2 are independent and can be written in parallel
- Tasks 3.1, 3.2, 3.3 are independent implementation subtasks
- Task 3.4 depends on 3.3 (needs logger parameter added to OutputFormatter first)
- Use `hypothesis` library for property-based tests (should be installed as dev dependency)
- All tests use `pytest` as the test runner
- The bugfix.md requirement numbers (1.x = current behavior, 2.x = expected behavior, 3.x = preservation) are referenced in task annotations
