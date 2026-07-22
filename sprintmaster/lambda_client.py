"""Lambda Client for SprintMaster.

Handles HTTP communication with the AWS Lambda backend,
including retries with exponential backoff for 429 responses.
"""

import argparse
import os
import sys
import time

import requests

from sprintmaster.models import EXIT_SERVICE_ERROR


class LambdaClient:
    """Client for communicating with the SprintMaster Lambda backend."""

    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 1
    TIMEOUT_SECONDS = 30

    def __init__(self, args: argparse.Namespace) -> None:
        """Initialize LambdaClient with the Lambda URL.

        Reads URL from args.lambda_url first, falls back to
        SPRINTMASTER_LAMBDA_URL environment variable.

        Exits with EXIT_SERVICE_ERROR if neither is available.
        """
        url = getattr(args, "lambda_url", None) or os.environ.get(
            "SPRINTMASTER_LAMBDA_URL"
        )
        if not url:
            print(
                "Error: la URL del backend no está configurada. "
                "Defina SPRINTMASTER_LAMBDA_URL o use --lambda-url.",
                file=sys.stderr,
            )
            sys.exit(EXIT_SERVICE_ERROR)
        self.url: str = url

    def send(self, payload: dict) -> dict:
        """POST JSON payload to the Lambda backend.

        Handles:
        - Exponential backoff retry for HTTP 429 (max 3 retries)
        - HTTP 401/403 → error message + EXIT_SERVICE_ERROR
        - HTTP 5xx → error message + EXIT_SERVICE_ERROR
        - Timeout → error message + EXIT_SERVICE_ERROR

        Returns the parsed JSON response on success (HTTP 2xx).
        """
        attempt = 0
        max_attempts = self.MAX_RETRIES + 1  # initial + 3 retries

        while attempt < max_attempts:
            try:
                response = requests.post(
                    self.url,
                    json=payload,
                    timeout=self.TIMEOUT_SECONDS,
                )
            except requests.exceptions.Timeout:
                print(
                    "Error: tiempo de espera agotado al contactar el backend (30s).",
                    file=sys.stderr,
                )
                sys.exit(EXIT_SERVICE_ERROR)
            except requests.exceptions.RequestException as e:
                print(
                    f"Error: no se pudo conectar al backend: {e}",
                    file=sys.stderr,
                )
                sys.exit(EXIT_SERVICE_ERROR)

            # Handle 2xx success
            if 200 <= response.status_code < 300:
                try:
                    return response.json()
                except ValueError:
                    print(
                        "Error: la respuesta del backend no es JSON válido.",
                        file=sys.stderr,
                    )
                    sys.exit(EXIT_SERVICE_ERROR)

            # Handle 429 with retry
            if response.status_code == 429:
                attempt += 1
                if attempt >= max_attempts:
                    print(
                        "Error: máximo de reintentos agotado (HTTP 429). "
                        "El backend está sobrecargado.",
                        file=sys.stderr,
                    )
                    sys.exit(EXIT_SERVICE_ERROR)
                wait_time = self.BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                time.sleep(wait_time)
                continue

            # Handle 401/403
            if response.status_code in (401, 403):
                print(
                    "Error: la solicitud al backend fue rechazada por falta "
                    "de autorización (HTTP {}).".format(response.status_code),
                    file=sys.stderr,
                )
                sys.exit(EXIT_SERVICE_ERROR)

            # Handle 5xx
            if response.status_code >= 500:
                print(
                    "Error: error interno del backend (HTTP {}).".format(
                        response.status_code
                    ),
                    file=sys.stderr,
                )
                sys.exit(EXIT_SERVICE_ERROR)

            # Handle other unexpected status codes
            print(
                "Error: respuesta inesperada del backend (HTTP {}).".format(
                    response.status_code
                ),
                file=sys.stderr,
            )
            sys.exit(EXIT_SERVICE_ERROR)

        # Should not reach here, but safety net
        print(
            "Error: máximo de reintentos agotado.",
            file=sys.stderr,
        )
        sys.exit(EXIT_SERVICE_ERROR)
