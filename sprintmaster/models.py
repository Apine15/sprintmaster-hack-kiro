"""Data models for SprintMaster.

Defines Pydantic models for Ticket, TeamConfig, request/response payloads,
and exit code constants.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


# Exit code constants
EXIT_SUCCESS = 0
EXIT_USER_ERROR = 1
EXIT_SERVICE_ERROR = 2

# Valid Fibonacci story point values
FIBONACCI = {1, 2, 3, 5, 8, 13}


class Priority(str, Enum):
    """Priority levels for tickets."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Ticket(BaseModel):
    """Represents a single agile ticket."""

    title: str
    description: str
    acceptance_criteria: list[str]
    story_points: int
    priority: Priority
    assignee: str
    dependencies: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("story_points")
    @classmethod
    def must_be_fibonacci(cls, v: int) -> int:
        if v not in FIBONACCI:
            raise ValueError(f"story_points {v} no es un valor Fibonacci válido")
        return v

    @field_validator("assignee")
    @classmethod
    def must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("assignee no puede ser una cadena vacía")
        return v

    @field_validator("dependencies")
    @classmethod
    def validate_dependencies(cls, v: list[str]) -> list[str]:
        for item in v:
            if not item.strip():
                raise ValueError("los elementos de dependencias no pueden ser vacíos")
            if len(item) > 200:
                raise ValueError(f"el elemento de dependencia excede 200 caracteres: {item[:50]}...")
        if len(v) != len(set(v)):
            raise ValueError("las dependencias no pueden contener valores repetidos")
        return v


class TeamMember(BaseModel):
    """Represents a team member with their role and tech stack."""

    name: str
    role: str
    stack: list[str]


class TeamConfig(BaseModel):
    """Team configuration containing a list of team members."""

    team: list[TeamMember]


class LambdaRequestPayload(BaseModel):
    """Payload sent to the AWS Lambda function."""

    feature_description: str
    team_config: TeamConfig | None = None
    model_id: str = "us.anthropic.claude-3-haiku-20240307-v1:0"


class TokenUsage(BaseModel):
    """Token usage statistics from the LLM invocation."""

    input: int
    output: int


class LambdaResponse(BaseModel):
    """Response received from the AWS Lambda function."""

    tickets: list[dict]
    token_usage: TokenUsage
    model_id: str
    region: str
