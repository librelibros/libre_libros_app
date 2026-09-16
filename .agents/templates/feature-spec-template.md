# Especificación: {{nombre}}

## Identidad y autorización

- ID / slug / fecha: {{valores reales}}
- Estado: BORRADOR | CONFIRMADA | EN_CURSO | VALIDADA_LOCAL | BLOQUEADA
- Responsable / referencia de confirmación: {{persona o mensaje; pendiente si no existe}}
- Objetivo docente y resultado observable: {{sin afirmar demanda real}}
- Alcance de lectura/escritura por repo: {{rutas autorizadas}}
- Autorización: código, pruebas, iteraciones y commits locales por el orquestador; lectura pública web/buenas prácticas y dependencias necesarias. Referenciar autonomía ya delegada, sin aprobación redundante.
- Restricciones: sin push, deploy, contactos con colegios, contratación ni producción; sin datos de alumnos. Escrituras, entornos, cachés y temporales solo dentro de los dos repos.

## Contexto y alcance

- Piloto previsto: 3–5 colegios de Primaria, 10–20 docentes; no usuarios reales todavía.
- Incluido / excluido: {{capacidades y límites}}
- Estado actual comprobado / objetivo / hipótesis: {{separados, con fuentes archivo:línea}}
- Decisiones anteriores: {{enlaces a MEMORY o spec canónica, sin duplicarla}}
- Preguntas bloqueantes y decisiones confirmadas: {{pregunta, responsable, respuesta o pendiente}}

## Historias y aceptación

| Historia / rol sintético | Precondición | Acción | Resultado esperado | AC-ID | Prueba prevista |
|---|---|---|---|---|---|
| {{US-01}} | {{estado local}} | {{acción}} | {{observable}} | AC-01 | {{comando/pasos, sin afirmar ejecución}} |

Considerar en el alcance relevante: invitación sin GitHub, catálogo por curso/materia, lectura, edición/vista previa, propuesta pendiente, revisión autorizada y rechazo. Si una capacidad falta, registrarla como brecha; no presentarla como existente.

## Estados, datos y permisos

- Carga, vacío, error, sesión caducada, invitación inválida/usada/caducada, acceso denegado y recuperación: {{comportamiento esperado}}
- Matriz rol × colegio × leer/proponer/revisar/administrar: {{permitido/denegado y pruebas negativas}}
- App frente a content: {{qué persiste dónde, contrato Markdown, compatibilidad}}
- Datos de demo sintéticos y mínimos; ningún dato de alumnos. Contenido no confiable y revisión antes de incorporar propuestas.
- Infraestructura gratuita: {{estado degradado esperado, sin garantía always-on}}

## UX, riesgos y gates

- UI existente a conservar; flujos y criterios accesibles: {{enlace a ux-spec}}
- Riesgos, severidad provisional y mitigación: {{lista con owner}}
- QA/UX/seguridad/operaciones: {{aplica y pruebas, o N/A razonado; ver VALIDATOR}}
- A/B o personas ficticias, si se usan: **SIMULADOS**, hipótesis pendientes de futura validación humana autorizada.
- Condición de cierre local y reversión propuesta: {{aceptación verificable}}
- Gate final independiente: {{informe de PROJECT-MANAGER, versión y ACCEPTED_LOCAL / REJECTED / BLOCKED; aprobar un hito o una simulación no acepta el proyecto}}

## Seguimiento

- Resultado por AC y evidencia: {{enlace al informe según CONTRACTS; pendiente hasta ejecutar}}
- Cambios de alcance y motivo: {{fecha/decisión}}
- Riesgos residuales y próximo paso: {{sin promesas de perfección}}
