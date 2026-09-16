# Auditoría de producto y UX — piloto de Primaria

Fecha: 16 de septiembre de 2026. Alcance: piloto gratuito de 6 semanas, 3–5 centros de Primaria en España, 10–20 docentes adultos, sin datos de alumnado. Entrada por invitación sin cuenta GitHub; crear, editar, importar, obtener PDF y proponer cambios revisados.

## 1. Método y límites de la evidencia

- Inspección estática, de solo lectura, de plantillas, JavaScript, `user_stories.md` y rutas/servicios necesarios para entender sus consecuencias. No se han leído `.env` ni secretos, ni navegado producción, contactado terceros o ejecutado recorridos de navegador.
- **Evidencia de código** significa que el comportamiento está expresado en los archivos inspeccionados; no acredita su funcionamiento en el despliegue ni en todos los navegadores.
- **Predicción** significa juicio experto o simulación de perfiles ficticios. No hay participantes humanos, entrevistas, resultados de usabilidad, clics medidos ni tiempos medidos. Las secuencias siguientes describen acciones previstas, no mediciones.
- Se contrastó mediante lectura automatizada en memoria la divergencia entre fuente y bundle del resumen de guardado, sin escribir tests ni modificar código. No se ejecutó la suite del proyecto. Los vídeos exigidos por `user_stories.md` no se han producido ni se afirma que sus historias estén superadas.
- Las referencias son relativas a `libre_libros_app`; los números de línea corresponden a la lectura de esta auditoría y pueden cambiar con trabajos paralelos.

## 2. Dictamen de producto

**Piloto condicionado, no listo para prometer el alcance completo.** Conservar catálogo, detalle, editor visual y modelo de versión docente/aprobada. Son una base aprovechable; no se justifica cambiar framework, navegación completa o motor editorial por motivos estéticos.

Bloqueos frente al encargo: no se identifica flujo de invitación de un solo uso; no se identifica importador de documentos; guardar no equivale a enviar una propuesta; el PDF transforma las columnas en secuencia y no reproduce fielmente la lectura web. La revisión interna tiene aprobación, pero no una experiencia completa de comparación/devolución. No presentar esas capacidades como resueltas por una guía o un cambio de etiquetas.

Valor a validar: «Adaptar material propio o autorizado, conservar una versión docente y preparar una copia imprimible; compartir cambios con revisión del centro, sin aprender Git». La primera tarea debe producir una actividad breve útil, no exigir crear un libro de texto entero.

## 3. Flujos reales y fricciones trazables

| Flujo | Evidencia de código y recorrido actual | Consecuencia y mínimo viable |
|---|---|---|
| Acceso | `app/templates/auth/login.html:13–57` presenta GitHub como identidad principal, muestra acceso local condicionado y proveedores opcionales. `auth/register.html:11–30` denomina el alta local interna. `app/routers/auth.py:129–171` redirige al proveedor si lo hay o registra sin token de invitación. `admin/index.html:13–35` permite crear usuario con contraseña. | No confundir alta administrativa con invitación segura. Incorporar aceptación de invitación limitada a correo/centro/rol, caducidad, un solo uso, revocación y recuperación. No compartir contraseñas ni requerir GitHub al docente. Comprobar configuración real en entorno de ensayo antes de anunciarlo. |
| Primera visita | `dashboard/index.html:4–99` antepone revisiones y estadísticas; bienvenida después, catálogo a partir de 166. La guía afirma «se guarda como una propuesta» y «Tu trabajo nunca se pierde» (118–120). `welcome-card.js:28–43` oculta la guía por navegador mediante localStorage. | El primer resultado queda por debajo de información vacía; las promesas contradicen el guardado real. Priorizar continuar/crear material, conservar avisos si hay pendientes, guía breve recuperable mediante Ayuda. Sustituir absolutos por guardado explícito. |
| Encontrar material | `books/list.html:12–35` permite Curso/Materia → Filtrar, con Limpiar y estado vacío. La guía llama «curso» a etapas, mientras `books/form.html:18` ejemplifica «1º ESO» y acepta texto libre. | Mantener filtros con envío explícito, sin buscador avanzado todavía. Para piloto, vocabulario coherente «Etapa: Primaria» y «Curso: 1º–6º», valores normalizados y ejemplo de Primaria; no mezclar etapa y nivel. |
| Crear | `books/form.html:11–54` pide título, curso, materia, visibilidad, repositorio, organización y resumen. `books.py:553–562` crea un esqueleto y vuelve al detalle; editar requiere después otra transición. | Preasignar centro y repositorio autorizado desde invitación, enseñar audiencia en lenguaje claro y permitir cambiarla solo con permisos. Título/curso/materia como decisiones iniciales. Abrir editor tras crear. Validar esas restricciones también en servidor; ocultar campos no proporciona aislamiento. |
| Elegir versión | `books/detail.html:17–48` cambia colegio/curso/versión con `onchange` y recarga; Editar usa `edit_branch`, PDF usa `selected_branch`. | Riesgo de perder contexto con teclado y de creer que se exporta otra versión. Mostrar «Mi versión · Centro · Curso» junto a las acciones. Preseleccionar el contexto del participante; cambios avanzados explícitos y aplicados conjuntamente, sin recarga al recorrer opciones. |
| Editar | `books/editor.html:16–27, 66–223` activa editor enriquecido, inserta texto, columnas, imagen/audio y edita texto alternativo. `frontend/editor/index.js:896–920` implementa los comandos; Imagen y Audio abren el mismo selector. | Conservar procesador visual. Etiquetas visibles para Edición/Lectura/Recursos y acciones menos obvias; no convertir toda la cinta en un asistente obligatorio. Documentar tipos/límites antes de elegir archivo y validar también arrastre. |
| Guardar | `books/editor.html:58–61, 334–384`: Guardar → diálogo, resumen opcional → Guardar cambios. `frontend/editor/index.js:818–840` abre diálogo con Ctrl/Cmd+S. `books.py:685–737` escribe contenido/recursos y retorna al detalle; no crea propuesta. | Hay una confirmación para una operación frecuente y reversible. Guardar borrador directamente, resumen opcional desplegable, estado confirmado por servidor; reservar confirmación para publicar/aprobar. No afirmar autoguardado. Mantener contenido y recursos pendientes si falla. |
| Importar | En las plantillas y rutas inspeccionadas no aparece importación DOCX/ODT/PDF. `editor.html:27` admite imágenes/audio; `frontend/editor/index.js:748–788` inserta imágenes o trata el resto como audio. | Subir recursos **no es importar documentos**. No aceptar DOCX arrastrado como si funcionara. Proponer importación acotada a TXT UTF-8/pegado como primer incremento, siempre a borrador y con vista previa; declarar incompatibles DOCX/ODT/PDF hasta disponer de conversión validada. Si importar Word es requisito esencial del centro, posponer su incorporación, no rebautizar el pegado como importación Word. |
| Previsualizar/PDF | `frontend/editor/index.js:700–714` envía borrador a `/books/preview`, sin comprobar `response.ok` ni capturar error. `books/detail.html:46–49` ofrece PDF bajo condición de edición aunque `books.py:1186–1208` exige visualización. El PDF lee la versión guardada, no el borrador abierto. | Mostrar estado de carga y error recuperable de lectura; no sustituirla por HTML de error o login. PDF debe corresponder al guardado confirmado y a una versión identificada. Permitir exportación a lectores autorizados sin ligarla a permiso de editar. |
| Fidelidad PDF | `app/services/book_content.py:53–81` convierte columnas en secciones consecutivas. `app/services/books.py:67–100` procesa por líneas y escapa texto; `112–137` muestra avisos de imágenes omitidas y usa alt como pie. | PDF válido no significa misma maquetación. No prometer WYSIWYG: avisar de columnas linealizadas, revisar negritas/listas/enlaces, fichas y audio. Para piloto imprimible, usar material de una columna y descargar/abrir el PDF real antes de imprimir. Si se exige conservar dos columnas, es bloqueo hasta resolverlo. No afirmar PDF accesible etiquetado sin verificación. |
| Proponer/revisar | `books/detail.html:164–206` separa enviar propuesta de aceptar versión, muestra estados y enlace «Ver en GitHub». `books.py:1007–1115` crea propuesta y permite aprobación del centro copiando archivos; no es necesariamente un merge externo. `dashboard/index.html:69–74` deriva al proveedor o muestra «Local». | Mover acceso a «Enviar a revisión» junto al guardado/detalle superior; indicar destinatario, versión enviada y que no publica todavía. Revisor con enlace interno al cambio concreto, comparación mínima antes/después, pedir cambios y aprobar con confirmación de destino. No exigir cuenta Git al coordinador pedagógico. No equiparar estado local con revisión externa sincronizada sin comprobarlo. |

### Hallazgos de fiabilidad que afectan a la confianza

1. **Fuente/bundle divergentes, no fallo actual demostrado.** `editor.html:26` contiene `input[type=hidden][name=branch_name]` y su etiqueta legible. `frontend/editor/index.js:648–660` busca `select[name="branch_name"]` y puede mostrar «Sin seleccionar» al reconstruir desde esa fuente. Pero el bundle cargado por la plantilla (`editor.html:4`), `app/static/js/editor-rich.js:25514–25525`, ya usa `[name="branch_name"]` y `dataset.branchLabel`. Alinear fuente y artefacto, luego verificar reconstrucción reproducible. No reportar como bug reproducido de producción.
2. **No hay protección explícita de salida ni autoguardado en el JS inspeccionado.** Cancelar y Abrir ficha navegan fuera del editor; la bienvenida promete que el trabajo nunca se pierde. Añadir estado sucio y aviso solo cuando hay cambios, recuperación tras fallo de envío y explicación honesta. La persistencia local de borradores sería otra decisión, especialmente en ordenadores compartidos; no habilitarla silenciosamente.
3. **Quitar recurso preparado no retira su referencia del documento.** `frontend/editor/index.js:627–639` elimina el archivo de la cola sin editar nodos. `992–994` elimina el nodo seleccionado por otra vía. Riesgo de imagen visible en sesión pero ausente tras guardar. Unificar semántica o avisar y ofrecer quitar ambas cosas/deshacer; validar recurso no referenciado y referencia sin archivo.
4. **Guardado y publicación deben distinguirse por rol.** `app/services/permissions.py:160–172` permite a administración más destinos que al docente. La condición de revisión no queda garantizada para todo actor por una frase de bienvenida. En piloto, limitar roles y probar que editar como docente nunca modifica directamente la versión aprobada; acotar también la aprobación al centro y versión correctos.
5. **Privado en la interfaz no garantiza privacidad en Git.** `books.py:723–729` y creación/aprobación escriben nombre y correo del autor; las ramas derivan de su identidad (`permissions.py:19–41`). Verificar exposición de repositorios, metadatos e historial antes de participantes reales. «Sin datos de alumnado» no significa «sin datos personales».

## 4. Dos diseños propuestos A/B

Ambos son **propuestas no implementadas ni ensayadas**. Comparten invitación segura, límites explícitos de importación/PDF y modelo de permisos; no comparar un acceso roto con otro funcional.

### A — Continuidad: editor y detalle simplificados (recomendado)

- Invitación aceptada → «Tu centro» con un material de ejemplo y «Crear material». Mantener Panel/Libros; ocultar detalles de proveedor a docentes, no rehacer la aplicación.
- Crear: título, curso, materia; audiencia del centro visible y preconfigurada. Tras crear, entrar al editor existente.
- Cabecera persistente: `Mi versión · [Centro] · [Curso]` / `Sin guardar` / `Guardar borrador` / `Lectura` / `PDF` / `Enviar a revisión` como acción secundaria contextual.
- Guardar realiza un envío, muestra éxito del servidor y conserva contexto. «Resumen opcional» no bloquea guardados normales. Si se pide PDF con cambios, ofrecer «Guardar y generar PDF», sin exportar silenciosamente la versión vieja.
- «Importar texto» en Nuevo/Recursos: seleccionar TXT admitido → vista previa y advertencias → insertar en borrador; nunca sustituir contenido existente sin elección explícita y recuperación.
- Tras guardar: «Guardado en tu versión. Aún no se ha enviado a revisión». Tras enviar: «Pendiente de [rol revisor del centro]». Enlace interno al estado, sin navegación Git.
- Mantener confirmación para aprobar/sustituir versión del centro, con origen y destino. No ahorrar acciones a costa de publicar por accidente.

### B — Guía opcional por tarea sobre las mismas pantallas

- Entrada con tres tarjetas: «Crear», «Adaptar», «Importar texto». Barra de pasos: `Preparar → Editar → Revisar y entregar`.
- Preparar agrupa contexto, audiencia y formato; Editar reutiliza exactamente el editor; Revisar muestra advertencias de importación/PDF, destinatario y salida elegida.
- Ofrecer «Continuar editando sin guía» y recordar preferencia solo si se explica. Sin ventanas emergentes encadenadas ni tutorial obligatorio.
- Potencial beneficio: separar objetivos para principiantes. Coste: más transiciones y estado que mantener, posible confusión entre paso «Revisar» y revisión por otra persona. Nombrarlo «Comprobar mi material» si se desarrolla.

**Elección provisional: A.** El mayor riesgo visible es la semántica y fiabilidad, no la ausencia de un asistente. B solo merece prototipo ligero si docentes reales siguen sin encontrar cómo empezar tras corregir A. No desplegar dos implementaciones completas para 10–20 participantes.

## 5. Simulación experta de tres perfiles docentes

### Protocolo comparable (solo simulación)

Personajes ficticios, no representativos de todo el profesorado. Todos realizan las mismas tareas y disponen de idéntico contenido sintético de Lengua de 3º de Primaria, una imagen con licencia y un TXT corto. Se permite teclado en ambos diseños; no se presupone velocidad por edad o discapacidad.

- T1: aceptar invitación sin GitHub, localizar material del centro y explicar quién puede verlo.
- T2: crear una actividad, escribir dos párrafos, insertar dos columnas e imagen con alt; guardar y volver a abrir.
- T3: importar TXT a borrador; intentar seleccionar DOCX de ejemplo y comprender que no está soportado, sin modificar el original.
- T4: generar PDF de la versión guardada, reconocer la linealización de columnas y decidir si sirve para imprimir.
- T5: enviar propuesta y explicar que todavía no es la versión aprobada. Para comparar revisión, los tres reciben después el mismo rol temporal de revisor en un escenario ficticio aislado: localizar cambios, pedir una corrección y aprobar solo la revisión adecuada.

### Predicciones, no resultados humanos

| Perfil simulado | Predicción con A | Predicción con B | Riesgo a verificar con personas |
|---|---|---|---|
| Elena, tutora de 1º–3º, maneja correo y documentos, poca experiencia editorial | T1–T2 probablemente más claros con ejemplo inicial, etiquetas y guardado explícito. T3 podría interpretar «importar» como Word si no ve el formato junto al botón. T4 necesitaría advertencia visible. T5 mejoraría con estado y destinatario, no solo color. | Preparar puede ayudar en T1–T3; los pasos pueden inducir a pensar que cerrar el último publica automáticamente en T5. No cambia la limitación de T4. | ¿Distingue guardar/enviar/aprobar sin explicación del facilitador? ¿Encuentra un primer material sin guía larga? |
| Sergio, especialista de Lengua, reutiliza muchas actividades y prefiere teclado | Se predice preferencia por edición directa, Ctrl/Cmd+S y mantener posición (T2); TXT resulta estrecho para su repertorio DOCX (T3), aunque el límite es honesto. En T4 compararía el PDF; en T5 buscaría cambios concretos. | Preparar puede resultar redundante en cada adaptación (T2–T3); agradecería poder omitirlo. El paso final podría ayudar a revisar destino, no compensa fallos de teclado. | ¿Puede hacer T1–T5 sin ratón ni pérdida del cursor? ¿Importación limitada impide valor real? |
| Nuria, coordinadora de ciclo y autora ocasional, debe revisar materiales ajenos | T1–T3 necesitan contexto del centro inequívoco; T4 exige claridad sobre versión. T5 depende más de comparación y trazabilidad que del editor. A conserva acceso directo a pendientes. | El resumen final podría ayudar en T4–T5, pero repetir el asistente por propuesta podría estorbar. Las tareas T1–T3 no justifican una navegación distinta por rol. | ¿Reconoce qué se sustituirá y quién lo aprobó? ¿Puede devolver cambios sin GitHub y sin conceder rol global de administración? |

No se asignan porcentajes de éxito, puntuaciones, clics ni segundos ficticios. Confianza de estas predicciones: limitada; derivan de correspondencia tarea/interfaz, no de observación. La simulación sirve para priorizar preguntas, no para afirmar que A gana estadísticamente.

### Validación humana futura, no realizada

Con consentimiento separado, invitar a 6 docentes voluntarios del piloto a comparar maquetas A/B antes de desarrollar B: mitad A→B, mitad B→A, contenidos equivalentes y protocolo idéntico para limitar aprendizaje. Es comparación exploratoria, no experimento con potencia estadística. Registrar tarea completada, ayuda necesaria, comprensión del destino, error recuperable y preferencia razonada. No grabar por defecto. Si se miden acciones o duración, definir inicio/fin, interrupciones y dispositivo, y separarlas de este documento predictivo. Usar la matriz del plan de comunicación para decidir el piloto, no para fabricar significación A/B.

## 6. Accesibilidad y feedback: incrementos verificables

Hay fundamentos útiles: `lang="es"`, salto al contenido, navegación con `aria-current` (`base.html`), etiquetas asociadas por envoltura, botones nativos, texto `sr-only`, diálogo nativo, selector de archivos alternativo al arrastre y tooltip al foco (`app.css:805–852`). No constituyen una declaración de conformidad WCAG.

Antes de invitar:

- **Teclado y foco:** completar login, catálogo, creación, columnas, selección/alt de imagen, guardado, importación y propuesta con Tab/Shift+Tab, Enter/Espacio y Ctrl/Cmd+S. Verificar vuelta del foco al cerrar diálogo y conservación del cursor al insertar. El diálogo necesita nombre accesible (`aria-labelledby`); no depender solo del h3 visual.
- **Modos del editor:** `role=tablist` con botones sin `role=tab`, asociación a paneles ni navegación de flechas en el JS propio (`editor.html:36–56`; `frontend/editor/index.js:684–698`). Elegir botones de cambio de vista correctamente etiquetados, o implementar patrón completo de pestañas. No añadir ARIA parcial.
- **Arrastre no obligatorio:** el botón Elegir archivos ya es alternativa. El contenedor enriquecido tiene `tabindex=0` sin manejador propio Enter/Espacio; quitar esa parada redundante o darle conducta coherente. El manejador de `editor.js` pertenece al editor antiguo (`data-markdown-editor`), no asumir que resuelve el enriquecido.
- **Estado accesible:** `base.html:48–52`, la tira del editor y paginación carecen de anuncio vivo explícito. Éxitos con `role=status`/`aria-live=polite`; errores asociados al campo y resumen enfocable; indicar carga/guardado/fallo en texto, sin anunciar cada pulsación. Añadir mensaje de reintento a preview y generación PDF.
- **Cambios de contexto:** retirar autosubmit al recorrer colegio/curso/versión, mantener foco y selección; anunciar destino al aplicar. Índice/paginación deben comunicar página actual sin desplazar foco de modo impredecible.
- **Legibilidad:** comprobar con navegador real zoom 200%/400%, ancho estrecho, contraste y foco no tapado por cabecera. Conservar nombres visibles de las acciones clave; tooltip no es sustituto suficiente en táctil. Respetar reducción de movimiento al desplazarse a anclas.
- **Contenido accesible:** pedir alt significativo, no nombre de archivo automático; orientar encabezados por estructura y texto alternativo/transcripción para audio. Revisar orden de lectura de columnas y PDF por separado. No asumir que alt mostrado como pie equivale a etiqueta accesible de imagen PDF.

## 7. Priorización y criterios de aceptación propuestos

| Prioridad | Entrega mínima | Criterio de salida, pendiente de verificación |
|---|---|---|
| P0 — antes de participantes | Invitación sin GitHub, aislamiento de centro, audiencia privada validada, recuperación y aviso de privacidad | Invitación aceptada/revocada/caducada; cuenta no invitada rechazada; docente de otro centro no accede a material ni metadatos restringidos; roles mínimos. Comprobar Git además de UI. |
| P0 — confianza | Alinear fuente/bundle; guardado explícito, versión visible, errores sin pérdida silenciosa y salida con cambios | Guardar y reabrir conserva texto/imagen/alt; error de red no se presenta como éxito; quitar recursos no deja referencia rota; reconstrucción mantiene etiqueta de versión. |
| P0 — promesa de alcance | Delimitar importación y PDF, retirar afirmaciones falsas de bienvenida | TXT validado con vista previa y recuperación, formatos no soportados rechazados; o declarar función pendiente y retrasar piloto de alcance completo. PDF de muestra abierto e inspeccionado, limitaciones aceptadas por centro. |
| P0 — colaboración | Envío explícito y revisión interna controlada | Docente guarda sin publicar; revisor ve origen/destino/cambios, devuelve y aprueba una revisión concreta sin GitHub; no sobrescribe revisión nueva no examinada. Si solo hay aprobación manual asistida, etiquetar limitación y registrar decisión antes de aplicarla. |
| P1 — primera semana de uso | Defaults de Primaria, entrada al editor tras crear, guardado sin diálogo rutinario, Ayuda recuperable | Las tareas nucleares se encuentran sin conocimientos de repositorios; feedback y uso por teclado comprobados en entorno aislado. |
| P2 — después de evidencia | B guiado, conversión DOCX avanzada, búsqueda amplia, nuevos motores de maquetación | Solo priorizar si necesidades reales lo justifican. No distraer de pérdida de trabajo, privacidad o revisión. |

Los P0 son gates de producto; necesitan comprobaciones técnicas específicas adicionales. Esta auditoría no sustituye revisión de seguridad ni determina capacidad/horas de implementación.

## 8. Brecha de `user_stories.md` y ampliaciones recomendadas

Las tres historias actuales usan **administrador**: filtrar/comentar (6–19), columnas/imagen/PDF (21–38) y administración/logout (40–51). Útiles como regresión administrativa, insuficientes para el piloto. La segunda pide PDF válido, no fidelidad ni accesibilidad; tampoco comprueba invitación, importación, recuperación ni revisión por otro docente.

Añadir posteriormente —sin modificar ese fichero en este encargo— historias con cuentas sintéticas no administradoras:

1. Invitación válida/caducada, rechazo ajeno y reentrada sin proveedor Git.
2. Crear material de 3º Primaria con centro/audiencia correctos; editar, guardar, reabrir y recuperar de error.
3. Importar formato admitido sin reemplazo silencioso; rechazar DOCX/PDF cuando no hay conversión; conservar original.
4. Imagen y dos columnas → lectura → PDF real: detectar limitaciones, falta de recurso y versión antigua.
5. Docente propone → coordinador pide cambios → docente corrige → coordinador aprueba; versión aprobada no cambia antes. Probar docente de otro centro y revisión concurrente.
6. Mismas tareas por teclado y anuncio de errores/estados; cierre de sesión en ordenador compartido.

Si se ejecutan con la convención de `user_stories.md`, generar sus evidencias con datos sintéticos; las sesiones reales del piloto no requieren grabación y no deben incorporarse a un repositorio público. Comunicación, consentimiento y métricas operativas en [`../pilot-communication-plan.md`](../pilot-communication-plan.md).
