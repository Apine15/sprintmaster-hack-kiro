"""Bug condition exploration tests for UI/UX visual defects.

These tests encode the EXPECTED (correct) behavior for all 5 bugs.
They are designed to FAIL on the unfixed code, proving the bugs exist.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
"""

from __future__ import annotations

import ast
import inspect
import io
import sys
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sprintmaster.logger import Logger
from sprintmaster.output_formatter import OutputFormatter


class TestBug1BannerMultiLine:
    """Bug 1: Banner should render multi-line ASCII art, not a single line."""

    def test_banner_outputs_multiple_lines(self):
        """Banner output must contain at least 5 lines of ASCII art.

        On unfixed code, banner is only 1 line ('SprintMaster' in bold cyan).
        """
        logger = Logger(quiet=False)

        # Capture stderr output
        captured = io.StringIO()
        with patch.object(logger, "_console") as mock_console:
            # Collect all print calls
            printed_lines = []

            def capture_print(*args, **kwargs):
                for arg in args:
                    printed_lines.append(str(arg))

            mock_console.print = capture_print

            logger.banner()

        # The banner should produce at least 5 lines of output
        # On unfixed code, it produces only 1 line
        assert len(printed_lines) >= 5, (
            f"Banner should output >= 5 lines of ASCII art, "
            f"but got {len(printed_lines)} line(s): {printed_lines}"
        )


class TestBug2ValidationWarningsBypassLogger:
    """Bug 2: Validation warnings should route through logger.warning()."""

    def test_invalid_ticket_triggers_logger_warning(self):
        """When a ticket is invalid, warning should go through logger.warning().

        On unfixed code, print() is used directly, bypassing the logger.
        """
        mock_logger = MagicMock()
        mock_logger.warning = MagicMock()

        # OutputFormatter should accept a logger parameter
        # On unfixed code, __init__ does not accept logger parameter
        try:
            formatter = OutputFormatter(logger=mock_logger)
        except TypeError:
            pytest.fail(
                "OutputFormatter does not accept a 'logger' parameter. "
                "Bug 2 confirmed: validation warnings bypass the logger."
            )

        # Provide invalid ticket data (story_points=99 is not Fibonacci)
        raw_response = {
            "tickets": [
                {
                    "title": "Valid Ticket",
                    "description": "A valid ticket",
                    "acceptance_criteria": ["criterion 1"],
                    "story_points": 3,
                    "priority": "high",
                    "assignee": "dev1",
                },
                {
                    "title": "Invalid Ticket",
                    "description": "Bad ticket",
                    "acceptance_criteria": ["criterion"],
                    "story_points": 99,  # Invalid: not Fibonacci
                    "priority": "high",
                    "assignee": "dev2",
                },
            ]
        }

        formatter.parse_and_validate(raw_response)

        # logger.warning() should have been called for the invalid ticket
        assert mock_logger.warning.called, (
            "logger.warning() was not called for invalid ticket. "
            "Bug 2 confirmed: warnings bypass the logger."
        )


class TestBug3SpinnerOverlap:
    """Bug 3: stop_progress() must be called BEFORE formatter.write()."""

    def test_stop_progress_before_write_in_main(self):
        """In cli.py main(), stop_progress() must precede formatter.write().

        On unfixed code, the sequence is:
            formatter.write(tickets, args)
            logger.stop_progress()
        which causes spinner overlap.
        """
        import sprintmaster.cli as cli_module

        source = inspect.getsource(cli_module.main)
        tree = ast.parse(source)

        # Find positions of stop_progress() and formatter.write() calls
        # in the "Processing response..." block
        stop_progress_line = None
        formatter_write_line = None

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Look for logger.stop_progress() or similar
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "stop_progress":
                        # We want the second stop_progress (after "Processing response...")
                        stop_progress_line = node.lineno
                    elif node.func.attr == "write":
                        # Look for formatter.write()
                        if isinstance(node.func.value, ast.Name) and node.func.value.id == "formatter":
                            formatter_write_line = node.lineno

        assert stop_progress_line is not None, "Could not find stop_progress() call in main()"
        assert formatter_write_line is not None, "Could not find formatter.write() call in main()"

        # Find the second "Processing response..." section
        # In the source, locate start_progress("Processing response...") 
        # then find the stop_progress and write after it
        lines = source.split("\n")
        processing_response_line = None
        for i, line in enumerate(lines, 1):
            if "Processing response" in line:
                processing_response_line = i
                break

        # Now find the LAST stop_progress and the formatter.write after that section
        # We need stop_progress to come BEFORE write
        # Get all stop_progress and write calls with their line numbers
        stop_calls = []
        write_calls = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "stop_progress":
                    stop_calls.append(node.lineno)
                elif (
                    node.func.attr == "write"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "formatter"
                ):
                    write_calls.append(node.lineno)

        # The relevant stop_progress is the one closest to (and after) formatter.write
        # OR it should be BEFORE formatter.write (expected behavior)
        assert len(write_calls) > 0, "No formatter.write() found"
        assert len(stop_calls) >= 2, "Expected at least 2 stop_progress() calls"

        # The last stop_progress should be AFTER the "Processing response" start
        # and it should come BEFORE formatter.write
        write_line = write_calls[-1]

        # Find the stop_progress that is in the same block as formatter.write
        # (after "Processing response..." start_progress)
        relevant_stops = [s for s in stop_calls if s > processing_response_line]

        assert len(relevant_stops) > 0, "No stop_progress after 'Processing response...'"

        # The earliest relevant stop_progress must come BEFORE formatter.write
        earliest_stop = min(relevant_stops)

        assert earliest_stop < write_line, (
            f"stop_progress() (line {earliest_stop}) must come BEFORE "
            f"formatter.write() (line {write_line}). "
            f"Bug 3 confirmed: spinner overlap due to wrong call order."
        )


class TestBug4WarningEmoji:
    """Bug 4: Logger.warning() should use '[!] Warning:' not '⚠️ Warning:'."""

    @given(msg=st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_warning_no_emoji_property(self, msg: str):
        """For ANY message, warning output must not contain ⚠️ emoji.

        On unfixed code, output always contains ⚠️.
        """
        logger = Logger()

        captured = io.StringIO()
        with patch.object(logger, "_console") as mock_console:
            printed_output = []

            def capture_print(*args, **kwargs):
                for arg in args:
                    printed_output.append(str(arg))

            mock_console.print = capture_print
            logger.warning(msg)

        output = " ".join(printed_output)

        # Must NOT contain the warning emoji
        assert "⚠️" not in output, (
            f"Warning output contains ⚠️ emoji: {output!r}. "
            f"Bug 4 confirmed: emoji used instead of text prefix."
        )

        # Must contain the text prefix
        assert "[!] Warning:" in output, (
            f"Warning output missing '[!] Warning:' prefix: {output!r}. "
            f"Bug 4 confirmed: text prefix not used."
        )


class TestBug5ErrorEmoji:
    """Bug 5: Logger.error() should use '[x] Error:' not '❌ Error:'."""

    @given(msg=st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_error_no_emoji_property(self, msg: str):
        """For ANY message, error output must not contain ❌ emoji.

        On unfixed code, output always contains ❌.
        """
        logger = Logger()

        captured = io.StringIO()
        with patch.object(logger, "_console") as mock_console:
            printed_output = []

            def capture_print(*args, **kwargs):
                for arg in args:
                    printed_output.append(str(arg))

            mock_console.print = capture_print
            logger.error(msg)

        output = " ".join(printed_output)

        # Must NOT contain the error emoji
        assert "❌" not in output, (
            f"Error output contains ❌ emoji: {output!r}. "
            f"Bug 5 confirmed: emoji used instead of text prefix."
        )

        # Must contain the text prefix
        assert "[x] Error:" in output, (
            f"Error output missing '[x] Error:' prefix: {output!r}. "
            f"Bug 5 confirmed: text prefix not used."
        )
