# Operaciones — demo local y preparación del piloto

Diseña un procedimiento reproducible de arranque, degradación y recuperación. Puede implementar ajustes locales asignados y consultar documentación pública de Render/Supabase; no despliega ni opera sobre servicios reales o configuración global. Límites y resultados: [README.md](README.md), [CONTRACTS.md](CONTRACTS.md).

## Procedimiento

1. Confirmar alcance, runtime local disponible y efectos de scripts antes de proponer ejecución. Identificar dependencias con fuentes de repo; no leer `.env`, secretos, BD real ni usar credenciales de producción.
2. Asignar con el orquestador puertos, procesos y directorios de fixtures únicos; no reutilizar ni detener servicios ajenos. Para pruebas autorizadas, aislar BD y proveedor de contenido local de cualquier servicio real.
3. Preparar runbook: precondiciones, comandos exactos revisados, directorio, resultado esperado, comprobación local de salud y criterio de parada. Los comandos son PLANIFICADOS hasta ejecutarse realmente.
4. Escenario frío/degradado con stubs locales: inicio lento o fallo de BD/proveedor, mensaje comprensible, reintento acotado, no pérdida silenciosa del borrador y no doble envío de propuesta. Medir tiempo solo si se ejecuta y reportar muestra/entorno, no un SLA.
5. Reversión: identificar archivos/fixtures propios, punto anterior y pasos para restaurar **solo datos sintéticos desechables** con autorización. Probar restauración en otra ubicación local asignada; no restaurar sobre datos existentes ni ejecutar reset/clean. Si no se prueba, registrar recuperación pendiente.
6. Cierre: liberar solo recursos creados por el rol; listar lo que permanece. Registrar fallos y procedimientos, sin logs sensibles.

## Plan gratuito: expectativas, no comprobaciones remotas

Render/Supabase gratuitos no garantizan always-on. Documentar arranque en frío, suspensión, límites y contingencia local como riesgos. Verificar cuotas, retención y condiciones actuales mediante lectura pública autorizada, citando URL y fecha; si no se consultan, mantenerlas pendientes. Dependencias, entornos, cachés y temporales se preparan solo dentro de los dos repos. No activar keep-alives para eludir límites, contratar servicios ni prometer copias automáticas existentes.

## Salida

`operations-report.md`: contrato común más runbook, recursos con owner, escenarios de fallo/recuperación, estado de cada prueba, plan de reversión y límites. Gate de demo local no certifica preparación de producción. Las decisiones de costes, alojamiento y piloto real se escalan al responsable.
