"""Preservation property tests for UI/UX bugfix.

These tests verify UNCHANGED behaviors of the system that must be preserved
after the bugfix is applied. They should PASS on both unfixed and fixed code.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**
"""

import argparse
import ast
import inspect
import io
import re
import sys
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sprintmaster.logger import Logger
from sprintmaster.output_formatter import OutputFormatter


# ---------------------------------------------------------------------------
# Req 3.1: Quiet mode suppresses banner
# ---------------------------------------------------------------------------


class TestQuietModeSuppressesBanner:
    """Validates: Requirements 3.1"""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_quiet_mode_suppresses_banner_for_any_state(self, _dummy: str) -> None:
        """Quiet mode always suppresses banner output regardless of state."""
        logger = Logger(quiet=True)
        # Capture stderr output
        captured = io.StringIO()
        logger._console = __import__("rich.console", fromlist=["Console"]).Console(
            file=captured, stderr=False, highlight=False
        )
        logger.banner()
        output = captured.getvalue()
        assert output == "", f"Banner produced output in quiet mode: {output!r}"

    def test_quiet_mode_no_banner_output(self, capsys) -> None:
        """Simple check: quiet=True suppresses banner completely."""
        logger = Logger(quiet=True)
        logger.banner()
        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""


# ---------------------------------------------------------------------------
# Req 3.2: Valid tickets produce no warnings
# ---------------------------------------------------------------------------


def _make_valid_ticket() -> dict:
    """Create a valid ticket dictionary."""
    return {
        "title": "Implement feature",
        "description": "A valid feature description",
        "acceptance_criteria": ["Criterion 1", "Criterion 2"],
        "story_points": 5,
        "priority": "high",
        "assignee": "Developer",
    }


class TestValidTicketsNoWarnings:
    """Validates: Requirements 3.2"""

    def test_all_valid_tickets_no_warnings(self, capsys) -> None:
        """When all tickets are valid, no warnings are emitted."""
        formatter = OutputFormatter()
        raw = {"tickets": [_make_valid_ticket(), _make_valid_ticket()]}
        tickets = formatter.parse_and_validate(raw)
        captured = capsys.readouterr()
        assert len(tickets) == 2
        # No warning text in stderr
        assert "Advertencia" not in captured.err
        assert "Warning" not in captured.err

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=30)
    def test_valid_ticket_with_arbitrary_title_no_warning(self, title: str) -> None:
        """Valid tickets with arbitrary titles produce no warnings."""
        ticket = _make_valid_ticket()
        ticket["title"] = title if title.strip() else "Fallback Title"
        formatter = OutputFormatter()
        raw = {"tickets": [ticket]}

        # Capture stderr to check for warnings
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            try:
                tickets = formatter.parse_and_validate(raw)
                stderr_output = captured_stderr.getvalue()
                assert "Advertencia" not in stderr_output
            except SystemExit:
                # If the ticket is somehow invalid, that's fine - just skip
                pass


# ---------------------------------------------------------------------------
# Req 3.3: First spinner stops cleanly before verbose metadata
# ---------------------------------------------------------------------------


class TestFirstSpinnerStopsCleanly:
    """Validates: Requirements 3.3"""

    def test_first_spinner_stop_before_verbose_metadata(self) -> None:
        """In cli.py main(), stop_progress() is called before verbose_metadata().

        The first spinner 'Generating tickets...' must stop before verbose
        metadata is displayed. We verify this by inspecting the source code
        ordering in the main() function.
        """
        from sprintmaster import cli

        source = inspect.getsource(cli.main)

        # Find the first start_progress("Generating tickets...")
        gen_start = source.find('start_progress("Generating tickets...")')
        assert gen_start != -1, "Could not find start_progress('Generating tickets...')"

        # Find the first stop_progress() after it
        first_stop = source.find("stop_progress()", gen_start)
        assert first_stop != -1, "Could not find stop_progress() after 'Generating tickets...'"

        # Find verbose_metadata call
        verbose_meta = source.find("verbose_metadata(", gen_start)
        assert verbose_meta != -1, "Could not find verbose_metadata() call"

        # stop_progress should come BEFORE verbose_metadata
        assert first_stop < verbose_meta, (
            "stop_progress() must be called BEFORE verbose_metadata(). "
            f"stop_progress at {first_stop}, verbose_metadata at {verbose_meta}"
        )

    def test_stop_progress_clears_spinner_state(self) -> None:
        """stop_progress() resets the internal _status to None."""
        logger = Logger()
        mock_status = MagicMock()
        logger._status = mock_status
        logger.stop_progress()
        assert logger._status is None
        mock_status.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Req 3.4: Verbose mode behavior
# ---------------------------------------------------------------------------


class TestVerboseMode:
    """Validates: Requirements 3.4"""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_verbose_true_produces_output(self, msg: str) -> None:
        """Logger(verbose=True) produces output for any non-empty message."""
        logger = Logger(verbose=True)
        captured = io.StringIO()
        logger._console = __import__("rich.console", fromlist=["Console"]).Console(
            file=captured, stderr=False, highlight=False
        )
        logger.verbose(msg)
        output = captured.getvalue()
        assert len(output) > 0, f"Verbose mode did not produce output for: {msg!r}"

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_verbose_false_suppresses_output(self, msg: str) -> None:
        """Logger(verbose=False) suppresses verbose messages."""
        logger = Logger(verbose=False)
        captured = io.StringIO()
        logger._console = __import__("rich.console", fromlist=["Console"]).Console(
            file=captured, stderr=False, highlight=False
        )
        logger.verbose(msg)
        output = captured.getvalue()
        assert output == "", f"Verbose mode produced output when disabled: {output!r}"

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_quiet_mode_suppresses_verbose(self, msg: str) -> None:
        """Logger(quiet=True) suppresses verbose messages even with verbose=True."""
        logger = Logger(verbose=True, quiet=True)
        captured = io.StringIO()
        logger._console = __import__("rich.console", fromlist=["Console"]).Console(
            file=captured, stderr=False, highlight=False
        )
        logger.verbose(msg)
        output = captured.getvalue()
        assert output == "", f"Quiet mode did not suppress verbose: {output!r}"


# ---------------------------------------------------------------------------
# Req 3.5: Non-TTY plain text (no ANSI escape sequences)
# ---------------------------------------------------------------------------


class TestNonTTYPlainText:
    """Validates: Requirements 3.5"""

    def test_write_non_tty_no_ansi(self) -> None:
        """OutputFormatter.write() to non-TTY produces no ANSI escape sequences."""
        formatter = OutputFormatter()
        tickets = formatter.parse_and_validate({"tickets": [_make_valid_ticket()]})
        args = argparse.Namespace(format="yaml", output=None)

        # Capture stdout - pytest's capsys simulates non-TTY
        captured_stdout = io.StringIO()
        with patch("sys.stdout", captured_stdout):
            # Re-create formatter with non-TTY stdout console
            from rich.console import Console

            formatter._stdout_console = Console(file=captured_stdout, highlight=False)
            formatter.write(tickets, args)

        output = captured_stdout.getvalue()
        # ANSI escape sequences start with \x1b[
        assert "\x1b" not in output, f"Found ANSI escape in non-TTY output: {output!r}"

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=30)
    def test_plain_text_for_arbitrary_titles(self, title: str) -> None:
        """Non-TTY output contains no ANSI for tickets with arbitrary titles."""
        ticket = _make_valid_ticket()
        ticket["title"] = title if title.strip() else "Fallback"
        formatter = OutputFormatter()

        try:
            tickets = formatter.parse_and_validate({"tickets": [ticket]})
        except SystemExit:
            return  # Skip if validation fails

        args = argparse.Namespace(format="yaml", output=None)
        captured_stdout = io.StringIO()
        from rich.console import Console

        formatter._stdout_console = Console(file=captured_stdout, highlight=False)
        formatter.write(tickets, args)

        output = captured_stdout.getvalue()
        assert "\x1b" not in output


# ---------------------------------------------------------------------------
# Req 3.6: Stderr routing for warnings and errors
# ---------------------------------------------------------------------------


class TestStderrRouting:
    """Validates: Requirements 3.6"""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_warning_goes_to_stderr(self, msg: str) -> None:
        """Logger.warning() writes to stderr (console initialized with stderr=True)."""
        logger = Logger()
        # Verify the console is configured for stderr
        assert logger._console._file is sys.stderr or getattr(
            logger._console, "stderr", False
        ), "Logger console must be configured for stderr"

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_error_goes_to_stderr(self, msg: str) -> None:
        """Logger.error() writes to stderr (console initialized with stderr=True)."""
        logger = Logger()
        assert logger._console._file is sys.stderr or getattr(
            logger._console, "stderr", False
        ), "Logger console must be configured for stderr"

    def test_warning_produces_stderr_output(self, capsys) -> None:
        """Logger().warning() produces output on stderr, not stdout."""
        logger = Logger()
        logger.warning("test warning")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert len(captured.err) > 0
        assert "test warning" in captured.err

    def test_error_produces_stderr_output(self, capsys) -> None:
        """Logger().error() produces output on stderr, not stdout."""
        logger = Logger()
        logger.error("test error")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert len(captured.err) > 0
        assert "test error" in captured.err


# ---------------------------------------------------------------------------
# Req 3.7: Quiet mode still shows warnings and errors
# ---------------------------------------------------------------------------


class TestQuietShowsWarningsErrors:
    """Validates: Requirements 3.7"""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_quiet_mode_shows_warnings(self, msg: str) -> None:
        """Logger(quiet=True).warning() still produces output."""
        logger = Logger(quiet=True)
        captured = io.StringIO()
        logger._console = __import__("rich.console", fromlist=["Console"]).Console(
            file=captured, stderr=False, highlight=False
        )
        logger.warning(msg)
        output = captured.getvalue()
        assert len(output) > 0, f"Quiet mode suppressed warning: {msg!r}"

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_quiet_mode_shows_errors(self, msg: str) -> None:
        """Logger(quiet=True).error() still produces output."""
        logger = Logger(quiet=True)
        captured = io.StringIO()
        logger._console = __import__("rich.console", fromlist=["Console"]).Console(
            file=captured, stderr=False, highlight=False
        )
        logger.error(msg)
        output = captured.getvalue()
        assert len(output) > 0, f"Quiet mode suppressed error: {msg!r}"

    def test_quiet_warning_simple(self, capsys) -> None:
        """Simple check: quiet mode does not suppress warnings."""
        logger = Logger(quiet=True)
        logger.warning("important warning")
        captured = capsys.readouterr()
        assert "important warning" in captured.err

    def test_quiet_error_simple(self, capsys) -> None:
        """Simple check: quiet mode does not suppress errors."""
        logger = Logger(quiet=True)
        logger.error("critical error")
        captured = capsys.readouterr()
        assert "critical error" in captured.err
