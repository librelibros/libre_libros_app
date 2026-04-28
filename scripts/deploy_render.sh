#!/usr/bin/env bash
# Script simple para lanzar un deploy en Render via API
# Requisitos (exportar o dejar como secrets en CI):
# - RENDER_API_KEY
# - RENDER_SERVICE_ID
# Uso local:
#   export RENDER_API_KEY=...
#   export RENDER_SERVICE_ID=...
#   ./scripts/deploy_render.sh

set -euo pipefail

if [ -z "${RENDER_API_KEY:-}" ] || [ -z "${RENDER_SERVICE_ID:-}" ]; then
  echo "ERROR: debes exportar RENDER_API_KEY y RENDER_SERVICE_ID"
  echo "Sugerencia: en Render Dashboard -> Service -> Settings encuentras el Service ID"
  exit 1
fi

echo "Triggering deploy for service $RENDER_SERVICE_ID..."

resp=$(curl -s -X POST "https://api.render.com/v1/services/$RENDER_SERVICE_ID/deploys" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"clearCache": false}')

echo "Render API response:" 
echo "$resp" | jq .

echo "Deploy requested. Monitoriza en Render dashboard." 

echo "Nota: asegúrate de haber configurado las env vars en Render: LIBRE_LIBROS_DATABASE_URL, SUPABASE_URL, SUPABASE_KEY, LIBRE_LIBROS_SECRET_KEY"
