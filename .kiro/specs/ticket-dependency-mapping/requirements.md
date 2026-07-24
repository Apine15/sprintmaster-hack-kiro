# Requirements Document

## Introduction

Esta característica agrega mapeo de dependencias entre tickets en SprintMaster. Permite que el LLM identifique relaciones de bloqueo entre tickets generados, indicando qué tareas deben completarse antes de poder iniciar un ticket dado. El campo `dependencies` se integra en el modelo de datos Pydantic, en el prompt del LLM, en el formateo de salida y en las pruebas unitarias existentes.

## Glossary

- **Ticket**: Modelo Pydantic que representa un ticket ágil con campos como título, descripción, criterios de aceptación, puntos de historia, prioridad y asignado.
- **PromptBuilder**: Módulo (`lambda/prompt_builder.py`) responsable de construir el prompt del sistema y los mensajes para la API de Bedrock Converse.
- **OutputFormatter**: Clase (`sprintmaster/output_formatter.py`) que parsea, valida y serializa los tickets en formato YAML o JSON con estilos Rich.
- **TICKET_KEYS**: Conjunto definido en `output_formatter.py` que contiene las claves reconocidas de un ticket para aplicar estilo en la salida con Rich.
- **Dependencies**: Campo opcional en el modelo Ticket que contiene una lista de títulos de tickets de los cuales depende el ticket actual.
- **LLM**: Modelo de lenguaje grande (Claude 3 Haiku vía AWS Bedrock) que genera los tickets a partir de la descripción de la feature.

## Requirements

### Requisito 1: Campo dependencies en el modelo de datos

**Historia de usuario:** Como desarrollador, quiero que el modelo Ticket incluya un campo opcional de dependencias, para que se puedan representar relaciones de bloqueo entre tickets.

#### Criterios de Aceptación

1. THE Ticket SHALL incluir un campo `dependencies` de tipo lista de strings con valor por defecto de lista vacía y un máximo de 50 elementos.
2. WHEN el campo `dependencies` contiene una lista vacía, THE Ticket SHALL ser válido sin errores de validación.
3. WHEN el campo `dependencies` contiene una lista de strings donde cada elemento tiene al menos 1 carácter no-espacio y no excede 200 caracteres, THE Ticket SHALL ser válido.
4. WHEN el campo `dependencies` no se proporciona en los datos de entrada, THE Ticket SHALL asignar una lista vacía como valor por defecto.
5. IF el campo `dependencies` contiene un elemento que es un string vacío o compuesto únicamente por espacios en blanco, THEN THE Ticket SHALL rechazar la validación con un mensaje de error indicando que los elementos de dependencias no pueden ser vacíos.
6. IF el campo `dependencies` contiene elementos duplicados, THEN THE Ticket SHALL rechazar la validación con un mensaje de error indicando que las dependencias no pueden contener valores repetidos.

### Requisito 2: Instrucción de dependencias en el prompt del LLM

**Historia de usuario:** Como usuario de SprintMaster, quiero que el LLM analice las relaciones de bloqueo entre tickets, para que el campo dependencies se complete automáticamente indicando qué tareas deben finalizarse antes de iniciar cada ticket.

#### Criterios de Aceptación

1. THE PromptBuilder SHALL incluir en el prompt del sistema una instrucción que indique al LLM analizar relaciones de bloqueo entre tickets, definiendo que un ticket B bloquea a un ticket A cuando el ticket A no puede iniciarse hasta que el ticket B esté completado.
2. THE PromptBuilder SHALL instruir al LLM a completar el campo `dependencies` con una lista de títulos exactos de otros tickets del mismo conjunto de respuesta que deben finalizarse antes de poder iniciar el ticket actual, excluyendo el título del propio ticket.
3. IF un ticket no tiene dependencias de otros tickets en el conjunto generado, THEN THE PromptBuilder SHALL instruir al LLM a devolver una lista vacía `[]` en el campo `dependencies` de dicho ticket.
4. THE PromptBuilder SHALL incluir el campo `dependencies` en la lista de campos obligatorios de cada objeto ticket dentro del prompt del sistema.
5. THE PromptBuilder SHALL incluir un ejemplo de respuesta JSON que demuestre el uso del campo `dependencies` mostrando al menos un ticket con una lista no vacía de dependencias y al menos un ticket con una lista vacía.

### Requisito 3: Reconocimiento del campo dependencies en el formateo de salida

**Historia de usuario:** Como usuario de SprintMaster, quiero que el campo dependencies se muestre correctamente en la salida formateada, para poder visualizar las dependencias de cada ticket.

#### Criterios de Aceptación

1. THE OutputFormatter SHALL incluir `dependencies` en el conjunto TICKET_KEYS.
2. WHEN la salida se renderiza en modo YAML con terminal TTY, THE OutputFormatter SHALL mostrar la clave `dependencies` con el label humanizado "Dependencies" y estilo bold cyan, siguiendo el mismo patrón de renderizado que las demás claves en TICKET_KEYS.
3. WHEN la salida se renderiza en modo YAML plano o JSON, THE OutputFormatter SHALL incluir el campo `dependencies` en la serialización conservando el orden original de los elementos.
4. WHEN un ticket tiene una lista vacía en `dependencies`, THE OutputFormatter SHALL serializar el campo como una lista vacía ([] en JSON, línea vacía en YAML).
5. WHEN un ticket tiene dependencias, THE OutputFormatter SHALL serializar cada elemento de la lista `dependencies` como un string representando el título del ticket dependiente, manteniendo el orden de entrada.
6. IF un ticket no contiene el campo `dependencies` o su valor es null, THEN THE OutputFormatter SHALL omitir el campo `dependencies` de la salida serializada sin generar error.
7. WHEN un ticket tiene dependencias, THE OutputFormatter SHALL serializar un máximo de 50 elementos en la lista `dependencies`.

### Requisito 4: Actualización de pruebas unitarias

**Historia de usuario:** Como desarrollador, quiero que las pruebas unitarias validen el campo dependencies, para garantizar que la integración funcione correctamente en todos los componentes.

#### Criterios de Aceptación

1. THE test suite SHALL incluir una prueba que valide la creación de un Ticket con el campo `dependencies` como lista vacía por defecto, verificando que `ticket.dependencies == []` cuando no se proporciona el argumento.
2. THE test suite SHALL incluir una prueba que valide la creación de un Ticket con el campo `dependencies` conteniendo una lista de 1 o más strings no vacíos (strings con al menos 1 carácter visible tras aplicar strip), confirmando que el Ticket se instancia sin error de validación.
3. THE test suite SHALL incluir una prueba que valide el rechazo de un Ticket con `dependencies` conteniendo al menos un string vacío o compuesto solo por espacios en blanco, verificando que se lanza un `ValidationError`.
4. THE test suite SHALL incluir una prueba que valide que el conjunto `TICKET_KEYS` en `output_formatter.py` contiene el elemento `"dependencies"`.
5. THE test suite SHALL incluir una prueba que valide que `BASE_SYSTEM_PROMPT` contiene la cadena `"dependencies"` como parte de la definición de campos requeridos del ticket.
6. THE test suite SHALL incluir una prueba que valide la serialización en formato YAML de un ticket cuyo campo `dependencies` contiene al menos 2 elementos, verificando que el YAML resultante incluye la clave `dependencies` con una lista parseable por `yaml.safe_load`.
7. THE test suite SHALL incluir una prueba que valide la serialización en formato JSON de un ticket cuyo campo `dependencies` contiene al menos 2 elementos, verificando que el JSON resultante incluye la clave `dependencies` con un array parseable por `json.loads`.
8. THE test suite SHALL incluir una prueba que valide que un Ticket con `dependencies` conteniendo strings duplicados se rechaza con un `ValidationError`.

### Requisito 5: Consistencia del campo dependencies en el ciclo completo

**Historia de usuario:** Como desarrollador, quiero que el campo dependencies se mantenga consistente a través de todo el pipeline (modelo → prompt → respuesta → formateo), para garantizar integridad de datos.

#### Criterios de Aceptación

1. WHEN el LLM retorna un ticket con campo `dependencies` conteniendo una lista de strings válidos (strings no vacíos), THE OutputFormatter SHALL parsear el campo mediante el modelo Ticket y producir un objeto Ticket cuyo atributo `dependencies` sea igual a la lista original sin modificaciones.
2. WHEN un ticket validado se serializa a YAML y se deserializa de vuelta, THE Ticket resultante SHALL contener la misma lista de `dependencies` que el original, preservando el orden y contenido exacto de los elementos (propiedad round-trip verificada con listas de 0 a 10 elementos, cada elemento de 1 a 100 caracteres).
3. WHEN un ticket validado se serializa a JSON y se deserializa de vuelta, THE Ticket resultante SHALL contener la misma lista de `dependencies` que el original, preservando el orden y contenido exacto de los elementos (propiedad round-trip verificada con listas de 0 a 10 elementos, cada elemento de 1 a 100 caracteres).
4. IF el LLM retorna un ticket con campo `dependencies` conteniendo valores inválidos (strings vacíos, elementos no-string, o tipo no-lista), THEN THE OutputFormatter SHALL omitir ese ticket de la salida y emitir una advertencia indicando el ticket inválido.
