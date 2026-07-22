"""Unit tests for sprintmaster.logger.Logger."""

import sys

from sprintmaster.logger import Logger


class TestLoggerProgress:
    """Tests for Logger.progress() method."""

    def test_progress_standard_mode(self, capsys):
        """Progress messages are shown in standard mode (default)."""
        logger = Logger()
        logger.progress("Processing...")
        captured = capsys.readouterr()
        assert captured.err == "Processing...\n"
        assert captured.out == ""

    def test_progress_verbose_mode(self, capsys):
        """Progress messages are shown in verbose mode."""
        logger = Logger(verbose=True)
        logger.progress("Processing...")
        captured = capsys.readouterr()
        assert captured.err == "Processing...\n"

    def test_progress_quiet_mode(self, capsys):
        """Progress messages are suppressed in quiet mode."""
        logger = Logger(quiet=True)
        logger.progress("Processing...")
        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""


class TestLoggerVerbose:
    """Tests for Logger.verbose() method."""

    def test_verbose_when_verbose_active(self, capsys):
        """Verbose messages are shown when --verbose is active."""
        logger = Logger(verbose=True)
        logger.verbose("Model: claude-3-haiku")
        captured = capsys.readouterr()
        assert captured.err == "Model: claude-3-haiku\n"
        assert captured.out == ""

    def test_verbose_standard_mode(self, capsys):
        """Verbose messages are suppressed in standard mode."""
        logger = Logger()
        logger.verbose("Model: claude-3-haiku")
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_verbose_quiet_mode(self, capsys):
        """Verbose messages are suppressed in quiet mode."""
        logger = Logger(quiet=True)
        logger.verbose("Model: claude-3-haiku")
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_verbose_quiet_overrides_verbose(self, capsys):
        """Quiet mode suppresses verbose even if both flags are set."""
        logger = Logger(verbose=True, quiet=True)
        logger.verbose("Should not appear")
        captured = capsys.readouterr()
        assert captured.err == ""


class TestLoggerWarning:
    """Tests for Logger.warning() method."""

    def test_warning_standard_mode(self, capsys):
        """Warnings are shown in standard mode."""
        logger = Logger()
        logger.warning("something unexpected")
        captured = capsys.readouterr()
        assert captured.err == "Warning: something unexpected\n"
        assert captured.out == ""

    def test_warning_quiet_mode(self, capsys):
        """Warnings are shown even in quiet mode."""
        logger = Logger(quiet=True)
        logger.warning("something unexpected")
        captured = capsys.readouterr()
        assert captured.err == "Warning: something unexpected\n"

    def test_warning_verbose_mode(self, capsys):
        """Warnings are shown in verbose mode."""
        logger = Logger(verbose=True)
        logger.warning("something unexpected")
        captured = capsys.readouterr()
        assert captured.err == "Warning: something unexpected\n"


class TestLoggerError:
    """Tests for Logger.error() method."""

    def test_error_standard_mode(self, capsys):
        """Errors are shown in standard mode."""
        logger = Logger()
        logger.error("connection failed")
        captured = capsys.readouterr()
        assert captured.err == "Error: connection failed\n"
        assert captured.out == ""

    def test_error_quiet_mode(self, capsys):
        """Errors are shown even in quiet mode."""
        logger = Logger(quiet=True)
        logger.error("connection failed")
        captured = capsys.readouterr()
        assert captured.err == "Error: connection failed\n"

    def test_error_verbose_mode(self, capsys):
        """Errors are shown in verbose mode."""
        logger = Logger(verbose=True)
        logger.error("connection failed")
        captured = capsys.readouterr()
        assert captured.err == "Error: connection failed\n"


class TestLoggerVerboseMetadata:
    """Tests for Logger.verbose_metadata() helper method."""

    def test_verbose_metadata_when_verbose(self, capsys):
        """Verbose metadata is displayed when verbose mode is active."""
        logger = Logger(verbose=True)
        logger.verbose_metadata(
            model_id="us.anthropic.claude-3-haiku-20240307-v1:0",
            region="us-east-1",
            input_tokens=150,
            output_tokens=800,
            processing_time=2.345,
        )
        captured = capsys.readouterr()
        assert "Model: us.anthropic.claude-3-haiku-20240307-v1:0" in captured.err
        assert "Region: us-east-1" in captured.err
        assert "Tokens: 150 input / 800 output" in captured.err
        assert "Processing time: 2.35s" in captured.err

    def test_verbose_metadata_standard_mode(self, capsys):
        """Verbose metadata is suppressed in standard mode."""
        logger = Logger()
        logger.verbose_metadata(
            model_id="claude-3-haiku",
            region="us-east-1",
            input_tokens=100,
            output_tokens=500,
            processing_time=1.0,
        )
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_verbose_metadata_quiet_mode(self, capsys):
        """Verbose metadata is suppressed in quiet mode."""
        logger = Logger(quiet=True)
        logger.verbose_metadata(
            model_id="claude-3-haiku",
            region="us-east-1",
            input_tokens=100,
            output_tokens=500,
            processing_time=1.0,
        )
        captured = capsys.readouterr()
        assert captured.err == ""


class TestLoggerProperties:
    """Tests for Logger properties."""

    def test_is_verbose_default(self):
        logger = Logger()
        assert logger.is_verbose is False

    def test_is_verbose_true(self):
        logger = Logger(verbose=True)
        assert logger.is_verbose is True

    def test_is_quiet_default(self):
        logger = Logger()
        assert logger.is_quiet is False

    def test_is_quiet_true(self):
        logger = Logger(quiet=True)
        assert logger.is_quiet is True


class TestLoggerStderrOnly:
    """Verify all output goes exclusively to stderr, never stdout."""

    def test_no_stdout_output(self, capsys):
        """No Logger method should write to stdout."""
        logger = Logger(verbose=True)
        logger.progress("progress msg")
        logger.verbose("verbose msg")
        logger.warning("warning msg")
        logger.error("error msg")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err != ""
