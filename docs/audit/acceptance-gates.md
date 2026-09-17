# Criterios de validación por Project Manager

Fecha: 2026-09-16. Documento de criterios; **no es una aprobación**.

## Principio
El mandato sigue siendo preparar un piloto robusto y reducir fricción. Los hitos técnicos facilitan integrar cambios pequeños; aprobar un hito no aprueba el piloto. El PM debe poder rechazar la entrega y enumerar bloqueantes. No se repetirá una evaluación solo para obtener un dictamen favorable.

## Niveles de decisión
- **Hito técnico validado:** corrección concreta con prueba ejecutada y revisión independiente del diff. No permite despliegue.
- **Demo local validada:** recorrido docente completo con datos aislados, pruebas backend y navegador ejecutadas, limitaciones documentadas.
- **Candidato a piloto:** sin bloqueantes de permisos, pérdida silenciosa de contenido ni fallos de acceso/importación/exportación en el subconjunto declarado. Requiere aprobación del propietario antes de publicar.
- **Utilidad validada con docentes:** solo tras observación de personas reales; no puede concederla una simulación de agentes.

## Matriz mínima de aceptación
| Área | Evidencia exigida | Rechazo |
|---|---|---|
| Invitación | Alta de docente sin GitHub, token de uso único, caducidad/revocación y cuenta existente protegida | Alta abierta o suplantación |
| Catálogo | Encontrar material por etapa/materia con lenguaje docente | Acciones Git imprescindibles para tarea básica |
| Editor | Abrir sin cambios conserva original; editar conserva estructura soportada; recuperación ante error | Pérdida silenciosa o abandono sin aviso |
| Importación | Formatos explícitos, confirmación antes de sustituir, errores comprensibles | Afirmar soporte DOCX/PDF sin implementar/probar |
| PDF | Archivo abierto y revisado: acentos, tablas soportadas, imágenes, saltos y contenido completo | Exportado ilegible, truncado o distinto sin aviso |
| Colaboración | Dos usuarios distintos, propuesta y revisión autorizada; conflicto recuperable | Sobrescritura ajena o publicación no revisada |
| Seguridad | Revisión defensiva y regresiones aisladas de autorización/confinamiento/saneamiento | Cualquier P1 aplicable abierto |
| Accesibilidad | Teclado, foco, nombres accesibles, errores y responsive comprobados | Tarea esencial inaccesible |
| Operación | Arranque reproducible y CI revisado, backups/restauración propuestos, límites gratis | Promesa always-on sin infraestructura que la respalde |
| Trazabilidad | Hallazgo → cambio → prueba → resultado → pendiente | Tests/capturas/feedback inventados |

## Hito inicial: confinamiento de recursos (B01)
- Revisión del cambio de validación de rutas y eliminación del fallback mutable.
- Prueba aislada con recursos válidos del libro; lectura normal sigue funcionando.
- Rechazo de recursos fuera del ámbito permitido y ausencia de lectura de archivos externos.
- Rama inexistente no devuelve contenido del checkout actual.
- Contrato equivalente para recursos usados en PDF.
- Tests ejecutados y códigos de salida registrados por nombre; ningún ensayo sobre producción.
- Si la suite completa aún no puede ejecutarse, el hito puede tener evidencia parcial pero la demo/piloto sigue bloqueada.

## Formato del dictamen PM
1. Alcance y commit/diff revisado.
2. Evidencias ejecutadas frente a inspección o simulación.
3. Aceptado/rechazado por criterio, con justificación.
4. Bloqueantes y mejoras no bloqueantes separados.
5. Siguiente iteración concreta y responsable.
6. Límite: no push, no deploy, no comunicación real sin autorización posterior.
