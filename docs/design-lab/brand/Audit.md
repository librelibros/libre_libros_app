# Libre Libros · Estudio independiente de marca

## Alcance y decisión

Este estudio no sustituye el logo del producto. Solo añade archivos en `docs/design-lab/brand/`. La web A/B debe mantener **el mismo logo actual en ambas variantes**: cambiar simultáneamente marca y diseño impediría atribuir una diferencia a una variable concreta. No se ha modificado esa web ni `app/`.

Se entrega una copia intacta y dos alternativas dibujadas para este estudio, con nombre **Libre Libros visible como texto HTML separado**. No son identidad aprobada ni arte final. El objetivo de reconocimiento a 16/24/32 px es una hipótesis de diseño, no un resultado de pruebas con personas. No se afirma un significado inequívoco.

## Evidencia inspeccionada (solo lectura)

- `app/static/img/libre-libros-mark.svg`: `width="220" height="96" viewBox="0 0 220 96"`; placa clara redondeada, dos degradados, páginas azules, cuatro líneas de lectura, tres nodos y sus enlaces. Incluye texto SVG «BIBLIOTECA» de 12 unidades y «material docente vivo» de 11 unidades. Su título interno es «Logo Biblioteca Docente», no Libre Libros.
- `app/templates/base.html:16–20`: enlace `.brand` a `/` con `aria-label="Inicio"`; imagen con `alt="Logo de la biblioteca docente"`; descripción visible y un `span.sr-only` con «Libre Libros». El nombre de marca no está presentado como wordmark visible en ese bloque. El `aria-label` del enlace determina normalmente su nombre accesible y puede eclipsar el contenido, por lo que «Inicio» no explicita la marca.
- `app/static/css/app.css:98–116`: `.brand` es grid; `.brand-mark` usa `width: min(160px, 100%)`, `height: auto`, `display: block`; `.brand-note` limita ancho a 150 px. La zona lateral usa un fondo azul degradado (`#133a70` a `#102f5d`).
- No hay declaración de favicon en el `base.html` leído; una búsqueda de «favicon» en HTML/Python de `app/` no devolvió coincidencias. Esto **no verifica** la respuesta real de `/favicon.ico` ni configuración externa de despliegue.

### Consecuencias medibles de la geometría actual

A 160 px de ancho, el SVG conserva 69,82 px de alto; las letras de 12 y 11 unidades equivalen aproximadamente a 8,73 y 8 px CSS. En caja de 16 px, las letras quedan en 0,87 y 0,80 px y la altura completa del lienzo es 6,98 px. Además, la placa solo ocupa 190 de las 220 unidades de ancho; el libro principal, 114. El libro ocupa aproximadamente 8,29 px de ancho cuando el recurso mide 16 px.

El problema no se limita a «demasiado detalle»: hay una diferencia de proporción y aprovechamiento del lienzo. Texto, nodos y líneas compiten por muy pocos píxeles. Reducir el archivo o exportarlo a PNG no elimina ese problema geométrico. No se ha recortado la copia para favorecerla ni perjudicarla: se conserva byte a byte.

## Propuestas originales

| Recurso | Qué conserva / cambia | Hipótesis | Coste y riesgo |
| --- | --- | --- | --- |
| `mark-current-copy.svg` | Referencia exacta del recurso existente | A gran tamaño comunica libro y red colaborativa | Formato horizontal; textos diminutos; dependencias de tipografía local; nombres de marca inconsistentes |
| `mark-blue.svg` | Azul `#2457C5`, páginas curvas, lomo y una línea blanca por página; elimina placa, red y letras | Mayor presencia del libro a 16/24/32 px con continuidad cromática | El blanco es una segunda tinta; las líneas pueden desaparecer en reducción; pierde la pista explícita de colaboración |
| `mark-teal.svg` | Dos páginas verdes `#087F78` con abertura central transparente; sin detalle interior | Menos ruido y una silueta de libro/apertura más estable en reducción | Más genérico: puede recordar hojas, alas o un escudo; requiere aprendizaje de marca; menor continuidad cromática |

Ambas alternativas usan `viewBox="0 0 32 32"`, páginas de 26 unidades de ancho total y margen lateral de 3 unidades. A 16 px el libro tiene 13 px de ancho y la separación central de 2 unidades se convierte en 1 px. A 24 px, esa separación es de 1,5 px: el antialiasing puede suavizarla. En azul también se reduce a 1 px el trazo blanco de 2 unidades. No hay letras, fuentes, máscaras, filtros, símbolos reutilizados ni recursos externos dentro de las propuestas.

Los trazados se han redactado aquí sin incorporar iconos de terceros. El HTML usa `system-ui, sans-serif`: puede variar entre plataformas. No se ha realizado búsqueda de anterioridades, evaluación legal de marca ni examen de similitud exhaustivo. «Original» describe su creación para este estudio, no garantiza exclusividad comercial o registrabilidad. La copia actual conserva sus metadatos y fuentes locales; no se atribuye una licencia nueva al original ni se afirma haber auditado su procedencia.

## Hoja comparativa

Abrir `index.html` localmente, sin servidor ni conexión. La matriz se genera con JavaScript propio sin dependencias. Cada candidato muestra:

- Cajas de **16, 24, 32, 48 y 160 píxeles CSS**, con ancho y alto explícitos, `object-fit: contain` y sin `transform` ni escalado de CSS.
- Color sobre blanco `#FFFFFF` y oscuro `#112A36`.
- Monocromo **tonal** en ambos fondos (`grayscale(1)`, no implica una sola tinta).
- Tinta plana negra de estrés (`brightness(0)`). Esta conversión conserva alfa pero aplana todos los colores opacos: la placa original se vuelve una masa y los trazos blancos de azul se pierden. No es una conversión de producción. La propuesta verde conserva su abertura al ser transparente.
- Un montaje de icono a 48 px con «Libre Libros» en HTML. El nombre no forma parte de ningún trazado propuesto.

Usar zoom del navegador al 100 %. La densidad física depende de la pantalla: las capturas se generaron a DPR 1. El original entra en una caja cuadrada manteniendo su aspecto horizontal. Esto aproxima el caso de un favicon, mientras que en producción su altura es automática. El fondo oscuro de prueba es uniforme y **no** pretende reproducir exactamente el degradado de la sidebar.

### Contraste orientativo

Cálculo sRGB de colores planos (sin antialiasing):

| Relleno | Sobre blanco | Sobre oscuro de prueba |
| --- | ---: | ---: |
| Azul `#2457C5` | 6,47:1 | 2,30:1 |
| Verde `#087F78` | 4,86:1 | 3,07:1 |

El azul necesita una adaptación para fondos oscuros si fuera un gráfico funcional que requiere 3:1; no basta con reutilizarlo sin considerar el contexto. El verde apenas supera ese umbral en el fondo elegido: no asegura resultados con otros fondos o bordes suavizados. La excepción de logotipos a determinados requisitos de contraste no significa que se vean bien. Una eventual versión inversa debe prepararse y probarse aparte. No se ha certificado cumplimiento WCAG.

## Accesibilidad: adorno frente a nombre

- **Icono junto al nombre visible:** usar `<img alt="">` y texto HTML «Libre Libros», evitando leer el nombre dos veces. En la comparación las imágenes repetidas son decorativas; títulos, descripciones y tamaños ya proporcionan el contexto textual. Se comprobó la presencia de los `alt` vacíos, no el anuncio real de un lector de pantalla.
- **Imagen de marca aislada:** el nombre accesible debe ser «Libre Libros», normalmente mediante `alt="Libre Libros"` en `<img>`. Un título interno del SVG no sustituye el `alt` en ese uso.
- **Enlace solo con icono:** el enlace requiere un nombre que combine marca y destino, por ejemplo `aria-label="Libre Libros · Inicio"` con la imagen decorativa. Si también se ve el nombre, conservarlo dentro del nombre accesible y evitar etiquetas redundantes. No cambiar la etiqueta sin comprobar navegación y foco en el producto.
- **SVG inline:** si decorativo, `aria-hidden="true"` y, por compatibilidad, `focusable="false"`; si informativo, `role="img"` y referencias a título/descripción con IDs únicos por instancia. Los IDs simples de estas piezas son seguros como archivos separados; al duplicarlas inline deberán renombrarse.
- El texto HTML seleccionable y adaptable no depende del reconocimiento de la silueta. La marca no se debe distinguir solo por azul frente a verde.

## Favicon y portabilidad

Los dos SVG nuevos son cuadrados, autónomos y carecen de fuentes externas: candidatos apropiados para evaluar como favicon SVG en navegadores compatibles. Su tamaño intrínseco de 32 px no limita su escalado vectorial. La copia horizontal no se vuelve cuadrada de forma útil sin rediseñar o recortar; esta hoja no altera su aspecto.

No se han generado ni instalado favicons. Una eventual integración independiente requeriría declarar SVG con `type="image/svg+xml"` y `sizes="any"`, considerar PNG/ICO de respaldo (16/32/48 px), e icono táctil/manifest según destinos (por ejemplo 180/192/512 px). Los archivos `.svg` no son un contenedor `.ico` y no cubren automáticamente todas esas rutas. Revisar rasterización a 16 px, caché, transparencia y modo oscuro en navegadores reales. La previsualización como `<img>` no prueba la pestaña del navegador ni el icono de la pantalla de inicio. No hay prueba de Firefox, Safari, iOS o Android.

## Comprobaciones realizadas

Se ejecutó desde la raíz de `libre_libros_app`:

```sh
PLAYWRIGHT_BROWSERS_PATH="$PWD/.local/browsers" .venv/bin/python docs/design-lab/brand/verify.py
```

Resultado registrado en `verification.json`:

- Tres SVG parseados correctamente por `xml.etree.ElementTree`.
- Copia original idéntica en bytes; SHA-256 registrado para cada SVG.
- Propuestas sin nodos `<text>`, scripts, imágenes, `foreignObject` ni atributos `href`; viewBox cuadrado comprobado. Los `<title>` y `<desc>` existen.
- Chromium **139.0.7258.5**, headless, Playwright local, sin descargas de navegadores.
- Viewports **1440×1000** y **390×844**, `device_scale_factor=1`.
- En cada viewport: **78 imágenes cargadas**, **15 filas**, **75 muestras**; cajas verificadas a sus tamaños nominales, 3 nombres HTML, imágenes con `alt=""`; sin desbordamiento horizontal del documento ni errores JavaScript.
- Intercepción de solicitudes: solo permitidos `file://` y `data:`; **cero intentos externos** durante la prueba. No se contactó a terceros.
- Capturas completas `screenshots/desktop.png`, `screenshots/mobile.png` y por candidato `screenshots/current.png`, `screenshots/blue.png`, `screenshots/teal.png`.

Las capturas se generaron correctamente y se abrieron mediante el lector local, pero su respuesta fue una representación codificada; no se presenta esto como una inspección visual humana ni como prueba de reconocimiento. Las verificaciones geométricas y de carga son automatizadas. Tampoco se ejecutó un lector de pantalla, prueba de impresión, forced colors, zoom extremo o batería automática de accesibilidad.

## Siguiente decisión (no ejecutada)

Comparar con personas las tres siluetas sin rótulos a 16/24/32 px, pedir qué creen que representa y evaluar confusiones; después repetir con el nombre visible. Mantener separados reconocimiento, preferencia y recuerdo. La variante verde simplifica más y permite tinta única; la azul mantiene continuidad. Ninguna gana por defecto: simplicidad puede mejorar reproducción y empeorar distintividad. Solo tras decidir la identidad conviene preparar inversas, favicons y especificaciones finales en otra intervención.
