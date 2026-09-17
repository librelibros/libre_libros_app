# Monitor público de disponibilidad

Actualización: 2026-09-17. Solicitado por el propietario como parte del despliegue gratuito.

Hermes ejecuta `scripts/libre_libros_healthcheck.py` cada cinco minutos (`*/5 * * * *`) en modo `--no-agent`, sin tokens LLM ni navegador. Job creado: `735bc23f4712` (`libre-libros-healthcheck`), script instalado en `/data/agents/hermes/scripts/libre_libros_healthcheck.py`. Entrega y fallos locales: no envía avisos a Telegram. Gateway activo comprobado. La prueba manual del script falló por timeout; DNS resolvió, una petición de control a example.com respondió 200, pero tanto `/` como `/healthz` de Render agotaron el plazo. Cron instalado no equivale a web disponible ni a despliegue actualizado.

`.github/workflows/keepalive.yml` conserva una comprobación independiente cada hora para evitar duplicar 288 jobs diarios de Actions. Consulta `https://libre-libros-app.onrender.com/healthz`. Requiere HTTP 200 y JSON `status=ok`. No usa secretos, no imprime cuerpos, no modifica datos ni reinicia/despliega ante fallos. Límite de petición: 90 segundos; job: tres minutos; ejecuciones serializadas. Ejecución manual disponible en Actions.

## Activación

- El workflow programado debe estar en la rama predeterminada (`main`), y Actions habilitado. Un commit en una rama de trabajo no activa el cron.
- Revisar ejecución manual y después una programada en Actions. Fallos quedan visibles allí; notificaciones por email dependen de las preferencias de GitHub, no se han configurado alertas externas.
- Es independiente de `deploy-to-render.yml`: este último utiliza secretos almacenados en GitHub (no es necesario descargarlos al entorno local), exige CI correcto, rama main y variable `ENABLE_RENDER_DEPLOY=true`, además de las protecciones del entorno production.

## Límites

Render Free suspende por inactividad tras 15 minutos sin tráfico y concede 750 horas por workspace/mes. Las peticiones pueden reducir el reposo por inactividad, pero no evitan cuotas, reinicios o suspensiones del proveedor. GitHub schedules son best-effort, pueden retrasarse o desactivarse (en repos públicos, por inactividad del repositorio). La frecuencia solicitada no es una frecuencia de ejecución garantizada. Hermes realiza 288 comprobaciones diarias sin LLM; depende de que el servidor y gateway estén activos. Actions conserva 24 comprobaciones diarias; revisar consumo/límites, especialmente en repositorios privados. No contratar capacidad adicional sin autorización.

Un healthcheck satisfactorio no prueba acceso a la BD, login, persistencia de materiales ni exportación PDF. La publicación exige comprobaciones funcionales separadas.

Referencias: https://render.com/docs/free y https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

## Evidencia local

YAML parseado y script validado con `bash -n`; contrato de `/healthz` contrastado con `app/main.py`. No se ha ejecutado aún este workflow en GitHub. `git ls-remote` confirmó acceso de lectura por SSH y main remoto en `69e3f5b`; no acredita permiso de push ni acceso a configuración de Actions. La última comprobación pública anterior agotó 90 segundos sin respuesta; no se certifica disponibilidad.
