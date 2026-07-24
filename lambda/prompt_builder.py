"""Prompt Builder for SprintMaster Lambda.

Constructs the system prompt and user messages for the Bedrock Converse API,
injecting team context when available for intelligent ticket assignment.
"""

BASE_SYSTEM_PROMPT = """You are an agile project planner. Your task is to decompose a feature description into structured agile tickets.

You MUST respond with ONLY valid JSON. No markdown, no explanations, no text outside the JSON object.

Your response MUST be a JSON object with a single key "tickets" containing an array of ticket objects.

Each ticket object MUST contain exactly these fields:
- "title": A concise, actionable title for the ticket
- "description": A detailed description of the work to be done
- "acceptance_criteria": An array of strings, each describing a testable acceptance criterion
- "story_points": An integer from the Fibonacci sequence: 1, 2, 3, 5, 8, or 13
- "priority": One of exactly these values: "high", "medium", or "low"
- "assignee": The name of the assigned team member, or "unassigned" if no team is provided
- "dependencies": A list of exact titles of other tickets in this response that MUST be completed
  before this ticket can start. If a ticket has no blockers, use an empty list [].
  A ticket B blocks ticket A when A cannot begin until B is finished.
  Never include the ticket's own title in its dependencies list.

Rules for story_points:
- Use ONLY values from the Fibonacci sequence: 1, 2, 3, 5, 8, 13
- 1-2: trivial tasks (config changes, small fixes)
- 3: small but meaningful tasks
- 5: medium complexity tasks
- 8: large tasks requiring significant effort
- 13: very large tasks that might need to be broken down further

Rules for priority:
- "high": Critical path items, blockers, or security-related work
- "medium": Important but not blocking other work
- "low": Nice-to-have improvements or non-urgent tasks

Rules for assignee:
- If no team information is provided, set assignee to "unassigned" for ALL tickets
- If team information is provided, assign each ticket to the team member whose role and tech stack is most suitable for the task

Example response format:
{"tickets": [{"title": "Set up database schema", "description": "Create the initial database schema for user management...", "acceptance_criteria": ["Tables exist", "Migrations run successfully"], "story_points": 5, "priority": "high", "assignee": "unassigned", "dependencies": []}, {"title": "Implement user login endpoint", "description": "Create a REST API endpoint for user authentication...", "acceptance_criteria": ["User can log in with email and password", "Returns JWT token on success", "Returns 401 on invalid credentials"], "story_points": 5, "priority": "high", "assignee": "unassigned", "dependencies": ["Set up database schema"]}]}"""


NO_TEAM_SUFFIX = """

IMPORTANT: No team configuration has been provided. You MUST set the "assignee" field to "unassigned" for every ticket."""


def build_team_context_section(team_config: dict) -> str:
    """Build the team context section to append to the system prompt.

    Args:
        team_config: Dictionary with a "team" key containing a list of team members,
                     each with "name", "role", and "stack" fields.

    Returns:
        A formatted string describing the team members for injection into the prompt.
    """
    lines = [
        "",
        "",
        "TEAM CONFIGURATION:",
        "The following team members are available for ticket assignment.",
        "Assign each ticket to the team member whose role and tech stack is most suitable for the task.",
        "",
    ]

    for member in team_config.get("team", []):
        name = member.get("name", "Unknown")
        role = member.get("role", "Unknown Role")
        stack = member.get("stack", [])
        stack_str = ", ".join(stack) if stack else "Not specified"
        lines.append(f"- {name} | Role: {role} | Tech Stack: {stack_str}")

    lines.append("")
    lines.append(
        "Choose the best match for each ticket based on the task requirements "
        "and each team member's role and technical expertise."
    )

    return "\n".join(lines)


def build_messages(
    feature_description: str, team_config: dict | None
) -> tuple[str, list]:
    """Build the system prompt and messages for the Bedrock Converse API.

    Args:
        feature_description: The user's feature description text.
        team_config: Optional dictionary with team member information.
                     Expected format: {"team": [{"name": str, "role": str, "stack": [str]}]}

    Returns:
        A tuple of (system_prompt, messages) where:
        - system_prompt is the complete system instruction string
        - messages is the list of message dicts for the Converse API
    """
    system_prompt = BASE_SYSTEM_PROMPT

    if team_config:
        system_prompt += build_team_context_section(team_config)
    else:
        system_prompt += NO_TEAM_SUFFIX

    messages = [{"role": "user", "content": [{"text": feature_description}]}]

    return system_prompt, messages
