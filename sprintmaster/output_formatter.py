"""Output Formatter for SprintMaster.

Parses and validates the LLM response, then serializes
validated tickets to YAML (default) or JSON format.
"""

import argparse
import json
import re
import sys

import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text

from .models import EXIT_SERVICE_ERROR, Ticket

TICKET_KEYS = {"title", "description", "acceptance_criteria", "story_points", "priority", "assignee"}


class OutputFormatter:
    """Handles parsing, validation and serialization of ticket data."""

    def __init__(self) -> None:
        self._stdout_console = Console(file=sys.stdout)

    def parse_and_validate(self, raw: dict) -> list[Ticket]:
        """Parse raw Lambda response and validate each ticket.

        Extracts the 'tickets' list from the raw response dict, validates
        each ticket against the Ticket schema, emits warnings to stderr
        for invalid tickets, and returns only the valid ones.

        If the response is malformed (no 'tickets' key or not a list),
        exits with EXIT_SERVICE_ERROR. If all tickets are invalid,
        exits with EXIT_SERVICE_ERROR.

        Args:
            raw: The dict parsed from the Lambda response. Expected to have
                 a "tickets" key containing a list of ticket dicts.

        Returns:
            A list of validated Ticket objects.
        """
        # Validate that raw contains a 'tickets' key with a list
        if not isinstance(raw, dict) or "tickets" not in raw:
            print(
                "Error: la respuesta del modelo fue malformada (falta clave 'tickets').",
                file=sys.stderr,
            )
            sys.exit(EXIT_SERVICE_ERROR)

        raw_tickets = raw["tickets"]
        if not isinstance(raw_tickets, list):
            print(
                "Error: la respuesta del modelo fue malformada ('tickets' no es una lista).",
                file=sys.stderr,
            )
            sys.exit(EXIT_SERVICE_ERROR)

        valid_tickets: list[Ticket] = []

        for i, ticket_data in enumerate(raw_tickets):
            if not isinstance(ticket_data, dict):
                print(
                    f"Advertencia: ticket #{i + 1} no es un objeto válido, omitido.",
                    file=sys.stderr,
                )
                continue

            try:
                ticket = Ticket(**ticket_data)
                valid_tickets.append(ticket)
            except ValidationError as e:
                title = ticket_data.get("title", f"#{i + 1}")
                print(
                    f"Advertencia: ticket '{title}' es inválido y fue omitido: {e}",
                    file=sys.stderr,
                )

        if not valid_tickets:
            print(
                "Error: todos los tickets de la respuesta son inválidos.",
                file=sys.stderr,
            )
            sys.exit(EXIT_SERVICE_ERROR)

        return valid_tickets

    def write(self, tickets: list[Ticket], args: argparse.Namespace) -> None:
        """Serialize tickets with optional Rich styling.

        Routes rendering based on output target and format:
        - YAML to stdout + TTY: syntax highlighting via Syntax, bold cyan keys
        - YAML to stdout + non-TTY: plain text (no ANSI)
        - JSON to stdout: plain text always
        - YAML/JSON to file: plain text always
        - Visual spacing: one blank line between consecutive tickets

        Args:
            tickets: List of validated Ticket objects.
            args: argparse.Namespace with .format (yaml/json) and
                  .output (file path or None) attributes.
        """
        # Convert tickets to list of dicts for serialization.
        # mode="json" ensures enums are serialized as their string values.
        tickets_data = [ticket.model_dump(mode="json") for ticket in tickets]

        output_format = getattr(args, "format", "yaml") or "yaml"
        output_path = getattr(args, "output", None)

        if output_path:
            # File output: always plain text
            self._render_plain(tickets_data, output_format, output_path)
        elif output_format == "json":
            # JSON to stdout: always plain text (no syntax highlighting)
            self._render_plain(tickets_data, output_format, None)
        elif self._stdout_console.is_terminal:
            # YAML to stdout + TTY: rich syntax highlighting
            self._render_yaml_highlighted(tickets_data)
        else:
            # YAML to stdout + non-TTY (piped): plain text
            self._render_plain(tickets_data, output_format, None)

    def _render_plain(self, tickets_data: list[dict], output_format: str, output_path: str | None) -> None:
        """Render plain text to stdout or file.

        Serializes tickets to YAML or JSON format without any Rich styling
        or ANSI escape sequences. Applies blank-line separation: exactly one
        blank line between consecutive ticket blocks, no leading or trailing
        blank lines.

        Args:
            tickets_data: List of ticket dictionaries to render.
            output_format: Either "yaml" or "json".
            output_path: File path to write to, or None for stdout.
        """
        blocks: list[str] = []

        for ticket_data in tickets_data:
            if output_format == "json":
                block = json.dumps(ticket_data, indent=2, ensure_ascii=False)
            else:
                block = yaml.dump(
                    ticket_data,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                ).rstrip("\n")
            blocks.append(block)

        # Join with exactly one blank line between tickets
        content = "\n\n".join(blocks)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
                # Add trailing newline for file output
                if content and not content.endswith("\n"):
                    f.write("\n")
        else:
            sys.stdout.write(content)
            # Add trailing newline for stdout so prompt isn't on same line
            if content and not content.endswith("\n"):
                sys.stdout.write("\n")

    def _render_yaml_highlighted(self, tickets_data: list[dict]) -> None:
        """Render YAML with syntax highlighting and bold cyan ticket keys to stdout.

        Uses Rich's Syntax object with the "yaml" lexer for highlighting.
        Applies bold cyan styling to the six ticket keys (title, description,
        acceptance_criteria, story_points, priority, assignee).
        Inserts one blank line between consecutive ticket blocks.
        Falls back to plain text on any rendering failure.

        This method should only be called when stdout is connected to a TTY.

        Args:
            tickets_data: List of ticket dictionaries to render.
        """
        # Regex to detect a YAML key at the start of a line (with optional list prefix)
        key_pattern = re.compile(r"^(\s*-?\s*)(\w+)(:.*)")

        try:
            for i, ticket_data in enumerate(tickets_data):
                # Serialize individual ticket to YAML
                ticket_yaml = yaml.dump(
                    ticket_data,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )

                lines = ticket_yaml.rstrip("\n").split("\n")

                for line in lines:
                    match = key_pattern.match(line)
                    if match:
                        prefix, key, rest = match.groups()
                        if key in TICKET_KEYS:
                            # Render key in bold cyan, rest in default style
                            text = Text()
                            text.append(prefix)
                            text.append(key, style="bold cyan")
                            text.append(rest)
                            self._stdout_console.print(text)
                        else:
                            # Non-ticket key line — render with yaml syntax
                            syntax = Syntax(line, "yaml", theme="monokai")
                            self._stdout_console.print(syntax)
                    else:
                        # Continuation line (e.g., list items under acceptance_criteria)
                        syntax = Syntax(line, "yaml", theme="monokai")
                        self._stdout_console.print(syntax)

                # Insert blank line between tickets (not after last)
                if i < len(tickets_data) - 1:
                    self._stdout_console.print()
        except Exception:
            # Fall back to plain text on any rendering failure
            content = yaml.dump(
                tickets_data,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
            sys.stdout.write(content)
