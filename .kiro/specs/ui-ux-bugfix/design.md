# Diseño de Bugfix: UI/UX Defects en SprintMaster CLI

## Overview

Este documento formaliza el enfoque de corrección para cuatro defectos de UI/UX en SprintMaster CLI:
1. El banner se renderiza como texto plano de una sola línea en lugar de arte ASCII multi-línea
2. Las advertencias de validación usan `print()` directamente en lugar del logger estilizado
3. El spinner no se limpia antes de la salida de tickets, causando solapamiento visual
4. Los emojis (⚠️ y ❌) no se renderizan correctamente en todos los terminales/OS

La estrategia general es realizar cambios mínimos y focalizados en `logger.py`, `output_formatter.py` y `cli.py` para corregir cada defecto sin alterar el comportamiento existente para inputs que no activan la condición de bug.

## Glossary

- **Bug_Condition (C)**: Conjunto de condiciones que activan los defectos visuales — invocación de `banner()`, ocurrencia de `ValidationError` en parsing, secuencia spinner→write sin limpieza, o uso de emojis en warning/error
- **Property (P)**: Comportamiento esperado correcto — banner ASCII art, warnings enrutados por logger, spinner limpio antes de output, prefijos texto en lugar de emojis
- **Preservation**: Comportamientos existentes que NO deben cambiar — modo quiet, salida a stderr, plain text en non-TTY, verbose metadata, etc.
- **`Logger`**: Clase en `sprintmaster/logger.py` que gestiona toda la salida no-ticket a stderr con soporte de verbosidad
- **`OutputFormatter`**: Clase en `sprintmaster/output_formatter.py` que parsea, valida y serializa tickets
- **`main()`**: Función en `sprintmaster/cli.py` que orquesta el flujo completo del CLI
- **Rich Console**: Librería de renderizado utilizada para estilos, colores y spinners

## Bug Details

### Bug Condition

Los bugs se manifiestan en cuatro escenarios independientes dentro del sistema de logging y output. Cada uno representa un path de código que produce salida visual incorrecta o degradada.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type CLIInvocation
  OUTPUT: boolean
  
  // Bug 1: Banner siempre renderiza incorrectamente (texto plano)
  condition1 := input.action == "banner" AND NOT input.quietMode
  
  // Bug 2: ValidationError usa print() en vez de logger
  condition2 := input.action == "parse_and_validate" 
                AND input.ticketData IS invalid
                AND validationWarningRouted_via_print()
  
  // Bug 3: Spinner no se detiene antes de write()
  condition3 := input.action == "process_response"
                AND spinnerActive("Processing response...")
                AND formatter.write() invoked BEFORE logger.stop_progress()
  
  // Bug 4+5: Emojis en warning/error
  condition4 := input.action IN ["warning", "error"]
                AND outputContainsEmoji(input.message)
  
  RETURN condition1 OR condition2 OR condition3 OR condition4
END FUNCTION
```

### Examples

- **Bug 1**: `logger.banner()` → muestra `"SprintMaster"` en bold cyan (una línea) en vez de arte ASCII multi-línea con gradiente
- **Bug 2**: Ticket con campo inválido → `print("Advertencia: ticket 'X' es inválido...", file=sys.stderr)` en vez de `logger.warning("ticket 'X' es inválido...")`
- **Bug 3**: Spinner "⠙ Processing response..." aparece concatenado con la primera línea del ticket: `"⠙ Processing response...title: Modelado de datos"`
- **Bug 4**: `logger.warning("algo")` → muestra `"⚠️ Warning: algo"` donde ⚠️ puede no renderizar en Windows CMD o terminales sin soporte Unicode completo
- **Bug 5**: `logger.error("fallo")` → muestra `"❌ Error: fallo"` con el mismo problema de renderización

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- El flag `--quiet` DEBE seguir suprimiendo el banner completamente
- Cuando todos los tickets son válidos, no se emiten advertencias
- El primer spinner ("Generating tickets...") se detiene limpiamente antes de metadata verbose
- `logger.verbose()` sigue mostrando mensajes en dim style solo con `--verbose`
- En non-TTY (piped), los tickets se renderizan como plain text sin ANSI en stdout
- `logger.warning()` y `logger.error()` siguen escribiendo a stderr (no stdout)
- Con `--quiet`, warnings y errors se siguen mostrando

**Scope:**
Todos los inputs que NO involucran las cuatro condiciones de bug deben permanecer completamente sin afectar. Esto incluye:
- Flujo normal de tickets válidos sin spinner overlap
- Output a archivo via `--output`
- Formato JSON via `--format json`
- Resolución de input (positional, --file, stdin)
- Comunicación con Lambda backend

## Hypothesized Root Cause

Basándonos en el análisis del código fuente:

1. **Banner single-line (Bug 1)**: `Logger.banner()` en `logger.py:46` simplemente llama `self._console.print("SprintMaster", style="bold cyan")`. No hay arte ASCII definido; solo se imprime el nombre como texto estilizado.

2. **Warnings bypass logger (Bug 2)**: En `output_formatter.py:73-79`, el catch de `ValidationError` usa `print(..., file=sys.stderr)` directamente. El `OutputFormatter` no tiene referencia al `Logger`, por lo que no puede usar `logger.warning()`.

3. **Spinner overlap (Bug 3)**: En `cli.py:237-240`, la secuencia es:
   ```python
   logger.start_progress("Processing response...")
   tickets = formatter.parse_and_validate(raw_response)
   formatter.write(tickets, args)
   logger.stop_progress()  # ← DESPUÉS de write(), debería ser ANTES
   ```
   El spinner sigue activo cuando `formatter.write()` escribe los tickets, causando solapamiento.

4. **Emojis incompatibles (Bug 4+5)**: `Logger.warning()` usa `f"⚠️ Warning: {msg}"` y `Logger.error()` usa `f"❌ Error: {msg}"`. Estos caracteres Unicode pueden no renderizarse en terminales sin soporte completo (Windows CMD, terminales legacy).

## Correctness Properties

Property 1: Bug Condition - Corrección visual de output

_For any_ invocación del CLI donde se activa alguna de las condiciones de bug (banner sin quiet, ValidationError durante parsing, secuencia spinner→write, o llamada a warning/error), las funciones corregidas SHALL producir la salida visual correcta: banner como ASCII art multi-línea, warnings enrutados por el logger con estilo amarillo, spinner detenido completamente antes de la escritura de tickets, y prefijos texto `[!]`/`[x]` en lugar de emojis.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation - Comportamiento sin cambios para inputs no-bug

_For any_ invocación del CLI donde NINGUNA condición de bug aplica (modo quiet activo para banner, tickets todos válidos, interacciones sin warning/error, output piped), las funciones corregidas SHALL producir exactamente el mismo resultado que las funciones originales, preservando el comportamiento de quiet mode, stderr routing, plain text en non-TTY, verbose metadata, y flujo normal de tickets.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

## Fix Implementation

### Changes Required

Asumiendo que nuestro análisis de causa raíz es correcto:

**File**: `sprintmaster/logger.py`

**Function**: `banner()`

**Cambios Específicos**:
1. **ASCII Art Banner**: Reemplazar la línea `self._console.print("SprintMaster", style="bold cyan")` con un bloque multi-línea de arte ASCII (estilo bloque o slant). Usar gradiente de colores bold cyan/magenta con Rich markup.
   - Definir constante `BANNER_ART` con el arte ASCII
   - Iterar líneas aplicando estilo gradiente (cyan→magenta)

2. **Reemplazar emoji en warning()**: Cambiar `f"⚠️ Warning: {msg}"` por `f"[!] Warning: {msg}"` manteniendo style="yellow"

3. **Reemplazar emoji en error()**: Cambiar `f"❌ Error: {msg}"` por `f"[x] Error: {msg}"` manteniendo style="bold red"

---

**File**: `sprintmaster/output_formatter.py`

**Function**: `parse_and_validate()`

**Cambios Específicos**:
4. **Inyectar Logger**: Modificar `OutputFormatter.__init__()` para aceptar un parámetro opcional `logger: Logger | None = None` y almacenarlo como `self._logger`
5. **Enrutar warnings por logger**: Reemplazar las llamadas `print(f"Advertencia: ...", file=sys.stderr)` por `self._logger.warning(...)` cuando el logger esté disponible. Si no hay logger, mantener el fallback a print para backward compatibility.

---

**File**: `sprintmaster/cli.py`

**Function**: `main()`

**Cambios Específicos**:
6. **Reordenar spinner/write**: Mover `logger.stop_progress()` ANTES de `formatter.write(tickets, args)`:
   ```python
   logger.start_progress("Processing response...")
   tickets = formatter.parse_and_validate(raw_response)
   logger.stop_progress()          # ← mover aquí
   formatter.write(tickets, args)
   # logger.stop_progress()        # ← eliminar de aquí
   ```
7. **Pasar logger a OutputFormatter**: Cambiar `OutputFormatter()` a `OutputFormatter(logger=logger)` para habilitar el enrutamiento de warnings

## Testing Strategy

### Validation Approach

La estrategia de testing sigue un enfoque de dos fases: primero, generar counterexamples que demuestren los bugs en código sin corregir, luego verificar que la corrección funciona y preserva el comportamiento existente.

### Exploratory Bug Condition Checking

**Goal**: Generar counterexamples que demuestren los bugs ANTES de implementar la corrección. Confirmar o refutar el análisis de causa raíz.

**Test Plan**: Escribir tests que invoquen cada función afectada y capturen su output a stderr. Ejecutar en el código SIN corregir para observar los fallos.

**Test Cases**:
1. **Banner Test**: Invocar `logger.banner()` y verificar que el output tiene más de una línea (fallará en código sin corregir)
2. **Validation Warning Routing Test**: Parsear un ticket inválido y verificar que el warning pasa por `logger.warning()` (fallará en código sin corregir)
3. **Spinner Sequence Test**: Simular la secuencia main() y verificar que `stop_progress()` se llama antes de `write()` (fallará en código sin corregir)
4. **Emoji-Free Warning Test**: Invocar `logger.warning("test")` y verificar que no contiene emojis Unicode (fallará en código sin corregir)
5. **Emoji-Free Error Test**: Invocar `logger.error("test")` y verificar que no contiene emojis Unicode (fallará en código sin corregir)

**Expected Counterexamples**:
- Banner output es una sola línea sin caracteres de arte ASCII
- Warnings se emiten via print() sin estilo
- Spinner overlap visible en la captura de output
- Output contiene caracteres Unicode ⚠️ / ❌

### Fix Checking

**Goal**: Verificar que para todos los inputs donde la condición de bug se cumple, las funciones corregidas producen el comportamiento esperado.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixedFunction(input)
  ASSERT expectedBehavior(result)
  // Para Bug 1: banner output tiene múltiples líneas con arte ASCII
  // Para Bug 2: warning se enruta por logger.warning()
  // Para Bug 3: stop_progress() se invoca antes de write()
  // Para Bug 4-5: output NO contiene emojis, usa prefijos texto
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todos los inputs donde la condición de bug NO se cumple, las funciones corregidas producen el mismo resultado que las originales.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalFunction(input) = fixedFunction(input)
  // quiet mode suprime banner
  // tickets válidos no generan warnings
  // verbose metadata no cambia
  // non-TTY output sigue siendo plain text
  // stderr routing se mantiene
END FOR
```

**Testing Approach**: Property-based testing es recomendado para preservation checking porque:
- Genera automáticamente muchos casos de prueba en el dominio de inputs
- Detecta edge cases que tests manuales podrían omitir
- Provee garantías fuertes de que el comportamiento no cambió para inputs no-bug

**Test Plan**: Observar comportamiento en código SIN corregir primero para interacciones normales, luego escribir property-based tests capturando ese comportamiento.

**Test Cases**:
1. **Quiet Mode Preservation**: Verificar que `--quiet` sigue suprimiendo el banner en código corregido
2. **Valid Tickets Preservation**: Verificar que tickets válidos no generan warnings en código corregido
3. **Stderr Routing Preservation**: Verificar que warning/error siguen escribiendo a stderr
4. **Non-TTY Preservation**: Verificar que output piped sigue siendo plain text sin ANSI
5. **Verbose Mode Preservation**: Verificar que verbose metadata se muestra igual que antes
6. **First Spinner Preservation**: Verificar que el primer spinner "Generating tickets..." se detiene limpiamente

### Unit Tests

- Test `Logger.banner()` produce output multi-línea con al menos 5 líneas de arte ASCII
- Test `Logger.banner()` no produce output cuando `quiet=True`
- Test `Logger.warning("msg")` produce `"[!] Warning: msg"` sin emojis
- Test `Logger.error("msg")` produce `"[x] Error: msg"` sin emojis
- Test `OutputFormatter.parse_and_validate()` con ticket inválido invoca `logger.warning()`
- Test secuencia en `main()` donde `stop_progress()` precede a `write()`
- Test edge case: `OutputFormatter` sin logger inyectado usa fallback a print

### Property-Based Tests

- Generar mensajes aleatorios y verificar que `warning()` nunca contiene caracteres emoji (U+2600-U+27BF, U+1F600-U+1F64F, etc.)
- Generar mensajes aleatorios y verificar que `error()` nunca contiene caracteres emoji
- Generar configuraciones aleatorias de Logger (verbose/quiet combinaciones) y verificar que preservation se mantiene
- Generar listas de tickets (válidos e inválidos mezclados) y verificar que warnings se enrutan por logger

### Integration Tests

- Test flujo completo CLI con tickets inválidos: verificar que la salida final no tiene overlap de spinner y warnings están estilizados
- Test flujo CLI con `--quiet`: verificar que banner no aparece pero warnings sí
- Test flujo CLI con output piped (non-TTY): verificar plain text sin ANSI
- Test visual de banner en terminal real (manual): verificar gradiente y multi-línea
