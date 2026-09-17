# CI y despliegue del piloto

Cambios locales preparados el 2026-09-16. **No se ha desplegado, hecho push, contratado servicios ni cambiado secretos o ajustes remotos.** No se activa el modo invitación: requiere validación funcional y autorización separadas.

## Flujo propuesto

- PR: `ci.yml` ejecuta build de editor, tests y build Docker sin publicar.
- Push a cualquier rama / dispatch: `deploy-to-render.yml` llama al mismo workflow CI, sin `secrets: inherit`. Evita duplicar la definición de pruebas. Un push con PR abierto puede tener dos ejecuciones CI; ninguna PR recibe secretos de despliegue.
- Deploy requiere CI completa verde, rama `main`, variable **de repositorio** `ENABLE_RENDER_DEPLOY=true` y entorno GitHub `production`. La variable es un opt-in deliberado y queda sin configurar en esta tarea. Configurar protecciones/aprobación del entorno antes de habilitarla; declarar `environment` en YAML no crea por sí solo una aprobación obligatoria.
- Permiso GitHub: `contents: read`. Los checkouts no persisten credenciales. La app y el repositorio público de contenido se descargan dentro de `$GITHUB_WORKSPACE` como carpetas hermanas: `libre_libros_app/` y `libre_libros_content/`. Desde el directorio de la app, el fixture queda en `../libre_libros_content`, sin intentar un checkout fuera del workspace.
- El contenido se obtiene de `librelibros/libre_libros_content`, rama `main`, solo para fixtures locales. No se usa PAT ni token de producción. Al ser una referencia móvil, sus cambios pueden afectar a los tests: para reproducibilidad estricta, revisar y fijar un SHA de contenido en una PR posterior.
- `python -m pytest tests` limita la recolección a la suite, evitando recolectar scripts de diagnóstico/journeys. `conftest.py` desactiva dotenv y aísla SQLite y repositorios temporales. Los tests de arranque existentes prueban `LIBRE_LIBROS_ENVIRONMENT=production` con clave sintética válida y con clave ausente. No añadir credenciales reales a CI.

## Docker y assets

Docker usa dos etapas: Node 22 (`node:22-bookworm-slim`) instala el lockfile con `npm ci` y construye `editor-rich.js`; Python conserva `python:3.12.13-slim`. Node 22 coincide con el major local observado y supera el requisito Node >=20 de `marked`; CI usa también 22. Los parches del major pueden actualizarse: no se afirma reproducibilidad por digest.

El bundle generado se copia **después** de `COPY app`, por lo que prevalece sobre el bundle versionado. La imagen final no contiene Node ni `node_modules`. Se copian entradas explícitas, incluido el entrypoint local existente; no se usa `COPY . .`. `.dockerignore` excluye dotenv, datos, configuración privada de agentes, entornos y cachés. El CMD usa `exec` para señales de Uvicorn. CI construye la imagen, pero no la publica ni arranca servicios de producción.

Pendientes fuera de esta mejora mínima: usuario no root compatible con permisos locales, lock Python transitivo/digests, acciones fijadas a SHA y escaneo de dependencias. El build Docker y un smoke de la imagen todavía deben validarse; los tests de lifespan prueban Python, no la imagen final.

## Fuente única del deploy y pasos previos a habilitarlo

`render.yaml` declara `autoDeploy: false`. **Esto no desactiva el autodeploy de un servicio ya creado manualmente.** Antes de habilitar Actions, el propietario debe autorizar y verificar en Render que los autodeploys están desactivados. No habilitar dos disparadores. Revisar además que el servicio apunta al repositorio/rama correctos y que su healthcheck es `/healthz`.

Blueprint y sincronización Actions añaden `LIBRE_LIBROS_ENVIRONMENT=production`: ese es el nombre con prefijo que lee `Settings`; un `ENVIRONMENT` sin prefijo no activa la validación. Se conserva el modo OAuth GitHub existente y ahora su client ID/secret son obligatorios antes de sincronizar. No se añade `INVITATION_ONLY` ni se altera la configuración con valores privados.

Deploys Actions serializados, sin cancelar una sincronización ya iniciada. El POST pide el SHA probado, no el último commit de la rama por defecto. Solo se admite HTTP 201/202 y un ID válido, se espera `live` con el mismo SHA hasta un límite de 15 minutos y se falla ante error, estado inesperado o timeout. Un 202 sin ID también falla: revisar el Dashboard, **no repetir el POST automáticamente**, pues puede estar ya encolado. Se registran ID/SHA y mensajes limitados, no cuerpos de respuesta ni valores de secretos. Finalmente se comprueba HTTP 200 y JSON de `/healthz`.

Limitaciones conocidas:

- Un fallo del monitor posterior no hace rollback automático; el deploy podría estar live. Revisar antes de volver a desplegar.
- La comprobación pública no acredita DB, esquema, catálogo ni login OAuth. El paso `live` verifica el SHA vía Render, no mediante el cuerpo de `/healthz`.
- Los PUT de entorno siguen siendo individuales, no transaccionales. Opcionales ausentes se conservan en Render; eliminación/rotación requiere un procedimiento aprobado.
- La cola de Actions puede reemplazar ejecuciones pendientes; serialización no garantiza desplegar cada push. `cancel-in-progress: false` protege la ejecución activa.
- Ni el Blueprint ni esta PR sustituyen la revisión de backups, migraciones, conexión TLS/pooler y seguridad pendiente en `docs/audit/deployment.md`.
- `scripts/deploy_render.sh` queda fuera del ownership y conserva los problemas descritos en la auditoría: **no usarlo como alternativa** al workflow revisado.

## Monitor gratuito: observar, no mantener despierto

El antiguo `keepalive.yml` ahora ejecuta una sola comprobación en el minuto 23 de cada hora (UTC por defecto), máximo 90 segundos, job de 3 minutos. Permite que Render duerma; puede provocar un arranque frío. Solo acepta HTTP 200 y JSON con `status=ok`, no publica el cuerpo de fallos y marca error visible en Actions. No consulta Supabase ni inicia sesión. Configurar notificaciones de fallos en GitHub: no se ha añadido un canal externo.

GitHub cron es best-effort: puede retrasarse, descartarse o desactivarse por inactividad del repositorio público. Un resultado verde no garantiza continuidad y uno rojo no identifica por sí solo la causa. No añadir pings cada minuto para eludir inactividad o cuotas.

## Gratis, con expectativas realistas

- **Render Free:** duerme tras 15 minutos sin tráfico; despertar alrededor de un minuto según documentación, sin máximo garantizado. 750 horas compartidas por workspace/mes, disco efímero y cuotas de transferencia/build. No usar SQLite para datos duraderos. Puede reiniciarse/suspenderse; un monitor no evita esas limitaciones.
- **Supabase Free:** posible pausa por baja actividad durante 7 días; 500 MB de DB por proyecto, límites de egress/almacenamiento y sin backups automáticos incluidos ni SLA de uptime. `/healthz` de Render no mantiene ni valida Supabase. Definir exportaciones cifradas externas y probar restauración antes de datos reales.
- **Alternativa sin SLA:** publicar una edición estática de solo lectura de los libros en Render Static Sites permite consultar material sin arrancar FastAPI. También tiene cuotas de transferencia/build y requiere otro pipeline; no ofrece edición, comentarios ni sesiones. No se ha creado ese servicio. Para edición continua con latencia acotada, este stack gratuito no permite prometer el requisito; cambiar a otra oferta Free sin estudiar sus límites no lo resuelve.

Fuentes oficiales (consulta 2026-09-16):

- https://render.com/docs/free
- https://supabase.com/pricing
- https://supabase.com/docs/guides/platform/going-into-prod
- https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- https://api-docs.render.com/reference/create-deploy
- https://api-docs.render.com/reference/retrieve-deploy

## Validación local y bloqueos

- PyYAML 6.0.3 de `.venv`: parseo de los workflows y Blueprint; se usa `BaseLoader` para conservar `on` como clave (SafeLoader YAML 1.1 puede interpretarla como booleano).
- `bash -n` sobre bloques `run`; aserciones de triggers, dependencia `needs: ci`, ausencia de herencia de secretos, `autoDeploy: false` y variable de entorno producción: correctos en la validación local.
- `tests/test_config.py` + `tests/test_startup.py`: **7 passed**, con dotenv deshabilitado y bytecode desactivado. Python local 3.12.3; CI/imagen especifican 3.12.13.
- Un intento de pytest sin limitar directorio agotó 120 segundos sin resultado; no cuenta como aprobado. El workflow se corrigió para recolectar exclusivamente `tests/`.
- Suite `pytest tests -v -x`: **110 tests recogidos, 8 passed y 1 failed antes de detenerse**. Falla `tests/test_app.py::test_book_detail_rewrites_asset_urls_and_serves_assets`: esperaba `image/svg+xml`, recibió `application/octet-stream`. Trabajo concurrente de backend/seguridad debe resolver el contrato; no se cambia test ni código desde este ownership. **La puerta CI bloqueará deploy mientras falle.** No se afirma que sea el único fallo.
- No disponibles localmente actionlint/act. PyYAML comprueba sintaxis, no toda la semántica del motor Actions. Debe observarse una ejecución real de CI sin habilitar deploy.
- No ejecutados localmente `npm ci`, regeneración del bundle o build Docker para no sobrescribir assets/dependencias de otro ownership ni consumir recursos innecesarios. Están declarados como puertas CI, pero no se presentan como ya aprobados.
- Ningún commit, push, despliegue, acceso API autenticado, modificación de secrets/servicios host ni activación del piloto realizada.
