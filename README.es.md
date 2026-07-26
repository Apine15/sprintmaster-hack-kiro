# 🚀 SprintMaster CLI

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-FF9900?logo=awslambda&logoColor=white)
![Amazon Bedrock](https://img.shields.io/badge/Amazon-Bedrock-232F3E?logo=amazonaws&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

> 🌐 [Read in English](README.md)

> Automatización inteligente de tickets ágiles para equipos de alto rendimiento.

```text
  ____             _       _   __  __           _            
 / ___| _ __  _ __(_)_ __ | |_|  \/  | __ _ ___| |_ ___ _ __ 
 \___ \| '_ \| '__| | '_ \| __| |\/| |/ _` / __| __/ _ \ '__|
  ___) | |_) | |  | | | | | |_| |  | | (_| \__ \ ||  __/ |   
 |____/| .__/|_|  |_|_| |_|\__|_|  |_|\__,_|___/\__\___|_|   
       |_|
```

---

## 📌 Enlaces Importantes (Entregables del Hackathon)

| Entregable | Enlace |
|---|---|
| 🎥 Video Presentación (Pitch & Demo 5 min) | [Enlace a YouTube/Vimeo] |
| 💻 Demo Interactiva en Línea | [Enlace a Replit] |

---

## 🎯 El Problema y la Solución

**El Problema:** Los líderes técnicos y Product Managers invierten una gran cantidad de tiempo traduciendo requisitos de negocio o descripciones de características en tickets de desarrollo estructurados, definiendo criterios de aceptación y asignando tareas según el seniority de su equipo.

**La Solución:** SprintMaster es una herramienta CLI que recibe una descripción en lenguaje natural y la configuración del equipo de desarrollo. Utilizando Inteligencia Artificial (Qwen3 Coder 30B vía Amazon Bedrock), analiza el contexto y genera instantáneamente tickets estructurados — con estimación de Story Points, prioridad y asignación de responsables — listos para integrarse al backlog del proyecto.

---

## 🏗️ Arquitectura y Componentes Principales

```
┌─────────────────────┐       HTTPS        ┌──────────────────┐       Converse API       ┌─────────────────┐
│   SprintMaster CLI  │ ──────────────────► │  AWS API Gateway │ ────────────────────────► │  Amazon Bedrock │
│   (Python + Rich)   │ ◄────────────────── │  + AWS Lambda    │ ◄──────────────────────── │  Qwen3 Coder    │
└─────────────────────┘    JSON Response    └──────────────────┘     Structured JSON       └─────────────────┘
        │                                           │
        ▼                                           ▼
  feature_spec.txt                          prompt_builder.py
  team_config.yaml                          (System prompt + messages)
```

| Componente | Descripción |
|---|---|
| **Cliente CLI** | Python + Rich. Captura argumentos, parsea archivos locales (`.txt` y `.yaml`), comunica con el backend con backoff exponencial. |
| **Backend Serverless** | AWS API Gateway + AWS Lambda. Sin servidores que mantener, escala automáticamente. |
| **Motor de IA** | Modelo Qwen3 Coder 30B A3B invocado vía Amazon Bedrock Converse API. |
| **Seguridad** | Sin credenciales hardcodeadas. IAM Roles + variables de entorno. |

---

## 🛠️ Stack Tecnológico

| Capa | Tecnologías |
|---|---|
| CLI | Python 3.11+, Pydantic, Rich, PyYAML |
| Backend | AWS Lambda, API Gateway, Amazon Bedrock |
| IA | Qwen3 Coder 30B A3B (vía Bedrock Converse API) |
| Testing | Pytest, Hypothesis (property-based testing), Coverage |
| Infraestructura | Serverless (AWS), IAM Roles |

---

## ⚡ Demo Rápida

**Input:** Una descripción en lenguaje natural + configuración del equipo.

**Output:** Tickets estructurados con título, descripción, criterios de aceptación, story points, prioridad y asignación.

```bash
$ sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml

# Resultado: tickets YAML con syntax highlighting en terminal
```

---

## 🖥️ Instalación Local

```bash
# Clonar el repositorio
git clone https://github.com/Apine15/sprintmaster-hack-kiro.git
cd sprintmaster

# Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# Instalar la CLI y sus dependencias
pip install -e .

# Configurar la URL del Lambda (variable de entorno)
set SPRINTMASTER_LAMBDA_URL=https://tu-api-gateway-url.amazonaws.com/prod
```

> 💡 **Para desarrollo y testing:** si deseas ejecutar la suite de tests (pytest + Hypothesis), instala también las dependencias de desarrollo:
>
> ```bash
> pip install -e ".[dev]"
> ```

---

## 🛠️ Cómo Probar la Demo en Replit

Para facilitar la evaluación, se ha preparado un entorno interactivo en Replit que **no requiere instalaciones locales**.

1. Abre el enlace de Replit (ver tabla de entregables arriba).
2. El entorno ya cuenta con archivos de prueba en inglés y español.
3. En la consola (Shell), ejecuta:

```bash
# Ejemplo principal (input en inglés)
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml

# Forzar salida en español con --lang
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml --lang Spanish
```

4. Observa cómo el backend procesa la solicitud y la CLI imprime los tickets generados con formato enriquecido.

---

## 🧪 Testing

El proyecto cuenta con una suite de tests robusta que incluye tests unitarios, de integración y **property-based testing** con Hypothesis:

```bash
# Ejecutar todos los tests
pytest

# Con cobertura
pytest --cov=sprintmaster

# Solo tests unitarios
pytest tests/unit/

# Solo property-based tests
pytest tests/property/
```

---

## 📖 Uso Detallado

```bash
# Descripción como argumento posicional
sprintmaster "Implement user authentication with OAuth2"

# Desde archivo (inglés)
sprintmaster --file feature_spec_en.txt

# Con configuración de equipo
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml

# Forzar salida en español
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml --lang Spanish

# Salida en JSON a archivo
sprintmaster "Build REST API" --format json --output tickets.json

# Input por pipe
echo "Add shopping cart functionality" | sprintmaster

# Modo verbose (muestra tokens, modelo, región)
sprintmaster --file feature_spec_en.txt --verbose

# Con contexto del codebase (escanea la estructura del proyecto)
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml --codebase .

# Limitar la profundidad del escaneo a 2 niveles
sprintmaster --file feature_spec_en.txt --codebase ./mi-proyecto --codebase-depth 2
```

> 💡 **Tip:** Usa `sprintmaster --help` para ver todas las flags disponibles con su descripción.

### 🌳 Contexto del Codebase

La flag `--codebase <PATH>` permite que SprintMaster escanee la estructura de archivos y carpetas de tu proyecto (solo nombres, nunca contenido) e inyecte esa información como contexto adicional al modelo de IA. Esto permite que los tickets generados referencien rutas, módulos y patrones arquitectónicos reales de tu código.

```bash
# Ejemplo: generar tickets con conocimiento de la estructura del proyecto
sprintmaster --file feature_spec_en.txt --team-config team_config_en.yaml --codebase .
```

**Opciones relacionadas:**

| Flag | Descripción | Default |
|------|-------------|---------|
| `--codebase PATH` | Ruta al directorio del proyecto a escanear | _(ninguno)_ |
| `--codebase-depth N` | Profundidad máxima del árbol de directorios | `4` |

**Comportamiento:**
- Respeta automáticamente tu `.gitignore` (solo el del directorio raíz escaneado).
- Excluye por defecto directorios comunes como `node_modules`, `.git`, `__pycache__`, `.venv`, `dist`, `build`, etc.
- Si el árbol excede 10,000 caracteres, se trunca automáticamente en un límite de línea para no desbordar la ventana de contexto del modelo.

### 🌐 Nota sobre el Idioma del Output

El repositorio incluye archivos de ejemplo en **dos idiomas**:

| Archivo | Idioma |
|---|---|
| `feature_spec_en.txt` / `team_config_en.yaml` | Inglés |
| `feature_spec.txt` / `team_config.yaml` | Español |

**Comportamiento del modelo (Qwen3 Coder 30B):** el modelo tiende a generar el contenido de los tickets en el mismo idioma del input proporcionado. La flag `--lang` funciona correctamente para cambiar el idioma de salida cuando el input está en inglés (por ejemplo, `--lang Spanish` produce tickets en español). Sin embargo, cuando el input está en español, el modelo prioriza el idioma del contexto y genera los tickets en español independientemente del valor de `--lang`.

**Recomendación:** para demostrar la funcionalidad multilenguaje, usar los archivos en inglés (`*_en.*`) como base y alternar con `--lang Spanish`.

---

## 🗺️ Roadmap Futuro

El desarrollo de SprintMaster no termina en este hackathon. Próximas iteraciones:

- 🔗 **Integraciones Nativas** — Conexión directa con Jira, Linear y Trello para inyectar tickets en los tableros.
- 🔄 **Flujos Personalizados** — Soporte para Scrum vs. Kanban, ajustando redacción y criterios.
- 📊 **Módulo de Métricas** — Análisis del histórico de velocidad para ajustar automáticamente la estimación de Story Points.
- 🌳 **Contexto de Codebase Avanzado** — Soporte para `.gitignore` anidados, análisis de dependencias entre módulos y detección de patrones arquitectónicos.

---

## 👨‍💻 Construido con Kiro

La orquestación, estructuración y desarrollo de este proyecto se llevó a cabo aplicando metodologías de **desarrollo guiado por especificaciones** con la asistencia del agente de IA [Kiro](https://kiro.dev). Todos los registros y especificaciones de este flujo de trabajo pueden auditarse en la carpeta `.kiro/` de este repositorio.

---

## 📜 Licencia

Este proyecto es de código abierto y está disponible bajo los términos de la [Licencia MIT](LICENSE).
