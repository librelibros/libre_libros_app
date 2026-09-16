# Contratos comunes de trabajo y resultados

Aplican a todos los perfiles junto con los límites del [README](README.md). Un resultado documental no equivale a validación de la app.

## Encargo mínimo antes de escribir

`ID · objetivo · entradas · repo/rutas de lectura · repo/rutas exclusivas de escritura · exclusiones · dependencias · aceptación AC-XX · pruebas permitidas · ruta de salida · propietario · revisor`.

Sin permisos concretos, entregar propuesta en el canal de respuesta, no crear rutas. Cada salida y cada recurso mutable (archivo, fixture, BD local, puerto, sesión de navegador) debe tener propietario. Los revisores leen una versión estabilizada; no corrigen código ni editan informes ajenos.

## Contrato de informe (único formato común)

1. **Cabecera:** ID de tarea/ejecución, rol, fecha real, alcance, repos, versión local revisada (hash si existe; de lo contrario estado y archivos), estado `COMPLETED | PARTIAL | BLOCKED`.
2. **Hechos y cambios:** archivos leídos/modificados, decisiones, supuestos separados, discrepancias y exclusiones. `COMPLETED` solo si se cumple la aceptación asignada.
3. **Aceptación:** tabla `AC-ID | esperado | observado | PASS / FAIL / NOT_RUN / N/A | evidencia`. `N/A` exige justificación y acuerdo de alcance; no sustituye una prueba pendiente.
4. **Ejecuciones:** comando exacto o pasos, directorio, entorno local/fixtures sintéticos, fecha, salida relevante, código de salida cuando exista y evidencia. Separar `PLANIFICADO`, `EJECUTADO` y `SIMULADO`.
5. **Hallazgos:** formato de abajo; indicar explícitamente si no se encontraron hallazgos dentro del alcance revisado, sin extender la conclusión a todo el producto.
6. **Cierre:** bloqueos, riesgos residuales, siguiente acción, propietario y propuestas para MEMORY (sin editarla en paralelo).

## Hallazgo accionable

`ID | severidad | tipo de evidencia | repo/archivo:línea(s) | problema e impacto | reproducción | esperado/observado | corrección propuesta | aceptación de corrección | owner | estado`.

- Citar líneas vigentes, no inventadas. Para evidencia visual, enlazar captura/log y paso; si no se localizó el código causal, decir «ubicación de código pendiente» y citar `run-log.md:línea` cuando exista.
- Reproducción: precondiciones, rol sintético, pasos o comando exacto y resultado observable. Revisión estática: indicar «no ejecutado» y cómo confirmar. Hipótesis sin reproducción no se convierte en defecto confirmado.
- Aceptación de corrección: prueba concreta de regresión y condición de éxito, no «mejorar seguridad».

| Severidad | Criterio de impacto | Tratamiento |
|---|---|---|
| CRITICAL | Acceso indebido entre colegios/roles, exposición sensible, pérdida de datos o ejecución de contenido no confiable con impacto grave | Bloquea; detener el flujo afectado y escalar |
| MAJOR | Flujo esencial roto, requisito de revisión/invitación incumplido o barrera de accesibilidad que impide la tarea | Bloquea; corregir y repetir prueba |
| MINOR | Fricción o inconsistencia con alternativa utilizable, sin incumplimiento esencial | Registrar owner y prioridad; no bloquea por sí sola |
| INFO | Pregunta, oportunidad o hipótesis sin defecto acreditado | Investigar; no contar como fallo confirmado |

La severidad depende del impacto, no de preferencias de estilo. Una sospecha de alto impacto puede bloquear cautelarmente hasta aclararse, manteniendo su etiqueta de hipótesis.

## Integridad de evidencia

- **ESTÁTICA:** documentos/código inspeccionados; no prueba ejecución.
- **EJECUTADA LOCAL:** salida o flujo realmente observado con datos sintéticos; no es investigación con docentes.
- **SIMULADA:** razonamiento/personas/A/B ficticios; nunca evidencia humana ni métricas de uso real.
- **PENDIENTE:** no comprobado, herramienta ausente o entorno no autorizado. No marcar PASS por ausencia de errores observados.
- Capturas, videos, logs y habilidades usadas solo se citan si existen y se han revisado. No deducir mirada, satisfacción o vacilación humana de una grabación automatizada.
- No guardar contraseñas, cookies, cabeceras de autorización, tokens de invitación, emails personales o datos de alumnos. Usar alias sintéticos; redactar evidencia antes de persistirla. Los flujos de prueba usan datos y servicios locales aislados de producción. La lectura pública web y obtención de dependencias están permitidas por separado: registrar fuentes/versiones, sin enviar información privada; escrituras y cachés solo dentro de los dos repos.
- Toda modificación posterior invalida la evidencia afectada; repetir los checks correspondientes sobre la versión final. Una excepción documentada no convierte FAIL/NOT_RUN en PASS.
