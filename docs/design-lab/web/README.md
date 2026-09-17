# Prototipos A/B · biblioteca docente (laboratorio local)

Comparación de dos propuestas de interfaz para Libre Libros con el mismo catálogo
sintético de Primaria, el mismo perfil docente ficticio (Elena Martín) y la misma
propuesta pendiente de revisión. Están pensados para abrirse con `file://`,
sin servidor, sin red y sin datos de alumnado.

## Archivos

| Archivo | Contenido |
| --- | --- |
| `index.html` | Selector neutro entre versiones. No recomienda ninguna. |
| `a.html` | Variante A: referencia fiel a la jerarquía, colores y navegación actuales (`base.html`, `dashboard/index.html`, `books/list.html`, `books/detail.html`, `app.css`). |
| `b.html` | Variante B: biblioteca centrada en tareas con cabecera compacta, verde petróleo + crema, catálogo y filtros antes que estadísticas, etiquetas docentes y pendientes accesibles también para coordinación. |
| `shared.css` / `shared.js` | Recursos comunes. El editor de texto es idéntico en ambas variantes a propósito (no es objeto de comparación). |
| `libre-libros-mark.svg` | Copia literal del logo actual (`app/static/img/libre-libros-mark.svg`) para controlar la variable de marca. |

Capacidades idénticas en A y B: filtros Curso/Materia con estado vacío y
limpieza, abrir material, adaptar copia (solo en memoria), importar `.txt`/`.md`
a un textarea con confirmación previa a la sustitución, guardar copia SIMULADO,
enviar a revisión SIMULADO, sección de pendientes con enlace interno a la
propuesta mock y aviso de que el PDF no se genera. Nada está roto a propósito
en A y no hay asistente obligatorio en ninguna variante.

## Limitaciones declaradas

- Todo es un prototipo sin servidor: guardar, enviar a revisión, crear material
  y cerrar sesión son simulaciones y no conservan nada tras recargar.
- El editor es un textarea idéntico en ambas variantes; no compara motores de
  edición ni renderizado Markdown.
- La acción de PDF solo muestra un aviso: no genera, descarga ni imprime nada.
- «Coordinador» y «Docente» son un selector de demostración; no existen
  permisos reales ni datos de organizaciones.
- No contiene resultados de evaluación ni atribución de preferencias: la
  comparación con personas usuarias se realiza fuera de estos archivos.

## Contrato de selectores (`data-testid`)

Estables y equivalentes en ambas variantes salvo donde se indica. La matriz de
pruebas central puede navegar con `location.hash` (`#catalogo`,
`#material/{id}`, `#editar/{id}`, `#propuesta/{id}`, `#pendientes`) y esperar a
que el elemento objetivo deje de estar `[hidden]`.

### Globales

| Test ID | Descripción |
| --- | --- |
| `prototype-banner` | Aviso de prototipo sin servidor con enlace al selector. |
| `global-status` | Región `role="status"` para avisos de rol. |
| `user-name` | Chip con el nombre del perfil ficticio. |
| `role-select` | Selector de demostración docente/coordinador. |
| `mock-dialog`, `dialog-title`, `dialog-cancel`, `dialog-confirm` | Diálogo nativo accesible. `dialog-confirm` está oculto en diálogos informativos; `dialog-cancel` muestra «Cerrar» en ese caso. |
| `nav-home`, `nav-catalog`, `nav-new`, `nav-pending` | Navegación principal. `nav-pending` incluye el contador actualizado en su texto. |

`nav-exit` es un botón nativo con `data-testid="nav-exit"` (abre el diálogo de
sesión ficticia). El enlace de saltar al contenido no lleva test ID: se usa el
texto «Saltar al contenido».

### Inicio (vista `#panel`)

| Test ID | Descripción |
| --- | --- |
| `home-view`, `pending-section`, `pending-count`, `stats` | Contenedores de la portada y contador de pendientes. |
| `catalog-section`, `catalog-results`, `result-count`, `empty-state` | Catálogo y resultados de filtrado. |
| `filter-form`, `filter-course`, `filter-subject`, `filter-apply`, `filter-clear` | Filtros explícitos con estado vacío y limpieza. |
| `material-card-{id}`, `open-material-{id}` | Tarjeta y enlace de cada material. IDs: `mates-3`, `lengua-3`, `ciencias-4`, `mates-4`, `lengua-5`, `ciencias-6`. |
| `create-material` | Enlace a la vista de creación (no hay asistente obligatorio). |
| `new-title`, `new-course`, `new-subject`, `new-submit`, `new-view` | Formulario de borrador local. |

### Detalle y editor

| Test ID | Descripción |
| --- | --- |
| `detail-view`, `material-title`, `material-content`, `detail-back` | Lectura del material base. |
| `detail-pdf` | Acción PDF que solo muestra un aviso mock. |
| `adapt-copy` | Enlace al editor de la copia docente. |
| `editor-view`, `editor-back`, `editor-title`, `copy-title`, `editor-text` | Editor de copia (idéntico en A y B). |
| `import-file`, `import-status` | Importación de `.txt`/`.md` con confirmación; rechaza otras extensiones, >1 MB y binarios. |
| `save-copy`, `send-review` | Acciones SIMULADO separadas: guardar copia y enviar a revisión. |
| `editor-pdf` | Acción PDF del editor (aviso mock). |
| `copy-status`, `review-status` | Estados independientes de copia guardada y envío a revisión. |

### Pendientes y propuesta

| Test ID | Descripción |
| --- | --- |
| `proposal-view`, `proposal-title`, `proposal-content`, `proposal-back` | Propuesta mock enlazada desde pendientes. |
| `open-propuesta-1` | Enlace a la propuesta pendiente inicial. |

Los envíos simulados crean `propuesta-2`, `propuesta-3`, etc., con los mismos
test IDs de vista.

## Diferencias intencionales A/B

Solo presentación, orden visual y redacción de etiquetas; capacidades y datos
idénticos, incluido el editor, que se mantiene neutro en ambas.

| Aspecto | A | B |
| --- | --- | --- |
| Jerarquía de portada | Pendientes → estadísticas → catálogo agrupado por curso y materia. | Catálogo con filtros → pendientes → estadísticas. |
| Cabecera | Barra lateral azul con marca y navegación vertical. | Cabecera compacta horizontal petróleo con la misma navegación en una fila. |
| Paleta | Azules de la app (`#2457c5`, `#163f97`) y fondo actual. | Verde petróleo + crema con equivalencias AA verificadas. |
| Agrupación del catálogo | Secciones por curso y materia. | Cuadrícula plana con curso y materia como etiquetas en cada tarjeta. |
| Etiquetas | «Panel», «Libros», «Nuevo libro», chips `public`/`local` | «Inicio», «Catálogo», «Crear material», chips «Compartido»/«Biblioteca local». |
| Editor | El mismo bloque neutro en ambas. | El mismo bloque neutro en ambas. |

## Comprobaciones realizadas

- Sintaxis JS verificada y humo de DOM con jsdom local: enrutado, filtros,
  importación con confirmación y rechazos, guardar/enviar separados, propuesta
  y rol de coordinación, en ambas variantes.
- Contraste verificado numéricamente (WCAG 2.x relativo): los 18 pares de
  color de texto/fondo de la interfaz miden entre 6.0:1 y 13.4:1, por encima
  del objetivo AA de 4.5:1.
- Las pruebas de humo usan APIs simuladas y no evalúan navegadores reales,
  lectores de pantalla ni rendimiento; son comprobaciones de comportamiento
  del prototipo, no de personas.
