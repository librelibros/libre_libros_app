# Monitor de disponibilidad sin agente

`scripts/libre_libros_healthcheck.py` es un script determinista para un trabajo Hermes `--no-agent`. No invoca Hermes, LLM, navegador, Telegram ni acciones de recuperación. Su stdout está pensado para el **destino local de Hermes**; no demuestra entrega a otros canales. Esta implementación no instala ni modifica cron.

## Comprobaciones punto a punto

Una petición GET por endpoint, secuencial, al origen fijo `https://libre-libros-app.onrender.com`:

1. `/healthz`: HTTP 200 y objeto JSON con `status: "ok"`.
2. `/healthz/db`: HTTP 200 y objeto JSON con `status: "ok"` y `db: "ok"`.

Sin redirects ni reintentos. Cada endpoint tiene límite de 60 segundos (socket y reloj de pared mediante SIGALRM). El plazo global es de 145 segundos, inferior al presupuesto de 150 segundos, incluyendo lectura/escritura de estado. Requiere Linux/POSIX y ejecución en el hilo principal. SIGALRM cubre DNS y streaming lento, no solo espera inicial del socket. No es garantía de tiempo real ante un proceso congelado o IO del kernel no interrumpible.

Lee como máximo 4097 bytes por respuesta; rechaza cuerpos mayores de 4096. No imprime ni persiste cuerpos, cabeceras, URLs suministradas por respuestas ni mensajes de excepciones. El estado contiene únicamente códigos cerrados: `ok`, `http_error`, `timeout`, `network_error`, `body_too_large`, `invalid_json`, `unhealthy`.

## Estado local y transiciones

Por defecto mantiene un único resultado en `scripts/libre_libros_healthcheck.state.json`. Puede seleccionarse otro archivo mediante `LIBRE_LIBROS_HEALTHCHECK_STATE_PATH`. El directorio debe existir y ser escribible por el usuario del trabajo. No usar un directorio publicado por HTTP ni una ruta a credenciales. El script no carga dotenv.

El JSON, limitado a 4096 bytes, incluye versión, fecha UTC (`checked_at`), estados de ambos endpoints, `consecutive_failures`, `alerted` y `transition` (`alert`, `recovered` o null). Se reemplaza atómicamente mediante un temporal hermano con permisos privados; no conserva historial ni temporales tras una ejecución normal. El contador se satura en un millón para mantener tamaño acotado.

- Ambos endpoints correctos: exit 0 y stdout vacío.
- Uno o ambos fallan: exit 1 y diagnóstico breve fijo en stderr.
- **Tercer fallo consecutivo**: una línea de alerta en stdout y `transition: "alert"`.
- Fallos posteriores: stdout vacío; el contador continúa.
- Recuperación **después de alertar**: una línea en stdout, contador cero y `transition: "recovered"`.
- Recuperación tras uno o dos fallos: silenciosa.

Archivo ausente significa primera ejecución. Estado corrupto, demasiado grande, inconsistente o ilegible produce exit 1 y stderr explícito: no se sobrescribe ni se reinician silenciosamente los contadores, y no se consulta la red hasta resolverlo. Un error de escritura también produce exit 1 y no anuncia una transición que no se ha persistido. Un plazo global agotado no promete persistencia nueva; revisar la fecha del último resultado.

Ejecutar **un solo trabajo a la vez por archivo**: no hay bloqueo entre procesos. El planificador debe evitar solapamientos y espaciar ejecuciones más que el presupuesto global. El estado y stdout no constituyen una cola de entrega fiable: una interrupción entre persistir y emitir puede perder una notificación. Verificar por separado cómo Hermes registra exit 1 y trata stdout de un trabajo fallido; no se ha probado esa integración ni la entrega local.

## Límites

Esto **no es E2E**: no prueba login, invitaciones, editor, guardado Git, comentarios, propuestas ni exportación PDF. Una respuesta saludable no prueba que esos recorridos funcionen. Tampoco evita todas las pausas de alojamiento, suspensión, indisponibilidad de red o BD. No reinicia, despliega ni mantiene artificialmente activo el servicio como garantía. No recoge secretos ni lee configuración de producción.

## Validación hermética

```sh
.venv/bin/python -m pytest tests/test_availability_monitor.py -q
```

Los tests inyectan un opener simulado y archivos temporales: éxito, fallo BD, JSON inesperado, timeout, cuerpo grande, redirect rechazado, estado corrupto, error de persistencia, tercer fallo y recuperación. No ejecutar el script directamente para esta validación: su entrada CLI sí consulta el origen configurado. No se invocan Hermes ni servicios externos.
