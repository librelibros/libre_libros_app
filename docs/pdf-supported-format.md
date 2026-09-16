# Motor PDF ReportLab: formato admitido e integración

## Estado y contrato

Motor independiente en `app/services/pdf_export.py`. No importa `app.main`, configuración, modelos ni repositorios; no lee `.env`, no consulta red y no abre rutas de recursos del sistema de archivos. Reutiliza Python Markdown, Pillow y ReportLab ya instalados. No añade fuentes ni dependencias de ejecución.

```python
render_pdf(
    title: str,
    content: str,
    asset_loader: Callable[[str], bytes] | None = None,
) -> bytes
```

Devuelve PDF A4 completo en memoria. `content` es Markdown. El callback recibe una ruta relativa `assets/...` ya filtrada, y devuelve bytes. Las ausencias y fallos de carga/decodificación de imagen generan un aviso visible, sin revelar excepciones del proveedor. Los límites globales/complejidad y los errores de distribución A4 generan `PDFExportError`, nunca un PDF parcial deliberado.

### Conexión pendiente para el agente propietario de `books.py`/router

La firma pública inspeccionada es `export_markdown_to_pdf(book, content, asset_loader=None) -> bytes`. No había función `render_pdf` en ese servicio. Mantener esa API y delegar:

```python
from app.services.pdf_export import render_pdf


def export_markdown_to_pdf(book, content, asset_loader=None):
    return render_pdf(book.title, content, asset_loader=asset_loader)
```

No preaplanar el Markdown antes de delegar: el motor añade sus propios avisos y preserva todos los cuerpos de columnas, incluso los sobrantes o sin cierre. `markdown_utils.py` importa `PAGEBREAK_PATTERN` de `books.py`; conservar esa constante aunque se retire después el renderer antiguo. No importar `markdown_utils` desde el motor: introduciría dependencia circular con `books.py`.

El endpoint existente puede conservar MIME y `Content-Disposition`. Debe capturar `PDFExportError` y responder con error recuperable (por ejemplo 422), no 500 ni PDF vacío, usando un mensaje seguro. El callback debe seguir imponiendo autorización de libro/versión y confinamiento real en repositorio; filtrar rutas en este motor no sustituye esos controles. Resolver una revisión coherente antes de exportar si existe concurrencia.

**No se han modificado `books.py`, router, requirements ni otros archivos de aplicación.** La conexión y las pruebas HTTP/E2E corresponden al agente de integración. Importar este motor no activa automáticamente el endpoint.

## Formato soportado

| Elemento | Salida |
|---|---|
| Párrafos y español | Helvetica estándar, texto seleccionable. Normalización NFC de acentos combinantes. Español habitual y caracteres WinAnsi: tildes, ñ, ü, ¿, ¡, €, º. Caracteres no representables se convierten a `[U+XXXX]`, no se prometen emoji/Unicode completo. |
| Título | Escapado como texto, también en metadatos. Se conserva el título de entrada y cualquier H1 del cuerpo; pueden repetirse. |
| H1–H6 | Encabezados con jerarquía tipográfica, dividibles si son excepcionalmente largos. Sin índice PDF automático. |
| Negrita/cursiva/código inline/tachado HTML | Traducción explícita a marcado permitido de ReportLab; nunca se pasa HTML arbitrario a su parser. `~~tachado~~` GFM no está anunciado como soportado. |
| Listas | Ordenadas y no ordenadas, anidación básica; `sane_lists` conserva inicio numérico. No reproducción exacta de sangrías/CSS del editor. |
| Enlaces | Anotación clicable para HTTP/HTTPS y mailto sencillo. No se descargan destinos. Otros esquemas y anclas internas quedan como etiqueta de texto, sin enlace activo. |
| Código | Bloques cercados o indentados y código inline en Courier. Líneas largas se ajustan; bloques largos se reparten en páginas. Se expanden tabuladores a cuatro espacios, sin resaltado de sintaxis. |
| Tablas tipo GFM | Python Markdown `tables`: celdas simples, pipes escapados y formato inline. `LongTable` repite primera fila de encabezados al dividir por páginas. Anchos iguales; no se replica alineación GFM/CSS. |
| Tablas extremas | Más de 8 columnas, celdas combinadas o fila demasiado alta: aviso **tabla aplanada**, seguido de todas las filas/celdas en orden. No se truncan ni se fuerzan letras minúsculas para hacerlas caber. No reconstruye semántica rowspan/colspan. |
| Imágenes dentro de tablas | Marcador con alt en celda y recursos después de la tabla en orden, con aviso. No se promete imagen dentro de la propia celda. |
| Saltos | `<!-- pagebreak -->` (variantes de espacios/mayúsculas) y `[[pagebreak]]` en línea propia, más paginación automática. Los marcadores dentro de código cercado/indentado literal no se interpretan. Saltos consecutivos pueden producir páginas vacías. |
| Columnas | `[[columns:2]]`/`[[columns:3]]`, `[[col]]`, `[[/columns]]`: aplanadas secuencialmente con aviso visible. Conserva cuerpos adicionales y contenido sin cierre. No layout lateral, no truncado al número declarado. |
| Imágenes locales | PNG/JPEG/GIF/WebP reconocidos por Pillow, verificación y decodificación antes de ReportLab. Solo primer fotograma de animación. Escala proporcional sin ampliar, altura máxima 42% del área de contenido; ancho completo o `.doc-w-33/50/66`, alineación `.doc-align-left/right`. |
| Imagen ausente/dañada/no admitida | Placeholder explicativo con alt. El callback que falla no provoca por sí solo abortar toda la exportación. Sin modo global nuevo de tolerar imágenes truncadas. |
| SVG | **No admitido**, ni siquiera SVG local. Aviso para convertir previamente a PNG/JPEG. No se invoca svglib, no se procesan referencias externas, XML, CSS ni fuentes SVG. SVG disfrazado de PNG tampoco es aceptado como raster. |
| Audio/vídeo/fichas | Aviso de multimedia no incluida; token de ficha se representa como `Ficha (no incluida): etiqueta`. No se anexan documentos ni se reproduce audio. |
| HTML | Parser inerte de biblioteca estándar y allowlist de traducción. Scripts, estilos, iframe, object y SVG no se ejecutan; contenido activo sustituido por aviso. CSS/atributos desconocidos no se envían al parser ReportLab. No es un motor HTML/CSS de navegador. |

Imágenes inline se representan con marcador/alt en el texto y como bloque después de su párrafo. El PDF incluye numeración de página. Márgenes: 48 pt laterales, 56 pt superior/inferior. La vista Lectura de la web no es previsualización fiel de este PDF.

## Seguridad y presupuestos

- Entrada: máximo 1 MB UTF-8 de Markdown, título de hasta 2000 caracteres; HTML intermedio limitado a 30000 etiquetas y profundidad menor de 64.
- Tablas: máximo 10000 celdas por tabla, además del límite de nodos/documento.
- Imágenes: máximo 64 apariciones; hasta 10 MB codificados y 16 millones de píxeles por imagen; hasta 40 MB de bytes admitidos y 32 millones de píxeles sumados por exportación. Las apariciones repetidas cuentan. Límite individual produce placeholder; agotamiento global aborta con error explícito.
- Máximo 250 páginas, comprobado durante construcción. Sin archivos temporales de salida creados por el servicio.
- Solo rutas `assets/...` o `./assets/...`; se rechazan segmentos vacíos, `.`/`..`, barras inversas, porcentajes, consultas, fragmentos, dos puntos y controles. Política deliberadamente estricta: nombres codificados con `%` no se resuelven. Nunca pasar una URL a ReportLab Image ni a Pillow.
- Callback confiable: es el único acceso a bytes externos al módulo. Su implementación debe ser segura; estos filtros no impiden que un callback mal implementado haga red o lea un archivo incorrecto por su cuenta.
- No límites duros de CPU/concurrencia/tiempo de proveedor en este módulo. El tamaño se comprueba después de que el callback entregue bytes; el proveedor debe limitar lectura y tiempo previamente. Los límites de página se aplican durante build, no antes de construir todos los flowables. El despliegue debe limitar concurrencia y recursos del proceso.
- No declaración de PDF/UA, PDF etiquetado, WCAG, fidelidad visual completa ni accesibilidad de lector de pantalla. Usar HTML accesible como alternativa y realizar revisión visual de PDF antes de prometer impresión fiel.

## Pruebas aisladas

Archivo: `tests/test_pdf_export.py`. Carga únicamente el servicio con `importlib`; sobrescribe la fixture orientada a aplicación de `tests/conftest.py` y bloquea conexiones de socket. No importa `app.main` ni inicializa modelos/proveedores. El conftest compartido mantiene sus ajustes herméticos de entorno/directorio temporal.

Ejecutado en `.venv`, 16 de septiembre de 2026:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest tests/test_pdf_export.py -q -p no:cacheprovider -rs
```

**Resultado: 31 passed, 9 skipped, 2.61 s.** Duración del runner, no métrica UX. ReportLab instalado: 4.4.10.

Verificado sin pypdf: bytes PDF completos, estructura y repetición configurada de tablas de 50 filas, escapes/formato seguro, generación con código/encabezado largo, columnas extra/sin cierre, PNG embebido y escalado, placeholders por corruptos/ausentes/excepciones, bloqueo de URLs/traversal/SVG antes del callback, límites de entrada/píxeles/imágenes/páginas/profundidad y aplanado de tablas altas/anchas.

**Pendiente por dependencia dev ausente:** nueve casos con `pytest.importorskip("pypdf")`: extracción de acentos/título/columnas/celda larga, repetición real de encabezado y todas las filas sobre páginas, anotaciones de enlaces y ubicación real de los tres tipos de salto. No presentar estas verificaciones como superadas. Solicitar al agente central que instale `pypdf` solo en el entorno de desarrollo y vuelva a ejecutar el comando; no se ha editado requirements ni instalado nada desde este encargo.

No se ha ejecutado suite general (carga aplicación), validación HTTP ni inspección visual/humana. Antes de integrar, ejecutar las pruebas de extracción sin skips y revisar páginas rasterizadas de tabla larga, tabla aplanada, código largo e imágenes; comprobar el PDF descargado desde el endpoint con permisos y versión correctos en entorno aislado.
