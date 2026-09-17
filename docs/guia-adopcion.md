# Libre Libros: presentación y primeros pasos

Guía breve · 17 de septiembre de 2026 · Propuesta de adopción, no campaña ejecutada.

## Qué contar del proyecto

> Libre Libros es una herramienta en fase piloto para crear, adaptar y revisar
> materiales educativos en equipo. Permite editar libros, conservar versiones
> y exportar un PDF básico. Buscamos docentes que prueben una actividad concreta
> y nos ayuden a mejorar tanto la herramienta como los materiales.

El foco del piloto es Infantil y Primaria. No presentar el catálogo como una
colección de libros terminados, una solución avalada por docentes o una mejora
educativa demostrada. El PDF puede diferir de la vista web: revisarlo antes de imprimir.

## Elige cómo participar

| Vía | Para quién | Primer paso |
|---|---|---|
| Probar el piloto alojado | Docentes y pequeños equipos | Acordar acceso, alcance y soporte con quien coordina el piloto. |
| Instalar una instancia propia | Centros o asociaciones con apoyo técnico | Preparar una prueba local y revisar los requisitos de producción. |
| Contribuir | Docentes, revisores, diseñadores y desarrolladores | Proponer una mejora pequeña en el repositorio correspondiente. |

## Onboarding docente: tu primera actividad

1. Pide a quien coordina el piloto la URL, el método de acceso y los permisos.
2. Entra con el método habilitado en esa instalación; no des por hecho que
   necesitas GitHub. No compartas contraseñas ni enlaces de invitación.
3. Localiza un libro de tu etapa y materia en el catálogo y abre su contenido.
4. Elige una actividad breve y pulsa **Editar**, si tienes ese permiso.
5. Cambia una instrucción o añade un ejemplo propio. Revisa la vista previa.
6. Pulsa **Guardar**, comprueba **Destino**, añade un resumen y confirma con
   **Guardar cambios**. Vuelve a abrir esa versión para comprobarla.
7. Confirma con el coordinador qué rama o propuesta contiene tus cambios y
   quién los revisará. Guardar no demuestra que estén aprobados o publicados.
8. Exporta el PDF de la versión elegida y comprueba texto, imágenes y saltos.
9. Comunica una cosa útil y un problema encontrado. No hace falta probar todo.

Usa únicamente material propio o con autorización compatible. No subas nombres,
fotos, calificaciones ni otros datos de alumnado, tampoco en comentarios o capturas.
Si falta **Editar**, consulta tus permisos. Si falla algo, comunica el paso,
el libro y el mensaje de error, sin secretos ni datos personales.
La [guía ampliada](user-guide.md) aporta contexto; algunos pasos dependen de la instalación.

## Instalación propia: recorrido técnico

1. Lee el [README](../README.md) y prepara un entorno local aislado siguiendo
   «Arranque en local»: entorno virtual, dependencias y `.env` desde el ejemplo.
2. Sustituye la clave de sesión y las credenciales de administrador de ejemplo.
   No publiques `.env`, tokens ni copias de la base de datos.
3. Inicia la prueba solo en tu equipo con
   `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
4. Desde **Administración**, configura un repositorio local de pruebas o uno
   GitHub/GitLab dedicado. No empieces con el repositorio real del centro.
5. Comprueba acceso, permisos, guardado/reapertura, revisión y exportación PDF.
6. Antes de abrirlo a otras personas, revisa [despliegue](deploy-render-supabase.md)
   y [condiciones del piloto](pilot-communication-plan.md): HTTPS, secretos,
   persistencia, restauración de backups, privacidad y responsable de soporte.

**No expongas el `docker-compose.yml` de depuración en Internet:** incluye GitLab,
credenciales de ejemplo y acceso al socket Docker. No es una receta de producción.
El autoalojamiento requiere operación propia y puede tener costes; no se promete SLA.
Antes de redistribuir código o materiales, revisa el `LICENSE` de cada repositorio
por separado y los derechos de sus recursos. Esta guía no concede licencias nuevas.

## Cómo contribuir sin montar infraestructura

- **Contenido:** proponer una actividad original, corregir una errata o revisar
  un objetivo curricular en el repositorio de contenido.
- **Revisión:** indicar libro, sección, problema y alternativa; aportar fuentes.
- **Diseño y accesibilidad:** revisar legibilidad, texto alternativo y PDF real.
- **Código y documentación:** abrir una incidencia concreta o una propuesta pequeña
  en el repositorio de la aplicación, con comprobaciones de lo cambiado.
- Acordar primero cambios grandes. No aportar material editorial copiado, secretos
  o datos personales. Una propuesta no equivale a una aportación aceptada.

## Plan de comunicación en cuatro pasos

1. **Preparar:** una presentación de una página, esta guía y una demo de cinco
   minutos con material sintético: abrir → editar → guardar → revisar → PDF.
2. **Escuchar:** buscar encaje con asociaciones docentes, movimientos de renovación
   pedagógica, grupos de didáctica y redes de recursos abiertos. Pedir feedback
   sobre una tarea, no adhesión al proyecto. Consulta la [selección de entidades
   y mensaje de presentación](asociaciones-y-contacto.md).
3. **Invitar:** mediante canales que admitan propuestas o una respuesta solicitada,
   ofrecer una demo y las tres vías de participación. No hacer envíos masivos ni
   interpretar un correo público como consentimiento para campañas.
4. **Acompañar y decidir:** comenzar con un equipo pequeño; registrar bloqueos,
   tareas completadas y ayuda necesaria. Devolver resultados agregados y acordar
   continuidad, exportación o salida, sin publicar testimonios o logos sin permiso.

Antes de dar acceso real, completar las puertas de acceso, privacidad, tareas,
soporte y acuerdo informado del [plan detallado](pilot-communication-plan.md).
No anunciar fechas, plazas o soporte que nadie pueda atender.
