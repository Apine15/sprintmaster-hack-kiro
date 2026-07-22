"""Logger for SprintMaster.

Provides verbosity-aware logging with support for standard,
verbose, and quiet modes. All non-ticket output goes to stderr.
"""

from __future__ import annotations

from rich.console import Console


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
        self._console = Console(stderr=True, highlight=False)
        self._status = None  # Active status context (spinner)

    @property
    def is_verbose(self) -> bool:
        """Return whether verbose mode is active."""
        return self._verbose

    @property
    def is_quiet(self) -> bool:
        """Return whether quiet mode is active."""
        return self._quiet

    def banner(self) -> None:
        """Print 'SprintMaster' in bold + color. Suppressed in quiet mode."""
        if not self._quiet:
            self._console.print("SprintMaster", style="bold cyan")

    def progress(self, msg: str) -> None:
        """Display progress with animated spinner. Suppressed in quiet mode."""
        if self._quiet:
            return
        self.stop_progress()
        self._status = self._console.status(msg)
        self._status.start()

    def start_progress(self, msg: str) -> None:
        """Start an animated spinner with the given message."""
        if self._quiet:
            return
        self._status = self._console.status(msg)
        self._status.start()

    def stop_progress(self) -> None:
        """Stop the current animated spinner if one is active."""
        if self._status:
            self._status.stop()
            self._status = None

    def verbose(self, msg: str) -> None:
        """Print verbose information to stderr.

        Shown only when --verbose is active. Suppressed in quiet mode.
        """
        if self._quiet:
            return
        if not self._verbose:
            return
        self._console.print(msg, style="dim")

    def warning(self, msg: str) -> None:
        """Print '⚠️ Warning: {msg}' in yellow. Always shown."""
        self._console.print(f"⚠️ Warning: {msg}", style="yellow")

    def error(self, msg: str) -> None:
        """Print '❌ Error: {msg}' in red. Always shown."""
        self._console.print(f"❌ Error: {msg}", style="bold red")

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
