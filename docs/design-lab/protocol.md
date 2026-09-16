# Comparación de diseño A/B — protocolo previo

Fecha: 2026-09-16. Estado: preparación; aún sin resultados. Encargo: valorar si otro diseño general y otro icono facilitan el uso docente. Solo archivos locales, sin despliegue ni contacto con participantes.

## Qué podemos concluir

Comparación exploratoria de prototipos y revisión heurística mediante perfiles de agentes **simulados**, no experimento con docentes. Automatizar acciones demuestra funcionamiento del mock, no facilidad de descubrimiento ni comprensión humana. No estimar tiempos docentes, tasas de éxito poblacionales o significación estadística. No dar por implementadas las capacidades de un mock en la aplicación real.

## Condiciones

- **A (referencia):** reproduce la jerarquía visual actual: barra lateral, avisos, estadísticas y catálogo. No es una captura ni una réplica exacta del producto.
- **B (alternativa):** cabecera compacta y catálogo prioritario, filtros visibles, lenguaje docente y acceso a pendientes sin ocupar la entrada completa.
- Ambos: mismo catálogo sintético de Primaria, mismo perfil y propuesta pendiente, filtros por curso/materia, editor simplificado idéntico y mismas capacidades. Los cambios de etiquetas/jerarquía/color se estudian como un paquete, no se podrá aislar causalmente cada componente.
- Mantener el icono actual en A y B. Estudiar la marca en una hoja separada: actual frente a dos candidatos, sin declarar que cambiarla mejora tareas.
- Edición/guardado/revisión son estados locales simulados; no backend, persistencia real, colaboración real ni PDF generado. Límite visible en cada pantalla.
- Sin datos de alumnado, fuentes externas, analítica remota ni cuentas reales.

## Hipótesis y riesgos contrarios

| Hipótesis | Evidencia posible en esta fase | Qué la debilitaría |
|---|---|---|
| B hace más visible encontrar material | Posición de catálogo/filtros en viewport y evaluación independiente del primer paso | Pendientes o ayuda difíciles de localizar, demasiadas acciones rivales |
| Etiquetas docentes aclaran destino del guardado | Texto visible distingue copia, envío y publicación; juicio de perfiles | «Guardado» parece publicación, confirmación sin contexto |
| B funciona mejor en pantallas estrechas | Sin desbordamiento a 390 y 320 px, controles y foco utilizables | Cabecera envuelve excesivamente, acciones quedan ocultas |
| Icono simple resiste tamaños pequeños | Capturas 16/24/32 px y revisión visual | Libro irreconocible o demasiado genérico; mejora estética sin efecto de uso |

## Tareas iguales

1. Encontrar material de Lengua de 3º de Primaria y abrirlo; explicar su audiencia.
2. Adaptar una copia; escribir una modificación y guardar. Identificar qué queda publicado (nada en el mock).
3. Importar TXT/Markdown autorizado, cancelar primero la sustitución y verificar que conserva el texto; aceptar después. Intentar DOCX y comprobar mensaje y conservación.
4. Localizar salida PDF y su limitación explícita. **No puntuar generación/fidelidad de PDF: fuera del alcance del mock.**
5. Enviar copia a revisión, localizar el estado pendiente y distinguirlo de aprobación.
6. Localizar una propuesta pendiente como coordinador simulado. Valorar si la prioridad de catálogo perjudica este rol.
7. Repetir acciones esenciales mediante teclado y en ancho estrecho; revisar retorno de foco de diálogos y estado vacío de filtros.

## Registro automatizado previsto

Capturas A/B a 1440×1000 y 390×844; comprobación adicional a ancho CSS 320 px (aproxima reflow, no sustituye zoom real). Registrar errores JS, ancho documento, posición vertical de catálogo/filtros, comportamiento de filtros y transiciones simuladas, conservación de texto al cancelar/rechazar importación, foco visible y retorno al cerrar diálogos. Las acciones de scripts son recorridos programados, no clics de descubrimiento humano. Medición de contraste de pares usados, sin declarar conformidad WCAG completa.

## Revisión independiente prevista

Tres perfiles ficticios: docente que usa correo/documentos y no Git; docente que reutiliza materiales y prefiere teclado; coordinación con prioridad de revisar propuestas. Revisores reciben tareas, artefactos y límites, no una conclusión deseada. Orden A→B y B→A alternado cuando sea posible; agentes no equivalen a una muestra independiente de personas y el contrabalanceo no elimina sus sesgos. Informar ventajas, costes y evidencia por variante, con opción **ninguna / insuficiente evidencia**. Separar inspección del código, lectura de capturas y acciones realmente ejecutadas.

## Regla de decisión previa

- Rechazar una variante como candidata si impide una tarea esencial, pierde texto silenciosamente en el mock o hace ambiguo guardar frente a publicar.
- B solo se recomienda para implementación acotada si supera las comprobaciones compartidas, mejora visibilidad de la tarea de catálogo y no oculta pendientes ni empeora teclado/reflow. La recomendación será provisional y trazable, no «validada por docentes».
- Un cambio solo cosmético de color/icono no basta para justificar rehacer la aplicación.
- No sustituir templates ni CSS de producto en esta fase. Implementación posterior por componentes y con regresiones existentes; ningún mock autoriza relajar permisos o confirmar publicación automáticamente.

## Validación humana posterior (no ejecutada)

Con autorización y consentimiento, comparación exploratoria con 6 docentes adultos: tres A→B y tres B→A, ejercicios equivalentes de dificultad comparable para reducir aprendizaje, mismo dispositivo por persona. Anotar tarea terminada, ayuda solicitada, errores, explicación del destino y preferencia razonada. Sin grabación por defecto, sin datos de alumnado. Si se registran tiempos, definir inicio/fin y excluir interrupciones explícitamente. No tratar esta muestra como prueba estadística. La decisión del propietario y las puertas de aceptación del piloto siguen siendo necesarias.
