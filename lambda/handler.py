"""AWS Lambda handler for SprintMaster.

Receives feature description and team config from the CLI,
invokes Bedrock Converse API with Claude 3 Haiku,
and returns structured ticket data.
"""
