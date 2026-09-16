# Baseline de tests y aislamiento — 2026-09-16

## Alcance

Modificados exclusivamente `tests/test_app.py`, `tests/test_validation_regressions.py`,
`tests/conftest.py`, `scripts/journey_support.py` y este informe. Artefactos en
`test_plan/`. Sin commits, sin leer `.env` reales ni credenciales. No se han
modificado `app/`, `.agents/` ni el repositorio de contenido.

## Baseline inicial

- Recolección: **1 error, 2 tests recolectados**. `test_app.py` intentaba leer al
  importar un PNG de `../data/repo/.../column-demo-image.png`, inexistente.
  Registro: `test_plan/test-baseline-before.log`.
- La regresión de copia también falló con `FileNotFoundError` para
  `../data/repo/.../book.md` al ejecutarla sola.
- `build_client` solo vaciaba `get_settings()`; `app.main`, `app.database`,
  routers y servicios seguían conservando engines, sessionmakers y ajustes.
  Los tests sin contexto de cliente dependían del startup de otros tests.
- Se heredaban variables de proveedores y se permitía cargar `.env`.
  Estos riesgos se identificaron leyendo código, no leyendo secretos ni
  conectando a producción.

## Correcciones

- PNG autocontenido: primeros 45 bytes del PNG sintético ya incluido. Conserva
  cabecera y un IDAT truncado. Nueva prueba confirma que Pillow estricto lo
  rechaza y que `LOAD_TRUNCATED_IMAGES=True` lo recupera. Se conserva así la
  intención de la regresión PDF (normalización de raster roto recuperable).
  Una primera variante de 33 bytes era irrecuperable y causó un fallo de PDF:
  se corrigió la fixture, no el exportador ni la aserción de imagen embebida.
- `conftest.py` asigna temporales a `test_plan/tmp/` antes de la colección y
  rechaza `--basetemp` externo. Elimina `LIBRE_LIBROS_*`/`SUPABASE_*` heredadas.
  Fixture autouse aplica defaults explícitos locales por test y deshabilita
  dotenv tanto con el flag de entorno como con `Settings.model_config`.
- Se descarga todo `app.*` y se dispone el engine antes/después de cada test;
  no se recarga solo SQLAlchemy dejando modelos o sessionmakers antiguos.
  Dos casos parametrizados comprueban URL SQLite por `tmp_path`, identidad de
  `main.engine`/`SessionLocal` y ausencia de filas de un test anterior.
- `build_client` ejecuta startup con la DB nueva incluso si el test no usa
  `with client`. Los contextos explícitos existentes siguen funcionando.
- Se actualiza el mensaje de éxito de propuestas al literal actual:
  «Propuesta de cambio enviada para revisión.» La aserción antigua falló en
  la primera ejecución aislada; el código de app ya tenía el texto nuevo.
- Journeys y regresiones usan `../libre_libros_content`. Copian solo `books/`
  a un Git nuevo, sin heredar remotos, hooks o config del repositorio fuente;
  se excluyen `.git` y `.env*`. El contenido fuente no se modifica.
- Salidas restringidas a `test_plan/`; las ejecuciones nuevas no borran las
  anteriores. `build_env` filtra variables heredadas, configura SQLite local,
  OAuth desactivado, bootstrap local, admin ficticio y temporales locales.
  Deshabilita config global/system de Git y prompts. Los tests pueden hacer
  overrides después de estos defaults.
- Regresiones adicionales comprueban filtrado de entorno, rechazo de salida
  externa y ausencia de dotenv en proceso y subproceso con un archivo
  **sintético** (nunca el del propietario).

## Ejecución y resultados

Deps comprobadas una vez disponibles en `.venv` (sin instalación ni polling).
Desde `libre_libros_app`:

```sh
.venv/bin/python -m pytest tests/test_app.py tests/test_validation_regressions.py -q
```

`conftest.py` selecciona `test_plan/tmp/pytest-<único>` automáticamente. Para
ruta explícita, debe quedar dentro de `test_plan/tmp/`.

- Primera suite tras aislamiento: **23 passed, 2 failed** (fixture inicial
  demasiado truncada y literal de propuesta obsoleto, corregidos).
- Comprobación focal PDF + contrato PNG: **2 passed**.
- Suite con nuevas regresiones: **30 passed, 2 failed**. Registro:
  `test_plan/test-baseline-after.log`. Fallos posteriores corregidos en la
  ronda siguiente (ver «Resultados»).
- Hay warnings de deprecación en Starlette/httpx, AnyIO, passlib/crypt y
  `datetime.utcnow`; no se han ocultado.

## Ronda B0x (continuación, mismo ownership)

Contexto recibido del orquestador: cambios B01–B06 en `app/routers/books.py`,
frontend PDF integrado en `app/services/books.py`/`pdf_export.py`, tests PDF
40 verdes con pypdf. Al retomar, `tests/test_app.py` tenía **8 fallos**.

### Causas y arreglos (números)

1. PNG de subida: la app ahora valida uploads con Pillow de forma estricta y
   recodifica (seguridad). `TEST_PNG` era un PNG de 1×1 base64 que ya no
   pasaba la validación (400) y además ReportLab no incrustaba imagen.
   **Arreglo**: `TEST_PNG` generado con Pillow en memoria
   (`Image.new("RGB", (16, 16)).save(BytesIO(), "PNG")`). Resultado:
   `test_editor_save_persists_uploaded_assets_in_repository` y
   `test_pdf_export_includes_embedded_images` en verde. Como el backend
   recodifica el raster, la aserción compara tamaño/píxeles, no bytes.
2. `BROKEN_RASTER_PNG` se conserva solo para la regresión de placeholders:
   nueva prueba `test_pdf_export_replaces_corrupt_raster_with_placeholder`
   valida con `pypdf` que un raster corrupto produce el texto
   «Imagen no disponible (…)» y que el PDF no incrusta imágenes.
3. Contrato de seguridad SVG (deliberado, B0x): ahora se sirve como
   `application/octet-stream` con `Content-Disposition: attachment` y
   `X-Content-Type-Options: nosniff`. La prueba de detalle de libro comprueba
   esos tres encabezados y que el contenido sea el SVG esperado (no se borra
   la prueba, se actualiza el contrato).
4. Ramas docentes `users/id-<ID>` (cambio intencional de
   `app/services/permissions.py`; antes `users/<slug>`):
   - `test_public_book_edit_link_falls_back_to_teacher_branch` pasa usando el
     objeto `User` real (con `id`) leído de la DB, no el fake `UserLike`.
   - En `test_teacher_can_propose_and_org_admin_can_accept_school_course_version`
     se elimina el fake sin `id`; ahora usa el usuario real de la DB. Pasa.
   - `test_public_book_prefers_legacy_teacher_branch_when_repo_already_has_it`
     se reescribe como `test_public_book_does_not_claim_legacy_branch_based_on_display_name`:
     la app ya no deriva la rama del nombre visible; crea `users/id-<ID>` y
     deniega `users/ana-profe` con 403 (verificado).
5. Red bloqueada sin romper `TestClient`: fixture `block_external_network` en
   `tests/conftest.py` que rechaza `socket.connect`/`connect_ex`/`getaddrinfo`
   a hosts no loopback; loopback permitido. Regresión añadida en
   `test_validation_regressions.py`.
6. Sin imports de `app` al importar los tests (colección limpia) y startup
   aislado por test vía `build_client`/conftest, sin dotenv.

### Fallos restantes (fuera de ownership; no se debilitan)

- `test_editor_shows_asset_library_and_snippets` — marcada **xfail estricto**
  con diagnóstico: la biblioteca del editor abre la rama personal
  `users/id-1/base/primaria` pero muestra «Todavía no hay recursos en esta
  rama» aunque `aula.png`/`cover.svg` están committeados en `main` (verificado
  con `git ls-tree` en el repo fixture). La prueba vuelca
  `editor-response.html` en el tmp para el propietario de `app/`. La
  biblioteca debería aplicar el fallback de lectura a la rama base.
- `test_public_book_does_not_claim_legacy_branch_based_on_display_name`:
  `GET /books/1?workspace=personal` → **404** (esperado 200 con el enlace de
  edición de la rama propia). Fricción real de backend; central debe arreglar
  el fallback de workspace. No debilitada.
- `test_book_detail_uses_school_course_and_workspace_selectors`:
  `GET /books/1?school=colegio-selector&course_version=Primaria&workspace=shared`
  → **404**. Fricción real del flujo docentes/escuela. No debilitada.
- Ambos 404 ocurren tras login correcto y con organización creada en DB; no
  dependen de red externa (el bloqueo de red está activo en todas las pruebas
  y las 40 demás rutas funcionan). Reproducción: pytest con la suite completa
  o los dos tests en solitario.

### Ejecución final

- `tests/test_app.py`: **31 passed, 2 failed, 1 xfailed** (xfail estricto
  documentado arriba). Registro: `test_plan/test-suite-final.log`.
- `tests/test_validation_regressions.py`: **6 passed**.
- Targeted de la ronda: 13 passed (`test_plan/test-app-targeted-final.log`).

## Coordinación necesaria

1. `app/config.py` ya tiene un cambio concurrente que hace
   `Settings(_env_file=env_file or None)` con `LIBRE_LIBROS_ENV_FILE`.
   **Mantener ese cambio**: `journey_support.build_env` fija el flag vacío para
   todos los workers de uvicorn. No es necesario modificar el launcher ni
   `Settings.model_config` en el proceso padre (eso no llega a los workers).
   La regresión de subproceso verifica ese contrato. No se ha tocado config.
2. Backend (otra sesión): arreglar los dos 404 de workspace (`workspace=personal`
   y `school=...&workspace=shared` en `GET /books/1`) y el fallback de la
   biblioteca de assets del editor; luego eliminar la marca `xfail` de
   `test_editor_shows_asset_library_and_snippets` (estricta).
3. `scripts/validator_playwright_smoke.py` tiene funciones propias que todavía
   copian `data/repo` y heredan entorno. Otros launchers independientes, como
   `gitlab_debug_playwright_smoke.py`, necesitan revisión separada. No se han
   ejecutado ni modificado, al estar fuera de la propiedad asignada.
4. Los helpers realizan commits **solo en repos de fixtures temporales**, como
   exige la prueba de Git. No se han creado commits en app ni contenido.
