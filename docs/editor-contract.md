# Contrato del editor (frontend)

Última actualización: 16 de septiembre de 2026. Alcance: `frontend/editor/**` y el bundle generado `app/static/js/editor-rich.js` (reconciliado con la fuente antes de este cambio; a partir de ahora la fuente es la única de verdad y el bundle se regenera con `npm run build:editor`). La lectura del servidor y el PDF mantienen sus propias reglas; este bundle no corrige sus limitaciones.

## Estado de la interfaz y del original

- Al abrir el libro, el frontend retiene `original` (valor exacto del formulario, incluidos `\r\n`). Si no hay ediciones, el docente guarda exactamente esos bytes: el backend no recibe un documento reescrito.
- `dirty` = el Markdown difiere del original o hay recursos pendientes. `invalid` = el documento actual no supera la verificación de integridad. `blocked` = el original contiene estructura no soportada: la edición visual se bloquea, el original se muestra en un textarea de solo lectura y Guardar queda deshabilitado con explicación.
- Estado visible con `role="status"` al inicio del formulario (Edición/Lectura, guardado, errores).

## Estructuras aceptadas

- Columnas `[[columns:2|3]]` / `[[col]]` / `[[/columns]]`: sin anidar, sin saltos de página dentro, número de columnas exacto. Un bloque sin cerrar o con más columnas que las declaradas **bloquea** en lugar de truncar o descartar.
- Saltos: `<!-- pagebreak -->` (mayúsculas permitidas) y `[[pagebreak]]`. Los marcadores dentro de vallas de código no se interpretan.
- Fichas: `[[worksheet:slug|Etiqueta]]` ⇄ enlace con `data-worksheet-slug`; sin marcas combinadas ni corchetes en la etiqueta.
- Imágenes: `![alt](assets/archivo.ext){: .doc-image .doc-align-left|center|right .doc-w-33|50|66|100}`; se conservan `data-asset-path` y títulos. Referencia servida con URL codificada (`/books/{id}/assets/…?branch=…`).
- Audio: solo la forma literal `<audio controls src="assets/…"></audio>`.
- Tablas: GFM simple (cabecera + filas de párrafo, sin celdas combinadas ni bloques internos; `resizable:false`, sin `colwidth`). Celdas con pipes escapados y negrita admitidas.
- Listas ordenadas conservan `start` (incluido 5., 6.); sublistas anidadas con sangría; código con vallas y lenguaje (`python`, etc.); tachado `~~…~~`.
- Texto literal se escapa (`\[`, `\(`, `\*`, `<`, `|`, `:` como entidades); reabrirlo no lo interpreta.
- Borradores con CRLF se preservan byte a byte mientras no se edite; tras editar se normaliza a `\n` (cambio visible en diff, documentado aquí).

## Estructuras no soportadas: bloquear, nunca truncar

`iframe`, comentarios HTML distintos del salto, notas al pie, tareas, atributos `{: ...}` distintos de las clases de imagen, HTML arbitrario, columnas malformadas, tablas irregulares/combinadas, bloques dentro de celdas, audio en celda, celdas multilínea, nodos de esquema desconocidos → `loadDocument` falla, el original permanece intacto y visible; guardar queda bloqueado hasta deshacer o descargar el borrador. El permiso de guardado lo revalida siempre el servidor; el bloqueo de cliente es protección de datos, no seguridad.

## Importación

- Botón «Importar .md/.txt» (formato explícito; **no** DOCX ni PDF, y un `.txt` se trata como texto literal, sin interpretar Markdown). UTF-8 estricto: si la codificación es inválida, se rechaza con mensaje. Máximo 2 MB.
- Siempre pide confirmación con informe (tamaño y avisos) y **añade al final del borrador**; no publica ni guarda por sí misma. Se puede deshacer. Avisa de que las imágenes del archivo no se importan.
- Pendiente de decisión de producto: DOCX (requiere conversor y fixtures propias) y PDF (texto de PDF digital como revisión manual; escaneado solo con OCR y aviso de confianza). No se anuncia ninguna de las dos.

## Guardado e integridad

- Cada actualización serializa y **re-parsea** (`checkedSerialization`): si el resultado no reproduce el documento, se bloquea el guardado y se conserva el último estado válido.
- Guardar usa `fetch` sobre `action` con `FormData` (incluye recursos pendientes); exige redirección same-origin a `/books/…` sin `error`. En fallo: estado, borrador y archivos se conservan y se puede reintentar; `beforeunload` avisa mientras haya cambios sin guardar.
- El guardado exige que toda referencia `assets/…` del borrador exista en la biblioteca o esté en la cola local; si falta, no se envía y se lista la que falta.
- Colisiones de nombres de recursos: nombres normalizados con desambiguación (`recurso-2.png`) consultando biblioteca y documento; quitar un recurso pendiente elimina también sus nodos del documento.
- Ctrl/Cmd+S global abre el diálogo una sola vez (listener en `document`, no por formulario).

## Pruebas y build

- `npm run build:editor` regenera el bundle; fuente y bundle reconciliados (el bundle anterior tenía ajustes que la fuente no tenía; ahora la fuente manda).
- Tests Node reales: `node --test tests/editor-contract.mjs tests/editor-ui.mjs` (19 pruebas: round-trips con acentos/tachado/código/lista desde 5/tablas/columnas/pagebreak/imágenes/fichas, escaping literal, bloqueos, vallas con marcadores dentro, nodo desconocido fail-closed, importaciones, CRLF, bloqueo malformado, fallos de preview/guardado sin pérdida).
- Build y tests verificados en verde; `npm audit` en 0 vulnerabilidades.

## Versiones (package-lock 3.30.5)

- Tiptap 3.30.5 coherente (core, starter-kit, image, link, placeholder, **table**) — resuelve GHSA-cp6q-959q-f8rh y GHSA-j95f-988m-3j2f; linkify-it/markdown-it actualizados → `npm audit` 0. Turndown eliminado (su conversión no se usaba para guardar).
- Se usa el Link interno de StarterKit (`link:false` antes; ahora sin doble registro), Placeholder y TableKit (`resizable:false`).

## Hooks para backend/plantillas (otro agente)

1. `editor.html` debe incluir `data-branch-label="{{ version_context.active_branch_label }}"` en el control de rama y mantener `data-editor-book-id`/`data-editor-branch`. El bundle reconciliado ya los usaba; la fuente lo necesitaba para el resumen de guardado.
2. Mantener `<input type="hidden" name="content" data-editor-input>` (con `type="hidden"`). El servidor sigue siendo la autoridad de permisos; el bloqueo visual del cliente no es seguridad.
3. El POST debe seguir aceptando `content` + archivos `assets` multipart como hasta ahora. Hook **sugerido** (no requerido): `base_revision` para conflictos entre pestañas.
4. El auto-inicializador busca `[data-rich-markdown-editor]` y no cambia clases CSS existentes; `<script defer src="/static/js/editor-rich.js"></script>` como hoy.
5. Para un follow-up del servidor (P0 de la auditoría): revisión base de edición concurrente y verificación servidor-side de estructura antes de commit; el cliente ya no envía documentos degradados, pero un cliente manipulado podría hacerlo.
