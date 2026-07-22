"""Logger for SprintMaster.

Provides verbosity-aware logging with support for standard,
verbose, and quiet modes. All non-ticket output goes to stderr.
"""

from __future__ import annotations

import sys


class Logger:
    """Verbosity-aware logger that writes all output to stderr.

    Modes:
        - Standard (default): progress messages shown, verbose suppressed.
        - Verbose (--verbose): progress and verbose messages shown.
        - Quiet (--quiet): only warnings and errors shown.
    """

    def __init__(self, *, verbose: bool = False, quiet: bool = False) -> None:
        self._verbose = verbose
        self._quiet = quiet

    @property
    def is_verbose(self) -> bool:
        """Return whether verbose mode is active."""
        return self._verbose

    @property
    def is_quiet(self) -> bool:
        """Return whether quiet mode is active."""
        return self._quiet

    def progress(self, msg: str) -> None:
        """Print a progress indicator to stderr.

        Shown in standard mode. Suppressed in quiet mode.
        """
        if self._quiet:
            return
        print(msg, file=sys.stderr)

    def verbose(self, msg: str) -> None:
        """Print verbose information to stderr.

        Shown only when --verbose is active. Suppressed in quiet mode.
        """
        if self._quiet:
            return
        if not self._verbose:
            return
        print(msg, file=sys.stderr)

    def warning(self, msg: str) -> None:
        """Print a warning message to stderr.

        Always shown, regardless of quiet/verbose mode.
        """
        print(f"Warning: {msg}", file=sys.stderr)

    def error(self, msg: str) -> None:
        """Print an error message to stderr.

        Always shown, regardless of quiet/verbose mode.
        """
        print(f"Error: {msg}", file=sys.stderr)

    def verbose_metadata(
        self,
        *,
        model_id: str,
        region: str,
        input_tokens: int,
        output_tokens: int,
        processing_time: float,
    ) -> None:
        """Print verbose metadata about the API response.

        Convenience method that formats and displays model_id, AWS region,
        token usage, and processing time. Only shown when --verbose is active.
        """
        self.verbose(f"Model: {model_id}")
        self.verbose(f"Region: {region}")
        self.verbose(f"Tokens: {input_tokens} input / {output_tokens} output")
        self.verbose(f"Processing time: {processing_time:.2f}s")
