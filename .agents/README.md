# Agentes de Libre Libros

Procedimientos documentales para preparar una demo **LOCAL** y un futuro piloto. Estos Markdown no configuran el runtime, no registran agentes ni acreditan skills cargadas. Leer este índice, [CONTRACTS.md](CONTRACTS.md) y [MEMORY.md](MEMORY.md) antes de asumir un rol.

## Contexto y límites comunes

- Dos repositorios: `libre_libros_app` (FastAPI y frontend) y `libre_libros_content` (libros Markdown). Identificar siempre el repositorio en cada ruta; la carpeta padre no implica un único repo Git.
- Objetivo futuro: 3–5 colegios de Primaria, 10–20 docentes. **Todavía no hay usuarios reales**; las pruebas con personas ficticias no validan adopción ni aprendizaje.
- Acceso previsto por invitación **sin exigir cuenta GitHub**. El proveedor de contenidos es un detalle técnico, no la identidad obligatoria del docente. Es un requisito, no una afirmación de implementación.
- No recopilar ni usar datos de alumnos, ni siquiera en comentarios, adjuntos, capturas o ejemplos. Datos de demo sintéticos. Propuestas de contenido revisadas antes de incorporarse al material compartido.
- Render/Supabase gratuitos son el objetivo de infraestructura, sin garantía de disponibilidad continua. No afirmar cuotas, configuración ni rendimiento vigentes sin verificarlos.
- Mandato global: implementar código, ejecutar pruebas/demo e iterar con autonomía delegada; **commits locales coordinados exclusivamente por el orquestador**. Permitidas lectura pública web, consulta de buenas prácticas y descarga de dependencias necesarias, registrando fuentes y versiones.
- **Sin push, deploy, PR remota, contratación, contactos con colegios ni modificación de producción**. Las consultas públicas no autorizan operaciones sobre servicios reales ni pruebas contra terceros.
- Toda escritura propia (código, artefactos, entornos, cachés y temporales) queda dentro de `libre_libros_app` o `libre_libros_content`. No escribir configuración global, alterar servicios ajenos ni leer/copiar secretos (`.env`, credenciales, tokens, `settings.local.json`). No reset, limpieza destructiva ni sobrescritura de trabajo ajeno.
- Los límites de una subtarea concreta no sustituyen este mandato global. Estas guías describen desarrollo real autorizado; ser Markdown no restringe el proyecto a documentación. Consultar la [memoria canónica](../MEMORY.md) y no pedir aprobaciones ya delegadas.

## Mapa de roles

| Perfil | Responsabilidad | Resultado habitual |
|---|---|---|
| [ORCHESTRATOR](ORCHESTRATOR.md) | Alcance, dependencias, ownership, commits y cierre local | Plan de ejecución y resumen local |
| [PROJECT-MANAGER](PROJECT-MANAGER.md) | Aceptación o rechazo final independiente del proyecto | `project-acceptance-report.md` |
| [PRODUCT-MANAGER](PRODUCT-MANAGER.md) | Necesidad docente y aceptación | `feature-spec.md` |
| [CODEBASE-ANALYST](CODEBASE-ANALYST.md) | Mapa verificable app/content | `codebase-context.md` |
| [UX-EXPERIENCE](UX-EXPERIENCE.md) | Flujos y accesibilidad | `ux-spec.md` |
| [TECHNICAL-PRODUCT-MANAGER](TECHNICAL-PRODUCT-MANAGER.md) | Tareas y contratos de integración | `technical-plan.md` |
| [DEVELOPER](DEVELOPER.md) | Una tarea autorizada y sus pruebas | `task-report-TASK-XXX.md` |
| [VALIDATOR](VALIDATOR.md) | QA independiente y consolidación de gates | `validation-report.md` |
| [UX-REFINEMENT](UX-REFINEMENT.md) | Revisión de evidencia y mejoras acotadas | `ux-refinement-report.md` |
| [SECURITY](SECURITY.md) | Privacidad, permisos y contenido no confiable | `security-report.md` |
| [OPERATIONS](OPERATIONS.md) | Preparación y recuperación local; límites gratuitos | `operations-report.md` |
| [SIMULATED-TEACHERS](SIMULATED-TEACHERS.md) | Heurísticas docentes y A/B **SIMULADOS** | `simulated-teachers-report.md` |
| [COMMUNICATION](COMMUNICATION.md) | Textos claros y borradores no enviados | `communication-report.md` |

## Uso

Encargo mínimo: objetivo, alcance de lectura/escritura, repos implicados, exclusiones y aceptación. Reutilizar la autonomía ya delegada. Ejemplo: «Implementa e itera la demo local para encontrar un libro, adaptar y proponer a revisión; ejecuta regresiones y solicita el gate final independiente antes del cierre. El orquestador coordina los commits locales; sin push ni deploy».

El [orquestador](ORCHESTRATOR.md) asigna únicamente fases relevantes y justifica las no aplicables. No presupone herramientas de subagentes, navegador o grabación: si faltan, declara la limitación y trabaja secuencialmente o entrega un plan sin ejecutar.

## Artefactos y fuentes únicas

- Una especificación por entrega usando [templates/feature-spec-template.md](templates/feature-spec-template.md); el archivo homónimo en raíz es solo un enlace de compatibilidad.
- Para futuras ejecuciones autorizadas: `libre_libros_app/generated/<run-id>/` con un archivo por propietario; evidencia en `libre_libros_app/test_plan/<run-id>/<rol>/`. Son convenciones, no carpetas creadas por este encargo.
- No duplicar especificaciones entre `generated/` y `specs/`: si ya existen specs persistentes autorizadas, elegir una canónica y enlazarla. `MEMORY.md` guarda decisiones y enlaces, no copias de informes.
- Las reglas de severidad, evidencia y aceptación están únicamente en [CONTRACTS.md](CONTRACTS.md). Los gates operativos de aprobación están en [VALIDATOR.md](VALIDATOR.md).
