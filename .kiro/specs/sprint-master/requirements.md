# Requirements Document

## Introduction

SprintMaster es una herramienta CLI construida en Python que acepta una descripción de funcionalidad en lenguaje natural y utiliza un LLM (Amazon Bedrock con Claude 3 Haiku) para generar un desglose estructurado de tickets ágiles. La herramienta produce resultados en formato YAML o JSON, permitiendo a desarrolladores y product managers descomponer rápidamente ideas de funcionalidades en elementos de trabajo accionables para sprints.

## Glossary

- **CLI**: Interfaz de Línea de Comandos — la superficie principal de interacción del usuario con SprintMaster
- **SprintMaster**: La aplicación CLI en Python que orquesta la descomposición de funcionalidades
- **Lambda_Client**: El componente de la CLI responsable de enviar solicitudes HTTP a la AWS Lambda backend
- **Lambda_Function**: La función AWS Lambda que recibe la solicitud de la CLI, usa Boto3 para invocar Claude 3 Haiku vía API Converse y retorna la respuesta estructurada
- **Prompt_Builder**: El componente (dentro de la Lambda_Function) que construye el prompt del LLM a partir de la entrada del usuario, las instrucciones del sistema y el contexto del equipo
- **Output_Formatter**: El componente de la CLI que serializa la respuesta del LLM en YAML o JSON estructurado
- **Ticket**: Un elemento de trabajo ágil individual que contiene título, descripción, criterios de aceptación, estimación de story points, nivel de prioridad y responsable asignado
- **Feature_Description**: El texto en lenguaje natural proporcionado por el usuario que describe la funcionalidad a descomponer
- **Team_Config**: Archivo YAML de configuración que describe los miembros del equipo, sus roles y su stack tecnológico; permite la asignación automática e inteligente de tickets
- **Converse_API**: La API del runtime de Bedrock en Boto3 utilizada por la Lambda_Function para invocar el modelo LLM
- **Ticket_Schema**: El formato estructurado que define los campos y tipos de un ticket generado
- **Exit_Code**: Código numérico de salida del proceso — 0 indica éxito, 1 indica error de entrada del usuario, 2 indica error de servicio externo

## Requirements

### Requisito 1: Aceptar Descripción de Funcionalidad y Configuración del Equipo como Entrada

**Historia de Usuario:** Como desarrollador, quiero proporcionar una descripción de funcionalidad y la configuración de mi equipo a SprintMaster a través de la línea de comandos, para generar tickets ágiles asignados automáticamente según el stack técnico del equipo.

#### Criterios de Aceptación

1. WHEN una Feature_Description es proporcionada como argumento posicional, THE CLI SHALL aceptar el texto y pasarlo al Lambda_Client
2. WHEN el flag --file es proporcionado con una ruta de archivo válida, THE CLI SHALL leer el contenido del archivo y usarlo como Feature_Description
3. WHEN una Feature_Description es proporcionada vía stdin (entrada canalizada), THE CLI SHALL leer stdin y usarla como Feature_Description
4. IF no se proporciona Feature_Description a través de ningún método de entrada, THEN THE CLI SHALL mostrar un mensaje de error de uso y salir con Exit_Code 1
5. IF el flag --file referencia un archivo inexistente, THEN THE CLI SHALL mostrar un mensaje de error indicando que el archivo no fue encontrado y salir con Exit_Code 1
6. WHEN el flag --team-config es proporcionado con una ruta de archivo YAML válida, THE CLI SHALL leer el contenido del archivo y enviarlo junto con la Feature_Description al Lambda_Client como Team_Config
7. IF el flag --team-config referencia un archivo inexistente o no es un YAML válido, THEN THE CLI SHALL mostrar un mensaje de error describiendo el problema y salir con Exit_Code 1
8. IF múltiples condiciones de error ocurren simultáneamente, THEN THE CLI SHALL mostrar el error más específico primero (archivo no encontrado tiene prioridad sobre error genérico de uso)

### Requisito 2: Invocar el Backend a través de AWS Lambda

**Historia de Usuario:** Como desarrollador, quiero que SprintMaster envíe la solicitud a una AWS Lambda que actúa como backend, para mantener la CLI ligera y delegar a la Lambda la responsabilidad de invocar Amazon Bedrock.

#### Criterios de Aceptación

1. WHEN una Feature_Description válida es recibida, THE Lambda_Client SHALL enviar una solicitud HTTP POST a la URL de la Lambda_Function con la Feature_Description y el Team_Config como cuerpo de la solicitud en formato JSON
2. THE Lambda_Client SHALL leer la URL de la Lambda_Function desde la variable de entorno SPRINTMASTER_LAMBDA_URL
3. IF la variable de entorno SPRINTMASTER_LAMBDA_URL no está definida, THEN THE Lambda_Client SHALL mostrar un mensaje de error indicando que la URL del backend no está configurada y salir con Exit_Code 2
4. IF la Lambda_Function retorna un código HTTP 2xx, THEN THE Lambda_Client SHALL retornar el cuerpo de la respuesta al Output_Formatter
5. IF la Lambda_Function retorna un código HTTP 429, THEN THE Lambda_Client SHALL reintentar la solicitud hasta 3 veces con backoff exponencial comenzando en 1 segundo
6. IF la Lambda_Function retorna un código HTTP 401 o 403, THEN THE Lambda_Client SHALL mostrar un mensaje indicando que la solicitud al backend fue rechazada por falta de autorización y salir con Exit_Code 2
7. IF la Lambda_Function retorna un código HTTP 5xx, THEN THE Lambda_Client SHALL mostrar un mensaje indicando un error interno del backend y salir con Exit_Code 2
8. IF la solicitud HTTP no recibe respuesta en 30 segundos, THEN THE Lambda_Client SHALL mostrar un mensaje de error de tiempo de espera agotado y salir con Exit_Code 2

### Requisito 3: Construir Prompt del LLM con Contexto del Equipo

**Historia de Usuario:** Como desarrollador, quiero que SprintMaster inyecte la configuración del equipo en el prompt del LLM, para que los tickets generados sean asignados automáticamente al miembro más adecuado según el stack técnico.

#### Criterios de Aceptación

1. THE Prompt_Builder (dentro de la Lambda_Function) SHALL construir un prompt de sistema instruyendo al modelo a retornar tickets ágiles en formato JSON estructurado
2. WHEN el Team_Config está disponible, THE Prompt_Builder SHALL inyectar en el prompt de sistema los nombres, roles y stacks tecnológicos de cada miembro del equipo para habilitar la asignación inteligente de tickets
3. THE Prompt_Builder SHALL incluir la Feature_Description como mensaje del usuario en la solicitud a la API Converse
4. THE Prompt_Builder SHALL instruir al modelo a generar tickets que contengan: título, descripción, criterios de aceptación, estimación de story points, nivel de prioridad y responsable asignado (assignee)
5. THE Prompt_Builder SHALL instruir al modelo a asignar story points usando la secuencia Fibonacci (1, 2, 3, 5, 8, 13)
6. THE Prompt_Builder SHALL instruir al modelo a asignar niveles de prioridad del conjunto: high, medium, low
7. WHEN el Team_Config está disponible, THE Prompt_Builder SHALL instruir al modelo a asignar cada ticket al miembro del equipo cuyo rol y stack técnico sea más adecuado para la tarea
8. IF no se proporciona Team_Config, THEN THE Prompt_Builder SHALL construir el prompt de sistema sin contexto de equipo y el campo assignee de cada ticket SHALL contener el valor "unassigned"

### Requisito 4: Producir Tickets Estructurados

**Historia de Usuario:** Como desarrollador, quiero recibir los tickets generados en formato YAML o JSON, para integrarlos en mi flujo de trabajo de gestión de proyectos.

#### Criterios de Aceptación

1. THE Output_Formatter SHALL usar formato YAML como valor predeterminado cuando no se especifica formato de salida
2. WHEN el flag --format json es proporcionado, THE Output_Formatter SHALL producir tickets en formato JSON válido
3. WHEN el flag --format yaml es proporcionado, THE Output_Formatter SHALL producir tickets en formato YAML válido
4. WHEN no se proporciona el flag --output, THE Output_Formatter SHALL escribir la salida formateada en stdout
5. WHEN el flag --output es proporcionado con una ruta de archivo, THE Output_Formatter SHALL escribir la salida formateada en el archivo especificado
6. WHEN un Ticket es producido, THE Output_Formatter SHALL incluir los campos: title, description, acceptance_criteria (como lista), story_points, priority y assignee

### Requisito 5: Parsear y Validar Respuesta del LLM

**Historia de Usuario:** Como desarrollador, quiero que SprintMaster valide la respuesta del LLM antes de producir la salida, para recibir siempre datos de tickets bien formados.

#### Criterios de Aceptación

1. WHEN el Lambda_Client retorna una respuesta, THE Output_Formatter SHALL parsear el texto de respuesta como JSON
2. IF la respuesta del LLM no contiene JSON válido, THEN THE Output_Formatter SHALL mostrar un mensaje de error indicando que la respuesta del modelo fue malformada y salir con Exit_Code 2
3. WHEN la respuesta parseada es validada, THE Output_Formatter SHALL verificar que cada Ticket contiene todos los campos requeridos definidos en el Ticket_Schema
4. IF un Ticket no tiene campos requeridos, THEN THE Output_Formatter SHALL mostrar una advertencia identificando el ticket incompleto y omitirlo de la salida final
5. THE Output_Formatter SHALL validar que los valores de story_points están dentro de la secuencia Fibonacci (1, 2, 3, 5, 8, 13)
6. THE Output_Formatter SHALL validar que los valores de priority son uno de: high, medium, low
7. THE Output_Formatter SHALL validar que el campo assignee de cada Ticket es una cadena de texto no vacía o el valor "unassigned"

### Requisito 6: Configurar URL del Backend y Modelo

**Historia de Usuario:** Como desarrollador, quiero configurar la URL de la Lambda y opcionalmente el modelo a usar, para adaptar SprintMaster a diferentes entornos de despliegue.

#### Criterios de Aceptación

1. THE CLI SHALL leer la URL del backend desde la variable de entorno SPRINTMASTER_LAMBDA_URL como configuración predeterminada
2. WHEN el flag --lambda-url es proporcionado, THE CLI SHALL usar esa URL como destino para todas las solicitudes HTTP del Lambda_Client, sobrescribiendo la variable de entorno
3. THE CLI SHALL incluir el identificador de modelo "us.anthropic.claude-3-haiku-20240307-v1:0" en el cuerpo de la solicitud HTTP cuando no se proporciona el flag --model
4. WHEN el flag --model es proporcionado, THE CLI SHALL incluir el identificador de modelo especificado en el cuerpo de la solicitud HTTP enviada a la Lambda_Function

### Requisito 7: Mostrar Ayuda e Información de Versión

**Historia de Usuario:** Como desarrollador, quiero acceder a la documentación de ayuda e información de versión desde la CLI, para entender las opciones disponibles y solucionar problemas.

#### Criterios de Aceptación

1. WHEN el flag --help es proporcionado, THE CLI SHALL mostrar instrucciones de uso, flags disponibles y ejemplos, y salir inmediatamente con Exit_Code 0 ignorando otros argumentos
2. WHEN el flag --version es proporcionado, THE CLI SHALL mostrar la versión actual de SprintMaster y salir inmediatamente con Exit_Code 0
3. THE CLI SHALL incluir ejemplos de uso en la salida de ayuda demostrando: entrada por argumento posicional, entrada por archivo, entrada canalizada y selección de formato de salida

### Requisito 8: Soportar Modos Verboso y Silencioso

**Historia de Usuario:** Como desarrollador, quiero controlar la verbosidad de la salida de SprintMaster, para depurar problemas o suprimir mensajes no esenciales en scripts automatizados.

#### Criterios de Aceptación

1. WHEN el flag --verbose es proporcionado, THE CLI SHALL mostrar información adicional incluyendo: el modelo utilizado, la región AWS, uso de tokens de la respuesta de la API y tiempo de procesamiento
2. WHILE el flag --quiet está activo y no hay errores, THE CLI SHALL mostrar únicamente los tickets formateados sin mensajes informativos adicionales
3. IF el flag --quiet está activo y ocurre un error, THEN THE CLI SHALL mostrar únicamente el mensaje de error y salir con el Exit_Code correspondiente
4. THE CLI SHALL usar como modo predeterminado un modo estándar que muestra un indicador breve de progreso durante la llamada a la API

