# Documento de Requisitos de Bugfix

## Introducción

Este documento aborda cuatro defectos de UI/UX en el sistema de registro y salida de SprintMaster CLI. Los problemas afectan la presentación visual del banner, el enrutamiento de advertencias de validación, la sincronización del spinner con la salida de tickets, y el uso de emojis que no se renderizan correctamente en todos los sistemas operativos. Estos defectos degradan la experiencia del usuario y la apariencia profesional de la herramienta.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN logger.banner() is invoked THEN the system renders only a single line of plain text ("SprintMaster" en bold cyan) without arte ASCII de múltiples líneas

1.2 WHEN a Pydantic ValidationError occurs during ticket parsing in OutputFormatter.parse_and_validate() THEN the system prints the warning message as plain text via print() directly to stderr, bypassing the styled logger.warning() method

1.3 WHEN logger.stop_progress() is called after "Processing response..." and before formatter.write() in cli.py THEN the system does not clear completely the spinner line, causing the spinner text to overlap visually with the first rendered ticket (e.g., "⠙ Processing response...title: Modelado...")

1.4 WHEN logger.warning() is invoked THEN the system renders the emoji ⚠️ which may not display correctly across all operating systems and terminals

1.5 WHEN logger.error() is invoked THEN the system renders the emoji ❌ which may not display correctly across all operating systems and terminals

### Expected Behavior (Correct)

2.1 WHEN logger.banner() is invoked THEN the system SHALL render an ASCII art multi-line representation of "SprintMaster" (estilo bloque o slant) using rich colors (bold cyan/magenta gradient) to stderr

2.2 WHEN a Pydantic ValidationError occurs during ticket parsing in OutputFormatter.parse_and_validate() THEN the system SHALL route the warning message through logger.warning() so it renders with the correct yellow style and color on stderr

2.3 WHEN the "Processing response..." spinner is active and tickets are ready to be written THEN the system SHALL call logger.stop_progress() and fully clear the spinner line in cli.py BEFORE invoking formatter.write(), ensuring no visual overlap between the spinner text and the first ticket output

2.4 WHEN logger.warning() is invoked THEN the system SHALL render the prefix "[!] Warning:" in yellow style instead of using the ⚠️ emoji

2.5 WHEN logger.error() is invoked THEN the system SHALL render the prefix "[x] Error:" in bold red style instead of using the ❌ emoji

### Unchanged Behavior (Regression Prevention)

3.1 WHEN --quiet flag is active THEN the system SHALL CONTINUE TO suppress banner output entirely

3.2 WHEN all tickets are valid (no ValidationError occurs) THEN the system SHALL CONTINUE TO output tickets without any warning messages

3.3 WHEN the first spinner ("Generating tickets...") is active and the Lambda response completes THEN the system SHALL CONTINUE TO stop the spinner cleanly before displaying verbose metadata

3.4 WHEN logger.verbose() is invoked THEN the system SHALL CONTINUE TO render messages in dim style only when --verbose is active

3.5 WHEN output is piped (non-TTY) THEN the system SHALL CONTINUE TO render tickets as plain text without ANSI escape sequences on stdout

3.6 WHEN logger.warning() or logger.error() are called THEN the system SHALL CONTINUE TO write output to stderr (not stdout)

3.7 WHEN --quiet flag is active THEN the system SHALL CONTINUE TO show warnings and errors regardless of quiet mode
