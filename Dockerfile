# Node 22 LTS satisfies the locked frontend toolchain (marked requires >=20).
# Keep this major aligned with CI; patch updates remain enabled intentionally.
FROM node:22-bookworm-slim AS editor
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY frontend ./frontend
COPY scripts/build-editor.mjs ./scripts/build-editor.mjs
RUN node scripts/build-editor.mjs

FROM python:3.12.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Explicit runtime inputs: never copy the entire developer workspace.
COPY app ./app
# Retain the local Compose entrypoint without including diagnostic/deploy scripts.
COPY scripts/start-with-runtime-config.sh ./scripts/start-with-runtime-config.sh
# Copy last so a checked-in stale bundle cannot overwrite the fresh build.
COPY --from=editor /build/app/static/js/editor-rich.js ./app/static/js/editor-rich.js

EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
