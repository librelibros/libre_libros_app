# Plan de comunicación y acompañamiento del piloto

Fecha: 16 de septiembre de 2026. **Plan propuesto, no ejecutado.** No se han obtenido contactos, hecho scraping, enviado mensajes ni contactado centros o terceros. Todos los textos son borradores con marcadores; requieren responsable, revisión y autorización antes de utilizarlos.

## 1. Objetivo, población y promesa honesta

Piloto gratuito de seis semanas con **3–5 centros de Primaria de España y 10–20 docentes adultos en total**. Objetivo: comprobar si pueden crear/adaptar material propio o autorizado, guardarlo, incorporar contenido en un formato admitido, obtener PDF y someter cambios a revisión del centro sin tener cuenta GitHub.

No es implantación escolar, evaluación del profesorado ni servicio para alumnado. No solicitar nombres, imágenes, voces, calificaciones, trabajos identificables, necesidades educativas, listados o cualquier dato de menores. Tampoco subir documentos que los contengan por accidente, incluidos comentarios, propiedades del archivo o fotografías. Usar ejemplos sintéticos o materiales docentes limpios con derechos de uso.

**No anunciar todavía como disponibles** invitación segura, importación documental amplia, PDF fiel a la maquetación o circuito completo de devolución de propuestas: son brechas de la inspección estática descritas en [`audit/product-ux.md`](audit/product-ux.md). La entrada por invitación sin GitHub es requisito de lanzamiento, no una opción sustituible por pedir al docente que se registre en GitHub.

Oferta, una vez verificada: sin coste durante las seis semanas, sin tarjeta, sin renovación ni conversión automática a pago, participación voluntaria y exportación/salida acordada. No prometer gratuidad indefinida, integración institucional, mejora de resultados académicos ni ahorro de tiempo que todavía no se ha medido.

## 2. Gates y responsables antes de cualquier invitación de acceso

| Gate | Evidencia a preparar en entorno aislado | Responsable propuesto |
|---|---|---|
| G1: acceso y alcance | Invitación de uso único/caducidad/revocación, recuperación, cuenta sin GitHub, centro y rol correctos. Sin alta abierta accidental ni contraseñas compartidas. | Responsable técnico |
| G2: privacidad real | Roles, visibilidad y aislamiento entre centros; exposición de repositorios, historial Git, correos/nombres de autor y registros. No basta etiqueta «privado». | Técnico + responsable de privacidad |
| G3: tareas útiles | Guardado/reapertura sin pérdida, carga de recursos, formato de importación declarado y probado, PDF real inspeccionado, propuesta y revisión interna con destinatario correcto. | Producto + coordinador pedagógico |
| G4: atención y salida | Canal atendido, horario realista, procedimiento de incidencias/baja y exportación/supresión, aviso de privacidad completo. | Responsable del piloto |
| G5: acuerdo informado | Centro acepta alcance y límites, responsable del tratamiento identificado y reparto de funciones documentado; participación y opciones individuales separadas. | Responsable del piloto + interlocutor del centro/DPD cuando corresponda |

Si falta un gate, retrasar acceso. Se puede mantener una conversación de descubrimiento **previamente solicitada**, indicando que es una preinscripción y no un piloto funcional. No solucionar un bloqueo de privacidad con una casilla de aceptación del riesgo.

Equipo mínimo: una persona responsable del piloto/producto y comunicación; una persona técnica con respaldo para incidentes; una persona coordinadora por centro (puede ser docente participante) y un revisor autorizado por centro. Privacidad requiere una persona responsable competente y consulta al DPD del centro cuando proceda, no necesariamente una nueva contratación. Nombrar titulares y suplencias antes de publicar horarios.

Capacidad de referencia: reservar 3–4 horas semanales de acompañamiento central, más un bloque técnico reservado para incidencias; es presupuesto propuesto, no tiempo observado ni garantía de resolución. Empezar con 3 centros/10 docentes y ampliar hasta 5/20 únicamente si soporte y gates se mantienen. Sin disponibilidad técnica real, reducir cohorte o aplazar.

## 3. Captación sin scraping ni prospección masiva

### Canales permitidos, sujetos a revisión previa

1. Centros que hayan solicitado información o autorizado expresamente recibir la invitación por ese canal.
2. Contacto personal existente: pedir autorización en una conversación ya abierta y apropiada antes de enviar información promocional; la mera relación previa no equivale a consentimiento comercial.
3. Referencia voluntaria: quien conoce al centro comparte, con sus propias autorizaciones, un enlace de información pública o facilita que el centro contacte. No pedir listas de correos del claustro ni datos de terceros.
4. Convocatoria informativa publicada por una asociación/red docente que haya aceptado alojarla bajo sus reglas; no publicar ni escribir a esa entidad sin autorización adicional. Las personas interesadas se inscriben por iniciativa propia.

No comprar bases, extraer directorios, usar correos públicos de webs para campañas, añadir a grupos ni subir agendas a plataformas publicitarias. Un correo institucional visible no autoriza publicidad. No considerar automáticamente exemptas de LSSI las invitaciones por ser gratuitas, educativas o B2B; incluso un mensaje para «pedir permiso» puede ser una comunicación promocional. Elegir canales de demanda entrante/permiso documentado y revisar la aplicabilidad antes de enviar.

### Selección y registro mínimo

Priorizar 3 centros con una persona coordinadora y 3–4 docentes iniciales por centro; incorporar hasta 5 centros y 20 docentes según disponibilidad. Buscar diversidad práctica de ciclos, experiencia digital, dispositivos y contexto de centro, sin recopilar categorías sensibles ni hacer inferencias sobre discapacidad. Ofrecer que cada participante comunique ajustes de accesibilidad necesarios sin exigir diagnóstico.

Confirmar: Primaria, material sin alumnado, derechos sobre contenidos, capacidad de realizar una actividad breve por semana y existencia de revisor. No seleccionar solo expertos digitales. No hay muestra representativa ni conclusiones generalizables a toda España.

Registro de contactos fuera del repositorio de código, acceso restringido:

- ID de centro/participante, interlocutor y correo profesional estrictamente necesario.
- Origen del contacto, fecha, alcance y prueba de solicitud/autorización, canal permitido.
- Estado: interesado, información solicitada, invitado, activo, baja/no contactar.
- Información de privacidad facilitada y versión; no almacenar cadenas de correo completas si basta registro mínimo.

No fijar objetivo de «cientos de contactos». Trabajar con un pequeño grupo de centros autorizados; detener captación al cubrir plazas y pedir permiso antes de conservar una lista de espera. Un único seguimiento de una solicitud reciente sin respuesta, si estaba dentro del permiso, y después cerrar. No insistir a quien rechaza o guarda silencio.

## 4. RGPD, LOPDGDD y LSSI: decisiones previas

Marco operativo orientativo, **no dictamen jurídico ni declaración de cumplimiento**. Antes de arrancar, responsable del proyecto y centro deben revisar las obligaciones aplicables, contratos y textos concretos.

### Separar tratamientos y permisos

| Finalidad | Propuesta a validar | Qué no hacer |
|---|---|---|
| Responder a una solicitud de información | Documentar solicitud, canal y base jurídica aplicable a la gestión de esa solicitud; informar al recoger datos. | Interpretar solicitud puntual como alta en boletín. |
| Cuenta y funcionamiento del piloto | Determinar responsable y base del art. 6 RGPD según relación real: ejecución del acuerdo cuando sea necesaria y procedente, u otra base documentada. Centro y proyecto deben decidir si existe encargo del art. 28 o responsabilidades independientes. | Usar un consentimiento genérico para justificar cualquier tratamiento o imponerlo a trabajadores mediante dirección. |
| Soporte y seguridad | Limitar a lo necesario, documentar base, destinatarios y conservación; no reutilizar incidencias para marketing. | Recoger contraseñas, tokens o documentos completos con datos personales para diagnosticar. |
| Feedback y observación opcionales | Participación libre e informada; consentimiento separado cuando sea la base elegida, revocable sin perder acceso al piloto. Sin grabación por defecto. | Confundir el acuerdo del centro con consentimiento individual a grabación o investigación. |
| Noticias/promoción posterior | Opt-in separado, no premarcado, finalidad/canal claros, prueba conservada y baja sencilla en cada mensaje; revisar art. 21 LSSI. | Añadir automáticamente participantes a campañas; asumir que la gratuidad elimina LSSI. |

El aviso de privacidad debe incluir identidad y contacto reales del responsable/DPD si aplica, finalidades y bases, destinatarios y encargados, transferencias internacionales y garantías si existen, plazos/criterios de conservación, derechos de acceso/rectificación/supresión/limitación/oposición/portabilidad cuando procedan, retirada del consentimiento y reclamación ante AEPD. Explicar si los campos son necesarios y consecuencias de no aportarlos. No publicar borradores con marcadores pendientes.

Revisar proveedores reales de alojamiento, identidad, correo, repositorio y soporte, región de datos, contratos y subencargados; no inferir residencia europea del idioma de la aplicación. Git puede conservar nombre, correo, ramas e historial: impedir exposición pública y explicar retención. Si no se puede garantizar el tratamiento acordado, no introducir cuentas reales.

Revisar cookies y almacenamiento local: distinguir sesión/preferencias necesarias de analítica opcional; no añadir rastreadores, píxeles de apertura o grabación de sesión para este piloto. Preferencia local de ocultar bienvenida no equivale a consentimiento publicitario.

### Información y elecciones individuales propuestas

- «He leído las condiciones y la información de privacidad del piloto» como constancia informativa, no como consentimiento universal.
- «Confirmo que no subiré datos de alumnado y que tengo derechos para usar los materiales» como regla de uso; no sustituye controles de producto.
- Opcional e independiente: «Quiero participar en una conversación de feedback sobre mi experiencia».
- Si excepcionalmente se propone grabación: consentimiento específico para audio/pantalla, finalidad, acceso y borrado; opción equivalente sin grabación. Evitar vídeos del escritorio con correo, nombres o notificaciones.
- Opcional e independiente: «Quiero recibir noticias de Libre Libros después del piloto por correo». No necesario para participar; retirada sencilla.

### Conservación, salida y accidentes

Plazos **propuestos**, a validar y comunicar antes de recoger datos:

- Interesados no incorporados: cerrar y borrar datos operativos dentro de 30 días tras cerrar selección; lista de espera solo con permiso y plazo explícito.
- Cuentas/materiales del piloto: exportación durante la semana 6 y ventana de 30 días posterior; luego desactivar y ejecutar política de eliminación/anominización acordada salvo nueva relación voluntaria. No migrar automáticamente a otro servicio.
- Tickets y notas identificables de feedback: borrar o anonimizar dentro de 90 días del cierre; conservar solo agregados no reidentificables para decisión de producto.
- Prueba de permisos, retirada y lista mínima de no contactar: conservar restringidamente lo necesario para acreditar cumplimiento/evitar nuevos mensajes, con plazo justificado; no retener el perfil entero bajo ese pretexto.
- Backups, logs y Git: fijar ciclos y límites reales de eliminación; no prometer borrado instantáneo de historial distribuido. Explicar las excepciones legales y periodos de conservación aplicables.

Solicitud de derechos: confirmar recepción, verificar identidad de forma proporcional y responder dentro del plazo RGPD aplicable (normalmente un mes), separando ese plazo del objetivo de respuesta de soporte. Baja del piloto no exige justificar motivos. El centro no recibe evaluaciones individuales del profesorado.

Si aparece material de alumnado o exposición entre centros: dejar de compartir, restringir acceso y detener la actividad afectada; escalar de inmediato a responsable técnico/privacidad; no reenviar capturas por correo colectivo. Evaluar contención, alcance y borrado, mantener registro mínimo del incidente y valorar las notificaciones RGPD pertinentes, incluida autoridad en 72 horas desde conocimiento cuando corresponda y personas afectadas si hay alto riesgo. No todo fallo técnico constituye una brecha notificable ni el plazo permite esperar tres días para actuar.

## 5. Calendario de seis semanas

Calendario relativo; acordar fechas con cada centro, evitando evaluaciones, cierres de trimestre y festivos autonómicos. Si el trabajo técnico previo supera la semana 1, desplazar el inicio, no comprimir artificialmente la evaluación. Dedicaciones de participantes son límites/estimaciones de planificación, no tiempos de tarea medidos.

| Semana | Comunicación y actividad | Carga y responsables | Salida/decisión |
|---|---|---|---|
| 1 — preparación y selección | Resolver gates, responder solicitudes autorizadas, acordar alcance gratuito y límites, confirmar 3 centros/10 participantes iniciales. Recoger opciones individuales; no enviar enlaces de acceso hasta G1–G5. | Responsable piloto y técnico; coordinador acuerda sesión y material sintético. Conversación de encaje propuesta de 20 min por centro. | Lista mínima autorizada; aviso definitivo; circuito de soporte; acceso probado. Si falla gate, aplazar y avisar sin promesas de fecha no confirmada. |
| 2 — incorporación | Invitación individual; sesión opcional de 30 min con alternativa guía accesible de una página. Tarea: entrar, localizar ejemplo y guardar una pequeña adaptación. | Cada docente elige sesión o guía; coordinador comprueba que nadie necesita GitHub. Soporte central recoge bloqueos, no exige éxito a todos. | Activación sin ayuda especial; subsanar acceso/guardado antes de sumar centros. |
| 3 — crear y reutilizar | Un mensaje de tarea: crear actividad propia limpia e importar el formato expresamente admitido. Mostrar advertencia de incompatibles. Prototipos A/B opcionales con voluntarios, sin despliegue doble. | Actividad semanal propuesta de 15–20 min, ampliable solo voluntariamente; franja de ayuda opcional. | Identificar si importación limitada impide valor; decidir corregir alcance o posponer centros dependientes de Word. |
| 4 — PDF y revisión | Descargar y abrir PDF real, revisar orden, imágenes y fidelidad; enviar una propuesta. Coordinador revisa, pide cambios o aprueba según circuito probado. | Docente y revisor del centro; objetivo operativo de primera respuesta de revisión en 3 días lectivos, no SLA garantizado. | Una propuesta por centro con resultado trazable y una salida PDF aceptada o limitación documentada. |
| 5 — repetición autónoma | Invitar a repetir una tarea útil sin facilitador. Un breve formulario opcional sobre valor, barreras y comprensión de versión. No introducir funciones nuevas salvo correcciones necesarias. | Responsable producto consolida casos; soporte ofrece ayuda, no rescata silenciosamente para mejorar tasas. | Medir retorno y carga real de soporte. Ampliar a 5/20 solo si queda una ventana útil; si no, diferir nueva cohorte. |
| 6 — cierre y devolución | Resumen agregado al centro, conversación opcional, instrucciones de exportación/baja, explicar ventana posterior y decisión. Pedir autorización separada si se desean noticias futuras. | Responsable piloto + coordinadores; conversación final propuesta de 20 min por centro. | Continuar, iterar o detener según criterios. Sin renovaciones automáticas, publicación de testimonios ni logos del centro sin permiso específico. |

Cadencia máxima ordinaria: un resumen de tarea semanal, además de invitación y comunicaciones necesarias de seguridad/servicio. No enviar recordatorios de tareas a quien se ha retirado; no confundir baja de noticias con eliminación automática de cuenta o supresión de avisos de seguridad necesarios.

## 6. Soporte realizable

Canal único: `[correo de soporte verificado]`, con alternativa de sesión concertada si hay barrera de accesibilidad. Horario propuesto: laborables de 16:00 a 18:00, zona Europe/Madrid, **solo si hay cobertura confirmada**. Acuse humano objetivo en un día laborable; no prometer resolución en ese plazo ni atención 24/7. Ofrecer una franja colectiva opcional de 30 min/semana, con pantalla/material sintético y sin datos personales de otros participantes.

Solicitud mínima de ayuda: tarea que intentaba hacer, ID no sensible del material, mensaje de error y navegador si lo conoce. Captura opcional recortada; recordar ocultar nombres/correos. Nunca pedir contraseña, enlace de invitación activo, token, archivo de alumnado o acceso remoto sin proceso separado.

Clasificación:

- **P0:** privacidad, pérdida confirmada de material o publicación no autorizada. Suspender flujo/cohorte afectada y escalar a técnica/privacidad; emitir instrucciones prácticas en cuanto estén verificadas.
- **P1:** no puede entrar, guardar, importar lo admitido, revisar o exportar. Priorizar siguiente bloque técnico; avisar del estado y alternativa segura, sin inventar plazo.
- **P2:** dudas de uso, etiquetas y mejoras. Responder en la franja habitual y agrupar para revisión semanal.

Cada ticket tiene ID, responsable, severidad, estado y cierre confirmado por quien consulta cuando sea posible. Contabilizar ayudas y rescates; no contabilizar como éxito autónomo una tarea hecha por soporte. Un canal de incidencias no debe transformarse en repositorio de datos personales públicos.

## 7. Mensajes borrador — no enviados

### M1. Respuesta a centro que ha solicitado información

**Asunto:** Información solicitada: piloto gratuito Libre Libros para Primaria

Hola, [nombre/interlocutor]:

Gracias por vuestro interés y por autorizarnos a responder por este canal. Estamos preparando un piloto gratuito de seis semanas para 3–5 centros y 10–20 docentes en total. Buscamos comprobar si resulta útil adaptar materiales docentes y revisarlos en equipo, sin datos de alumnado.

El acceso del piloto será por invitación, sin necesitar GitHub, una vez verificado. Compartiremos por escrito qué formatos se pueden importar y qué limitaciones tiene el PDF; no queremos prometer una conversión perfecta. No habrá tarjeta, contratación ni renovación automática.

Proponemos una actividad breve a la semana y una persona coordinadora por centro. ¿Queréis una conversación de encaje de unos 20 minutos o preferís recibir la ficha de alcance? Si no os interesa continuar, lo dejamos aquí.

[Responsable y entidad] · [contacto] · [información de privacidad]

*Uso: solo respuesta solicitada/autorizada; no plantilla para correo frío.*

### M2. Confirmación de alcance antes del alta

**Asunto:** Confirmación de participación y límites del piloto

Hola, [nombre]:

Estas son las fechas propuestas: [inicio–fin]. El piloto es gratuito y voluntario. Probaremos [funciones verificadas]; la importación admite [formatos comprobados] y el PDF [limitaciones verificadas]. No admite [formatos/funciones pendientes].

Usaremos únicamente materiales propios o autorizados, sin nombres, fotos, voces, trabajos identificables ni otros datos de alumnado. Tu material será visible para [audiencia comprobada]; [rol] revisará las propuestas antes de incorporarlas a la versión del centro.

Aquí están las condiciones, la información de privacidad, las opciones voluntarias de feedback y la salida/exportación: [enlaces revisados]. Confírmanos si este alcance os resulta útil. No necesitamos que nos enviéis una lista del claustro: cada participante puede solicitar su propia invitación.

[Responsable] · [soporte]

### M3. Invitación individual de acceso, solo tras superar gates

**Asunto:** Tu invitación al piloto Libre Libros — [centro]

Hola, [nombre]:

Has solicitado participar en el piloto de [centro]. Acepta tu invitación en [enlace individual]. Caduca el [fecha/hora] y es de un solo uso; no la reenvíes. No necesitas cuenta GitHub ni enviar una contraseña a nadie. Si caduca o no la has solicitado, escribe a [soporte].

Primera tarea: abre el material de ejemplo, cambia una actividad y guarda tu versión. Guardar no la publica ni la envía automáticamente a revisión. No subas datos de alumnado.

Guía accesible: [enlace]. Sesión opcional: [fecha]. Privacidad y retirada del piloto: [enlace].

[Responsable y entidad]

*No incluir enlace real ni contraseña en este documento.*

### M4. Acompañamiento semanal

**Asunto:** Semana [n]: [una tarea concreta]

Hola:

Esta semana proponemos [tarea] con el material de ejemplo o uno propio sin datos de alumnado. La actividad prevista es breve; si no tienes disponibilidad, puedes omitirla sin dar explicaciones.

Recuerda: [una limitación relevante, por ejemplo «el PDF puede mostrar las columnas una detrás de otra; ábrelo antes de imprimir»]. Para terminar, comprueba [resultado concreto]. ¿Has podido hacerlo sin ayuda, con ayuda o no has podido? Responder es opcional.

Si te bloqueas, envía a [soporte] el paso y el mensaje de error, sin contraseñas ni datos personales. [Horario confirmado].

[Responsable]

### M5. Acuse de soporte/incidencia

**Asunto:** Recibido: incidencia [ID]

Hola, [nombre]:

Hemos recibido tu consulta sobre [tarea]. La revisa [rol responsable]. [Instrucción verificada: por ejemplo «no vuelvas a enviar la propuesta hasta que confirmemos su estado»]. No necesitamos tu contraseña ni documentos con datos de alumnado.

Te informaremos del siguiente paso en [próxima franja confirmada]. Aún no tenemos un plazo de resolución. Si se trata de una exposición de datos, usa [canal de privacidad] y evita reenviar el contenido.

[Soporte]

### M6. Cierre, devolución y salida

**Asunto:** Cierre del piloto y opciones para tu material

Hola, [nombre]:

El piloto termina el [fecha]. Gracias por participar. Estas son las conclusiones agregadas: [hallazgos reales, distinguiendo límites y problemas]. No publicaremos valoraciones individuales, nombres, imágenes ni testimonios sin permiso específico.

Puedes exportar tu material mediante [procedimiento comprobado] hasta [fecha]. Después aplicaremos [desactivación y conservación/borrado acordados, incluidos límites de backups/historial]. Si deseas retirarte antes o ejercer derechos, contacta con [responsable de privacidad].

La decisión es [continuar de forma voluntaria / corregir y proponer otra fase / cerrar]. No hay renovación ni cobro automático. Solo enviaremos noticias posteriores a quien las haya solicitado por separado.

[Responsable y entidad]

## 8. Métricas y reglas de decisión

**Son objetivos propuestos, no resultados obtenidos.** Registrar recuentos y denominadores, no solo porcentajes: con 10–20 personas, una persona cambia mucho la tasa. Mostrar también distribución por centro cuando no permita identificar individuos; evitar rankings o segmentaciones de grupos demasiado pequeños. Las simulaciones de `audit/product-ux.md` no entran en estas métricas.

Preferir registro manual mínimo de estados confirmados y cuestionario opcional; cualquier instrumentación nueva requiere revisión de finalidad y minimización. No recoger texto escrito, pulsaciones, pantalla, rutas con nombres, tokens de invitación o contenido de archivos. ID seudónimo no convierte el registro en anónimo. Registrar accesos reales solo con información previa y base documentada. No usar aperturas de email como participación.

| Métrica | Definición y fuente futura | Umbral de referencia / acción |
|---|---|---|
| Cohorte | Centros confirmados y docentes que aceptan, excluyendo lista de espera | 3–5 y 10–20, sin escalar para maquillar abandono. |
| Activación | Invitados que aceptan y guardan/reabren una adaptación en los primeros 7 días / invitados con 7 días de oportunidad; estado servidor + confirmación, distinguir ayuda | Objetivo ≥80%; por debajo, arreglar acceso/primer guardado antes de captar más. Informar no activados y motivos voluntariamente aportados. |
| Tareas nucleares | Por tarea: completada sin ayuda, con ayuda o bloqueada / participantes que la intentaron; creación, edición, importación admitida, PDF y propuesta por separado | Objetivo ≥80% sin ayuda en cada tarea intentada. Añadir intentos/activos para que una tarea evitada no parezca exitosa. Fallos de integridad nunca compensados por promedio. |
| PDF utilizable | PDFs que el docente abre y considera utilizables para la tarea prevista / exportaciones revisadas; anotar límites de columnas/imágenes | Objetivo ≥80% y cero pérdida silenciosa; si exige intervención manual frecuente, reducir promesa o detener ese flujo. Un HTTP 200 no acredita utilidad. |
| Comprensión de publicación | Participantes que distinguen guardar, enviar y aprobar y reconocen audiencia en pregunta breve / quienes responden | Objetivo ≥80%, mostrando no respuestas; cualquier publicación involuntaria exige revisión inmediata. |
| Revisión efectiva | Propuestas con decisión/solicitud de cambios trazable / propuestas enviadas antes del cierre; informar pendientes y antigüedad | Al menos un ciclo completo por centro; objetivo de primera respuesta ≤3 días lectivos, distinguiendo disponibilidad humana de defecto del producto. |
| Repetición | Docentes que vuelven otra semana y completan una segunda tarea útil / activados con al menos dos semanas de oportunidad | Referencia ≥60%; estudiar razones de falta de retorno sin atribuirlas automáticamente a UX. |
| Carga de soporte | Tickets y minutos **reales futuros**, registrados por soporte, por activo y semana; severidad y rescates separados | Referencia mediana ≤15 min/activo/semana después de incorporación y total dentro del presupuesto central. Superar capacidad impide ampliar. No es tiempo de ejecución de tarea. |
| Valor percibido | Respuestas a «¿te serviría repetirlo en tu preparación habitual?» con sí/no/depende y motivo / quienes responden | Referencia ≥70% sí; publicar participación en encuesta y motivos, no inferir satisfacción de silencio. |
| Privacidad/control | Incidentes de exposición entre centros, datos de alumnado o publicación no autorizada; pérdida confirmada | Objetivo cero. Cualquier caso pausa el flujo afectado hasta investigar/contener; no esperar a la semana 6. |

### Decisión al final de la semana 6

- **Continuar en cohorte limitada:** gates vigentes, cero incidentes críticos sin resolver, un ciclo de revisión por centro, objetivos de activación/tareas/repetición/valor razonablemente cumplidos y soporte sostenible. Acordar nueva fase explícita; no declarar validación de mercado ni impacto educativo.
- **Iterar antes de ampliar:** valor percibido pero tareas, comprensión, importación/PDF o soporte no alcanzan referencias; seleccionar como máximo tres cambios ligados a evidencia, acordar nuevo alcance y solicitar voluntarios para otra fase. No sustituir umbrales retroactivamente para declarar éxito.
- **Detener o aplazar:** acceso sin GitHub no resuelto, aislamiento/privacidad insuficiente, pérdida de trabajo, publicación inesperada o tarea esencial no realizable de forma útil. Comunicar con transparencia, ofrecer exportación segura y cumplir bajas/conservación.

Revisión semanal de gates y métricas por responsable piloto/técnico, con coordinadores solo para datos de su centro que deban conocer. Informe final pequeño: recuentos, casos anonimizados, limitaciones de muestra, tareas no intentadas, ayudas dadas y decisión. Nunca convertir simulaciones docentes, borradores de mensajes o comprobaciones estáticas en evidencia de adopción real.
