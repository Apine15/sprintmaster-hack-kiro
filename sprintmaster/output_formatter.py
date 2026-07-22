"""Output Formatter for SprintMaster.

Parses and validates the LLM response, then serializes
validated tickets to YAML (default) or JSON format.
"""

import argparse
import json
import sys

import yaml
from pydantic import ValidationError

from .models import EXIT_SERVICE_ERROR, Ticket


class OutputFormatter:
    """Handles parsing, validation and serialization of ticket data."""

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
        """Serialize tickets and write to stdout or file.

        Serializes the list of tickets to YAML (default) or JSON format
        based on args.format, and writes to stdout or to a file specified
        by args.output.

        Args:
            tickets: List of validated Ticket objects.
            args: argparse.Namespace with .format (yaml/json) and
                  .output (file path or None) attributes.
        """
        # Convert tickets to list of dicts for serialization.
        # mode="json" ensures enums are serialized as their string values.
        tickets_data = [ticket.model_dump(mode="json") for ticket in tickets]

        output_format = getattr(args, "format", "yaml") or "yaml"

        if output_format == "json":
            content = json.dumps(tickets_data, indent=2, ensure_ascii=False)
        else:
            # YAML is the default format
            content = yaml.dump(
                tickets_data,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

        output_path = getattr(args, "output", None)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            sys.stdout.write(content)
