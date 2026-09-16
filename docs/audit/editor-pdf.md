# Auditoría del editor, importación y PDF

Fecha: 16 de septiembre de 2026. Alcance: `libre_libros_app` (frontend, plantillas, JS, transformación/guardado de documentos, recursos y PDF) y `../libre_libros_content`.

**Dictamen:** hay un editor visual útil como punto de partida, pero todavía no cumple «importar fácil y producir PDF sin romper tablas, imágenes, saltos y acentos». El problema principal no es cosmético: existen transformaciones con pérdida silenciosa. El PDF actual es una salida simplificada de texto e imágenes, no una reproducción de la maquetación del editor. No debe presentarse como PDF fiel ni prometerse PDF perfecto tras un cambio de motor.

## 1. Método y límites de evidencia

- Inspección de código, plantillas, bundle servido, manifiestos/lockfile, pruebas, scripts de validación y corpus de contenido. Referencias relativas a `libre_libros_app`, salvo prefijo `../libre_libros_content`.
- Comprobaciones **en memoria**, sin servicios: extracción de funciones JS puras con Node/VM; ejecución aislada por AST de la función Python que reescribe URLs; inventario de Markdown/referencias; inspección de chunks y CRC/zlib de PNG con biblioteca estándar.
- No se leyó ningún `.env` ni archivo de secretos. No se importó/inicializó la aplicación, ni se instanció un cliente de repositorio. No se arrancaron servicios, navegador o suite; no se instalaron dependencias. Única escritura de esta auditoría: este informe.
- No hay una validación visual de PDF generado, resultados de pytest ni porcentaje de cobertura ejecutada. El Python del sistema no tiene instalados `markdown`, `bleach`, `reportlab`, `Pillow`, `svglib` o `pypdf`; esto no demuestra que falten en producción.
- «Comprobado» indica salida de comprobación aislada o contrato inequívoco del código; los riesgos que requieren navegador/proveedor se distinguen explícitamente.

## 2. Flujo real, no el prometido

### Entrada de contenido

1. La incorporación existente es **técnica, desde un repositorio Git configurado**. `app/services/bootstrap.py:62-80` enumera `books/**/book.md`, deduce curso/materia/título de carpetas y registra los libros. No es un importador de documentos de usuario.
2. Crear libro utiliza un formulario de metadatos, con selección explícita de repositorio (`app/templates/books/form.html:11-52`). No hay selector de documento fuente.
3. No se encuentra ruta, formulario ni dependencia de conversión DOCX/ODT/PDF, extracción de texto PDF u OCR en el ámbito revisado. El único selector del editor acepta imágenes y MP3 (`app/templates/books/editor.html:27`). Arrastrar un PDF no lo importa: el JS lo trata como audio y el guardado normalmente lo rechaza por tipo.
4. Pegar desde Word/Google Docs depende del comportamiento genérico de Tiptap/ProseMirror y de su esquema; no existe asistente de pegado/importación con informe de pérdidas, recuperación de imágenes del portapapeles o vista de confirmación.

### Edición y guardado

- `GET /books/{id}/edit`: decide versión editable, asegura rama y lee Markdown, con fallback al libro base (`app/routers/books.py:641-681`). Este GET **puede crear una rama**; no se llamó durante la auditoría.
- La plantilla entrega Markdown en un input oculto y un host visual; carga `app/static/js/editor-rich.js` (`app/templates/books/editor.html:3-4,23-27,221-223`). `base.html:8` también carga el antiguo `editor.js`, cuyo editor solo se inicializa para `[data-markdown-editor]` (`editor.js:729-737`), no para este formulario. Ambos tienen código de lectura paginada; el atributo `data-document-ready` evita inicializarla dos veces.
- Pipeline activo: Markdown → conversiones regex de imágenes/fichas/columnas/saltos → `marked` → esquema Tiptap → **serializador JSON propio** → Markdown oculto. Se serializa inmediatamente después de abrir, aunque el docente no haya tocado nada (`frontend/editor/index.js:855-881`). `buildTurndown()` está definido, pero **no se utiliza para guardar** (`:304-363` frente a `:484-486,716-720`).
- Imágenes/MP3 seleccionados se insertan con URL `blob:` y se acumulan en `DataTransfer`. Guardar abre un diálogo y envía Markdown + recursos por multipart (`frontend/editor/index.js:748-788,818-840`; plantilla `:334-384`). No se guarda mientras se escribe.
- Backend comprueba permiso, prepara recursos y escribe documento y recursos mediante `repo.write_files` (`app/routers/books.py:685-737`). La comprobación de no-op es byte a byte, no semántica. Guardar **no crea por sí mismo una propuesta**; esta tiene un formulario separado en `app/templates/books/detail.html:164-168`.

### Lectura y PDF

- Lectura: POST `/books/preview` → `build_book_document` → Python Markdown → Bleach → reescritura de recursos → `_document.html`, que marca `page.html` como seguro (`app/routers/books.py:1152-1160`; `app/services/markdown_utils.py:29-61`; `app/templates/books/_document.html:51-59`).
- La paginación de lectura solo separa marcadores manuales. **No mide el tamaño A4 ni el desbordamiento físico**. El CSS oculta todas las páginas salvo la activa (`app/static/css/app.css:1247-1256`). No se encontró CSS `@media print`; imprimir la página del navegador no es alternativa segura para obtener el libro completo.
- Exportar está en el detalle y usa **el contenido ya guardado de la rama seleccionada**, no el borrador del editor (`app/templates/books/detail.html:46-48`; `app/routers/books.py:1186-1208`). No hay exportación específica de ficha en las rutas revisadas; las fichas enlazadas tampoco se anexan al PDF del libro.
- PDF: ReportLab A4, título de BD y procesado línea a línea. Las columnas se aplanan antes del renderizado; las imágenes se leen del repositorio y convierten con svglib/Pillow (`app/services/books.py:44-104,112-191`; `app/services/book_content.py:53-81`). No usa el HTML de lectura ni su CSS.

## 3. Hallazgos prioritarios: integridad y seguridad

Prioridades: **P0** antes de exponer importación/contenido no confiable o recomendar guardado general; **P1** para un piloto docente fiable; **P2** mejora posterior. La prioridad combina impacto y frecuencia, no equivale a CVSS.

### E01 — P0: las tablas no tienen un recorrido seguro

**Evidencia:** `frontend/editor/index.js:859-874` no incorpora nodos Table/TableRow/TableCell/TableHeader; `:453-472` no serializa tablas. `marked` sí reconoce tablas GFM (`:18-21`), pero el esquema no conserva su estructura. Al cargar se reescribe inmediatamente el input (`:881`).

Además, `app/services/markdown_utils.py:12-21` no permite `table`, `thead`, `tbody`, `tr`, `th`, `td` (no pertenecen a la allowlist básica de Bleach). Aunque Python Markdown habilita tablas, Bleach escapa esas etiquetas por defecto; la lectura puede enseñar HTML literal. El PDF no tiene ninguna rama Table: imprime las filas Markdown como párrafos (`app/services/books.py:67-101`).

**Consecuencia:** ni introducir una tabla por repositorio, ni pegarla desde Word, ni agregar solo un botón «Tabla» resuelve el problema. Abrir/guardar puede destruir celdas/estructura; lectura y PDF fallan por motivos independientes.

**Prueba de aceptación:** tabla de 3 columnas con encabezados, acentos, negrita, enlaces, pipes escapados y 50 filas. Abrir sin tocar no modifica nada; editar una celda conserva las restantes; lectura contiene tabla real y no `&lt;table&gt;`; PDF conserva filas/columnas y repite encabezados cuando corresponda. Inicialmente excluir explícitamente celdas combinadas si no se implementan.

### E02 — P0: round-trip con pérdida incluso sin cambios

**Evidencia:** serialización propia en `frontend/editor/index.js:365-486` y sincronización inicial en `:881`; mismo flujo en bundle `app/static/js/editor-rich.js:25286-25372,25715`.

Comprobaciones aisladas del serializador:

| Entrada JSON Tiptap | Salida observada | Pérdida |
|---|---|---|
| `codeBlock(language=python, text=print(1))` | `print(1)` | Cercas y lenguaje desaparecen |
| Texto con marca `strike` | texto sin marca | Tachado desaparece |
| Lista ordenada con `start: 5` | `1. Cinco` | Reinicia numeración |
| Texto literal `[literal](https://example.org)` | el mismo texto, sin escapar | Al reabrir se interpreta como enlace |

El serializador solo trata marcas bold/italic/link; ignora code, strike, underline y otros atributos. Tampoco escapa sintaxis Markdown literal en texto/alt/enlaces. StarterKit permite más estructuras de las que guarda. Los párrafos vacíos se descartan; espacios y separaciones se normalizan (`:456,475-481`). Se deshabilitan reglas horizontales, aunque hay una rama de serialización para ellas (`:471,861`).

**Consecuencia:** incluso una corrección de una palabra puede perder formato ajeno. El no-op del servidor (`app/routers/books.py:701-716`) no protege: recibe el documento ya transformado. La guía que dice que ese diff «no es un fallo» y promete detección de no-op (`docs/user-guide.md:131-147`) necesita matices y corrección.

**Mínimo:** conservar original hasta una transacción realmente modificadora; detectar estructuras no compatibles antes de habilitar guardado visual y ofrecer lectura/conservación del original; hacer simétrico el contrato parser/serializador. Preservar bytes sin edición y semántica dentro del subconjunto soportado tras editar. No arreglarlo solamente cambiando la comparación no-op.

### E03 — P0: inyección HTML tras la sanitización de lectura

**Comprobado en memoria:** `app/services/markdown_utils.py:116-123` concatena `branch_name` sin codificación/escape dentro de un atributo, **después de Bleach** (`:37-46`). Para HTML limpio `<img src="assets/a.png" alt="safe">` y rama `main" onerror="alert(1)` produce:

```html
<img src="/books/1/assets/a.png?branch=main" onerror="alert(1)" alt="safe">
```

El endpoint público `/books/preview` acepta ese parámetro sin validación (`app/routers/books.py:1152-1160`); la plantilla lo inserta con `safe` y el frontend mediante `innerHTML` (`frontend/editor/index.js:710-711`). La construcción de un atributo ejecutable está demostrada; **no se ejecutó una explotación en navegador ni se comprobó una ruta de entrega a otra sesión**.

**Mínimo:** construir query con URL encoding y escapar contexto HTML, idealmente reescribir un DOM antes de la sanitización final; no concatenar contenido de usuario después de sanear. Pruebas con comillas, ampersand, fragmentos y eventos tanto en lectura como preview.

### E04 — P0: recursos no confiables, MIME declarado y rutas sin confinamiento

- `_validate_asset_upload` únicamente comprueba MIME declarado y bytes (`app/routers/books.py:235-264`); no verifica firma, decodificación, extensión congruente, dimensiones o SVG activo. Puede aceptarse HTML con `Content-Type: image/png` y nombre `.html`; `serve_book_asset` elige MIME por **extensión** y lo sirve inline en el mismo origen (`:1175-1183`). Es una ruta concreta para contenido activo almacenado si un editor malicioso envía multipart; no se ensayó en navegador. SVG también requiere una política explícita; `<img>` y navegación directa a SVG no tienen el mismo aislamiento.
- `_pdf_asset_loader` solo comprueba prefijo `assets/` (`:267-272`); acepta `assets/../...`. `serve_book_asset` concatena igualmente un path libre (`:1163-1178`). En proveedor local, al fallar `git show`, `read_binary` abre el path de filesystem sin resolver/confinar (`app/services/repository/local_git.py:109-125`). Puede salir del directorio del libro y, con suficientes `..`, del repositorio. **No se intentó leer ningún archivo externo ni secreto.**
- Autorización de lectura de recursos/PDF es por libro, no por pertenencia a rama (`app/routers/books.py:1171-1178,1193-1198`). Si las versiones personales pretenden ser privadas dentro de un libro público, no hay esa garantía aquí; decidir el contrato y validarlo.

**Mínimo:** allowlist de formatos reales; verificar imagen con decodificador y límites de píxeles; extensión/cabecera coherentes; rasterizar SVG o servirlo en origen aislado con política restrictiva; bloquear traversal absoluto/relativo y fallback fuera de rama; autorización de versión. Pruebas usando exclusivamente archivos canario en repositorio temporal, nunca archivos reales del host. Revisar también recursos externos dentro de SVG antes de permitir su procesamiento con svglib; no se afirma aquí un comportamiento de red concreto de esa dependencia.

### E05 — P1: errores de parser de columnas y de saltos

**Comprobado con la función JS aislada** (`frontend/editor/index.js:258-297`):

- `Antes\n[[columns:2]]\nTexto sin cierre importante` se convierte en `Antes` y un contenedor de columnas vacío. Se pierde todo el texto tras el marcador abierto.
- Un bloque declarado de 2 columnas con 3 cuerpos descarta el tercero por `.slice(0, count)` (`:289-290`). El parser Python conserva el original si no hay cierre y no trunca los cuerpos (`app/services/book_content.py:40-44,107-128,131-150`): editor y lectura discrepan.
- El renderer de `ColumnsBlock` consulta `HTMLAttributes.count`, pero `renderHTML` del atributo genera `data-count` (`frontend/editor/index.js:59-79`). La clase puede terminar en `editor-columns-2` aunque `data-count=3`. Validar en DOM real las **tres columnas visuales**, no solo su número de nodos.
- Frontend solo sustituye el literal exacto `<!-- pagebreak -->` (`:238-240`), pero backend admite `[[pagebreak]]`, variantes de espacios y mayúsculas (`app/services/books.py:21`). Los comentarios con variantes se pierden en Tiptap; los tokens pueden quedar como texto.
- Lectura elimina páginas vacías al dividir (`app/services/markdown_utils.py:72-74`); PDF procesa cada marcador y puede crear páginas vacías. Un salto dentro de columnas rompe el bloque antes del parser de lectura. Los marcadores también se procesan sin tener en cuenta bloques de código.

**Mínimo:** un contrato compartido para marcadores válidos, validación de estructura y prohibición explicada de anidación/saltos dentro de columnas si no se soportan. Ante error, conservar original; nunca truncar silenciosamente.

### E06 — P1: integridad de multimedia y borradores

- Quitar un recurso pendiente solo lo elimina de `DataTransfer`, **no elimina/actualiza sus nodos del documento** (`frontend/editor/index.js:631-640`). Se puede guardar una imagen referenciada que nunca se subió. Quitar el bloque visual tampoco retira el upload pendiente (`:992-994`).
- No hay resolución de colisiones. `Foto 1.PNG` y `Foto-1.png` terminan en la misma ruta; la deduplicación usa nombre/tamaño/fecha, no el nombre final (`:149-163,750-758`). Servidor escribe las rutas sin detectar existencia/duplicados (`app/routers/books.py:243-250,723-725`). En local el último archivo sustituye al anterior (`local_git.py:152-155`). Puede cambiar otras apariciones de esa imagen sin intención del docente.
- El normalizador JS y `python-slugify` no son el mismo algoritmo: JS elimina caracteres no ASCII y usa fallback `asset`, servidor translitera y no tiene ese fallback (`frontend/editor/index.js:149-163`; `app/services/books.py:107-109`). Nombres de otros alfabetos o solo símbolos pueden dejar referencias distintas a lo guardado. La normalización española básica no implica corrupción del cuerpo de texto.
- La UI promete `image/*`, pero PDF solo reconoce rutas `assets/` o `./assets/` y una imagen Markdown que ocupe **toda la línea**. Imágenes remotas, `data:`, HTML `<img>`, imágenes inline, rutas con espacios o títulos tratados por la regex JS pueden divergir (`frontend/editor/index.js:14-16,205-224`; `app/services/books.py:22-24,75-88`; router `:267-272`).
- El audio que genera el editor tiene `src` en `<audio>`, pero Bleach solo permite `controls` en esa etiqueta (`app/services/markdown_utils.py:19`): el recurso deja de reproducirse en lectura. PDF imprime el HTML como texto escapado.
- Preview no comprueba `response.ok`, no captura errores, no cancela respuestas antiguas ni indica carga (`frontend/editor/index.js:700-714`). Guardar es navegación de formulario sin retención de borrador en error; no se encuentran autosalvado, estado sucio o aviso al abandonar. La guía recomienda cerrar el navegador (`docs/user-guide.md:165-166`), lo que puede perder cambios no guardados.

**Mínimo:** nombre definitivo asignado por servidor (o contrato único) y política de reemplazo explícita; estado común nodos/uploads; chequeo de referencias antes de guardar; borrador recuperable y aviso al salir; error de guardado mostrado sin destruir el formulario. Para borradores de material sensible, limitar persistencia local por usuario y limpiar al salir.

### E07 — P1: edición concurrente puede sobrescribir cambios ya guardados

El formulario no transporta SHA/revisión base (`app/templates/books/editor.html:23-27`); API y `RepositoryFileWrite` tampoco tienen precondición de versión (`app/routers/books.py:685-725`; `app/services/repository/base.py:7-10,58-67`). Dos pestañas que editaron la misma versión pueden guardar secuencialmente y la segunda reponer su texto antiguo completo. El lock local serializa escrituras, **no detecta conflictos editoriales**. GitHub hace PATCH no forzado y protege algunas carreras durante la operación (`github_api.py:142-176`), pero obtiene la revisión actual al guardar, no la que leyó el docente.

**Prueba:** A y B abren N; A guarda N+1; B guarda su borrador basado en N. Debe recibir conflicto recuperable/comparación, nunca éxito que elimine la edición de A. Mínimo: revisión base obligatoria, precondición por documento y UX de recuperar/copiar/comparar; mantener lote documento-recursos consistente.

### E08 — P1: fuente frontend y bundle servido han divergido

**Diferencia verificada, no hipotética:** fuente `frontend/editor/index.js:650-658` busca `select[name="branch_name"]`; plantilla tiene input oculto (`editor.html:26`). Reconstruir esa fuente haría que el resumen diga «Sin seleccionar». El bundle servido ya usa `[name="branch_name"]` y `data-branch-label` (`app/static/js/editor-rich.js:25516-25523`); también difiere su listener (`:25721` frente a fuente `:889`). **No atribuir ese bug de resumen al bundle actual**.

`Dockerfile:12-15` instala Python y copia el repositorio, pero no ejecuta build JS. `scripts/build-editor.mjs:3-10` sí define cómo hacerlo. Cambiar fuente no cambia la UI desplegada; reconstruir ahora puede revertir arreglos manuales del bundle.

**Mínimo:** reconciliar fuente sin perder cambios del bundle, bundle generado reproducible en CI y test que falle si no coincide. No editar minificado/generado como fuente de verdad. StarterKit 3 ya incluye Link (`editor-rich.js:22972`), mientras se añade `WorksheetLink` heredando ese nombre; desactivar Link del StarterKit para evitar duplicidad. El bundle contiene el aviso de extensiones duplicadas (`:13658`); impacto funcional pendiente de validar en navegador.

## 4. PDF: capacidades reales y límites

| Elemento | Comportamiento actual y evidencia | Evaluación |
|---|---|---|
| Texto/acentos | UTF-8 al guardar (`routers/books.py:704`); estilos estándar ReportLab sin registro de fuentes (`services/books.py:51-63`) | No hay evidencia de conversión ASCII del cuerpo. Helvetica cubre español común, pero no garantiza Unicode completo, combinantes, matemáticas, pictogramas o emoji. Probar extracción y aspecto |
| Tablas | No parser/nodo de tabla en el exportador; cada línea acaba en Paragraph (`:67-101`) | No soportadas como tablas |
| Columnas | Se sustituyen por secciones «Columna 1», «Columna 2» (`book_content.py:71-78`) | Pérdida deliberada de maquetación; el PDF no cumple la historia de varias columnas fieles |
| Negrita/cursiva/enlaces | `escape(line)` en vez de Markdown inline (`books.py:90-100`) | Marcadores literales; enlaces Markdown no se transforman deliberadamente en enlaces PDF |
| Encabezados/listas | Solo H1-H3 y detección simple por línea; `.strip()` quita indentación | H4-H6, código, citas y listas anidadas pierden semántica/formato |
| Imágenes locales | SVG por svglib; raster convertido a PNG; escala proporcional, sin agrandar (`:140-179`) | Base razonable para formatos decodificables; no garantía para todo `image/*` |
| Posición/tamaño imagen | `doc-w-*` soportado, alto máximo 42% de página; `hAlign="CENTER"` fijo (`:64-65,152,161,182-191`) | Ignora izquierda/derecha elegidas en editor; puede volver ilegible una imagen con texto |
| Imágenes inválidas | Fallback textual visible si no hay bytes o falla conversión (`:121-131`) | No es pérdida silenciosa en esos casos, pero no hay informe previo; `asset_loader()` está fuera del try (`:124`), un fallo de proveedor puede abortar toda la descarga |
| Saltos | PageBreak explícito y paginación automática ReportLab | No corresponde a las páginas lógicas de lectura; títulos, espacios y límites de imagen cambian la distribución |
| Fichas/audio | Ficha se vuelve «Ficha: etiqueta»; no incluye contenido enlazado. Audio queda literal | Debe advertirse y decidir anexos/enlaces alternativos |
| Título | `Paragraph(book.title, ...)` no escapado (`:63`); además se procesa el H1 del Markdown | Puede duplicar título y tratar etiquetas del título como markup ReportLab; probar `A & B`, `<b>`, `<img>` sin permitir interpretación activa |

No hay plantilla de impresión común, índice PDF generado, números de página/cabeceras ni perfil tipográfico verificable. `ImageFile.LOAD_TRUNCATED_IMAGES=True` es global (`app/services/books.py:27`): aceptar una imagen truncada no repara su integridad ni su valor docente. No reemplaza validación del archivo original.

### Propuesta mínima de salida PDF

1. **Inmediato:** etiquetar esta salida «PDF simplificado», mostrar advertencias de tablas/columnas/formato no compatible antes de descargar, informar recursos ausentes. No presentar «Lectura» como previsualización del PDF.
2. **Para cumplir tablas y maquetación básica:** usar un render intermedio validado y compartido con lectura, con tablas semánticas y recursos resueltos a una revisión inmutable. Evaluar un único motor HTML/CSS paginado (por ejemplo Chromium headless con una plantilla de impresión dedicada, o WeasyPrint tras validar sus dependencias) frente a implementar tablas y frames manualmente en ReportLab. No sumar un segundo motor permanentemente sin necesidad.
3. CSS de impresión específico: A4/márgenes, encabezados de tabla repetibles, `break-inside` como preferencia y no garantía, imágenes con límites de ancho/alto, saltos explícitos, todas las páginas visibles, sin controles de la aplicación. Fuentes locales con licencia y cobertura española/Unicode necesaria, embebidas y cargadas antes de imprimir.
4. Recursos servidos por bytes/identificadores verificados: sin URLs arbitrarias, `file://`, red saliente indiscriminada o SVG activo. Timeout, presupuesto de páginas/píxeles/bytes y límite de concurrencia. El endpoint actual procesa síncronamente toda la salida; no hace falta una cola compleja para el piloto, sí límites claros.
5. Validar casos límite antes de elegir motor: fila más alta que una página, tabla ancha, imagen con leyenda larga, columnas largas, marcadores dentro de columnas y caracteres no soportados. Para casos imposibles de mantener en A4, ofrecer ajuste o advertencia explícita, nunca truncado silencioso.

## 5. Estado de `../libre_libros_content`

Inventario de solo lectura: **16 libros**, **2 fichas**, `BASE_CURRICULAR.md` (19 Markdown en total); **25 saltos manuales**, **12 bloques de columnas**, **14 referencias de imagen** y **2 enlaces de ficha**. No se encontraron filas de tabla Markdown que empiecen con `|`. Assets: 9 SVG, 4 PNG, 1 JPG y 9 `.gitkeep`.

- Referencia rota confirmada: `../libre_libros_content/books/infantil/conocimiento-del-medio/conocimiento-del-medio-infantil/book.md:17` apunta a `assets/imagen.png`, inexistente. Hay una captura PNG con otro nombre en esa carpeta; **no se infiere que sea el reemplazo correcto**.
- PNG dañado confirmado mediante CRC y zlib: `../libre_libros_content/books/primaria/lengua/lengua-primaria/assets/column-demo-image.png`, 68 bytes, 1×1; chunk IDAT con CRC incorrecto y error de checksum al descomprimir. Se referencia como «Apoyo visual para exposición» en `book.md:77`. Incluso si Pillow tolera el archivo, una imagen 1×1 no aporta ese apoyo visual. No se modificó.
- Posibles restos editoriales a revisar con autor, **no borrar automáticamente**: `conocimiento-del-medio-infantil/book.md:7` termina en `AAAA`; `:15` contiene «otro punto importante».
- Muchas tildes ya faltan en el original (`lengua-primaria/book.md:7,22,28`; `../libre_libros_content/README.md:4,8-11`); hay también `pequeñas` y `Diseñar` correctamente codificados. No atribuir ausencias originales al PDF, ni «corregir» automáticamente normalizando todo a ASCII.
- Corpus corto, mayormente narrativo y listas. No prueba tablas, fórmulas, Unicode amplio, documentos largos, pegado Office, notas al pie, imágenes de gran tamaño o saltos difíciles. Añadir fixtures sintéticos aparte del contenido docente. Revisar textos y recursos con docentes, no confundir una demo funcional con revisión curricular/editorial completa.
- Bootstrap importa títulos a partir del slug, no del H1 (`app/services/bootstrap.py:76-99`), y hace públicas las entradas sincronizadas (`:100-102,112`). Es adecuado solo si se ha definido expresamente como repositorio base público, no como importador genérico de documentos privados.

## 6. Facilidad de uso para docentes no técnicos

**Lo aprovechable:** edición visual, resumen de guardado opcional, biblioteca multimedia, arrastrar imágenes, controles de tamaño/alineación y fichas, cambio rápido edición/lectura, etiquetas accesibles `sr-only`, atajo Ctrl/Cmd+S y diálogo nativo.

**Gaps que afectan tareas básicas:**

- No «Importar documento». Selector de recursos no sustituye importar una unidad didáctica ni un PDF.
- Sin tabla, deshacer/rehacer visibles, lista numerada o edición visible de enlace; StarterKit puede exponer acciones por atajo sin que el serializador las preserve. Título solo inserta H2 (`frontend/editor/index.js:899-907`).
- Botones exclusivamente con iconos, etiquetas ocultas/tooltips: probar descubribilidad con personas reales y móvil. El tablist no implementa roles completos de tab/tabpanel ni navegación por flechas (`editor.html:36-56`; JS `:684-697`). No es una certificación de accesibilidad.
- Si el bundle falla, host vacío e input oculto, sin editor alternativo ni error comprensible. DataTransfer, diálogo, APIs de selección y drag/drop necesitan pruebas Firefox/Safari además de Chromium.
- Falta estado inequívoco «Cambios sin guardar / Guardando / Guardado / Error» y recuperación. «Documento actualizado» en checklist solo cuenta marcadores, **no comprueba integridad ni persistencia**.
- Exportar se oculta si no hay `edit_branch` (`detail.html:46-48`) aunque la ruta exige poder ver, no editar. Una persona lectora con sesión puede tener permiso de exportación pero no botón.
- Guía desalineada: promete que «nada se pierde» (`docs/user-guide.md:12-13`), que guardar crea propuesta (`:55-63`) y enseña Markdown como interacción principal (`:95-112`). Cambiar a pasos reales y limitaciones explícitas. Git conserva commits anteriores, no borradores que nunca llegaron a guardarse.

### Importación mínima priorizada (funcionalidad nueva, no existente)

1. Un botón **Importar documento** separado de **Añadir imagen/audio**. Flujo «Elegir → Revisar lo importado → Añadir al borrador», sin publicar ni sustituir el libro de inmediato.
2. Primera entrega: TXT/Markdown UTF-8 con validación de estructura/recursos; pegado HTML saneado con informe de elementos no soportados. DOCX puede ser la siguiente prioridad de producto si es el formato principal de los docentes, pero necesita conversor/fixtures propios, no renombrar extensión.
3. PDF: ofrecer inicialmente adjuntar original o extraer texto **con revisión obligatoria**. Diferenciar PDF con texto de escaneado; si no hay OCR, decirlo antes de aceptar el trabajo. Con OCR, indicar confianza y pedir revisión de acentos, orden de lectura, tablas e imágenes. Un PDF describe posiciones, no un documento editable: no prometer recuperar la estructura original.
4. Preservar el archivo fuente, permisos/licencia y un informe de conversión; revertir la importación como una acción. Prohibir ejecución de macros/HTML activo, rutas ZIP peligrosas y extracción sin límite. Si se añade conversor externo, limitar CPU/memoria/tiempo y red.
5. Mensajes orientados al docente: «Se han importado 8 apartados y 3 imágenes; esta tabla necesita revisión», en vez de JSON, excepción en inglés o «rama/commit».

## 7. Dependencias, build y cobertura real

### Dependencias

- `package.json:8-14` declara Tiptap `^3.0.7`, marked `^16.3.0`, Turndown `^7.2.1`. El **lockfile resuelve** Tiptap core/StarterKit **3.21.0**, marked **16.4.2**, Turndown **7.2.2** y esbuild **0.25.12**. No confundir mínimos declarados con versiones instaladas.
- No hay dependencia de tablas Tiptap ni tests JS en los scripts npm (`package.json:4-18`). Hay tres caminos de Markdown con contratos diferentes: marked, Python Markdown y parser PDF de líneas; Turndown añade mantenimiento aunque su función de conversión no se invoque.
- `requirements.txt:12-16`: Markdown 3.10.2, Bleach 6.3.0, ReportLab 4.4.10, svglib 1.5.1. Pillow se usa directamente pero llega transitivamente, sin pin explícito; lo mismo debe evaluarse para dependencias transitivas de SVG/fuentes. Esto afecta reproducibilidad, no demuestra una vulnerabilidad conocida.
- `requirements-validator.txt:2` fija Playwright 1.54.0. No se hizo consulta de CVE, `npm audit` ni instalación; no se emite certificado de seguridad o actualidad de dependencias.
- Contenedor Python slim instala git, no motor HTML/CSS paginado ni paquete de fuentes explícito (`Dockerfile:1-15`). Cambiar motor obliga a medir tamaño, RAM, dependencias del sistema y tiempos del entorno de despliegue.

### Qué prueban los tests presentes

- `tests/test_app.py:187-227`: HTML de detalle/preview, URLs de recursos, clases de columnas y marcadores de página.
- `:230-255`: textos de la plantilla del editor, **sin ejecutar su JS**.
- `:258-321`: guardado de ficha y recurso mediante POST directo; no round-trip visual ni importación.
- `:387-401`: HTTP 200, MIME PDF, cabecera `%PDF` y presencia de `/Subtype /Image`. Confirma que hay algún objeto imagen; no que todas se vean, su posición/tamaño, acentos, tablas, columnas, orden o número de páginas.
- `scripts/validator_playwright_smoke.py:414-470`: crea dos columnas, comprueba DOM y descarga bytes PDF si HTTP es OK. No analiza el PDF. El propio script pide añadir comprobación de contenido (`:691`). `teacher_editor_click_audit.py:92-117` y `teacher_playwright_journey.py:129-155` prueban interacción, recurso y guardado, no conservación completa.
- **Bloqueo de ejecución en este checkout:** `tests/test_app.py:16-26` lee en tiempo de importación `../data/repo/.../column-demo-image.png`; `tests/test_validation_regressions.py:7-9` y `scripts/journey_support.py:44-49` dependen del mismo directorio antiguo. Se comprobó que `/home/jgorozco/git/libre-libros/data/repo` no existe. Incluso con dependencias Python resueltas, esa fixture impide coleccionar `test_app.py`. No se ejecutó pytest para afirmar un resultado observado.
- Los scripts de journey crean copias/commits, ficheros de salida y servidores; no se ejecutaron por la restricción de solo lectura. Además heredan entorno del proceso (`journey_support.py:62-73`): un futuro runner debe usar configuración explícita aislada, sin heredar proveedores remotos.

## 8. Plan mínimo por orden de ejecución y pruebas de salida

| Fase | Cambio mínimo | Puerta de aceptación |
|---|---|---|
| **P0-A Seguridad** | Reescritura URL segura; MIME real/origen de recursos; confinamiento de rutas y política de rama | Payload de comillas no crea atributos; HTML/SVG activo no se ejecuta; traversal solo devuelve error y nunca el canario externo; rama no autorizada denegada |
| **P0-B No perder trabajo** | Mantener original; bloquear edición destructiva de nodos no soportados; serialización simétrica; validar columnas | Abrir/guardar sin tocar deja bytes y commit sin cambios; corpus round-trip mantiene estructura; entrada malformada conserva texto y muestra aviso |
| **P1-A Build/pruebas** | Reconciliar fuente/bundle; fixtures autosuficientes, sin `../data/repo`; unit tests JS y backend | Build reproducible; source y bundle cumplen mismas pruebas; colección en checkout limpio; ninguna prueba escribe en contenido real |
| **P1-B Editor básico** | Tablas simples de extremo a extremo; estado sucio y recuperación; recursos sin colisiones; revisión base en guardado | Editar tabla, añadir/quitar/reutilizar imagen, error de red y conflicto entre pestañas sin pérdida; teclado y móvil usables |
| **P1-C PDF honesto** | Avisos en salida simplificada; implementar/probar pipeline paginado elegido y fuentes | Texto/acento correcto y recursos completos; filas sin pérdida, encabezados repetidos, saltos previstos; inspección visual de fixtures |
| **P1-D Importar** | Asistente de importación con formatos explícitos y vista previa; original conservado | Ninguna conversión sobrescribe/publica automáticamente; reporte de pérdidas; cancelar/deshacer conserva estado; PDF escaneado no promete texto inexistente |
| **P2** | DOCX más rico, OCR, tablas combinadas, opciones de impresión, accesibilidad extendida | Solo anunciar cada capacidad tras fixture y prueba docente correspondiente |

### Suite propuesta (no ejecutada)

1. **Unitario de contrato**: Markdown → editor → Markdown → editor para párrafos, marcas combinadas, `*`, `_`, `[]()`, pipes, código, listas desde 5, saltos, imágenes con `]`/comillas en alt, títulos, fichas y columnas. Comparar AST/semántica tras edición y bytes cuando no hay edición. Añadir property-based si el tamaño del parser lo justifica.
2. **Backend de lectura**: allowlist de tablas y audio funcional sin abrir XSS; variantes de marcador, contenido dentro de código, salto consecutivo/inicial/final; IDs y URLs codificados. Límites de tamaño para preview y carga, dimensiones de imágenes y lote total: hoy se lee cada upload completo antes del límite (`routers/books.py:238,257-262`).
3. **Integración de guardado**: dos imágenes con mismo nombre final, nombre Unicode, quitar pendiente, reemplazar biblioteca; proveedor falla a mitad de lote; documento y assets no quedan incongruentes. Dos pestañas/usuarios sobre misma revisión con conflicto recuperable.
4. **PDF automatizado**: parser de PDF para comprobar páginas y extracción de `áéíóú ü ñ Ñ ¿ ¡ € 1º`, texto con acento combinante, fórmulas sencillas y enlaces; contar presencia esperada de imágenes sin conformarse con una; ausencia de mensajes de fallback en fixture válida. Comprobación de cajas/coordenadas para recortes/solapamientos donde sea viable.
5. **PDF visual**: rasterizar páginas con resolución fija y comparar fixtures revisadas, tolerando diferencias de antialiasing; revisión humana de tablas largas/anchas, fila altísima, imagen vertical grande, leyenda larga, 2/3 columnas y 30+ páginas. Verificar orden de lectura y legibilidad, no solo similitud de píxeles.
6. **Importación**: documentos fuente conocidos, no documentos privados; TXT UTF-8/encoding inválido, Markdown con assets ausentes, HTML activo, DOCX con tabla/imagen/lista si se soporta, PDF digital multicolumna y escaneado. Texto extraído correcto y pérdidas explicadas; nunca interpretar «archivo aceptado» como conversión fiel.
7. **E2E docente**: abrir libro → cambiar una frase → pegar una tabla → añadir foto → lectura → guardar → reabrir → descargar PDF de esa versión. Verificar contenido persistido, imágenes cargadas (`naturalWidth > 0`, no solo elemento visible), todas las celdas y descarga correcta. Chromium/Firefox/WebKit, teclado y viewport móvil; prueba breve con docentes sin instruirles sobre Markdown/Git.

**Criterio de cierre:** toda estructura anunciada debe sobrevivir al recorrido importar/editar/guardar/reabrir/leer/exportar. Lo no soportado debe conservarse o rechazarse de forma explicada y recuperable. Que el servidor devuelva un PDF válido no demuestra que el material docente se haya conservado.
