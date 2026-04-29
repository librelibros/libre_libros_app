# Resoluciones en producción

Procedimiento estándar para diagnosticar y arreglar bugs detectados en `https://libre-libros-app.onrender.com/` (o el host de prod que sea). Aplica para incidencias funcionales, de auth, de configuración o de despliegue. **No** aplica para incidentes de datos, GDPR o caídas de Supabase — esos requieren su propio runbook.

## Cuándo aplicarlo

- El usuario o el oncall reporta un comportamiento incorrecto en la URL pública.
- El deploy salió verde en GitHub Actions pero el comportamiento real en Render no es el esperado (drift entre código y plataforma).
- Una env var nueva no se aplicó (servicio Render creado a mano, no por Blueprint).

Si el síntoma es un 5xx o el `/healthz` falla → primero estabilizar (rollback en Render Dashboard → Deploys → Rollback) y luego este flujo.

## El flujo, paso a paso

### 1. Reproducir el bug en live, sin el navegador

Captura el síntoma con `curl` para que tengas un registro objetivo y reproducible:

```bash
HOST=https://libre-libros-app.onrender.com
curl -fsS $HOST/healthz
curl -sS -o /dev/null -w 'HTTP %{http_code} -> %{redirect_url}\n' $HOST/ -L --max-redirs 0
curl -fsS $HOST/login   | grep -E 'site-footer|github|input type='
curl -fsS $HOST/register | head -80
```

Anota: HTTP code, headers relevantes, fragmentos de HTML que contradicen lo esperado.

### 2. Diagnosticar capa por capa

Tres capas posibles, en orden de coste de arreglo:

1. **Código** — la lógica del router/template no cubre el caso. Arreglo local + smoke test + push.
2. **Configuración del workflow** — un secret no se está sincronizando, o un flag de modo no se está hardcodeando. Editar `.github/workflows/deploy-to-render.yml`.
3. **Estado de Render** — el servicio fue creado a mano y arrastra env vars antiguas. Forzar el upsert desde el workflow (más fiable que tocar Render Dashboard a mano).

Lectura crítica: muchas veces el bug no es de código, es que el `render.yaml` declara una env var con `value:` pero el servicio fue creado antes de que ese valor existiera, así que no se aplica nunca. La regla práctica:

> Si una env var es **modo de operación** (no es secret y debe ser estable), hardcodéala en el workflow como `upsert "KEY" "valor"` para que cada deploy la reaplique. Así el render.yaml es documentación, pero el workflow es la fuente de verdad.

### 3. Arreglar localmente

```bash
cd libre_libros_app
# código
$EDITOR app/routers/...
# y/o workflow
$EDITOR .github/workflows/deploy-to-render.yml
```

### 4. Smoke test reproduciendo el escenario de producción

Construye y arranca el contenedor con las MISMAS env vars que tendrá producción tras el fix. Verifica el escenario que rompía Y los escenarios adyacentes para no romper otros caminos.

```bash
docker build -t lll-fix .

# Escenario producción objetivo (external auth + OAuth configurado):
docker run --rm -d --name llv \
  -p 18091:8000 \
  -e LIBRE_LIBROS_DATABASE_URL='sqlite:////tmp/x.db' \
  -e LIBRE_LIBROS_EXTERNAL_AUTH_ONLY=true \
  -e LIBRE_LIBROS_GITHUB_OAUTH_ENABLED=true \
  -e LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_ID=fake \
  -e LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_SECRET=fake \
  lll-fix
sleep 5
curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}\n' http://localhost:18091/register
docker stop llv
```

Comprueba al menos:
- El path bug-on-prod (sin OAuth aún): `LIBRE_LIBROS_EXTERNAL_AUTH_ONLY=true` sin client id/secret.
- El path final (con OAuth): los 4 vars OAuth presentes.
- El path dev: ninguna env var de auth — comportamiento legacy.

### 5. Validar el resto con la skill `/check-deploy`

```bash
python scripts/check_deploy.py
```

Revisa que: env local OK, Supabase REST OK, cliente Python OK, Postgres OK (si exportas la URL), y los secrets de GitHub si `gh` está autenticado.

### 6. Commit y push

Usa un mensaje que diga **qué se rompía y dónde**. El "por qué" lo dirá el código y la doc.

```bash
git add app/ docs/ .github/ render.yaml
git commit -m "fix(auth): /register redirige a OAuth externo cuando hay provider; force-apply external_auth_only desde el workflow"
git push origin main
```

Push dispara el workflow → workflow PUTea las env vars en Render → workflow lanza deploy → Render rebuildea.

### 7. Verificar live

Espera ~3-5 min al rebuild y reproduce el `curl` del paso 1. Compara HTTP codes y fragmentos. Solo cierras la incidencia cuando el curl post-fix demuestra el comportamiento esperado.

```bash
HOST=https://libre-libros-app.onrender.com
curl -sS -o /dev/null -w 'HTTP %{http_code} -> %{redirect_url}\n' $HOST/register
curl -fsS $HOST/login | grep -E 'site-footer|github|formulario'
```

Si después de 10 min el live no refleja el cambio:
- `gh run list --workflow="Deploy to Render" -L 3` → ¿el último run terminó verde?
- Si verde, abrir Render Dashboard → Logs del último deploy. ¿La env var nueva sale en `Building` con el valor esperado?
- Si la env var no aparece, el step `Sync env vars to Render` no la cubrió → volver a paso 2.

### 8. Cerrar

- Si la fix tocó env vars: añade el caso a la tabla "Modos de fallo conocidos" de [deploy-render-supabase.md](deploy-render-supabase.md).
- Si la fix tocó código de auth/UI: añade un test mínimo en `tests/` o un smoke test reproducible en este doc.

## Anti-patrones

- ❌ **Editar env vars en Render Dashboard a mano**. El siguiente deploy puede sobrescribirlas (si el workflow las upsertaa) o, peor, mantenerlas indefinidamente y crear drift entre prod y código.
- ❌ **Pushear sin smoke test local**. Si el escenario de prod tiene flags raros, reprodúcelo en Docker antes — un build de Render gasta 3-5 min y un fail allí es ciclo lento.
- ❌ **Asumir que `render.yaml` se aplica**. Solo se aplica para servicios creados por Blueprint. Para servicios manuales, lo único que llega es lo que el workflow upsertea.
- ❌ **Confundir "deploy verde en GitHub" con "fix en producción"**. El workflow hace `POST /deploys` y termina; el deploy real ocurre en Render después y puede fallar silenciosamente. Verifica con `curl` post-deploy, siempre.

## Bitácora

Mantén una entrada corta por incidencia para no repetir errores.

### 2026-04-29 — 500 al enviar propuesta de cambio + jerga técnica en la UI

- **Reportado por**: usuario en sesión interactiva al pulsar "Abrir pull request" en `/books/1/pull-requests`.
- **Síntoma**: 500 Internal Server Error sin mensaje útil. Stack trace mostraba `httpx.HTTPStatusError` desde `app/services/repository/github_api.py:create_pull_request` → `response.raise_for_status()`.
- **Causa raíz**: la ruta `POST /books/{id}/pull-requests` llamaba directa a la API de GitHub sin envolver la llamada. Cualquier respuesta 4xx (caso típico: PR sin commits porque el usuario no había editado todavía → 422 "No commits between main and feature") propagaba como excepción no manejada hasta el middleware de Starlette.
- **Fix**: commit `a7bf6f9`.
  - `_friendly_github_error()` clasifica el error de GitHub (422 sin commits / PR ya existe, 401/403 sin permiso, 404 rama no encontrada, fallback genérico) y devuelve un mensaje en español adecuado al docente, no a un dev.
  - `create_issue` y `create_pull_request` envuelven la llamada en `try/except httpx.HTTPStatusError` → redirect 303 al detalle del libro con `?error=...`. La plantilla ya renderiza `alert-error` desde el contexto.
  - Helpers `_redirect_with_error` / `_error_from_request` añadidos al lado de los de `message`. El detalle del libro pasa `error` al contexto.
  - El check `head == base` que devolvía `HTTPException(400)` crudo ahora también usa el redirect amigable.
  - Aprovechado para rebrand a lenguaje docente: `issue` → "Aviso de problema", `pull_request` → "Propuesta de cambio", estados `open/draft/merged/closed` → "Abierta/Borrador/Aceptada e integrada/Cerrada", "Abrir en proveedor" → "Ver en GitHub". Globals en `templates.env` para no salpicar las plantillas con condicionales repetidos.
- **Lección**: cualquier ruta que llame a una API externa debe convertir errores HTTP en redirects amigables; un 500 con stack trace es siempre un fallo del controlador, no de la API. Y la jerga de Git ("issue", "pull request", "rama") no debe filtrarse a la UI cuando el público objetivo son profesores. Mantener `globals` con los labels traducidos centraliza el cambio si más adelante se internacionaliza.

### 2026-04-28 — `/healthz/db` + cron keepalive + footer de contacto

- **Pedido por**: usuario en sesión interactiva tras detectar que el footer no aparecía.
- **Cambios**:
  - Nuevo endpoint `/healthz/db` ejecuta `select 1` contra el engine; devuelve 503 si la DB no responde. `/healthz` queda como liveness probe ligero.
  - Nuevo workflow [keepalive.yml](../.github/workflows/keepalive.yml) con `cron: '*/10 * * * *'` haciendo `GET /healthz` con 3 reintentos y 90s timeout. Render free duerme el servicio tras 15 min sin tráfico; con margen de 5 min, basta para mantenerlo caliente.
  - `LIBRE_LIBROS_CONTACT_EMAIL=libre_libros@proton.me` se hardcodea como upsert no condicional en el workflow (espejo del `value:` de `render.yaml`). Antes era `upsert_optional` y como el secret no estaba creado, el footer no salía.
- **Fix**: commit `6588028`.
- **Verificación live**: `/healthz/db` devuelve `{"status":"ok","db":"ok"}` (Postgres responde), `/login` renderiza el footer con `mailto:` clicable.

### 2026-04-28 — Libros del repo de contenido no aparecían en producción

- **Reportado por**: usuario en sesión interactiva.
- **Síntoma**: el repo `librelibros/libre_libros_content` tiene 16 `book.md` con la estructura esperada (`books/<curso>/<materia>/<slug>/book.md`, parts=5), pero ningún libro aparecía en producción.
- **Diagnóstico**:
  - `/books` requiere sesión, así que no era observable directamente sin login.
  - Reproducido en local con un Docker apuntando al mismo repo público + SQLite: el sync poblaba 16 libros sin tocar nada. Por tanto el bug no era de código.
  - Las env vars `LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_*` vivían en `render.yaml` con `value:`. **Mismo patrón** que la incidencia de `EXTERNAL_AUTH_ONLY`: servicio Render creado a mano → `value:` del yaml no se aplica → bootstrap no se ejecuta porque `bootstrap_repository_provider AND bootstrap_repository_name` resuelven a `None`.
- **Fix**: commit `beb40ef`.
  - Workflow hardcodea como upsert no condicional los 7 flags estables: `PROVIDER`, `NAME`, `SLUG`, `NAMESPACE`, `NAME_REMOTE`, `DEFAULT_BRANCH`, `PUBLIC`.
  - Lifespan ahora loguea explícitamente: WARNING si la config bootstrap falta, INFO al iniciar y al terminar el sync, exception completa si falla. Antes el sync podía morir silenciosamente.
- **Lección**: la regla "modos de operación estables → workflow, no `render.yaml`" hay que aplicarla **en bloque a todas las env vars no-secret estables**, no a las que toque ahora. Si una env var es estable (`value:` en yaml) y el servicio es manual, drift garantizado. Y si una pieza del lifespan puede tirar excepción, hay que loguearla — lección recurrente, no esperar a la siguiente incidencia.

### 2026-04-28 — `/register` mostraba formulario local en producción

- **Reportado por**: usuario en sesión interactiva.
- **Síntoma**: `https://libre-libros-app.onrender.com/register` devolvía `200 OK` con un `<h1>Crear usuario local</h1>` y un formulario email/password, en vez de delegar a GitHub OAuth.
- **Causa raíz** (dos capas):
  1. [app/routers/auth.py](../app/routers/auth.py) hardcodeaba el nombre del provider externo (`if "github" in oauth._registry`) en `/register` GET y POST. Si GitHub OAuth no estaba registrado, caía en la rama de form local sin distinguir entornos.
  2. `LIBRE_LIBROS_EXTERNAL_AUTH_ONLY=true` se declaraba en `render.yaml` con `value:`, pero el servicio Render fue creado a mano, no por Blueprint, así que ese valor no se aplicaba — drift entre `render.yaml` y la realidad de Render.
- **Fix**: commit `d8d1a48`.
  - Helper `_first_external_start_url()` que itera por prioridad (github → gitlab → google → oidc) y redirige al primero registrado.
  - Workflow hardcodea `upsert "LIBRE_LIBROS_EXTERNAL_AUTH_ONLY" "true"` (más `GITHUB_OAUTH_ENABLED`, `GITHUB_OAUTH_NAME`) como upserts no condicionales en cada deploy.
  - Copy del template `login.html` adaptado a cualquier provider externo, no solo GitHub.
- **Lección**: si una env var es **modo de operación estable y no secreta**, hardcodéala en el workflow como `upsert KEY VALOR`. `render.yaml` solo se aplica a servicios creados desde Blueprint — para servicios creados a mano, lo único confiable es el upsert del workflow. Esta regla queda explicitada en la sección "Diagnosticar capa por capa".

---

Formato sugerido para futuras entradas:

```
## YYYY-MM-DD — síntoma corto
- **Reportado por**: ...
- **Causa raíz**: ...
- **Fix**: commit hash + un párrafo
- **Lección**: ...
```
