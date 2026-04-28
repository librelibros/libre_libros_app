# Deploy: GitHub → Render → Supabase

Producción de Libre Libros corre en Render (Docker) contra Supabase (Postgres). El despliegue está automatizado: cualquier push a `main` dispara un workflow de GitHub Actions que sincroniza los secrets en Render vía API y lanza un deploy.

```
git push main
   └─ GitHub Actions (deploy-to-render.yml)
        ├─ valida secrets requeridos
        ├─ PUT /v1/services/$RENDER_SERVICE_ID/env-vars/{key}   ← inyecta SUPABASE_URL, SUPABASE_KEY,
        │                                                          LIBRE_LIBROS_SECRET_KEY,
        │                                                          LIBRE_LIBROS_DATABASE_URL
        └─ POST /v1/services/$RENDER_SERVICE_ID/deploys         ← lanza rebuild
              └─ Render rebuilda Docker (libre_libros_app/Dockerfile, python:3.12.13-slim)
                   └─ uvicorn app.main:app
                        ├─ supabase.create_client()             ← cliente REST (app/supabase_client.py)
                        └─ SQLAlchemy + psycopg                  ← conecta a Supabase Postgres
```

Local sigue usando SQLite por defecto: `app/database.py` lee `LIBRE_LIBROS_DATABASE_URL` y la app no toca Supabase si la URL apunta a `sqlite:///`.

## Secrets requeridos en GitHub

`Repo → Settings → Secrets and variables → Actions` — los 6 son obligatorios; el workflow aborta si falta cualquiera.

| Secret | De dónde sacarlo |
|---|---|
| `RENDER_API_KEY` | Render Dashboard → Account Settings → API Keys |
| `RENDER_SERVICE_ID` | Render Dashboard → tu servicio → URL contiene `srv-...` (también en Settings) |
| `SUPABASE_URL` | Supabase Dashboard → Project Settings → API → "Project URL" |
| `SUPABASE_KEY` | Supabase Dashboard → Project Settings → API → key publishable (`sb_publishable_*`) |
| `LIBRE_LIBROS_SECRET_KEY` | `openssl rand -hex 32` — clave de firma de sesiones |
| `LIBRE_LIBROS_DATABASE_URL` | Cadena Postgres del **Transaction pooler** (ver más abajo) |

Opcionales (auth — solo si quieres login por GitHub, ver sección dedicada más abajo):

| Secret | Para qué |
|---|---|
| `LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_ID` | Client ID de la GitHub OAuth App |
| `LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_SECRET` | Client secret de la misma OAuth App |
| `LIBRE_LIBROS_INIT_ADMIN_EMAIL` | Email que automáticamente entra como admin al hacer login OAuth |
| `LIBRE_LIBROS_INIT_ADMIN_PASSWORD` | Solo si **desactivas** `external_auth_only` (no recomendado en prod) |

Comandos `gh`:

```bash
gh secret set RENDER_API_KEY            --body 'rnd_...'
gh secret set RENDER_SERVICE_ID         --body 'srv-...'
gh secret set SUPABASE_URL              --body 'https://<ref>.supabase.co'
gh secret set SUPABASE_KEY              --body 'sb_publishable_...'
gh secret set LIBRE_LIBROS_SECRET_KEY   --body "$(openssl rand -hex 32)"
gh secret set LIBRE_LIBROS_DATABASE_URL --body 'postgresql+psycopg://postgres.<ref>:<URL_ENCODED_PASSWORD>@aws-0-<region>.pooler.supabase.com:6543/postgres'
```

## Construyendo `LIBRE_LIBROS_DATABASE_URL` (lo que más se rompe)

Tres reglas que no se pueden saltar:

### 1. Driver explícito: `postgresql+psycopg://`

`requirements.txt` ship `psycopg[binary]==3.3.3` (psycopg v3). Sin el sufijo `+psycopg`, SQLAlchemy carga `psycopg2` por defecto y falla con `ModuleNotFoundError: No module named 'psycopg2'`.

`app/database.py:_normalize_database_url()` reescribe `postgresql://` y `postgres://` automáticamente, así que el secret puede tener cualquiera de los tres prefijos. Aun así, ser explícito es preferible.

### 2. Pooler, no host directo

Render free tier es **IPv4-only** y el host directo de Supabase (`db.<ref>.supabase.co`) solo resuelve por IPv6 → falla con `Network is unreachable`.

Usa el **Transaction pooler** (Supavisor):

| Modo | Host | Puerto | Username |
|---|---|---|---|
| Transaction pooler ✅ | `aws-0-<region>.pooler.supabase.com` | `6543` | `postgres.<project_ref>` |
| Direct ❌ | `db.<ref>.supabase.co` | `5432` | `postgres` |

El host completo y la región los ves en Supabase → Project Settings → Database → "Connection pooling".

### 3. URL-encodea el password

Caracteres como `+`, `&`, `@`, `/`, `#`, `?` rompen el parser si van crudos en el password. El error típico es críptico:

```
failed to resolve host '+muR+daV23&@db.tvnlxffinhvowfpxblpe.supabase.co'
```

Significa que el parser no separó user/password/host porque encontró un `+` o `&` antes del `@`. Encodea cada reservado:

| Carácter | URL-encoded |
|---|---|
| `+` | `%2B` |
| `&` | `%26` |
| `@` | `%40` |
| `/` | `%2F` |
| `#` | `%23` |
| `?` | `%3F` |
| espacio | `%20` |

Atajo en Python:
```python
from urllib.parse import quote
quote('VQE@+muR+daV23&', safe='')   # → 'VQE%40%2BmuR%2BdaV23%26'
```

URL completa de ejemplo:
```
postgresql+psycopg://postgres.tvnlxffinhvowfpxblpe:VQE%40%2BmuR%2BdaV23%26@aws-0-eu-west-1.pooler.supabase.com:6543/postgres
```

## Autenticación: GitHub OAuth + admin inicial

Producción corre con `LIBRE_LIBROS_EXTERNAL_AUTH_ONLY=true` (definido en `render.yaml`). En este modo:

- El formulario email/password está **desactivado a nivel de router** ([app/routers/auth.py](../app/routers/auth.py): si la flag está activa, el POST `/login` redirige sin verificar).
- El admin inicial se crea con `password_hash=NULL` y `auth_provider='github'`.
- `LIBRE_LIBROS_INIT_ADMIN_PASSWORD` deja de tener uso — solo cuenta el email para identificar quién es admin.

### 1. Crear la GitHub OAuth App

`https://github.com/settings/developers` → New OAuth App.

| Campo | Valor |
|---|---|
| Application name | Libre Libros (o lo que quieras) |
| Homepage URL | `https://<tu-servicio>.onrender.com` |
| Authorization callback URL | `https://<tu-servicio>.onrender.com/auth/github/callback` |

Tras crear, **Generate a new client secret** y guarda los dos valores.

### 2. Subirlos como secrets de GitHub (opcionales)

El workflow los sincroniza a Render si están definidos; si faltan, el step lo loguea como `Skipping ...` y no rompe.

```bash
gh secret set LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_ID     --body 'Iv1.xxxxxxxxxxxxxxxx'
gh secret set LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_SECRET --body 'ghcs_xxxxxxxxxxxxxxxx'
gh secret set LIBRE_LIBROS_INIT_ADMIN_EMAIL           --body 'tu-email-verificado@dominio.com'
```

`LIBRE_LIBROS_GITHUB_OAUTH_ENABLED=true` ya está hardcoded en `render.yaml`, no hace falta secret.

### 3. Flujo de un usuario al entrar por primera vez

1. Visita `https://<servicio>.onrender.com` → sin sesión → redirect a `/login`.
2. La página `/login` solo muestra el botón **"Iniciar sesión con GitHub"** (sin formulario email/password porque `external_auth_only` los oculta).
3. Click → `/auth/github/start` → redirect al consent screen de GitHub.
4. Acepta → GitHub redirige a `/auth/github/callback`.
5. La app pide a la API de GitHub `user/emails` y toma el primary verificado.
6. Upsert en BBDD por email:
   - **No existía** → se crea como `member` (rol no-admin) con `auth_provider='github'`.
   - **Ya existía** (típicamente porque `LIBRE_LIBROS_INIT_ADMIN_EMAIL` lo creó como `admin` en el bootstrap) → se reutiliza con su rol actual.
7. Sesión iniciada → redirect al dashboard.

No hay registro manual. El primer login de cada email es a la vez registro y entrada.

### 4. Sub-trampas frecuentes

- **El email del secret debe coincidir EXACTAMENTE con el primary verificado de tu cuenta GitHub** (case-insensitive, pero el dominio importa). Compruébalo en `https://github.com/settings/emails` → "Primary email address".
- Typo del dominio: `pronton.me` ≠ `proton.me`. Si pones uno en el secret y tu GitHub usa el otro, entras como user normal en vez de admin.
- Si no se ve el botón de GitHub en `/login`: faltan `CLIENT_ID`/`CLIENT_SECRET` en Render. Revísalo en Dashboard → Environment.
- Si te redirige a `/login` tras volver de GitHub: el callback URL del OAuth App no coincide con la URL pública de tu servicio Render.

### 5. Promocionar a admin a un user que ya entró

Si quieres dar admin a alguien que ya entró por GitHub (no tiene tu init email), entra tú a la BBDD Supabase y haz:

```sql
update "user" set global_role = 'admin' where email = 'su-email@dominio.com';
```

(O cambia `LIBRE_LIBROS_INIT_ADMIN_EMAIL` y reinicia — el bootstrap actualiza el rol del user existente.)

## Verificación

### Antes de pushear: `/check-deploy` o el script

```bash
cd libre_libros_app
python scripts/check_deploy.py
```

Verifica .env local, REST de Supabase, cliente Python, conexión Postgres, secrets de GitHub (con `gh` autenticado) y estado del servicio Render (con `RENDER_API_KEY`/`RENDER_SERVICE_ID` exportados). Exit no-zero si falla algo requerido.

Para incluir los checks de Render:
```bash
RENDER_API_KEY=... RENDER_SERVICE_ID=... python scripts/check_deploy.py
```

La skill `/check-deploy` (en `.claude/skills/check-deploy/`) lo wrappea para invocarla desde Claude Code.

### Después del deploy

```bash
curl -fsS https://<tu-servicio>.onrender.com/healthz
# {"status":"ok"}
```

Y en logs de Render: la primera arrancada loguea `Application startup complete` + cualquier error de `Base.metadata.create_all` contra Supabase Postgres.

## Re-disparar un deploy sin cambios de código

```bash
# Opción A — push vacío
git commit --allow-empty -m "ci: re-trigger Render deploy" && git push origin main

# Opción B — desde la UI
# https://github.com/<owner>/<repo>/actions/workflows/deploy-to-render.yml → Run workflow

# Opción C — desde gh
gh workflow run "Deploy to Render" --ref main
```

## Rotación del password de la base de datos

Cuando rotes el password (Supabase → Project Settings → Database → Reset database password):

```bash
NEW_PWD='<nuevo>'
NEW_PWD_ENC=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$NEW_PWD")
gh secret set LIBRE_LIBROS_DATABASE_URL --body "postgresql+psycopg://postgres.<ref>:$NEW_PWD_ENC@aws-0-<region>.pooler.supabase.com:6543/postgres"
git commit --allow-empty -m "ci: rotate DB password" && git push origin main
```

El siguiente deploy hace `PUT /env-vars/LIBRE_LIBROS_DATABASE_URL` con el nuevo valor.

## Modos de fallo conocidos

| Síntoma en logs | Causa | Arreglo |
|---|---|---|
| `Invalid workflow file ... Unexpected symbol: '$v'` | `secrets[$v]` (indexing dinámico) en YAML | El workflow ya usa `env:` + expansión bash `${!v:-}` |
| `pyiceberg ... gcc: No such file` | Python 3.14 sin wheels de pyiceberg, transitivo de `storage3` | Dockerfile pinea `python:3.12.13-slim` |
| `ModuleNotFoundError: No module named 'psycopg2'` | URL con `postgresql://` y SQLAlchemy carga psycopg2 | `_normalize_database_url` lo reescribe; verifica que el secret no se quede sin reescribir |
| `failed to resolve host '...&@db.*.supabase.co'` | Password con chars reservados sin encodear | URL-encode todo el password |
| `Network is unreachable` / DNS timeouts contra `db.*.supabase.co` | Host directo sobre Render free (IPv4-only) | Cambia al pooler `*.pooler.supabase.com:6543` |
| `password authentication failed` | Password caducado / mal copiado | Reset en Supabase → re-set del secret |
| `clearCache` / HTTP 400 al disparar deploy | Render API espera `"do_not_clear"`/`"clear"`, no boolean | Workflow ya envía el valor correcto |

## Estabilidad

Lo que está pinado para que el deploy no se rompa al azar:

- `Dockerfile`: `python:3.12.13-slim` (versión exacta — el major/minor flotante exponía a fallos de wheels en cada release).
- `requirements.txt`: todas las dependencias con `==`, incluido `supabase==2.29.0` y `python-dotenv==1.0.1`.
- `render.yaml`: `runtime: docker` con `healthCheckPath: /healthz` y `autoDeploy: true`.
- Secrets sensibles (`SUPABASE_KEY`, `LIBRE_LIBROS_DATABASE_URL`, `LIBRE_LIBROS_SECRET_KEY`, OAuth secrets) declarados como `sync: false` en `render.yaml` — el workflow es la única fuente de verdad.

## Local: SQLite, no Supabase

`.env` y `.env_docker` por defecto apuntan a SQLite (`sqlite:///../data/libre_libros.db`). El cliente `supabase` solo se instancia si están presentes `SUPABASE_URL` y `SUPABASE_KEY`. Para una corrida local 100% offline, deja esas dos vars vacías.

Si quieres correr en local **contra Supabase** para depurar producción (no recomendado en general):

```bash
export SUPABASE_URL='https://<ref>.supabase.co'
export SUPABASE_KEY='sb_publishable_...'
export LIBRE_LIBROS_DATABASE_URL='postgresql+psycopg://postgres.<ref>:<encoded_pwd>@aws-0-<region>.pooler.supabase.com:6543/postgres'
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
