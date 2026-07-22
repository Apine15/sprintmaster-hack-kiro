"""AWS Lambda handler for SprintMaster.

Receives feature description and team config from the CLI,
invokes Bedrock Converse API with Claude 3 Haiku,
and returns structured ticket data.
"""

import json
import os

import boto3

from prompt_builder import build_messages

DEFAULT_MODEL_ID = "us.anthropic.claude-3-haiku-20240307-v1:0"


def lambda_handler(event: dict, context) -> dict:
    """AWS Lambda entry point.

    Parses the request, calls Bedrock Converse API via prompt_builder,
    and returns structured ticket JSON.

    Args:
        event: Lambda event dict. Body may be a JSON string (API Gateway)
               or a dict (direct invocation).
        context: Lambda context object (unused).

    Returns:
        dict with statusCode, headers, and JSON body.
    """
    try:
        body = _parse_event_body(event)
    except (json.JSONDecodeError, TypeError) as exc:
        return _error_response(400, f"Invalid request body: {exc}")

    feature_description = body.get("feature_description")
    if not feature_description or not feature_description.strip():
        return _error_response(400, "feature_description is required and cannot be empty")

    team_config = body.get("team_config")
    model_id = body.get("model_id", DEFAULT_MODEL_ID)

    try:
        system_prompt, messages = build_messages(feature_description, team_config)
    except Exception as exc:
        return _error_response(500, f"Error building prompt: {exc}")

    try:
        result = _invoke_bedrock(model_id, system_prompt, messages)
    except Exception as exc:
        return _error_response(500, f"Error invoking Bedrock: {exc}")

    return _success_response(result)


def _parse_event_body(event: dict) -> dict:
    """Parse the event body handling both API Gateway and direct invocation formats."""
    body = event.get("body", event)

    if isinstance(body, str):
        return json.loads(body)

    if isinstance(body, dict):
        # If the event itself has feature_description at top level (direct invocation)
        if "feature_description" in body:
            return body
        # If body key was present and is a dict
        if "body" in event and isinstance(event["body"], dict):
            return event["body"]
        return body

    raise TypeError(f"Unexpected body type: {type(body)}")


def _invoke_bedrock(model_id: str, system_prompt: str, messages: list) -> dict:
    """Invoke Bedrock Converse API and extract the response.

    Returns:
        dict with keys: tickets, token_usage, model_id, region
    """
    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-runtime", region_name=region)

    response = client.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=messages,
        inferenceConfig={
            "maxTokens": 4096,
            "temperature": 0.3,
        },
    )

    # Extract the assistant response text
    output_message = response["output"]["message"]
    response_text = ""
    for block in output_message["content"]:
        if "text" in block:
            response_text += block["text"]

    # Parse the response as JSON to extract tickets
    tickets_data = json.loads(response_text)
    tickets = tickets_data.get("tickets", [])

    # Extract token usage from response metadata
    usage = response.get("usage", {})
    token_usage = {
        "input": usage.get("inputTokens", 0),
        "output": usage.get("outputTokens", 0),
    }

    return {
        "tickets": tickets,
        "token_usage": token_usage,
        "model_id": model_id,
        "region": region,
    }


def _success_response(result: dict) -> dict:
    """Build a successful HTTP response."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result),
    }


def _error_response(status_code: int, message: str) -> dict:
    """Build an error HTTP response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }
