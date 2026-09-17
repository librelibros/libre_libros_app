# Libre Libros — memoria de preparación del piloto

## Mandato y límites (2026-09-16)
- Objetivo: aplicación colaborativa comprensible para profesores, piloto de 3–5 centros de Primaria en España y 10–20 docentes. Libros abiertos, sin datos de alumnos, propuestas revisadas antes de publicar.
- Acceso deseado: invitación sin exigir cuenta GitHub al docente.
- Autorizado: decisiones de implementación, pruebas, demo y commits **locales** en rama `improve/pilot-readiness`. NO push, despliegue, contratación, envíos comerciales ni modificación de producción.
- Trabajar exclusivamente dentro de los dos repositorios de `/home/jgorozco/git/libre-libros`. Referencias de agentes externas solo lectura. No modificar configuración global ni servicios ajenos.
- `.env`, `.env_docker` y configuración local se conservan privados. Pruebas con SQLite/repositorios temporales dentro del proyecto, nunca base de datos o libros remotos de producción.
- Producción declarada: https://libre-libros-app.onrender.com, sin usuarios reales todavía; Render gratuito se suspende. Evaluar alternativas gratis, no prometer disponibilidad continua.
- Especial atención: editor sencillo y útil, importación sin pérdida silenciosa, PDF robusto y limitaciones explícitas.
- Evaluaciones docentes mediante agentes son **simuladas**, no investigación con usuarios reales ni experimentos estadísticos A/B.

## Criterios de entrega
1. Hallazgos priorizados con evidencia, reproducción y estado.
2. Correcciones con pruebas de regresión; suite previa y posterior documentada.
3. Demo local aislada: entrar, encontrar libro, editar, importar, previsualizar, guardar/proponer, revisar y exportar PDF.
4. UX responsive y teclado; errores claros y prevención de pérdida de trabajo.
5. Seguridad de permisos/invitaciones, aislamiento y contenido no confiable.
6. Pipeline revisado sin ejecutarlo en producción; coste y límites gratuitos explícitos.
7. Instrucciones `.agents` actualizadas, guía operativa y plan de comunicación (sin contactar colegios).
8. Informe final honesto con resultados y bloqueos antes de un piloto real.

## Registro
- Exploración inicial: FastAPI + frontend; repo de libros separado. Documentación de GitHub Actions → Render → Supabase pendiente de contraste.
- Creada rama local `improve/pilot-readiness` en app; `content` permanece intacto en main.
- `.agents/` es trabajo local aportado por el propietario; se revisa y adapta, sin leer settings privados.
- Agentes paralelos asignados con archivos de escritura exclusivos: instrucciones, seguridad/backend, editor/PDF, producto/UX/comunicación y despliegue. Orquestación/validación central.
- Preparado entorno local: `.venv` con `requirements.txt`, `node_modules` vía `npm ci --ignore-scripts`. `npm audit`: 3 vulnerabilidades (tiptap ReDoS high, linkify-it ReDoS high, markdown-it moderate) con fix disponible — pendiente de aplicar tras validar suite.
- Corregido `app/config.py`: `LIBRE_LIBROS_ENV_FILE` permite desactivar carga de `.env` en tests (clave vacía = sin dotenv). `.gitignore` ahora excluye `settings.local.json` y `.local/`.
- Prueba base confirmó bloqueo real: `tests/test_app.py` importa un PNG desde `../data/repo` (inexistente en este layout). Agente de pruebas trabajando en aislamiento reproducible; baseline en `docs/audit/test-baseline.md`.
- Auditoría backend/seguridad recibida (18 hallazgos, docs/audit/backend-security.md): 10 P1 bloqueantes para piloto multiusuario. Lanzados 2 agentes de corrección con propiedad exclusiva de archivos: (A) auth/invitaciones/CSRF/sesiones, (B) books/paths/XSS/uploads/permisos/SHA. Integración y suite completa al terminar ambos.

## Índice de evidencias (en elaboración)
- `docs/audit/backend-security.md`
- `docs/audit/editor-pdf.md`
- `docs/audit/product-ux.md`
- `docs/audit/deployment.md`
- `docs/audit/acceptance-gates.md`
- `docs/audit/test-baseline.md`
- `docs/pilot-communication-plan.md`
- `test_plan/2026-09-16-local-demo/export-demo.pdf` (3 págs, acentos OK, placeholder visible para SVG legacy)
- `test_plan/2026-09-16-local-demo/lectura.png` (vista de lectura, 0 errores JS)
- `test_plan/test-suite-final.log` (31 passed / 2 failed / 1 xfail)

## Resultados verificados (rama local)
- `tests/test_config.py` — 5/5 pasan: producción rechaza clave de sesión por defecto (antes `NameError`, corregido en `app/config.py`).
- Suite completa `tests/test_app.py` + `tests/test_validation_regressions.py` — 31 passed / 2 failed / 1 xfail (`test_plan/test-suite-final.log`; baseline en `docs/audit/test-baseline.md`). Fallos restantes: 404 en `?workspace=personal` y `?school=…&workspace=shared` — corrección asignada al agente de books.
- Contratos de tests endurecidos: PNG válido con Pillow, raster corrupto → placeholder verificado con pypdf, SVG sirve como `application/octet-stream` adjunto con `nosniff`, ramas `users/id-<ID>`, red externa bloqueada en fixtures.
- `tests/test_validation_regressions.py` — 2/2 pasan. Recolección de `test_app.py` reparada (fixture ya no depende de `../data/repo`).

## Integración verificada — actualización 2026-09-16
- Los resultados anteriores son históricos. Suite completa actual: **146 passed**, 476 avisos de deprecación, 71,21 s; evidencia `test_plan/convergence-suite-current.log`. Sin fallos ni xfail. No equivale a aprobación PM ni piloto.- La integración CSRF inicialmente dio 16 failed / 121 passed / 1 xfailed (`test_plan/convergence-suite.log`). Los clientes legacy no enviaban token; no era evidencia de una regresión de books. `tests/test_app.py` usa ahora un cliente funcional que devuelve el token de su propia sesión (no valida wiring HTML). Una prueba adicional con TestClient sin adaptación comprueba rechazo sin token y login válido con el token real del formulario.
- Eliminado xfail que ya pasaba en biblioteca del editor; href personal espera `users/id-<ID>/base/primaria`; bootstrap no debe resetear contraseña existente. Fixture router de `tests/test_books_security_p1.py` incorpora SessionMiddleware y generador real de token, sin depender del startup principal. Selección de integración: 87 passed en `test_plan/convergence-integration.log`; dashboard aislado: 1 passed.
- Auth/invitaciones integrado por agente: alta por invitación, CSRF global, logout POST, sesiones y usuarios inactivos. Agente continúa integrando tokens/formularios/fetch en frontend; no certificar navegador hasta finalizar y ejecutar flujo completo.
- Books: ramas personales/selección base, assets, PDFExportError y permisos integrados. Sigue abierto B04 frente a concurrencia (unicidad libro repositorio/ruta y creación Git atómica), además de otros bloqueos del informe de seguridad. Migraciones reales requieren confirmación.
- Dashboard local cambió a catálogo primero, con enlace a avisos al inicio. Mediciones previas a CSRF: título catálogo escritorio y≈1032→163 px; móvil y≈2490→718 px. Capturas `test_plan/2026-09-16-local-demo/catalog-{before,after}-{1440,390}.png`. Avisos quedan mucho más abajo y móvil conserva cabecera alta: mejora parcial, no validación humana.
- Mocks A/B y alternativas de icono disponibles en `docs/design-lab/web/` y `docs/design-lab/brand/`; protocolo en `docs/design-lab/protocol.md`. Comprobaciones del autor no equivalen a revisión docente independiente; comparación independiente aún pendiente. Logo del producto no sustituido.
- Nueva petición de contenido: alcance provisional 1.º–6.º de Primaria, índices contrastados antes de autoría, fuentes/licencias verificadas, ejemplos/ejercicios/soluciones/exámenes y figuras claras. Agente de investigación escribe solo `libre_libros_content/docs/curriculum-madrid/`. Rama local de contenido creada `improve/pilot-content` (distinta de la rama de app); libros aún sin editar. Los 30 índices de cinco áreas encargados son un primer lote, NO acreditan cubrir todas las materias oficiales de Madrid; validar denominaciones, áreas desdobladas y materias faltantes antes de autorizar libros.

- Suite completa tras CSRF: **147 passed** (`test_plan/convergence-suite-nullorigin.log`). Corrección del bloqueo real de la demo: el navegador local envía el sentinel opaco `Origin: null` y el middleware lo rechazaba antes de evaluar el token. Reproducido con curl (403 con `Origin: null`, 400 esperado con origen propio/sin Origin, 403 con origen ajeno). Solución: `csrf_allow_null_origin` (por defecto **false**, OWASP: un iframe sandbox también envía `null`) + tolerancia solo si no hay Referer; la demo local la activa vía `LIBRE_LIBROS_CSRF_ALLOW_NULL_ORIGIN`. Test nuevo en `tests/test_auth_csrf.py`. **Corrección posterior:** el bypass se retiró por completo; el problema real era `Referrer-Policy: no-referrer` en login (Chromium envía `Origin: null` en POST sin referrer). Ahora login/register usan `same-origin` y `/invite/<token>` conserva `no-referrer`. Suite final: **180 passed** (`test_plan/ci-reproduce-local.log`).
- E2E en demo aislada (port 8766, artefactos en `test_plan/2026-09-16-local-demo-*`): `/register` → 403 con invitation_only; login con CSRF OK; edición enriquecida + guardado con token (commit verificado en rama `users/id-1/base/primaria`, marcador presente en `book.md`); logout POST; PDF export 200 `%PDF-1.4` con el marcador en la rama personal (3 págs, `test_plan/2026-09-16-csrf-e2e-rama-personal.pdf`); lectura con marcador visible; 0 errores JS. Nota: vista/PDF por defecto muestran `main` (sin la edición personal): comportamiento esperado, no bug.

## Despliegue a producción — 2026-09-17
- Causa de la caída: proyecto Supabase pausado por inactividad (plan Free: pausa tras 1 semana); la app arrancaba y moría con `FATAL (ENOTFOUND) tenant/user`. Restaurado por el propietario; conexión verificada con SELECT 1 usando la DATABASE_URL de Render.
- Desplegado en `main` y **live** en Render: commit `bf4b562` + variables de modo aplicadas vía API (`production`, `invitation_only=true`, `external_auth_only=false`; antes solo GitHub OAuth de abril). Commit final `4118f43` (workflow+render.yaml) en remoto; su ejecución de Actions aún no aparecía en la API pública al cerrar esta nota.
- Verificación pública punto por punto: `/healthz` 200, `/healthz/db` 200 con db ok, `/register` 403 (cerrado), login con token CSRF presente, POST sin token 403, POST con token+credenciales erróneas 400 (CSRF distingue credenciales), logs Render sin ERROR y startup completo, headers `cache-control: no-store` y `referrer-policy: same-origin`.
- Healthcheck Hermes (job `735bc23f4712`, cada 5 min, sin LLM): exit 0, estado `{healthz: ok, db: ok}`. Workflow Actions de observación: horario (los 5 min viven en Hermes). El monitor y el cron de Render/Supabase **no garantizan** ausencia de pausas ni uptime.
- Pendiente: validación PM independiente, primera invitación real en producción, b04 (concurrencia) y autoría curricular (revisión del estudio antes de escribir libros).

## Pendientes de validación
- Finalizar wiring CSRF frontend y verificar invitación→edición/importación→guardado→propuesta→revisión→PDF→logout en demo nueva y aislada. La demo anterior no demuestra los cambios auth actuales.
- Validación PM independiente y revisión A/B simulada pendientes; revisión humana futura no ejecutada.
- Revisar investigación curricular y licencias con un revisor distinto del autor antes de editar índices definitivos o libros; luego revisión simulada por curso/materia y por unidad/ejercicio.
- No push, despliegue ni contactos externos. Cambios locales todavía pendientes de commits por hitos.
