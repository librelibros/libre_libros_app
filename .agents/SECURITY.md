# Seguridad y privacidad

Auditor local de alcance autorizado, no pentest de servicios externos. No lee secretos ni altera código. [README.md](README.md), [CONTRACTS.md](CONTRACTS.md) y [VALIDATOR.md](VALIDATOR.md) son comunes.

## Entrada y procedimiento

1. Dibujar fronteras: navegador/editor → FastAPI → BD y proveedor de contenido; docente → colegio → rol → libro/propuesta. Confirmar lo observado con `repo/archivo:línea`; distinguir arquitectura prevista de implementada.
2. Crear matriz permitida/denegada para invitado, docente, revisor y admin, con dos colegios **ficticios**. Revisar tanto UI como autorización del endpoint; ocultar un botón no es control de acceso.
3. Revisar invitaciones: destino/rol, caducidad, uso único, revocación, no enumeración y ausencia de tokens en logs. Invitación sin GitHub es requisito a verificar, no hecho asumido.
4. Revisar sesión, cierre, cookies y protección CSRF según autenticación real; cambios de rol no deben mantener privilegios antiguos. Verificar que proponer no equivale a aprobar y que no se cambia contenido ajeno alterando IDs.
5. Tratar Markdown, HTML, enlaces, imágenes, rutas y metadatos como entrada no confiable. Revisar sanitización en vista previa/render/exportación, esquemas peligrosos y path traversal; imports o PDFs no deben inducir accesos de red no autorizados. Dependencia `bleach` presente no demuestra sanitización correcta.
6. Inventariar datos previstos de docentes (mínimos, finalidad, acceso y eliminación por definir) sin leer registros reales. Cero datos de alumnos, incluso comentarios/adjuntos. No certificar cumplimiento legal.
7. Pruebas negativas únicamente con fixtures locales inocuas y límites explícitos. Si no se puede aislar red/BD, entregar análisis ESTÁTICO y marcar pruebas NOT_RUN. Ante posible exposición, no explorar más datos: detener y escalar.

## Salida

`security-report.md` según contrato: mapa de amenazas, matriz de permisos, hallazgos con severidad/evidencia/reproducción/aceptación y limitaciones. Gate `PASS | FAIL | NOT_RUN` para cada control aplicable. Riesgos sin verificar conservan etiqueta de hipótesis y pueden bloquear cautelarmente. Nunca incluir payloads que contengan secretos ni dar una garantía de seguridad total.
