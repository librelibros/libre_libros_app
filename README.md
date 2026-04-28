# Libre Libros

Libre Libros es un MVP para crear, adaptar y revisar libros de texto colaborativos almacenados en Markdown sobre proveedores Git.

## Qué incluye

- Backend FastAPI y web server-side en `:8000`
- Gestión simple de usuarios, organizaciones y permisos en cascada
- Catálogo de libros por curso y materia
- Edición Markdown con vista previa
- Exportación básica a PDF
- Soporte para repositorios locales de prueba, GitHub y GitLab
- Flujo de comentarios, issues y pull requests
- Dockerfile, `docker-compose.yml` y `.env.example`

## Arquitectura

- `app/main.py`: arranque de FastAPI
- `app/models.py`: usuarios, organizaciones, repositorios, libros, comentarios y revisiones
- `app/routers/`: auth, panel, libros y administración
- `app/services/repository/`: abstracción local Git / GitHub REST / GitLab REST
- `../data/`: base SQLite y repositorio local montado para desarrollo y Docker

## Arranque en local

1. Crear entorno virtual e instalar dependencias:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Crear `.env` desde el ejemplo:

```bash
cp .env.example .env
```

Ajusta las rutas relativas si cambian. En local, la app usa el `data/` hermano:

```text
../data
```

3. Arrancar la aplicación:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. Abrir `http://localhost:8000`

## Arranque con Docker Compose

```bash
cp .env.example .env
cp .env_docker.example .env_docker
docker compose up --build
```

La app quedará publicada en `http://localhost:8000`.
Docker usa `.env_docker`, con rutas internas del contenedor (`/app/data`).

En modo debug, `docker compose` levanta también un GitLab local en `http://127.0.0.1:8081`, genera la configuración OAuth mínima y arranca Libre Libros con login delegado a GitLab.

## Despliegue gratuito

Para publicar una demo pequeña con el repositorio de libros en GitHub, ver [docs/deploy-free.md](docs/deploy-free.md).

## Usuario inicial

Si configuras estas variables en `.env`, al arrancar se crea un admin automáticamente:

- `LIBRE_LIBROS_INIT_ADMIN_EMAIL`
- `LIBRE_LIBROS_INIT_ADMIN_PASSWORD`
- `LIBRE_LIBROS_INIT_ADMIN_NAME`

## Configurar repositorios

### Repositorio local para pruebas

- Crea un repositorio desde `Administración`
- Usa `provider=local`
- Si no indicas ruta, la app usa `LIBRE_LIBROS_REPOS_ROOT`
- Si defines `LIBRE_LIBROS_EXAMPLE_REPO_PATH` en `.env`, la UI sugerirá esa ruta en el formulario de repositorios
- La configuración actual apunta al repo de prueba en `data/repo`

También puedes preparar uno manualmente:

```bash
python scripts/init_local_books_repo.py ./data/repos/demo-libros
```

Ruta local del repo de ejemplo desde la app en desarrollo:

```text
../data/repo
```

Ruta del repo de ejemplo dentro de Docker:

```text
/app/data/repo
```

### Repositorio GitHub o GitLab

Desde `Administración` registra:

- `provider=github` o `provider=gitlab`
- `provider_url`
- `repository_namespace`
- `repository_name`
- `service_token`

El token debe tener permisos para leer/escribir contenidos y crear issues o pull requests.

## Limitaciones del MVP

- El exportado PDF es simple y está pensado como punto de partida
- Los comentarios de detalle viven en la base de datos de la app
- Para GitHub y GitLab se usa la API REST con token; no se implementa todavía una GitHub App ni una GitLab Application de producción
- El editor Markdown es intencionalmente sencillo
