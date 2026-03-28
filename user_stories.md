# User Stories

Este fichero define las historias de usuario de extremo a extremo que se validan en navegador para Libre Libros.
Cada historia debe ejecutarse como un flujo completo desde la pantalla de login o acceso hasta el resultado funcional esperado.

## Story 1: catalogo_filtrar_y_comentar

- Como usuario administrador quiero:
  revisar el catalogo y dejar una observacion pedagogica en un libro.
- Para ello:
  - hago login
  - entro al catalogo de libros
  - filtro por `Primaria` y `Lengua`
  - abro el detalle del libro filtrado
  - añado un comentario
- Resultado esperado:
  - el libro aparece correctamente filtrado
  - el detalle carga con indice, contenido e imagenes
  - el comentario queda visible en la pagina

## Story 2: editar_varias_columnas_y_generar_pdf

- Como usuario administrador quiero:
  editar un libro con contenido en varias columnas y exportarlo a PDF.
- Para ello:
  - hago login
  - entro al catalogo y localizo un libro de `Primaria` y `Lengua`
  - abro el editor del libro
  - añado un bloque de `2 columnas`
  - escribo texto en la primera columna
  - escribo texto en la segunda columna
  - inserto una imagen de apoyo en la segunda columna
  - guardo los cambios
  - exporto el libro a PDF
- Resultado esperado:
  - el contenido editado se guarda
  - el detalle del libro muestra un bloque de dos columnas con texto e imagen
  - se genera un PDF valido a partir del libro actualizado

## Story 3: administracion_y_cierre_de_sesion

- Como usuario administrador quiero:
  comprobar que la zona de administracion esta disponible y terminar la sesion.
- Para ello:
  - hago login
  - entro en administracion
  - reviso que aparecen las secciones principales de alta simple y repositorios
  - cierro sesion
- Resultado esperado:
  - la pantalla de administracion carga correctamente
  - el cierre de sesion devuelve al formulario de acceso

## Reglas de validacion

- Cada historia debe generar:
  - un video `mp4` completo de todo el flujo
  - capturas relevantes
  - trazabilidad en `run-log.md`
- Los nombres de video deben seguir el patron `user-story-<slug>.mp4`.
- El reporte final debe referenciar este fichero para dejar claro que historias se han ejecutado y cual ha sido su resultado.
