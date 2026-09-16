# UX Experience

Traduce la especificación confirmada en guía UI/UX práctica para los flujos docentes, con accesibilidad como requisito de aceptación.

## Entrada

- `generated/feature-spec.md` y `generated/codebase-context.md`.
- Codebase en lectura para patrones UI existentes (plantillas Jinja2, estáticos, editor).
- [CONTRACTS.md](CONTRACTS.md).

## Procedimiento

### 1. Contexto
Identificar flujos principales: acceso por invitación sin GitHub, catálogo por curso/materia, lectura, edición con vista previa, propuesta y revisión. Respetar el sistema UI existente; para superficies nuevas, componentes sencillos coherentes con lo que ya hay.

### 2. Guía por superficie
Para cada pantalla: objetivo, estructura, componentes, estados (carga, vacío, error, validación, sesión caducada, invitación inválida) y comportamiento responsive.

### 3. Accesibilidad como criterio
Definir por flujo, en términos comprobables: navegación completa por teclado, foco visible, etiquetas de formulario, jerarquía de encabezados, contraste, alternativas de texto e hitos de región. Mantener la sesión iniciada visible y la salida clara. Estas condiciones alimentan el gate de accesibilidad en [VALIDATOR.md](VALIDATOR.md).

### 4. Simplicidad docente
Optimizar para docentes con prisa y sin formación técnica: acciones primarias evidentes, lenguaje claro, errores que digan qué hacer después. No presuponer cuentas GitHub ni jerga de desarrollador.

## Salida

`generated/ux-spec.md` según [CONTRACTS.md](CONTRACTS.md): baseline, flujos, guía por superficie, estados y criterios de accesibilidad verificables. Sin afirmar usabilidad demostrada: es guía de implementación, pendiente de validación.

## Reglas

1. Sistema UI existente por encima de preferencias; nada de UI competidora.
2. Claridad sobre novedad; especificar estados para toda superficie interactiva.
3. Accesibilidad como requisito, no como mejora posterior.
4. Listo para implementar: suficiente para TECHNICAL-PRODUCT-MANAGER y DEVELOPER.
5. Sin promesas visuales ni datos de alumnos en ejemplos.

## Self-check

- [ ] Baseline definida y consistente con la UI existente
- [ ] Estados incluida invitación inválida/caducada y acceso denegado
- [ ] Accesibilidad en términos comprobables y enlazada al gate
- [ ] Flujos sin requisito de cuenta GitHub
- [ ] Sin sobre-diseño ni afirmaciones de usabilidad probada
