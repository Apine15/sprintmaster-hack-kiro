# 🚀 SprintMaster CLI

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-FF9900?logo=awslambda&logoColor=white)
![Amazon Bedrock](https://img.shields.io/badge/Amazon-Bedrock-232F3E?logo=amazonaws&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

> 🌐 [Leer en Español](README.es.md)

> Intelligent agile ticket automation for high-performance teams.

```text
  ____             _       _   __  __           _            
 / ___| _ __  _ __(_)_ __ | |_|  \/  | __ _ ___| |_ ___ _ __ 
 \___ \| '_ \| '__| | '_ \| __| |\/| |/ _` / __| __/ _ \ '__|
  ___) | |_) | |  | | | | | |_| |  | | (_| \__ \ ||  __/ |   
 |____/| .__/|_|  |_|_| |_|\__|_|  |_|\__,_|___/\__\___|_|   
       |_|
```


## 🎯 The Problem & The Solution

**The Problem:** Tech leads and Product Managers spend a significant amount of time translating business requirements or feature descriptions into structured development tickets, defining acceptance criteria, and assigning tasks based on their team's seniority levels.

**The Solution:** SprintMaster is a CLI tool that takes a natural-language description and a team configuration. Using AI (Qwen3 Coder 30B via Amazon Bedrock), it analyzes the context and instantly generates structured tickets — with Story Point estimation, priority, and assignee allocation — ready to be added to the project backlog.

---

## 🏗️ Architecture & Main Components

```
┌─────────────────────┐       HTTPS         ┌──────────────────┐       Converse API        ┌─────────────────┐
│   SprintMaster CLI  │ ──────────────────► │  AWS API Gateway │ ────────────────────────► │  Amazon Bedrock │
│   (Python + Rich)   │ ◄────────────────── │  + AWS Lambda    │ ◄──────────────────────── │  Qwen3 Coder    │
└─────────────────────┘    JSON Response    └──────────────────┘     Structured JSON       └─────────────────┘
        │                                           │
        ▼                                           ▼
  feature_spec.txt                          prompt_builder.py
  team_config.yaml                          (System prompt + messages)
```

| Component | Description |
|---|---|
| **CLI Client** | Python + Rich. Parses arguments, reads local files (`.txt` and `.yaml`), communicates with the backend using exponential backoff. |
| **Serverless Backend** | AWS API Gateway + AWS Lambda. No servers to maintain, auto-scales. |
| **AI Engine** | Qwen3 Coder 30B A3B model invoked via Amazon Bedrock Converse API. |
| **Security** | No hardcoded credentials. IAM Roles + environment variables. |

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| CLI | Python 3.11+, Pydantic, Rich, PyYAML |
| Backend | AWS Lambda, API Gateway, Amazon Bedrock |
| AI | Qwen3 Coder 30B A3B (via Bedrock Converse API) |
| Testing | Pytest, Hypothesis (property-based testing), Coverage |
| Infrastructure | Serverless (AWS), IAM Roles |

---

## ⚡ Quick Demo

**Input:** A natural-language description + team configuration.

**Output:** Structured tickets with title, description, acceptance criteria, story points, priority, and assignee.

```bash
$ sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml

# Result: YAML tickets with syntax highlighting in terminal
```

---

## 🖥️ Local Installation

```bash
# Clone the repository
git clone https://github.com/Apine15/sprintmaster-hack-kiro.git
cd sprintmaster

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# Install the CLI and its dependencies
pip install -e .

# Set the Lambda URL (environment variable)
set SPRINTMASTER_LAMBDA_URL=https://your-api-gateway-url.amazonaws.com/prod
```

> 💡 **For development and testing:** if you want to run the test suite (pytest + Hypothesis), also install dev dependencies:
>
> ```bash
> pip install -e ".[dev]"
> ```

---

## 🛠️ How to Try the Demo on Replit

An interactive Replit environment is available for easy evaluation — **no local installation required**.

1. Open the Replit link (see deliverables table above).
2. The environment includes sample files in English and Spanish.
3. In the console (Shell), run:

```bash
# Main example (English input)
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml

# Force Spanish output with --lang
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml --lang Spanish
```

4. Watch the backend process the request and the CLI print the generated tickets with rich formatting.

---

## 🧪 Testing

The project has a robust test suite including unit tests, integration tests, and **property-based testing** with Hypothesis:

```bash
# Run all tests
pytest

# With coverage
pytest --cov=sprintmaster

# Unit tests only
pytest tests/unit/

# Property-based tests only
pytest tests/property/
```

---

## 📖 Detailed Usage

```bash
# Description as positional argument
sprintmaster "Implement user authentication with OAuth2"

# From file
sprintmaster --file feature_spec_en.txt

# With team configuration
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml

# Force Spanish output
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml --lang Spanish

# JSON output to file
sprintmaster "Build REST API" --format json --output tickets.json

# Pipe input
echo "Add shopping cart functionality" | sprintmaster

# Verbose mode (shows tokens, model, region)
sprintmaster --file feature_spec_en.txt --verbose

# With codebase context (scans the project structure)
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml --codebase .

# Limit scan depth to 2 levels
sprintmaster --file feature_spec_en.txt --codebase ./my-project --codebase-depth 2
```

> 💡 **Tip:** Run `sprintmaster --help` to see all available flags and their descriptions.

### 🌳 Codebase Context

The `--codebase <PATH>` flag lets SprintMaster scan your project's file and folder structure (names only, never file contents) and inject it as additional context to the AI model. This allows generated tickets to reference real paths, modules, and architectural patterns from your code.

```bash
# Example: generate tickets with project structure awareness
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml --codebase .
```

**Related options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--codebase PATH` | Path to the project directory to scan | _(none)_ |
| `--codebase-depth N` | Maximum depth of the directory tree | `4` |

**Behavior:**
- Automatically respects your `.gitignore` (root-level only).
- Excludes common directories by default: `node_modules`, `.git`, `__pycache__`, `.venv`, `dist`, `build`, etc.
- If the tree exceeds 10,000 characters, it is automatically truncated at a line boundary to avoid overflowing the model's context window.

### 🌐 Note on Output Language

The repository includes sample files in **two languages**:

| File | Language |
|---|---|
| `feature_spec_en.txt` / `team_config_en.yaml` | English |
| `feature_spec.txt` / `team_config.yaml` | Spanish |

**Model behavior (Qwen3 Coder 30B):** the model tends to generate ticket content in the same language as the provided input. The `--lang` flag works correctly to change the output language when the input is in English (e.g., `--lang Spanish` produces tickets in Spanish). However, when the input is in Spanish, the model prioritizes the context language and generates tickets in Spanish regardless of `--lang`.

**Recommendation:** to demonstrate multilingual functionality, use the English files (`*_en.*`) as a base and switch with `--lang Spanish`.

---

## 🗺️ Future Roadmap

SprintMaster's development doesn't end at this hackathon. Upcoming iterations:

- 🔗 **Native Integrations** — Direct connection to Jira, Linear, and Trello to push tickets into boards.
- 🔄 **Custom Workflows** — Support for Scrum vs. Kanban, adjusting wording and criteria.
- 📊 **Metrics Module** — Historical velocity analysis to automatically fine-tune Story Point estimation.
- 🌳 **Advanced Codebase Context** — Support for nested `.gitignore` files, cross-module dependency analysis, and architectural pattern detection.

---

## 👨‍💻 Built with Kiro

The orchestration, structuring, and development of this project was carried out using **spec-driven development** methodologies with the assistance of the AI agent [Kiro](https://kiro.dev). All workflow logs and specifications can be audited in the `.kiro/` folder of this repository.

---

## 📜 License

This project is open source and available under the terms of the [MIT License](LICENSE).
