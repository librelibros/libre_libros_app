# Despliegue: Render + Supabase (Free)

Este documento explica cómo desplegar `Libre Libros` usando Render para el servicio web y Supabase (Postgres) en su plan Free como base de datos. Es una buena opción para una prueba pública seria, con más garantías que usar SQLite o Render Postgres Free por sí solo.

## Resumen rápido
- Crear un proyecto en Supabase y copiar la cadena de conexión Postgres.
- En Render, crear un Web Service conectado al repo y definir la variable de entorno `LIBRE_LIBROS_DATABASE_URL` con la cadena transformada para SQLAlchemy.
- Opcional: ejecutar un job único para aplicar migraciones o dejar que la primera instancia las cree en el arranque (el app ejecuta `Base.metadata.create_all`).

## Pre-requisitos
- Cuenta en Supabase
- Cuenta en Render
- Repositorio con el código (ya en GitHub en este caso)
- En el repo: `requirements.txt` contiene `psycopg[binary]` y `sqlalchemy` (ya incluido)

## 1) Crear proyecto en Supabase
1. Entra a https://app.supabase.com y crea un proyecto nuevo.
2. Elige una contraseña segura para la base de datos y el nombre del proyecto.
3. Espera a que el proyecto quede listo.

## 2) Obtener la cadena de conexión
1. Ve a Settings → Database → Connection info (o sección equivalente).
2. Copia la cadena tipo `postgres://USER:PASS@HOST:PORT/DBNAME` (la que supabase muestra como "Connection string").

### Convertir la cadena para SQLAlchemy + `psycopg` (psycopg3)
Supabase da `postgres://...`. Para SQLAlchemy con `psycopg` (la dependenciya en `requirements.txt`) usa el esquema `postgresql+psycopg://`.

Ejemplo:

- Supabase: `postgres://user:password@db.host.supabase.co:5432/postgres`
- SQLAlchemy: `postgresql+psycopg://user:password@db.host.supabase.co:5432/postgres?sslmode=require`

Notas:
- Asegura `?sslmode=require` al final para forzar TLS en la conexión.
- Si la URL original tiene el prefijo `postgres://`, reemplázalo exactamente por `postgresql+psycopg://`.

## 3) Configurar el servicio en Render
1. Crea un nuevo Web Service en Render y conéctalo a tu repo GitHub.
2. Branch: `main` (o la rama que uses).
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Runtime: Python 3.x (usa la versión que necesites).

### Variables de entorno (mínimas recomendadas)
- `LIBRE_LIBROS_DATABASE_URL`: cadena SQLAlchemy preparada (ver arriba).
- `LIBRE_LIBROS_SECRET_KEY`: clave segura para sesiones (cambia el valor por defecto).
- `LIBRE_LIBROS_INIT_ADMIN_EMAIL`, `LIBRE_LIBROS_INIT_ADMIN_PASSWORD`, `LIBRE_LIBROS_INIT_ADMIN_NAME` (opcional, para crear admin inicial).
- Cualquier `LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_ID` / `LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_SECRET` u otras variables OAuth si vas a habilitar login externo.

Configura estas variables en la sección Environment → Environment Variables de Render (o usando `render.yaml` si prefieres infra-as-code).

## 4) Migraciones / Creación de tablas
El app ejecuta en el arranque:

- `Base.metadata.create_all(bind=engine)`
- `ensure_runtime_schema()` — para alteraciones menores en caliente

Esto significa que, por defecto, la primera instancia del servicio creará las tablas necesarias al arrancar. Para mayor control en entornos con más instancias:

- Recomendado: desplegar con `instances: 1` inicialmente y esperar a que la instancia arranque y cree las tablas.
- Alternativa robusta: ejecutar un job único o one-off command en Render que arranque la app localmente y salga después de crear las tablas (por ejemplo `python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"`) antes de escalar.

## 5) Seguridad de claves Supabase
- No expongas la `service_role` key en el cliente. Si necesitas funcionalidades admin, úsalas sólo en servidor y guárdalas como `SECRET` en Render.
- Para integración de frontend con Supabase (si decides usar Supabase Auth o Storage), usa la `anon` key en el navegador y la `service_role` sólo en backend cuando sea imprescindible.

## 6) Conexiones y pooling
- Ten en cuenta el límite de conexiones del plan free. Render puede abrir múltiples procesos/instancias y cada uno abrirá conexiones.
- Recomendaciones:
  - Mantén `instances=1` para demos serias si tienes límite de conexiones.
  - Usa el pool de SQLAlchemy (por defecto SessionLocal usa engine) y considera ajustar `pool_size` si fuera necesario mediante la URL o parámetros al crear el engine.
  - Si superas límites, usa un pooler (PgBouncer) o sube a un plan con más conexiones.

## 7) Backups y límites del Free tier
- Supabase Free tiene límites de almacenamiento, CPU y tamaño de base de datos. No es para producción crítica.
- Programa exportaciones regulares si los datos importan (pg_dump desde un job o export desde Supabase).

## 8) Comandos útiles (local y en Render one-off)

Local (exporta la env y arranca):

```bash
export LIBRE_LIBROS_DATABASE_URL="postgresql+psycopg://user:pass@host:5432/db?sslmode=require"
export LIBRE_LIBROS_SECRET_KEY="cambia-esto"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

One-off en Render (ejemplo):

```bash
# Ejecutar desde Render Dashboard → Shell / One-off command
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

## 9) Verificación post-despliegue
- Revisar `https://<your-render-service>/healthz` (debe devolver status ok).
- Revisar logs en Render: la primera arranque debe mostrar creación de tablas y cualquier error de conexión.

## 10) Notas finales y buenas prácticas
- Mantén las keys en el panel de Render y no en el repo.
- Revisa límites de Supabase Free antes de confiar en él para datos críticos.
- Para alta disponibilidad y carga real, considera un plan de pago en Supabase o usar Render Postgres / otro proveedor gestionado con backups.

---
Si quieres, puedo:
- Añadir un `render.yaml` de ejemplo con las env vars prácticas ya puestas como placeholders.
- Preparar un job `one-off` para crear tablas y poblar contenido de ejemplo antes de abrir al público.

## Automatización: GitHub Actions + disparo a Render

He añadido un ejemplo de `render.yaml` y un workflow de GitHub Actions en `.github/workflows/deploy-to-render.yml` que, al hacer push a `main`, lanza un deploy en Render usando la API.

Resumen de lo que debes configurar (por seguridad):

- En GitHub (Settings → Secrets → Actions) añade los siguientes secrets:
  - `RENDER_API_KEY` — tu API Key de Render (Dashboard → Account → API Keys).
  - `RENDER_SERVICE_ID` — el Service ID de tu servicio en Render (lo obtienes desde el Dashboard → Service → Settings).
  - `SUPABASE_URL` — tu URL de Supabase (ej. https://...supabase.co)
  - `SUPABASE_KEY` — tu Supabase Key (usa la `service_role` sólo en backend; si sólo utilizas anon para el cliente, guarda la `anon` en otro sitio).
  - `LIBRE_LIBROS_SECRET_KEY` — clave secreta para sesiones.

- En Render (Dashboard → Service → Environment) añade estas variables de entorno al servicio:
  - `LIBRE_LIBROS_DATABASE_URL` — la cadena SQLAlchemy: `postgresql+psycopg://USER:PASS@HOST:5432/DB?sslmode=require`
  - `LIBRE_LIBROS_SECRET_KEY`
  - `SUPABASE_URL`
  - `SUPABASE_KEY`

El workflow lanzará un deploy (POST a `https://api.render.com/v1/services/$RENDER_SERVICE_ID/deploys`). El script local `scripts/deploy_render.sh` hace lo mismo si prefieres ejecutar manualmente.

### Seguridad
- Nunca pongas `SUPABASE_KEY` ni `LIBRE_LIBROS_SECRET_KEY` en el repo.
- Usa GitHub Secrets para CI y las Environment variables del service en Render para runtime.

Si quieres que automáticamente el workflow también actualice las env vars en Render vía API (p. ej. inyectar `LIBRE_LIBROS_DATABASE_URL` desde GitHub secret hacia Render), puedo preparar ese paso, pero necesitaré que confirmes que quieres permitir que el workflow tenga permisos para modificar el servicio (usar la `RENDER_API_KEY`) — es seguro si confías en tu repo y en los secrets.
