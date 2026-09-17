# Auditoría de CI, despliegue y disponibilidad gratuita

Fecha: 2026-09-16. Repositorio: `libre_libros_app`, HEAD observado `69e3f5b`.

## Alcance y conclusión

Inspección de `.github/workflows/`, Docker, `render.yaml`, scripts y documentación; lectura puntual del arranque, configuración y base de datos para comprobar sus implicaciones operativas. Había cambios locales de otras sesiones, que no se han modificado. Las referencias describen lo observado durante la lectura, no certifican el estado final de esos cambios concurrentes.

**Único archivo creado por esta auditoría: `docs/audit/deployment.md`.** No se leyeron `.env` ni `.env_docker`; sí sus nombres, exclusiones y ejemplos públicos. No se ejecutaron scripts de despliegue, tests que pudieran arrancar la aplicación, APIs autenticadas, login OAuth, migraciones, Docker ni operaciones sobre datos remotos. Las propuestas siguientes no están implementadas ni desplegadas.

**Dictamen:** el stack puede servir para una demo/piloto pequeño con interrupciones aceptadas. No hay base para prometer disponibilidad continua gratuita. El pipeline actual puede estar verde sin haber desplegado el commit esperado ni tener una aplicación utilizable. Antes de distribuir nuevas imágenes o ampliar el piloto, deben resolverse la exclusión de secretos del contexto Docker, los falsos positivos del despliegue y la validación del modo de autenticación. La revisión de exposición de datos/credenciales es además un bloqueo de seguridad pendiente de validación por el propietario.

## Comprobación pública realizada

Dos peticiones anónimas `GET https://libre-libros-app.onrender.com/healthz` desde el entorno de auditoría:

| Intento | Límite | Resultado |
|---|---:|---|
| 1 | 90 s | curl exit 28; 90,002903 s; 0 bytes; código reportado `000` |
| 2 | 120 s | curl exit 28; 120,002469 s; 0 bytes; código reportado `000` |

`000` **no es un estado HTTP**: no se recibió una respuesta HTTP. Estos resultados no distinguen un problema de DNS/TLS/red/proxy, suspensión de Render, arranque bloqueado o indisponibilidad de la aplicación. No prueban que el código de `/healthz` sea culpable, ni permiten estimar uptime. No se consultó `/healthz/db` ni se completó login. Un GET puede despertar un servicio gratuito; no se solicitó ninguna modificación de aplicación o datos.

Siguiente prueba autorizable: repetir desde otra red con métricas de DNS, conexión, TLS y primer byte; contrastar con estado público del proveedor. Si el propietario revisa el Dashboard, comprobar estado/suspensión, cuota, último commit live y tiempos de startup, **sin copiar valores de entorno ni logs sin sanear**. No aumentar indefinidamente reintentos ni reiniciar a ciegas.

## Hallazgos prioritarios

P0 = contención si se confirma exposición real; P1 = bloqueo para un despliegue fiable/seguro; P2 = endurecimiento y reducción de costes.

### D01 — P1: el contexto Docker puede incluir secretos y datos locales

- Evidencia: `Dockerfile:15` usa `COPY . .`; `.dockerignore:1-6` no excluye `.env`, `.env_docker`, variantes de entorno, `.agents`, `.claude`, `.local`, `.venv` o cachés Python. `.gitignore` no controla Docker. Los dos archivos privados existen localmente, pero no se leyó su contenido; `git ls-files` únicamente mostró los ejemplos como archivos de entorno versionados.
- Impacto: un build local copia esos archivos a la imagen y puede enviar sus bytes a un builder remoto. `Settings` carga `.env`, por lo que además puede introducir configuración local no deseada. Un build de Render desde un checkout limpio no implica por sí solo que esos archivos privados existan allí: **no se afirma una filtración en producción**.
- Propuesta: preferir `COPY` explícitos de runtime; excluir `.env*`, `.env_docker*`, configuración privada de agentes, datos y entornos/cachés. Si se conservan ejemplos, usar excepciones deliberadas. Nunca corregirlo borrando secretos en una capa posterior: quedarían en capas anteriores.
- Verificación: en un contexto desechable con archivos de entorno **ficticios**, construir/exportar imagen y comprobar ausencia tanto de nombres como del marcador sintético en todas las capas. No construir el árbol actual antes de corregir las exclusiones.

### D02 — P1: no existe una puerta de CI previa al despliegue

- Evidencia: solo hay workflows de deploy y keepalive. `deploy-to-render.yml:3-12` ejecuta sobre push a `main` o dispatch; no instala dependencias, ejecuta pytest, valida workflows, construye Docker ni compila el editor.
- `Dockerfile` no ejecuta Node. `scripts/build-editor.mjs:3-5` genera `app/static/js/editor-rich.js` desde `frontend/editor/index.js`, pero no se comprueba su correspondencia. Un cambio de fuentes sin regenerar el bundle puede desplegar JavaScript antiguo. No se ha comprobado que el bundle actual esté desfasado.
- Propuesta: workflow sin secretos para PR y main; lint de workflows/shell, tests aislados, build de frontend con `npm ci`, validación del artefacto y build Docker limpio. Hacer que el deploy dependa de esos resultados y de un commit identificado.
- Reproducibilidad: dependencias Python directas con `==` es positivo, pero no bloquea todas las transitivas ni sus hashes. El tag de Python tampoco fija el digest de la imagen. Añadir resolución reproducible, actualización controlada y escaneo de dependencias, sin tratar cada build como una resolución nueva.

### D03 — P1: éxito del POST no equivale a deploy live

- Evidencia: `deploy-to-render.yml:101-118` solo hace POST, imprime respuesta y falla si HTTP >=400. No valida ID/status, espera la finalización, verifica SHA ni consulta el servicio público. Incluso una respuesta 3xx inesperada no provoca fallo explícito.
- El POST omite `commitId`: la API documenta que toma el último commit de la rama conectada [R3], no necesariamente `${{ github.sha }}` del workflow. `checkout` no hace que Render use ese checkout.
- `render.yaml:7` declara `autoDeploy: true`; existe además el disparador API. Si ambos están activos en el servicio real, habrá carreras/despliegues redundantes y un autodeploy podría arrancar antes de terminar los PUT de entorno. El estado real del servicio manual no se verificó.
- No hay `concurrency`, restricciones explícitas del dispatch a main, entorno protegido ni timeout del job. Los PUT individuales no son una transacción y pueden dejar configuración parcialmente actualizada si uno falla; los opcionales omitidos conservan valores antiguos.
- Propuesta: elegir **un único dueño del despliegue**. Para conservar Actions: desactivar autodeploy tras autorización, exigir main/CI verde, serializar despliegues sin cancelar una sincronización ya iniciada, fijar `commitId`, aceptar solo respuestas previstas, registrar únicamente ID/SHA/status y esperar resultado terminal con deadline. Fallar en `build_failed`, `update_failed`, `pre_deploy_failed`, `canceled`, timeout o SHA distinto. `deactivated` no acredita que esa versión esté sirviendo.
- Añadir smoke público de HTTP + cuerpo esperado y estrategia de rollback compatible con esquema. No reintentar POST indiscriminadamente: una respuesta perdida puede haber creado ya el deploy. PUT idempotentes pueden llevar reintentos acotados, backoff y respeto de `Retry-After`.

### D04 — P1: script manual tiene un contrato API incorrecto y falsos éxitos

- Evidencia: `scripts/deploy_render.sh:21-29` envía `{"clearCache": false}`. La API vigente acepta los strings `clear` / `do_not_clear` [R3]; el workflow principal sí usa el segundo correctamente.
- `curl -s` sin `--fail`/validación HTTP puede devolver JSON de un 400/401, `jq` procesarlo correctamente y terminar anunciando «Deploy requested». No hay límites de conexión/total ni seguimiento.
- Propuesta: reutilizar un solo cliente probado para workflow/script, validar esquema y estados, sanear respuesta y poner deadlines. Probarlo contra un servidor HTTP local simulado, nunca contra Render durante estos tests.

### D05 — P1: se fuerza OAuth exclusivo pero sus credenciales se consideran opcionales

- Evidencia: workflow `:78-80` fuerza auth externo/GitHub, pero `:93-94` omite credenciales vacías; validación `:24` no las incluye. `render.yaml:43-50` refleja ese modo. La documentación las llama opcionales.
- Impacto: un servicio nuevo/mal configurado puede desplegar sin vía de login funcional. Si antes existían credenciales, quitarlas de GitHub no las elimina de Render. `INIT_ADMIN_EMAIL` es relevante para el bootstrap privilegiado; la contraseña inicial no es necesaria en modo OAuth exclusivo y conviene no mantenerla sin motivo.
- Propuesta: validar configuración por modo antes de cualquier PUT; fallo cerrado si no hay proveedor utilizable. Definir qué claves se administran, cómo se eliminan y cómo se rota sin configuración parcial. No mostrar sus valores.
- Prueba: credenciales OAuth sintéticas presentes/ausentes; la configuración incompleta debe fallar antes del deploy. El GET local de login debe ofrecer el proveedor esperado; el redirect debe usar callback HTTPS correcto, sin efectuar consentimiento ni autenticar.

### D06 — P1: healthchecks incompletos y arranque acoplado a dependencias externas

- Evidencia: `app/main.py:92-115` hace creación de tablas, migraciones, admin y sync antes de `yield`. Fallos de DB anteriores al bloque de bootstrap impiden completar startup. El sync de contenido sí captura excepciones y permite arrancar sin haber sincronizado.
- `/healthz` (`:145-147`) es una respuesta constante: útil para liveness, pero no detecta DB caída después del arranque ni catálogo incompleto. `render.yaml` solo declara ese path; para un servicio manual no está demostrado que el Dashboard tenga el mismo healthcheck.
- `/healthz/db` (`:150-157`) hace `select 1`, pero devuelve `str(exc)[:200]` públicamente en error. Puede revelar hosts, usuarios, fragmentos SQL o datos de conexión; truncar no es sanear. No comprueba esquema ni disponibilidad de contenido.
- `app/database.py:25-29` no fija `pool_pre_ping`, timeout de conexión/consulta ni límites propios del pool PostgreSQL. El comprobador diagnóstico sí usa pre-ping/timeout: que ese script funcione no valida la política del runtime.
- Propuesta: mantener liveness barato; readiness DB acotada con respuesta genérica y señal de versión/esquema/bootstrap separada. No convertir una caída de Supabase en un bucle de reinicios. Añadir presupuesto de startup y recuperación controlada de conexiones. Aislar migración de catálogo remoto y diseñar reintentos/estado degradado.
- Docker/Compose no definen `HEALTHCHECK`; `depends_on` de GitLab no espera su salud (puede compensarlo el bootstrap, pero requiere prueba). Añadir comprobación local explícita sin confundirla con la que usa Render. El CMD Docker debería usar `exec uvicorn ...` para propagación fiable de señales; el script Compose ya usa `exec` pero fija puerto 8000.

### D07 — P1: conexión Supabase y migraciones requieren pruebas PostgreSQL reales, locales

- Las guías favorecen transaction pooler 6543, mientras el engine no desactiva prepared statements de psycopg. Supabase documenta que transaction mode no los soporta [S3]. Puede pasar un `select 1` y fallar bajo reutilización/repetición; no se reprodujo contra producción.
- Para este backend persistente, evaluar **session pooler IPv4 :5432** con pool pequeño. Si se mantiene transaction mode, configurar explícitamente psycopg (`prepare_threshold=None`) y probarlo con su pooler. No cambiar ciegamente puerto/host: copiar el endpoint correcto del diálogo Connect. El host directo Free es IPv6; eso no demuestra por sí solo la conectividad efectiva de este Render.
- Exigir SSL, como mínimo `sslmode=require`; preferir `verify-full` con CA correctamente configurada. Los ejemplos principales de la guía y Blueprint no lo exigen. No se inspeccionó el DSN real y no se afirma que la conexión desplegada vaya sin TLS.
- `runtime_migrations.py:9-40` inspecciona columnas y después hace ALTER: dos arranques concurrentes pueden observar la misma ausencia y competir. `create_all` no sustituye una historia versionada de migraciones. Bootstrap también puede actualizar/promover al admin en cada reinicio.
- Propuesta: migraciones versionadas, coordinación/lock y estrategia expand-contract, rol runtime de privilegio mínimo separado del rol de migración. En Render Free no asumir disponibilidad de shell, one-off jobs o fases propias de planes de pago [R1]. La herramienta de migración debe tener una ejecución explícita autorizada; no usar PR CI contra Supabase.

### D08 — P1/P0 condicionado: credenciales, logs y exposición de datos

1. `docs/deploy-render-supabase.md:79-105` incluye ejemplos con una contraseña y referencia de proyecto de aspecto concreto, no solo placeholders. No se reproducen aquí ni se intentó validarlos. El propietario debe determinar si fueron reales; **si lo fueron, rotar primero** y revisar exposición/historial mediante procedimiento autorizado. Borrar el texto no revoca una credencial.
2. `scripts/check_deploy.py:73-79,114,197,215-217` muestra prefijos/sufijos y errores crudos: un recorte de 24 caracteres de un DSN con usuario corto puede incluir parte de la contraseña. No confiar en truncado ni en el masking automático de Actions para variantes URL-encoded.
3. Workflow `:115` y script manual imprimen el cuerpo completo de la respuesta Render. No se ha demostrado que ese endpoint devuelva secretos, pero debe registrarse una lista permitida de campos, no cualquier cuerpo de error. Es positivo que los PUT actuales descarten su respuesta y no usen `set -x`.
4. El arranque y rutas pueden emitir excepciones completas; `books.py:985,1033` registra fragmentos de respuestas de terceros. Uvicorn lleva access log por defecto: un callback OAuth puede acabar con `code`/`state` en la query del log. Proponer redacción de query sensible y pruebas con marcadores sintéticos; conservar diagnóstico estructurado sin tokens, cookies, DSN o contenido personal.
5. El esquema crea `service_token` en DB (`runtime_migrations.py:23-24`). No se encontró aquí provisión de RLS/grants para Data API. Eso **no demuestra** que las tablas remotas sean públicas: verificar por el propietario exposición de esquemas, privilegios anon/authenticated y políticas. Si solo se usa SQLAlchemy, valorar desactivar Data API para esas tablas. La autenticación GitHub de la app no aplica RLS de Supabase automáticamente [S2].
6. `docker-compose.yml` contiene credenciales de desarrollo públicas, expone puertos sin bind a loopback y monta el socket Docker en bootstrap. No usarlo como receta de producción ni arrancarlo en un host compartido/red abierta. Bind `127.0.0.1`, perfil debug explícito y aislamiento del bootstrap; el socket implica privilegios sobre el host.
7. Endurecer workflow: `permissions: contents: read` (keepalive puede usar `{}`), checkout sin persistir credenciales y acciones fijadas a SHA revisado. El runtime Docker no define `USER`; ejecutar como usuario no root con directorios de trabajo limitados.

### D09 — P2: el diagnóstico no es una prueba end-to-end fiable ni aislada

`check_deploy.py` carga `.env` automáticamente y, según el entorno, accede a DB, `gh secret list` y API Render que devuelve variables completas aunque solo se impriman nombres. No se ejecutó en esta auditoría.

Falsos positivos concretos:

- `:172-178` llama «publishable key accepted» a respuestas 401/403/404, que no demuestran aceptación de la clave.
- `:102` trata la clave de sesión ausente como opcional, pese a ser crítica en producción.
- `:280` acepta `deactivated`; no compara SHA esperado ni identifica necesariamente el deploy live.
- Una lista vacía de deploys no agrega fallo (`:277`); errores de ese check son opcionales (`:283`).

Separar validación offline, checks públicos y diagnóstico autenticado opt-in. La ejecución normal de CI debe carecer de credenciales/red remota; mostrar `present/missing` en vez de prefijos. Las pruebas simuladas deben exigir non-zero en credencial inválida, deploy vacío/inactivo, SHA distinto y error obligatorio.

## Keepalive: limitaciones y corrección de expectativas

- `keepalive.yml:21-23` programa minutos 3, 17, 31, 45 y 58: intervalos **14, 14, 14, 13 y 5 minutos**. Las ventanas de 14 dejan solo un minuto de margen ante el umbral de 15 de Render. Perder uno de esos disparos abre huecos de 27/28 minutos; los tres schedules no proporcionan redundancia antes de cada umbral.
- GitHub documenta retrasos y posible descarte con carga, ejecución en la rama por defecto y desactivación de schedules en repos públicos tras 60 días sin actividad [G1]. Evitar el inicio de hora puede ayudar, pero «offsets primos» no es una garantía contractual ni prueba de causalidad del incidente histórico. La cifra de dos runs en 24 h consta en la bitácora; no se revalidó contra GitHub.
- El job tiene 5 minutos, pero 3 × 90 s + 3 × 15 s = **315 s**, sin contar overhead. Puede morir antes del mensaje final; incluso quitando el último sleep serían 300 s sin margen.
- `curl -f` considera exitosos otros estados además del 200 y no verifica JSON. Validar HTTP 200 y cuerpo esperado evita marcar como sana una respuesta intermedia/HTML.
- `/healthz` no consulta Supabase: mantener Render despierto **no demuestra** actividad de DB suficiente para evitar su pausa. Tampoco conviene usar un probe público frecuente como truco para garantizar que no pause; el criterio de baja actividad y otras restricciones siguen siendo del proveedor.
- Retirar la promesa «fiabilidad real >99 %» de comentarios y docs: no se ha medido ni está respaldada por SLA. Un monitor externo puede mejorar detección y reducir cold starts, pero no arregla suspensiones, cuotas, DB, errores de código o red. No se validaron aquí las cuotas actuales de UptimeRobot/cron-job.org: no repetir como vigentes «50 monitores» sin consultar sus condiciones.
- Recomendación gratis: monitorización opcional con alertas, timeouts compatibles con cold start y mantenimiento explícito; medir por separado disponibilidad HTTP, funcionalidad, latencia caliente y arranque frío. No montar múltiples cron redundantes ni generar actividad ficticia para prometer continuidad.

## Disponibilidad gratuita realista, a fecha de consulta

### Render Free [R1]

- Duerme tras 15 minutos sin tráfico entrante; el despertar tarda aproximadamente un minuto según documentación, **no un máximo garantizado**. Puede reiniciarse en cualquier momento.
- 750 horas de instancia gratis por workspace/mes, compartidas entre servicios. Un único servicio continuamente activo en un mes de 31 días consume 744 h: apenas 6 h de margen compartido, sin asegurar continuidad ni cubrir otro servicio activo. Al agotarse se suspenden los servicios Free hasta el mes siguiente.
- Filesystem efímero: se pierden cambios al redeploy, restart o spin-down; Free no admite disco persistente. SQLite es solo demo descartable. Usuarios/revisiones/comentarios deben persistir externamente y todo contenido prometido como guardado debe llegar a su fuente duradera, no solo a un clon local.
- Banda saliente y minutos de pipeline cuentan contra cuotas del workspace. Al agotarse puede haber cargos si hay método de pago o suspensión/deshabilitación de builds según cuota y límite de gasto. Verificar el plan real; no asumir que cualquier tráfico/build sigue siendo gratis.
- Render puede suspender tráfico saliente inusualmente alto, incluido DB externa y APIs. La documentación actual indica Free con 0,1 CPU/512 MB: PDF, Git y compilaciones necesitan presupuestos y carga local representativa, no multiplicar workers sin medir.
- Render Postgres Free expira a los 30 días, con posterior ventana de 14 días antes de borrado si no se mejora el plan; **no es sustituto duradero gratuito** de Supabase.

### Supabase Free [S1, S2, S3]

- 2 proyectos activos; DB 500 MB por proyecto; almacenamiento de archivos 1 GB; 5 GB egress y 5 GB cached egress; recursos compartidos. «API requests unlimited» no significa CPU, conexiones, tamaño o transferencia ilimitados.
- Posible pausa por baja actividad en una ventana de 7 días; restauración desde Dashboard. Un GET a Render no reanuda de forma garantizada un proyecto Supabase pausado.
- Sin SLA de uptime ni backups automáticos incluidos en Free; retención API/DB de logs de 1 día según pricing. Planificar exportaciones cifradas fuera de Render y prueba periódica de restauración. No incluir dumps/tokens en artifacts públicos de Actions. Ningún backup se realizó en esta auditoría.
- Las cuotas de Supabase Auth (p. ej. MAU) no describen automáticamente la capacidad del login de esta app: su OAuth GitHub y sesiones son propios. Las conexiones SQL/pooler son un presupuesto distinto de Realtime.

### Opciones sin coste, sin prometer uptime

1. **Conservar Render + Supabase** para piloto pequeño: aceptar cold starts/pausas, aviso visible al usuario, comprobación previa a sesiones de clase, contactos y procedimientos de recuperación, exportación verificada de datos. Es la menor migración, no una solución de alta disponibilidad.
2. **Añadir una edición estática de lectura** de los libros en hosting estático gratuito (Render Static Sites documentado en [R1]). Puede seguir ofreciendo material mientras el backend no esté disponible; cuotas de transferencia/build siguen aplicando. Requiere pipeline de publicación separado; no preserva edición, comentarios ni OAuth dinámico y no se ha implementado aquí.
3. Si el requisito es edición persistente siempre disponible o arranque con latencia acotada, declarar **incompatible con una garantía gratis en este stack**. Cambiar a otra oferta gratuita sin estudiar pausas, cuotas, backups y compatibilidad solo traslada riesgos. No se certifican las alternativas Neon/Koyeb citadas en docs sin auditoría actual de esas ofertas.

## Propuesta de pipeline local/CI — no ejecutar despliegues todavía

Orden recomendado para una futura PR:

1. **Contención**: Docker allowlist/exclusiones, ejemplos exclusivamente ficticios, sanitización de diagnósticos. El propietario decide si procede rotación por D08; no imprimir ni validar credenciales sospechosas.
2. **CI aislada**: copia/checkout limpio sin `.env`, DB temporal SQLite y PostgreSQL local desechable, repositorio de contenido fixture y HTTP de proveedores simulado. Deshabilitar explícitamente dotenv; no confiar solo en sobreescribir el DSN mientras quedan tokens reales en el entorno.
3. **Gates**: actionlint, shellcheck, pytest sin caché externa al sandbox, `npm ci` + build de editor, comprobación del bundle o generación multistage, build Docker limpio, escaneo de imagen/dependencias y smoke local de arranque/shutdown.
4. **Contrato de despliegue**: tests con API Render falsa, validación por modo, política de borrado de opcionales, SHA fijo, serialización, deadline y salida saneada. Probar el contrato sin credenciales ni red a Render.
5. **Pruebas de recuperación**: migraciones secuenciales/concurrentes sobre PostgreSQL local, DB desconectada después de startup, reinicio con caché vacía, bootstrap externo no disponible. Restaurar un backup ficticio y probar compatibilidad del rollback con esquema.
6. **Aprobación separada posterior** para cambiar ajustes remotos/autodeploy, secrets, migraciones o deploy. Hasta entonces, no push a main, pues el workflow actual despliega automáticamente incluso cambios solo de documentación.

### Criterios de aceptación verificables

| Test | Resultado exigido | Ejecutado aquí |
|---|---|---|
| Dos GET públicos `/healthz` | Registrar código, duración y límite sin atribuir causa | Sí: ambos timeout, sin HTTP |
| Docker con canarios `.env` ficticios | Ningún archivo/marcador privado en ninguna capa | No |
| CI sobre PR sin secretos | Tests/build pasan sin `.env`, tokens ni contacto a producción | No |
| Fuente editor modificada | CI detecta bundle viejo o lo regenera determinísticamente | No |
| Mock Render HTTP 400/401/429/500, 3xx, JSON inválido | Fallo controlado; nunca «deploy OK»; sin volcado de cuerpos | No |
| Mock deploy queued → live / failed / timeout | Solo live con SHA esperado es éxito; deadline respetado | No |
| Dos deploys simultáneos | No intercalan sincronización de entorno; un dueño de autodeploy | No |
| Modo external-only sin OAuth | Falla validación antes de PUT/POST; mensaje sin secretos | No |
| DB local caída/colgada | Liveness conserva semántica; readiness falla acotada y genérica | No |
| Excepción/DSN/query OAuth con canarios | No aparecen en HTTP, logs ni artifacts | No |
| Migraciones repetidas y concurrentes locales | Sin pérdida de datos, duplicados ni carreras DDL | No |
| PostgreSQL/pooler y consultas repetidas | Sin errores de prepared statements; pool/timeout documentados | No |
| Reinicio/sleep simulado con disco vacío | Usuarios y contenido guardado recuperables de almacenamiento duradero | No |
| Presupuesto keepalive | Peor caso completo inferior al timeout con margen; HTTP/JSON validados | Solo cálculo estático: falla margen actual |

No se declaran tests aprobados ni causa raíz de la indisponibilidad pública. Los cambios concurrentes de otras sesiones pueden resolver parte del código; requieren volver a ejecutar estos criterios sobre una revisión estable.

## Fuentes oficiales consultadas

Consultadas el 2026-09-16; límites y contratos pueden cambiar. El estado real del workspace/proyecto no se consultó con autenticación.

- **[R1] Render — Deploy for Free:** https://render.com/docs/free
- **[R3] Render API — Trigger deploy (contrato `clearCache`, `commitId`, estados):** https://api-docs.render.com/reference/create-deploy
- **[G1] GitHub Actions — schedule:** https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- **[S1] Supabase — Pricing / Free / límites y backups:** https://supabase.com/pricing
- **[S2] Supabase — Production Checklist / disponibilidad y RLS:** https://supabase.com/docs/guides/platform/going-into-prod
- **[S3] Supabase — Conexiones, poolers, IPv4/IPv6 y TLS:** https://supabase.com/docs/guides/database/connecting-to-postgres
