"""CLI entry point for SprintMaster.

Handles argument parsing, input resolution, and orchestrates the flow
between LambdaClient, OutputFormatter, and Logger.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import yaml
from pydantic import ValidationError
from rich_argparse import RawDescriptionRichHelpFormatter

from sprintmaster import tree_scanner
from sprintmaster.lambda_client import LambdaClient
from sprintmaster.logger import Logger
from sprintmaster.models import EXIT_SUCCESS, EXIT_USER_ERROR, TeamConfig
from sprintmaster.output_formatter import OutputFormatter

__version__ = "0.1.0"

EPILOG_EXAMPLES = """\
[bold]Examples:[/bold]

  # Feature description as positional argument
  sprintmaster "Implement user authentication with OAuth2"

  # Feature description from a file
  sprintmaster --file feature_spec.txt

  # Piped input from another command
  echo "Add shopping cart functionality" | sprintmaster

  # Specify output format and file
  sprintmaster "Build REST API" --format json --output tickets.json

  # Use a team configuration for smart assignment
  sprintmaster "Build REST API" --team-config team.yaml

  # Override Lambda URL and model
  sprintmaster "Add search" --lambda-url https://my-lambda.aws.com/invoke --model us.anthropic.claude-3-sonnet-20240229-v1:0
"""


class InputError(Exception):
    """Raised when feature description input cannot be resolved."""

    pass


class FileNotFoundInputError(InputError):
    """Raised when a specified input file does not exist."""

    pass


class TeamConfigFileNotFoundError(Exception):
    """Raised when the team config file does not exist."""

    pass


class TeamConfigInvalidYAMLError(Exception):
    """Raised when the team config file contains invalid YAML."""

    pass


class TeamConfigValidationError(Exception):
    """Raised when the team config YAML does not match the expected schema."""

    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list to parse. Defaults to sys.argv[1:].

    Returns:
        Parsed argument namespace.
    """
    # Configure RichHelpFormatter styles to match the app palette
    RawDescriptionRichHelpFormatter.styles["argparse.args"] = "cyan"
    RawDescriptionRichHelpFormatter.styles["argparse.groups"] = "bold cyan"
    RawDescriptionRichHelpFormatter.styles["argparse.metavar"] = "dim cyan"
    RawDescriptionRichHelpFormatter.styles["argparse.prog"] = "bold white"
    RawDescriptionRichHelpFormatter.styles["argparse.text"] = "default"

    parser = argparse.ArgumentParser(
        prog="sprintmaster",
        description="Decompose feature descriptions into structured agile tickets using AI.",
        epilog=EPILOG_EXAMPLES,
        formatter_class=RawDescriptionRichHelpFormatter,
    )

    parser.add_argument(
        "feature_description",
        nargs="?",
        default=None,
        help="Feature description text (positional argument)",
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        help="Path to a file containing the feature description",
    )
    parser.add_argument(
        "--team-config",
        metavar="PATH",
        help="Path to a YAML file with team member configuration",
    )
    parser.add_argument(
        "--format",
        choices=["yaml", "json"],
        default="yaml",
        help="Output format (default: yaml)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Write output to file instead of stdout",
    )
    parser.add_argument(
        "--lambda-url",
        metavar="URL",
        default=os.environ.get("SPRINTMASTER_LAMBDA_URL"),
        help="Lambda function URL (overrides SPRINTMASTER_LAMBDA_URL env var)",
    )
    parser.add_argument(
        "--model",
        default="qwen.qwen3-coder-30b-a3b-v1:0",
        help="Bedrock model ID (default: qwen.qwen3-coder-30b-a3b-v1:0)",
    )
    parser.add_argument(
        "--lang", "-l",
        default="English",
        metavar="LANGUAGE",
        help="Language for generated ticket content (default: English)",
    )
    parser.add_argument(
        "--codebase",
        metavar="PATH",
        default=None,
        help="Path to project directory to scan for context",
    )
    parser.add_argument(
        "--codebase-depth",
        metavar="N",
        type=int,
        default=4,
        help="Maximum directory depth for tree scan (default: 4)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed progress and response metadata",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all non-error output except formatted tickets",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args(argv)


def resolve_input(args: argparse.Namespace) -> str:
    """Resolve the feature description from available input sources.

    Priority: positional argument > --file > stdin (piped).

    Args:
        args: Parsed command-line arguments.

    Returns:
        The feature description text.

    Raises:
        FileNotFoundInputError: If --file references a non-existent file.
        InputError: If no input is provided through any method.
    """
    # Priority 1: Positional argument
    if args.feature_description is not None:
        text = args.feature_description.strip()
        if text:
            return text

    # Priority 2: --file flag
    if args.file is not None:
        file_path = Path(args.file)
        if not file_path.exists():
            raise FileNotFoundInputError(
                f"Error: file not found: {args.file}"
            )
        text = file_path.read_text(encoding="utf-8").strip()
        if text:
            return text

    # Priority 3: stdin (piped input)
    if not sys.stdin.isatty():
        text = sys.stdin.read().strip()
        if text:
            return text

    # No input provided
    raise InputError(
        "Error: no feature description provided. "
        "Use a positional argument, --file, or pipe input via stdin."
    )


def load_team_config(args: argparse.Namespace) -> TeamConfig | None:
    """Load and validate team configuration from a YAML file.

    Args:
        args: Parsed command-line arguments.

    Returns:
        A validated TeamConfig instance, or None if --team-config was not provided.

    Raises:
        TeamConfigFileNotFoundError: If the team config file does not exist.
        TeamConfigInvalidYAMLError: If the file contains invalid YAML.
        TeamConfigValidationError: If the YAML does not match the TeamConfig schema.
    """
    if args.team_config is None:
        return None

    config_path = Path(args.team_config)

    # Error hierarchy: file not found takes priority
    if not config_path.exists():
        raise TeamConfigFileNotFoundError(
            f"Error: team config file not found: {args.team_config}"
        )

    # Parse YAML
    try:
        raw_content = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_content)
    except yaml.YAMLError as e:
        raise TeamConfigInvalidYAMLError(
            f"Error: invalid YAML in team config file: {e}"
        ) from e

    # Validate against schema
    if data is None:
        raise TeamConfigInvalidYAMLError(
            "Error: team config file is empty"
        )

    try:
        team_config = TeamConfig.model_validate(data)
    except ValidationError as e:
        raise TeamConfigValidationError(
            f"Error: team config validation failed: {e}"
        ) from e

    return team_config


def main() -> None:
    """Entry point registered in pyproject.toml as console_scripts."""
    args = parse_args()
    logger = Logger(verbose=args.verbose, quiet=args.quiet)
    logger.banner()

    # Validate --codebase arguments
    codebase_path = None
    if args.codebase is not None:
        codebase_path = Path(args.codebase).resolve()
        if not codebase_path.exists():
            print(f"Error: codebase path does not exist: {codebase_path}", file=sys.stderr)
            sys.exit(EXIT_USER_ERROR)
        if not codebase_path.is_dir():
            print(f"Error: codebase path is not a directory: {codebase_path}", file=sys.stderr)
            sys.exit(EXIT_USER_ERROR)
    if args.codebase_depth < 1:
        print("Error: --codebase-depth must be at least 1", file=sys.stderr)
        sys.exit(EXIT_USER_ERROR)

    # Validate --lang argument
    args.lang = args.lang.strip()
    if not args.lang:
        print("Error: --lang value must not be blank", file=sys.stderr)
        sys.exit(EXIT_USER_ERROR)
    if len(args.lang) > 50:
        print("Error: --lang value exceeds maximum length of 50 characters", file=sys.stderr)
        sys.exit(EXIT_USER_ERROR)

    # Resolve feature description input
    try:
        feature_description = resolve_input(args)
    except FileNotFoundInputError as e:
        print(str(e), file=sys.stderr)
        sys.exit(EXIT_USER_ERROR)
    except InputError as e:
        print(str(e), file=sys.stderr)
        sys.exit(EXIT_USER_ERROR)

    # Load optional team configuration
    try:
        team_config = load_team_config(args)
    except TeamConfigFileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(EXIT_USER_ERROR)
    except TeamConfigInvalidYAMLError as e:
        print(str(e), file=sys.stderr)
        sys.exit(EXIT_USER_ERROR)
    except TeamConfigValidationError as e:
        print(str(e), file=sys.stderr)
        sys.exit(EXIT_USER_ERROR)

    # Scan codebase if requested
    codebase_context = None
    if codebase_path is not None:
        result = tree_scanner.scan(codebase_path, depth_limit=args.codebase_depth)
        if result.truncated and args.verbose:
            logger.verbose(f"Tree output truncated: {result.truncated_count} entries not shown")
        codebase_context = result.tree

    # Build request payload
    payload = {
        "feature_description": feature_description,
        "team_config": team_config.model_dump() if team_config else None,
        "model_id": args.model,
        "language": args.lang,
    }
    if codebase_context is not None:
        payload["codebase_context"] = codebase_context

    # Send request to Lambda backend
    logger.start_progress("Generating tickets...")
    start_time = time.time()
    client = LambdaClient(args)
    raw_response = client.send(payload)
    end_time = time.time()
    processing_time = end_time - start_time
    logger.stop_progress()

    # Display verbose metadata if requested
    if args.verbose:
        token_usage = raw_response.get("token_usage", {})
        logger.verbose_metadata(
            model_id=raw_response.get("model_id", args.model),
            region=raw_response.get("region", "unknown"),
            input_tokens=token_usage.get("input", 0),
            output_tokens=token_usage.get("output", 0),
            processing_time=processing_time,
        )

    # Parse, validate, and write output
    logger.start_progress("Processing response...")
    formatter = OutputFormatter(logger=logger)
    tickets = formatter.parse_and_validate(raw_response)
    logger.stop_progress()
    formatter.write(tickets, args)

    logger.progress(f"Done! Generated {len(tickets)} ticket(s).")
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
