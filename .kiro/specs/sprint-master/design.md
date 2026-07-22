# Design Document: SprintMaster

## Overview

SprintMaster es una herramienta CLI en Python que descompone descripciones de funcionalidades en lenguaje natural en tickets ágiles estructurados. La arquitectura separa la interfaz de usuario (CLI) del procesamiento de IA (Lambda + Bedrock), manteniendo la CLI ligera y las responsabilidades bien delimitadas.

El flujo general es:

```
Usuario → CLI (Python) → Lambda_Client → AWS Lambda → Bedrock (Claude 3 Haiku)
                                                              ↓
Usuario ← Output_Formatter ← Lambda_Client ←── respuesta estructurada JSON
```

La CLI acepta la descripción de la funcionalidad y una configuración de equipo opcional, los envía a una Lambda via HTTP POST, y formatea la respuesta como YAML o JSON.

---

## Architecture

### Componentes principales

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI (sprintmaster)                       │
│                                                             │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│  │ Arg Parser  │   │ Lambda_Client│   │ Output_Formatter│  │
│  │ (argparse)  │──▶│ (httpx/req.) │   │ (yaml/json)     │  │
│  └─────────────┘   └──────┬───────┘   └────────┬────────┘  │
│                           │                    │            │
└───────────────────────────┼────────────────────┼────────────┘
                            │ HTTP POST           │ valida + serializa
                            ▼                    ▲
              ┌─────────────────────────┐        │
              │     AWS Lambda          │        │
              │                         │        │
              │  ┌──────────────────┐   │        │
              │  │  Prompt_Builder  │   │        │
              │  └────────┬─────────┘   │        │
              │           │             │────────┘
              │           ▼             │  JSON response
              │  ┌──────────────────┐   │
              │  │  Bedrock Converse│   │
              │  │  (Claude 3 Haiku)│   │
              │  └──────────────────┘   │
              └─────────────────────────┘
```

### Separación de responsabilidades

| Componente | Responsabilidad | Tecnología |
|---|---|---|
| Arg Parser | Parseo de argumentos, validación de entradas | argparse (stdlib) |
| Lambda_Client | Comunicación HTTP con el backend | requests / httpx |
| Prompt_Builder | Construcción del prompt con contexto de equipo | Python (en Lambda) |
| Bedrock Converse | Invocación del LLM | boto3, Converse API |
| Output_Formatter | Validación del schema, serialización | pydantic, yaml, json |

### Decisiones de diseño

**¿Por qué Lambda como backend?**  
Mantiene la CLI ligera (sin credenciales AWS embebidas en el cliente), centraliza la lógica del prompt y facilita el despliegue independiente del cliente.

**¿Por qué Converse API sobre InvokeModel?**  
La Converse API proporciona una interfaz uniforme multi-modelo y soporta system prompts de forma nativa, simplificando la construcción del prompt.

**¿Por qué argparse sobre click/typer?**  
Dependencia cero fuera de stdlib para el parsing de argumentos; reduce el árbol de dependencias del paquete.

---

## Components and Interfaces

### CLI Entry Point (`sprintmaster/cli.py`)

```python
def main() -> None:
    """Entry point registrado en pyproject.toml como console_scripts."""
    args = parse_args()
    feature_description = resolve_input(args)   # posicional | --file | stdin
    team_config = load_team_config(args)         # --team-config (opcional)
    
    payload = build_request_payload(feature_description, team_config, args)
    raw_response = LambdaClient(args).send(payload)
    tickets = OutputFormatter().parse_and_validate(raw_response)
    OutputFormatter().write(tickets, args)
```

### Lambda_Client (`sprintmaster/lambda_client.py`)

```python
class LambdaClient:
    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 1

    def __init__(self, args: argparse.Namespace) -> None:
        self.url = args.lambda_url or os.environ["SPRINTMASTER_LAMBDA_URL"]

    def send(self, payload: dict) -> dict:
        """POST JSON payload, maneja reintentos para 429, errores para 4xx/5xx."""
        ...
```

**Interfaz de entrada:**
```json
{
  "feature_description": "string",
  "team_config": { ... } | null,
  "model_id": "us.anthropic.claude-3-haiku-20240307-v1:0"
}
```

**Interfaz de salida (respuesta Lambda):**
```json
{
  "tickets": [ { ...ticket_schema... } ],
  "token_usage": { "input": 0, "output": 0 },
  "model_id": "string",
  "region": "string"
}
```

### Prompt_Builder (dentro de Lambda, `lambda/prompt_builder.py`)

```python
def build_messages(feature_description: str, team_config: dict | None) -> tuple[str, list]:
    """Retorna (system_prompt, messages) para la Converse API."""
    system_prompt = BASE_SYSTEM_PROMPT
    if team_config:
        system_prompt += build_team_context_section(team_config)
    messages = [{"role": "user", "content": [{"text": feature_description}]}]
    return system_prompt, messages
```

El `BASE_SYSTEM_PROMPT` instruye al modelo a retornar exclusivamente JSON válido con el array `tickets`, usando story points Fibonacci y prioridades `high/medium/low`.

### Output_Formatter (`sprintmaster/output_formatter.py`)

```python
class OutputFormatter:
    def parse_and_validate(self, raw: dict) -> list[Ticket]:
        """Parsea JSON, valida schema, filtra tickets incompletos con advertencia."""
        ...

    def write(self, tickets: list[Ticket], args: argparse.Namespace) -> None:
        """Serializa en YAML (default) o JSON y escribe en stdout o archivo."""
        ...
```

---

## Data Models

### Ticket Schema

```python
from pydantic import BaseModel, field_validator
from typing import Literal
from enum import IntEnum

FIBONACCI = {1, 2, 3, 5, 8, 13}

class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Ticket(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str]
    story_points: int
    priority: Priority
    assignee: str

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
```

### Team_Config Schema (YAML de entrada)

```yaml
# Ejemplo de team_config.yaml
team:
  - name: "Ana García"
    role: "Backend Developer"
    stack: ["Python", "FastAPI", "PostgreSQL"]
  - name: "Luis Pérez"
    role: "Frontend Developer"
    stack: ["React", "TypeScript", "Tailwind"]
  - name: "María Torres"
    role: "DevOps Engineer"
    stack: ["Terraform", "AWS", "Docker", "Kubernetes"]
```

```python
class TeamMember(BaseModel):
    name: str
    role: str
    stack: list[str]

class TeamConfig(BaseModel):
    team: list[TeamMember]
```

### Request Payload

```python
class LambdaRequestPayload(BaseModel):
    feature_description: str
    team_config: TeamConfig | None = None
    model_id: str = "us.anthropic.claude-3-haiku-20240307-v1:0"
```

### Lambda Response

```python
class TokenUsage(BaseModel):
    input: int
    output: int

class LambdaResponse(BaseModel):
    tickets: list[dict]   # validado después por Ticket
    token_usage: TokenUsage
    model_id: str
    region: str
```

### Exit Codes

| Código | Constante | Significado |
|--------|-----------|-------------|
| 0 | `EXIT_SUCCESS` | Operación exitosa |
| 1 | `EXIT_USER_ERROR` | Error de entrada del usuario (argumento inválido, archivo no encontrado, etc.) |
| 2 | `EXIT_SERVICE_ERROR` | Error de servicio externo (Lambda, Bedrock, timeout, respuesta malformada) |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Reflexión de propiedades (consolidación)

Antes de definir las propiedades finales se identificaron los siguientes solapamientos:

- Los criterios 4.2, 4.3 y 5.1 comparten el mismo invariante de round-trip de serialización → se consolidan en **Property 1**.
- Los criterios 5.3 y 5.4 son la cara positiva y negativa del mismo comportamiento de validación de schema → se consolidan en **Property 4**.
- Los criterios 5.5, 5.6 y 5.7 prueban tres validadores de campos distintos con tipos de dato diferentes (entero, cadena categórica, cadena libre) → se mantienen separados como **Properties 2, 3 y 4** (dentro de la consolidación 5.3/5.4) pero los validadores de valor fijo (5.5, 5.6) se expresan con un solo generador de "valor inválido de campo".

---

### Property 1: Round-trip de serialización (YAML y JSON)

*For any* lista de tickets que pase la validación del Ticket_Schema, serializarla en el formato de salida (YAML o JSON) y parsear el resultado de vuelta deberá producir una lista de tickets equivalente a la original.

**Validates: Requirements 4.2, 4.3, 5.1**

---

### Property 2: Valores inválidos de story_points son rechazados

*For any* ticket cuyo campo `story_points` sea un entero que no pertenezca al conjunto Fibonacci {1, 2, 3, 5, 8, 13}, el Output_Formatter deberá omitirlo de la salida final y emitir una advertencia.

**Validates: Requirements 5.5**

---

### Property 3: Valores inválidos de priority son rechazados

*For any* ticket cuyo campo `priority` no sea exactamente uno de los valores {"high", "medium", "low"}, el Output_Formatter deberá omitirlo de la salida final y emitir una advertencia.

**Validates: Requirements 5.6**

---

### Property 4: Validación completa del Ticket_Schema

*For any* dict de ticket, si contiene todos los campos requeridos (title, description, acceptance_criteria, story_points, priority, assignee) con valores válidos, deberá incluirse en la salida; si le falta al menos un campo requerido o el valor de assignee es una cadena compuesta únicamente de espacios en blanco, deberá omitirse con una advertencia.

**Validates: Requirements 5.3, 5.4, 5.7**

---

### Property 5: Todos los campos requeridos están presentes en la salida serializada

*For any* ticket que pase la validación del Ticket_Schema, su representación serializada (YAML o JSON) deberá contener los seis campos: `title`, `description`, `acceptance_criteria`, `story_points`, `priority` y `assignee`.

**Validates: Requirements 4.6**

---

### Property 6: Reintentos con backoff exponencial

*For any* secuencia de n respuestas HTTP 429 consecutivas donde n ∈ {1, 2, 3}, el Lambda_Client deberá reintentar la solicitud exactamente n veces y el tiempo de espera antes del reintento i deberá ser ≥ BASE_BACKOFF_SECONDS × 2^(i-1).

**Validates: Requirements 2.5**

---

### Property 7: Prioridad del error más específico

*For any* combinación de condiciones de error simultáneas de entrada del usuario, el mensaje de error mostrado deberá corresponder al error más específico según la jerarquía definida: archivo no encontrado > YAML de equipo inválido > error genérico de uso.

**Validates: Requirements 1.8**

---

## Error Handling

### Jerarquía de errores y Exit Codes

```
Exit_Code 1 (errores de usuario):
  - Feature_Description vacía / no proporcionada
  - Archivo --file no encontrado
  - Archivo --team-config no encontrado o YAML inválido
  - Formato de salida inválido (no yaml/json)

Exit_Code 2 (errores de servicio):
  - SPRINTMASTER_LAMBDA_URL no definida
  - Lambda retorna 401/403 (no autorizado)
  - Lambda retorna 5xx (error interno)
  - Timeout de 30 segundos agotado
  - Respuesta del LLM no es JSON válido
  - Máximo de reintentos 429 agotado
```

### Estrategia de reintentos

```
Reintento 1: espera 1s  (2^0 × BASE_BACKOFF)
Reintento 2: espera 2s  (2^1 × BASE_BACKOFF)
Reintento 3: espera 4s  (2^2 × BASE_BACKOFF)
Si el 4° intento también es 429 → Exit_Code 2
```

### Manejo de tickets inválidos

Cuando la validación de un ticket falla (campos faltantes, story_points inválidos, priority inválida, assignee vacío):
1. Se emite una advertencia a stderr identificando el ticket (por índice o título si está disponible)
2. El ticket es omitido de la salida final
3. La ejecución continúa con los tickets válidos restantes
4. Si todos los tickets son inválidos, se muestra un mensaje de error y se sale con Exit_Code 2

### Modo verbose y quiet

```python
# Stderr para mensajes de progreso/verbose (no contamina stdout con tickets)
# Stdout exclusivamente para la salida de tickets formateados

class Logger:
    def progress(self, msg: str) -> None:  # modo estándar: spinner/indicador breve
    def verbose(self, msg: str) -> None:   # solo con --verbose
    def warning(self, msg: str) -> None:   # siempre a stderr
    def error(self, msg: str) -> None:     # siempre a stderr
```

---

## Testing Strategy

### Enfoque dual

SprintMaster combina tests de ejemplo (unitarios) y tests basados en propiedades para lograr cobertura completa:

- **Tests unitarios**: verifican comportamientos específicos, condiciones de error y casos límite
- **Tests de propiedad**: verifican invariantes universales sobre la validación del schema y la serialización

### Librería de Property-Based Testing

Se usará **Hypothesis** (Python), que es el estándar de facto para PBT en Python. Cada test de propiedad debe ejecutarse con un mínimo de 100 iteraciones (configurado via `@settings(max_examples=100)`).

### Tests de propiedad

Cada test debe incluir un comentario con el tag:
`# Feature: sprint-master, Property N: <texto de la propiedad>`

Configuración: `@settings(max_examples=100)` mínimo por test.

| Propiedad | Test | Estrategia de generación |
|-----------|------|--------------------------|
| P1: Round-trip serialización | `test_ticket_serialization_roundtrip` | `@given(st.sampled_from(["yaml","json"]), st.lists(valid_ticket_strategy(), min_size=1))` |
| P2: story_points inválidos rechazados | `test_invalid_story_points_rejected` | `@given(st.integers().filter(lambda n: n not in FIBONACCI))` |
| P3: priority inválida rechazada | `test_invalid_priority_rejected` | `@given(st.text(min_size=1).filter(lambda s: s not in {"high","medium","low"}))` |
| P4: Validación completa schema | `test_ticket_schema_validation` | `@given(ticket_dict_strategy())` — genera dicts con campos presentes/faltantes |
| P5: Campos presentes en salida | `test_all_fields_in_serialized_output` | `@given(st.lists(valid_ticket_strategy(), min_size=1))` |
| P6: Backoff exponencial | `test_retry_backoff_timing` | `@given(st.integers(min_value=1, max_value=3))` |
| P7: Prioridad de errores | `test_error_priority_ordering` | `@given(error_combination_strategy())` |

### Tests unitarios (ejemplo-based)

```
tests/
├── unit/
│   ├── test_cli_args.py          # parsing de argumentos, resolución de entradas
│   ├── test_lambda_client.py     # HTTP POST, reintentos, manejo de códigos HTTP
│   ├── test_prompt_builder.py    # construcción de prompts con/sin team_config
│   ├── test_output_formatter.py  # serialización YAML/JSON, escritura a archivo
│   └── test_validation.py        # validación de Ticket_Schema con pydantic
├── property/
│   ├── test_ticket_properties.py  # Properties 1-5 (validación y serialización)
│   ├── test_client_properties.py  # Property 6 (reintentos)
│   └── test_error_properties.py   # Property 7 (prioridad de errores)
└── integration/
    └── test_lambda_integration.py  # E2E con Lambda real (requiere credenciales AWS)
```

### Cobertura de casos de error

Los tests unitarios deben cubrir explícitamente:
- `SPRINTMASTER_LAMBDA_URL` no definida → Exit_Code 2
- Archivo `--file` no encontrado → Exit_Code 1
- YAML de `--team-config` inválido → Exit_Code 1
- Respuesta Lambda 429 × 4 veces → Exit_Code 2 tras reintentos
- Respuesta Lambda con JSON malformado → Exit_Code 2
- Ticket con `story_points: 7` (no Fibonacci) → advertencia + omisión
- Todos los tickets inválidos → Exit_Code 2
