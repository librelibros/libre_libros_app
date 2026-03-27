# Libre Libros

Libre Libros es un MVP para crear, adaptar y revisar libros de texto colaborativos almacenados en Markdown sobre Git o GitHub.

## Qué incluye

- Backend FastAPI y web server-side en `:8000`
- Gestión simple de usuarios, organizaciones y permisos en cascada
- Catálogo de libros por curso y materia
- Edición Markdown con vista previa
- Exportación básica a PDF
- Soporte para repositorios locales de prueba y repositorios GitHub
- Flujo de comentarios, issues y pull requests
- Dockerfile, `docker-compose.yml` y `.env.example`

## Arquitectura

- `app/main.py`: arranque de FastAPI
- `app/models.py`: usuarios, organizaciones, repositorios, libros, comentarios y revisiones
- `app/routers/`: auth, panel, libros y administración
- `app/services/repository/`: abstracción local Git / GitHub REST
- `data/`: base SQLite y repositorios de contenidos locales

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

3. Arrancar la aplicación:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. Abrir `http://localhost:8000`

## Arranque con Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

La app quedará publicada en `http://localhost:8000`.

## Usuario inicial

Si configuras estas variables en `.env`, al arrancar se crea un admin automáticamente:

- `LIBRE_LIBROS_INIT_ADMIN_EMAIL`
- `LIBRE_LIBROS_INIT_ADMIN_PASSWORD`
- `LIBRE_LIBROS_INIT_ADMIN_NAME`

## Configurar repositorios

### Repositorio local para pruebas

- Crea un repositorio desde `Administración`
- Usa `provider=local`
- Si no indicas ruta, la app usa `data/repos/<slug>`

También puedes preparar uno manualmente:

```bash
python scripts/init_local_books_repo.py ./data/repos/demo-libros
```

### Repositorio GitHub

Desde `Administración` registra:

- `provider=github`
- `github_owner`
- `github_repo`
- `github_token`

El token debe tener permisos para leer/escribir contenidos y crear issues o pull requests.

## Limitaciones del MVP

- El exportado PDF es simple y está pensado como punto de partida
- Los comentarios de detalle viven en la base de datos de la app
- Para GitHub se usa la API REST con token; no se implementa GitHub App todavía
- El editor Markdown es intencionalmente sencillo

