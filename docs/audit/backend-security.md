# Auditoría backend y seguridad — piloto Primaria

Fecha: 2026-09-16. Alcance: `libre_libros_app/app`, inspección de los tests existentes y muestreo de `../libre_libros_content/books`. Referencias relativas a `libre_libros_app`, salvo indicación contraria.

## Método y conclusión

Auditoría **estática y de solo lectura**, excepto la creación de este informe. No se han ejecutado tests, importado la aplicación, arrancado servicios, llamado a proveedores, probado payloads ni modificado producción. No se han leído `.env`, `.env_docker`, `settings.local.json`, bases de datos, configuración Git ni credenciales. Las reproducciones siguientes son **procedimientos propuestos**, no resultados observados. Deben realizarse posteriormente en un repositorio desechable y una BD aislada, sin red ni secretos reales.

**No abrir todavía el piloto a Internet.** Los 10–20 docentes invitados y la ausencia de datos de alumnos reducen el alcance de una filtración, pero no corrigen lectura arbitraria local, XSS de mismo origen, corrupción de libros o autorización por nombres. La arquitectura FastAPI + SQLAlchemy + Git permite solucionar estos problemas sin exigir GitHub a los docentes ni reemplazar toda la aplicación.

Prioridades:

- **P0:** no se declara un incidente P0 ni exposición efectiva de producción: no se ha inspeccionado ni probado el despliegue. Si se confirma que un repositorio local es accesible públicamente, B01 requiere contención inmediata; si se usa la clave por defecto, también B09.
- **P1:** B01–B10. Bloqueantes para un piloto multiusuario expuesto.
- **P2:** B11–B18. Integridad, aislamiento adicional y robustez; resolver los aplicables al piloto antes de ampliar uso.

## Hallazgos P1

### B01 — Lectura fuera de `assets` y del repositorio mediante fallback local

**Evidencia:** `app/routers/books.py:1163-1183` concatena `asset_path:path` sin validación. `app/services/repository/local_git.py:109-125` intenta `git show` y, si falla, lee `self.repo_path / rel_path` directamente; no resuelve ni comprueba el confinamiento. El equivalente textual está en `local_git.py:100-107`. El cargador PDF tampoco rechaza `assets/../...` (`app/routers/books.py:267-272`).

**Impacto:** un lector de un libro público, incluso anónimo, puede alcanzar archivos legibles por el proceso fuera del directorio de assets y potencialmente fuera del repositorio. El límite es el permiso del sistema operativo, no la visibilidad del libro. La ruta local del repositorio puede ser un directorio suministrado por configuración (`app/services/repository/factory.py:12-14`).

**Reproducción propuesta:** en un fixture local, colocar un archivo señuelo `audit-canary.txt` en el padre del repositorio, no un secreto. Pedir `/books/<public_id>/assets/<suficientes segmentos ../>/audit-canary.txt?branch=missing-audit-branch`, conservando la ruta cruda o usando segmentos codificados para que el cliente no la normalice. Ajustar la profundidad al `assets_path` del fixture. Comprobar también `../book.md`, ramas inexistentes y symlinks. El fallo de `git show` conduce al fallback de lectura del señuelo.

**Fix:** validar componentes POSIX en una única frontera de repositorio y en la ruta HTTP; rechazar rutas absolutas, `..`, caracteres nulos y escape mediante symlink. Exigir confinamiento **dentro de los assets del libro**, no solo dentro del repo. Eliminar los fallbacks al working tree en lectura HTTP: archivo ausente en la revisión solicitada debe ser 404. Si hace falta importar un árbol aún no versionado, hacerlo en un servicio separado y restringido.

**Tests:** traversal codificado/crudo, symlink externo, lectura cruzada entre dos libros, branch inexistente y PDF con `assets/../../...`; siempre rechazo sin devolver el señuelo. No probar con archivos del sistema ni secretos.

### B02 — XSS al interpolar la rama después de sanitizar HTML

**Evidencia:** `app/services/markdown_utils.py:24-26` limpia con Bleach, pero `:45-46` y `:116-123` insertan después `branch_name` sin escape en `src`/`href`. `app/templates/books/_document.html:57-59` imprime ese resultado como `safe`. `/books/preview` acepta `branch_name`, `book_id` y contenido sin autenticación (`app/routers/books.py:1152-1160`). Las páginas de libro aceptan rama arbitraria (`:352-364`, `:591-594`).

**Reproducción propuesta:** POST de formulario a `/books/preview` con `content=![x](assets/missing.png)`, `book_id=1`, `branch_name=main\" onerror=\"alert(1)`. Inspeccionar el HTML devuelto y abrirlo únicamente en navegador de prueba: se añade un atributo después de Bleach. Esta ruta no requiere que la rama sea válida en Git. Para la página del libro, evaluar por separado un nombre permitido por Git que cierre el atributo e introduzca markup, por ejemplo `main\"><svg/onload=alert(1)>`; la creación de ramas y el proveedor condicionan ese segundo recorrido.

**Impacto:** ejecución bajo el origen de la aplicación. HttpOnly no impide que un script ejecute acciones autenticadas con `fetch`; no necesita leer la cookie.

**Fix:** construir query strings con `urlencode`, escapar valores de atributos y no concatenar HTML después de la sanitización; preferiblemente reescribir URLs antes del saneamiento final con un parser HTML. Validar ramas en todos los endpoints. Añadir CSP como segunda barrera, no como sustituto.

**Tests:** comillas, `<`, `>`, `&`, nombres de rama con `/`, payload en preview, documento y enlaces a fichas. Comprobar DOM sin atributos/eventos inyectados y conservación de URLs válidas.

### B03 — Subida de HTML/SVG activo servido en el mismo origen

**Evidencia:** `app/routers/books.py:255-264` confía en `UploadFile.content_type`, acepta cualquier `image/*` y solo comprueba bytes. `:1130-1140` conserva la extensión tras sanitizar el nombre (`app/services/books.py:107-109`). `:1182-1183` decide el tipo de respuesta por extensión y devuelve contenido inline, sin sandbox ni separación de origen.

**Reproducción propuesta:** como editor de un libro público, subir `audit.html` con MIME declarado `image/png` y bytes HTML de demostración `<script>alert(1)</script>` a su rama. Abrir `/books/<id>/assets/audit.html?branch=<rama>` desde una cuenta de prueba: se selecciona `text/html` por extensión. Alternativa: SVG con script, abierto como documento, no como `<img>`.

**Impacto:** XSS almacenado al visitar el asset; escalada a acciones del docente/admin que abra el enlace. La sanitización Markdown no actúa en este endpoint.

**Fix:** allowlist de formatos, detectar/decodear bytes y recodificar imágenes raster; extensión derivada del formato real. Para el piloto, no aceptar SVG nuevo sin una política específica de saneamiento/rasterización. Los SVG de portadas existentes pueden rasterizarse al importar. Servir recursos no confiables desde origen separado sin cookies o como descarga con sandbox y `nosniff`.

**Tests:** HTML declarado PNG, SVG activo, extensión contradictoria, imágenes inválidas, URLs de documento directo y recursos existentes válidos. `nosniff` solo no arregla una respuesta marcada explícitamente como HTML.

### B04 — Crear libros permite escribir en repositorios ajenos y sobrescribir libros base

**Evidencia:** `app/routers/books.py:521-534`: el control de membresía y correspondencia con el repositorio solo se ejecuta si se envía `organization_id`. No se autoriza siempre `repo_source`. `:549-560` persiste el libro y escribe en `book.base_branch` usando credenciales de servicio. `app/services/books.py:30-34` deriva la ruta solo de curso, materia y slug del título. `app/models.py:129-144` no tiene unicidad de repo/ruta.

**Reproducciones propuestas:**

1. Usuario A sin membresía en B envía `/books/new` con el `repository_source_id` de B y omite `organization_id`. Debe rechazarse; el código actual continúa hasta la escritura.
2. Editor crea en el mismo repo un libro con los mismos valores normalizados de título, curso y materia que uno existente. Obtiene otra fila que apunta al mismo `book.md`; el contenido inicial reemplaza el archivo base sin propuesta. También ocurre por colisiones de slug, no solo por igualdad literal.

**Impacto:** salto de aislamiento y del flujo de revisión; sobrescritura en la versión base con el token de la aplicación. No depende de tener permiso ordinario para editar `main`.

**Fix:** permiso explícito `can_create_book_in_repository`, independiente del formulario; organización derivada/comprobada en servidor. Política separada para repositorios compartidos. Restricción única `(repository_source_id, content_path)` y comprobación del archivo existente en Git. Crear en rama de trabajo y publicar solo mediante aprobación. No confirmar definitivamente en BD antes de completar Git (ver B14).

**Tests:** dos organizaciones, repositorio global, org omitida/falsificada, slug duplicado y dos creaciones simultáneas; ninguna escritura en repo/rama no autorizados ni pérdida del libro previo.

### B05 — Las ramas personales usan un nombre no único como identidad

**Evidencia:** `app/services/permissions.py:19-24`, `:39-41`, `:113-115`, `:160-166`: la identidad es `slugify(full_name)` y se autoriza todo ese prefijo. El nombre se elige libremente al registrar (`app/routers/auth.py:143-167`).

**Reproducción propuesta:** crear dos usuarios con emails distintos y `full_name="Ana Profe"` (o nombres que colisionen al normalizar). En un libro público, A guarda en `users/ana-profe/base/primaria`; B puede enviar `/books/<id>/edit` con esa misma rama. La rama legacy `users/ana-profe` también colisiona.

**Impacto:** edición/suplantación entre docentes, tanto accidental por homónimos como intencionada. El email único no protege las ramas.

**Fix:** usar ID inmutable de usuario/UUID como clave de workspace; nombre solo para mostrar. Migrar ramas legacy con un mapa explícito de propietario; no mantener una excepción de permisos basada únicamente en el nombre antiguo.

**Tests:** homónimos, tildes/puntuación, cambio de nombre, prefijos parecidos y ramas legacy ambiguas. Un usuario nunca escribe el workspace del otro.

### B06 — Aprobar no exige acceso al libro ni un destino aprobado válido

**Evidencia:** `app/routers/books.py:1067-1076` solo exige que exista el libro y que el usuario administre la organización extraída de `target_branch`. No llama `can_view_book`, no comprueba el repositorio y no exige `target_context.is_personal == False`. `app/services/permissions.py:59-65` extrae organización también de `users/<otro>/<org>/<curso>`. `:1077-1095` copia archivos y borra sobrantes.

**Reproducciones propuestas:**

- Un admin de organización A solicita aprobación para un libro **privado de B**, con `target_branch=orgs/a/primaria` y `source_branch=main`: se llega al repositorio de B sin permiso sobre ese libro.
- Para un libro visible, A envía como destino `users/otro-docente/a/primaria`: se acepta como organización administrable y puede sobrescribir la rama personal ajena.

Además, `can_edit_book_on_branch` (`permissions.py:167-169`) permite a un gestor de A editar una rama personal ajena que contenga el segmento A; se debe decidir y expresar ese permiso de forma independiente, no inferirlo del nombre de una rama.

**Fix:** autorización conjunta usuario/libro/repositorio/acción; destino exclusivamente aprobado y canónico, no personal. Origen existente y accesible; no crear silenciosamente el origen. Aprobar por ID de propuesta y commit revisado, no por dos strings libres.

**Tests:** libro privado ajeno, workspace ajeno como destino, org inexistente, rama arbitraria, origen inexistente, y aprobación legítima limitada a los archivos del libro.

### B07 — No existe perímetro de invitaciones

**Evidencia:** `app/routers/auth.py:139-171` crea cuenta local y sesión sin invitación ni verificación de correo. `:186-202` crea cualquier identidad OAuth válida que llegue a callback. `external_auth_only` solo deshabilita contraseña; no impone allowlist. `:129-151` incluso redirige registro a proveedor externo cuando hay uno configurado.

**Reproducción propuesta:** con auth local habilitada y sin proveedores, POST `/register` con email nuevo y contraseña: se crea editor sin token. Con OAuth configurado, simular callback de identidad nueva no invitada: `_upsert_oidc_user` la crea. No hace falta atacar al proveedor.

**Impacto:** incumple el requisito explícito del piloto. Un no invitado accede a edición personal de libros públicos, comentarios, issues y creación de libros; combinado con B03/B04 eleva mucho el riesgo.

**Fix:** cerrar alta pública en servidor y añadir el flujo mínimo descrito al final. No basta ocultar el enlace. Aplicar la política también a OAuth si se conserva habilitado.

**Tests:** registro directo sin invitación, OAuth no invitado, expiración/revocación/reutilización, cuenta previamente invitada y errores indistinguibles donde proceda.

### B08 — OAuth enlaza por email sin identidad estable ni verificación explícita

**Evidencia:** `app/routers/auth.py:186-202` busca únicamente email y devuelve cuentas existentes, incluidas administradoras, sin comparar issuer/sub ni proveedor. Google/OIDC pasan `userinfo["email"]` sin comprobar `email_verified` (`:252-274`). `_github_email` acepta primero `user_info.email` sin contrastarlo con emails verificados (`:205-218`); GitLab tiene fallback a `public_email` (`:286-295`). El modelo solo tiene un string `auth_provider` (`app/models.py:54-66`).

**Reproducción propuesta:** test de callback con proveedor OIDC simulado que devuelve un email de cuenta existente, `email_verified=False` y un `sub` distinto. Comprobar que hoy se selecciona esa cuenta. Test de `_github_email` con email público que no aparece como verificado en la lista. No se afirma que todos los proveedores reales permitan elegir libremente el email ni que se haya eludido OAuth state/nonce.

**Impacto:** toma de cuenta si el proveedor configurado emite emails no verificados/controlables; enlace implícito entre proveedores. Además, una cuenta local precreada con email de otra persona conserva su contraseña cuando esa persona entra por OAuth.

**Fix:** identidad externa única `(issuer, subject)` y política de verificación documentada por proveedor. Nunca enlazar a una cuenta existente solo por email sin prueba segura/reautenticación. GitHub: seleccionar únicamente emails confirmados en `/user/emails`; OIDC: exigir claim verificado según contrato del proveedor. Evitar promoción automática a admin únicamente por email (`:194`, `:199-201`). Para este piloto puede deshabilitarse OAuth hasta completar esa política.

**Tests:** email sin verificar, email cambiado, issuer distinto, sub distinto, cuentas locales preexistentes y enlace explícito legítimo. Mantener tests de state/nonce y rechazo de callback inválido usando Authlib.

### B09 — Sesiones con clave por defecto aceptada y usuarios desactivados aún válidos

**Evidencia:** `app/config.py:16` define clave de firma conocida por defecto; `app/main.py:118-119` la usa sin validación y sin `https_only=True`. `app/dependencies.py:14-23` acepta el `user_id` de sesión sin comprobar `is_active`. Login local (`app/routers/auth.py:105-125`) y callbacks tampoco verifican ese campo, aunque existe (`app/models.py:66`).

**Impacto:** si se despliega sin sobreescribir la clave, una cookie firmada con el formato de SessionMiddleware puede suplantar IDs, incluido admin. **No se ha comprobado la clave efectiva.** Desactivar una cuenta no corta sus accesos ni impide nuevo login. Las sesiones firmadas no tienen revocación central/versionado.

**Reproducciones propuestas:** arrancar solo fixture con clave por defecto y verificar que el arranque debería fallar; en un test separado autenticar un usuario, marcarlo inactivo y reutilizar sesión/contraseña. Debe denegarse. Inspeccionar Set-Cookie en configuración HTTPS de prueba para Secure.

**Fix:** clave aleatoria obligatoria fuera de desarrollo, fallo cerrado ante default, cookie Secure/HttpOnly/SameSite explícitos, HTTPS. Rechazar inactivos en dependencia común y al iniciar sesión. Añadir `session_version` o sesiones opacas revocables, limpiar/renovar sesión al autenticar y al cambiar privilegios. Rotación de clave y revocación deben planificarse, no ejecutarse como parte de esta auditoría.

**Tests:** clave ausente/default, usuario borrado/inactivo, sesión antigua tras revocación, logout, duración y flags de cookie.

### B10 — CSRF sin defensa explícita y GET que modifica repositorios

**Evidencia:** solo SessionMiddleware en `app/main.py:118-119`; formularios de login/admin/libros no verifican token CSRF ni Origin. `app/routers/auth.py:180-183` hace logout por GET. `app/routers/books.py:591-594` y `:793-796` crean ramas durante lecturas públicas. `/pull-requests` también crea el destino enviado libremente (`:1020-1031`).

**Reproducciones propuestas:**

- Sin autenticar, visitar `/books/<public_id>?branch=audit-unrequested-branch`; comprobar que aparece una rama sin una operación de edición autorizada. Repetir con nombres diferentes permite proliferación de ramas y llamadas de API.
- Un formulario de sitio de pruebas hace POST `/login` con una cuenta controlada de fixture: login CSRF, sin sesión previa necesaria.
- Formularios autenticados sin token se aceptan. Para explotación desde otro origen debe verificarse el navegador y SameSite: el valor Lax predeterminado mitiga POST entre sitios diferentes, **no** constituye una defensa CSRF completa ni cubre orígenes distintos dentro del mismo site. No se afirma que todo POST cross-site enviará la cookie.

**Fix:** GET estrictamente de lectura; crear ramas solo en POST autorizado. Token CSRF vinculado a sesión para todos los formularios mutadores, incluidos login/invitación/logout; verificar Origin/Referer con política cerrada cuando corresponda. Restringir destinos de propuestas. Mantener state/nonce OAuth como mecanismo propio de ese flujo.

**Tests:** GET no cambia refs, formulario sin token/token ajeno/origen ajeno rechazados, mismo origen válido aceptado y límites a creación de ramas.

## Hallazgos P2

### B11 — Fugas de actividad entre usuarios y visibilidad de borradores

**Evidencia:** `app/routers/dashboard.py:43-49` selecciona las últimas 10 revisiones globales sin `can_view_book`, aunque los libros sí se filtran (`:32`). `app/routers/admin.py:176-200` entrega todos los usuarios al gestor de una organización. `app/routers/books.py:587-594`, `:619-633`, `:1171-1178` solo comprueban la visibilidad del libro, no la de la rama/comentario: cualquier lector del libro público puede solicitar workspaces personales y ver comentarios de todas las ramas.

**Reproducción propuesta:** crear revisión en libro privado B y abrir home como A; verificar metadatos mostrados. Como anónimo, acceder al libro público con la rama de otro profesor y revisar comentarios. Inspeccionar panel de A con usuarios solo de B.

**Impacto:** exposición de actividad privada y confusión entre “personal/no revisado” y “publicado”. En el piloto sin datos de alumnos puede ser una política aceptable que todas las ramas sean públicas, pero debe ser explícita: actualmente no hay privacidad por rama. Tampoco un repo Git público ofrece privacidad de borradores aunque se cierre el endpoint.

**Fix/tests:** filtrar revisiones por acceso antes de paginar/contar; limitar directorio de usuarios al ámbito necesario. Definir `can_read_branch` y separar catálogo publicado/borradores si se desea privacidad. Tests de dos orgs, autor, revisor y anónimo. No afirmar que “personal” equivale a privado mientras Git lo publique.

### B12 — Pérdida de cambios por edición obsoleta; lecturas locales no son snapshots

**Evidencia:** guardar acepta contenido pero ningún SHA/versión esperada (`app/routers/books.py:685-729`, `:873-906`). El lock local protege escrituras (`local_git.py:148-177`), no el ciclo lectura-edición-guardado; fallbacks de lectura/listado consultan el checkout mutable sin lock (`:100-138`). GitHub usa `force=False` (`github_api.py:173-176`), buena defensa frente a dos commits simultáneos, pero parte del HEAD actual al guardar (`:143`), no del documento que vio el editor. GitLab no envía `last_commit_id` (`gitlab_api.py:93-114`).

**Reproducción propuesta:** dos pestañas abren versión V; primera guarda A, segunda guarda B elaborado desde V: se acepta B y se pierde A. En local, pedir un archivo ausente de la rama solicitada pero presente en el working tree actual: aparece contenido de otra rama. Un `git show` exitoso sí lee su revisión; el riesgo de mezcla corresponde al fallback y a múltiples lecturas sin SHA fijo.

**Fix/tests:** enviar `expected_sha`, comparar y actualizar atómicamente; devolver 409 con resolución de conflicto y conservar borrador. Leer documento/recursos desde SHA fijado. Eliminar fallback. Tests de dos pestañas sobre mismo archivo, ramas diferentes, lectura simultánea y proveedor rechazando actualización no fast-forward. El lock existente es útil y no debe retirarse.

### B13 — Aprobar no es atómico ni aprueba el commit revisado; estado remoto divergente

**Evidencia:** `app/routers/books.py:1075-1095` realiza borrado y escritura en operaciones/commits separados y lee el origen vivo varias veces. `:1097-1110` marca `merged` sin exigir una propuesta ni ejecutar merge/cierre remoto. `app/models.py:173-189` no registra autor, aprobador ni SHA revisado. `app/services/review_sync.py:83-88` solo refresca abiertas/draft.

**Reproducciones propuestas:** cambiar la rama origen después de revisarla pero antes de aprobar: se publica el contenido nuevo no revisado. Inyectar fallo de `write_files` tras `delete_files`: quedan recursos borrados parcialmente. Aprobar propuesta GitHub: la BD se marca merged, pero no hay llamada de merge y esa fila deja de refrescarse. Crear dos propuestas iguales: solo se marca la más reciente; las demás quedan abiertas.

**Fix/tests:** propuesta con `head_sha`, `base_sha`, creador, revisor y timestamps; aprobación compare-and-swap sobre esos SHAs. Commit único con escrituras y borrados. Separar estado “aplicada por copia” de merge real o implementar/reconciliar explícitamente el remoto. Doble aprobación idempotente. Probar fallo a mitad, cambio concurrente, duplicado y PR que afecta a varios libros: una PR Git compara **toda la rama**, no solo el `book_id` asociado.

### B14 — BD/Git y bootstrap pueden dejar registros huérfanos o borrar/publicar catálogo

**Evidencia:** creación confirma BD antes de escribir Git (`app/routers/books.py:549-560`); issues/PRs hacen remoto antes de commit BD (`:983-1003`, `:1031-1051`). Bootstrap se ejecuta al arrancar (`app/main.py:95-112`). `app/services/bootstrap.py:92-103` convierte cualquier libro existente de la fuente a público y elimina propietario/org; `:122-125` borra libros no descubiertos; `app/models.py:149-155` propaga borrado a comentarios y revisiones.

**Reproducciones propuestas:** mock de fallo Git al crear: queda fila sin contenido. Mock de fallo BD tras crear PR: queda PR externa sin seguimiento; reintento puede duplicar. En fixture de bootstrap, marcar privado un libro existente y resincronizar: vuelve a público. Devolver un listado vacío/incompleto pero exitoso: desaparecen registros y sus comentarios/revisiones.

**Fix/tests:** estado de creación pendiente, idempotencia y reconciliación/outbox para efectos externos. Bootstrap solo debería importar fuentes explícitamente dedicadas y no sobreescribir ownership/visibilidad existentes sin decisión; no borrar automáticamente ante inventario incompleto. Tombstones y confirmación de catálogo completo. Tests de fallo en cada frontera, recuperación y preservación de comentarios.

### B15 — Adaptador GitLab no normaliza revisiones y faltan páginas de API

**Evidencia:** `app/services/repository/gitlab_api.py:177-190` devuelve payload GitLab crudo (`iid`, `web_url`), mientras routers esperan `number`, `html_url`/`url` (`app/routers/books.py:999-1000`, `:1047-1048`). GitLab/local no implementan `fetch_pull_request`/`fetch_issue` usados en `app/services/review_sync.py:53-60`; la interfaz `base.py:13-86` tampoco los define. Listado de ramas no pagina en GitHub (`github_api.py:58-60`) ni GitLab (`gitlab_api.py:49-51`); árbol GitLab pide 1000 pero no sigue paginación (`:71-82`); árbol GitHub no comprueba `truncated` (`github_api.py:94-102`).

**Reproducción propuesta:** mock GitLab devuelve `{iid: 7, web_url: 'https://example.invalid/mr/7'}`: la revisión queda sin número/enlace. Mock de dos páginas de ramas o árbol truncado: faltan resultados. Esto afecta detección de ramas legacy y, combinado con B14, importación/borrado del catálogo.

**Fix/tests:** DTO común de revisión y métodos de fetch explícitos; estado `merged`/draft según proveedor. Paginación completa y error explícito ante truncamiento no resuelto; tests contractuales mock para GitHub/GitLab/local. No precisa llamadas externas reales.

### B16 — Membresías sin unicidad ni validación de referencias consistente

**Evidencia:** `app/models.py:93-102` carece de unique `(user_id, organization_id)`. `app/routers/admin.py:105-115` inserta sin comprobar duplicado/existencia; `:215-225` hace check-then-insert susceptible a carrera. `app/database.py:25-30` no habilita `PRAGMA foreign_keys=ON` para SQLite. Permisos toman `.first()` (`app/services/permissions.py:88-98`).

**Reproducción propuesta:** insertar editor y organization_admin para mismo par por `/admin/memberships`; puede quedar una decisión de rol dependiente de la primera fila. Borrar una membresía no elimina la otra. En SQLite por defecto, enviar IDs inexistentes no queda protegido por FKs sin habilitarlas.

**Fix/tests:** constraint única, FK activadas por conexión SQLite, validación explícita de usuario/org, manejo de `IntegrityError` con rollback y respuesta 409/400. Tests de duplicados simultáneos, revocación efectiva, IDs inexistentes y último gestor de org.

### B17 — Límites y servicios síncronos facilitan agotamiento de recursos

**Evidencia:** uploads leen entero antes del límite (`app/routers/books.py:238-242`, `:1130-1132`) y no hay límite agregado de archivos; Markdown/preview no tiene límite de tamaño (`:1152-1160`). Endpoints async de guardado ejecutan Git/HTTP síncronos (`:723-729`, `:900-906`, `:1137-1144`). Git local no tiene timeout (`local_git.py:55-62`). Home refresca hasta 25 revisiones globales secuencialmente (`dashboard.py:40`, `review_sync.py:76-96`), cada HTTP admite hasta 30 s (`github_api.py:33-35`); errores no actualizan backoff. Seleccionar las 25 más recientes **antes** de filtrar frescura provoca inanición de anteriores. Login/registro no incluyen rate limiting ni política explícita de longitud de password (`auth.py:96-171`).

**Reproducciones propuestas:** con mocks, proveedor que agota timeout en cada revisión; home se retrasa y repite en la siguiente petición. Crear 26 revisiones abiertas: la más antigua no se visita mientras siga fuera del lote. Enviar archivo sobre límite y observar que se lee íntegro antes de rechazar; no realizar carga real pesada.

**Fix/tests:** cuotas de request/usuario, lectura acotada y límite agregado; tamaño de Markdown, imágenes y píxeles decodificados. Rate limiting de auth/alta/preview. IO bloqueante fuera del event loop, timeout de subprocess, sync de revisiones por job con backoff y selección por `last_synced_at`. Tests con reloj/transporte falsos, respuesta rápida bajo fallo y cola justa. No se ha verificado una protección adicional en proxy.

### B18 — Fugas de errores y metadatos docentes persistentes

**Evidencia:** `app/main.py:150-156` expone fragmentos de excepción DB en health público. `app/routers/books.py:987-989`, `:1035-1037` llevan excepciones crudas al usuario mediante query string. `app/models.py:118-122` guarda tokens de servicio como texto en BD. Commits usan nombre y email reales del docente (`books.py:727-728` y otros guardados); un repositorio público publica también esa historia.

**Reproducción propuesta:** mock de error con ruta/host señuelo y comprobar respuesta/Location; generar commit en fixture y observar author/email. No introducir tokens reales ni buscar datos existentes.

**Fix/tests:** errores públicos genéricos con ID de correlación, logs redactados; health solo estado. Protección del archivo/backup DB y referencia a almacén de secretos cuando corresponda, token con alcance mínimo por repo. Política informada de atribución pública: alias/email noreply estable si no se desea publicar dirección del docente. Tests de no inclusión de marcadores sensibles en respuesta, URLs y logs. No se afirma que se hayan filtrado tokens reales.

## Cobertura observada y límites

### Controles positivos

- Las consultas inspeccionadas utilizan SQLAlchemy/expresiones, no SQL construido con datos de formularios. No se identificó SQL injection en estas rutas.
- Contraseñas con PBKDF2 y migración de hashes bcrypt (`app/security.py:5-26`); no se almacenan contraseñas en claro en `User`.
- Bleach está presente en el render normal. B02 es un bypass **posterior** a ese control; no implica que todo Markdown ejecute HTML.
- Administración global protegida por `require_admin`; gestión de organización comprueba membresía en `admin.py:24-40`. Son controles útiles, aunque insuficientes en otras rutas.
- Git local usa argv sin `shell=True`, lock reentrante y flock entre procesos. No se declara shell injection. Faltan validación de refs/paths, timeouts y aislamiento de lectura.
- GitHub actualiza refs con `force=False`, evitando sobrescritura no fast-forward en una carrera de commits simultánea.

### Tests existentes: inspeccionados, no ejecutados

`tests/test_app.py` cubre importación, assets, fichas, PDF, comentarios, bcrypt, ramas y aprobación happy path. `test_local_git_repository_serializes_parallel_process_writes` (`:532-600`) prueba escritores en ramas distintas; no versiones obsoletas en un mismo documento ni lecturas durante checkout. `test_github_email_prefers_primary_verified_email` (`:518-529`) usa `user_info.email=None`, por lo que no detecta la prioridad insegura del email público. El test de propuesta/aprobación (`:710-884`) no prueba aislamiento, SHA revisado ni fallo parcial.

Antes de ejecutar la suite hay que aislarla: `tests/test_app.py:16-26` lee un asset externo en tiempo de importación desde `../data/repo/...`; `build_client` (`:29-60`) cambia algunas variables y limpia settings cache, pero importa `app.main` y su settings carga `.env` por defecto (`app/config.py:9-13`). No garantiza por sí solo que todos los proveedores/bootstrap/engine ya importados queden aislados. Usar proceso/CWD desechable, configuración completa de test sin env files, DB/repo temporales y bloqueo de red. Hay además una aserción aparentemente desactualizada: `test_app.py:832` espera `Pull request registrada correctamente.`, mientras `app/routers/books.py:1054` devuelve `Propuesta de cambio enviada para revisión.`; es discrepancia estática, no resultado de test.

No se ha hecho análisis de CVEs, validación dinámica de Authlib, del proxy, del navegador, del parser SVG/PDF ni del despliegue. SVG/PDF debe revisarse en sandbox respecto a referencias externas; no se etiqueta aquí como SSRF demostrado sin inspeccionar ese comportamiento de dependencia. URLs de proveedor/local_path son entradas de administrador: conviene allowlist, pero no se confunden con un SSRF anónimo probado.

### Contenido `../libre_libros_content`

Se listaron los archivos del árbol `books`, se leyó como muestra `books/primaria/lengua/lengua-primaria/book.md` y se buscaron patrones de HTML activo, URLs externas y `../` en `.md`/`.svg`. Los resultados de esa búsqueda fueron enlaces curriculares y namespaces SVG; no apareció un payload activo en esa búsqueda. **No equivale a certificar todos los materiales ni los binarios:** no se han examinado visualmente fotos/capturas, metadatos EXIF, derechos de imagen ni historia Git.

La muestra contiene enlaces locales a `assets/cover.svg`, `assets/lectura-aula.jpg` y fichas (`book.md:3`, `:39-41`, `:77`), que recorren los endpoints auditados. El proyecto de revista/entrevistas (`:20-22`, `:80-82`) es una consigna, no evidencia de datos reales de alumnos; para el piloto debe quedar explícito que no se suben respuestas, fotografías identificables, audios, nombres ni evaluaciones de alumnado. No convertir automáticamente cualquier directorio compartido en catálogo público (B14).

## Invitación segura mínima compatible con la arquitectura actual

### Decisiones de piloto

1. Mantener FastAPI/Jinja, SQLAlchemy y autenticación local. **Docente sin cuenta GitHub**; los commits usan la identidad de la aplicación/proveedor de servicio, independiente del login. No hace falta Supabase Auth ni una migración de framework.
2. Activar modo `invitation_only` obligatorio en el piloto. `/register` GET/POST no crea usuarios sin una invitación válida. Deshabilitar OAuth durante el piloto si no se implementa también su comprobación de invitación y enlace seguro.
3. Un admin global emite invitaciones de editor para una organización concreta. Para mínimo alcance, no delegar emisión ni permitir roles globales en el formulario público. Alta manual de admin inicial fuera del flujo de invitaciones, con credencial fuerte y control de bootstrap.
4. Separar lectura pública de edición: home/catálogo/PDF hoy requieren usuario (`dashboard.py:23-24`, `books.py:443-450`, `:1186-1195`) aunque el detalle público no. Si “libros públicos” incluye acceso anónimo usable, añadir catálogo público de versiones publicadas sin escritura incidental; no abrir endpoints de edición por ello.

### Modelo mínimo

Tabla `invitations`:

- `id` aleatorio o ID interno; `token_hash` único, **no token en claro**.
- `email_normalized`, `organization_id` FK y `membership_role` limitado por el emisor.
- `created_by_user_id`, `created_at`, `expires_at` UTC, `used_at`, `revoked_at`.
- Generar al menos 32 bytes con `secrets.token_urlsafe(32)`; guardar SHA-256 del token de alta entropía. TTL corto explícito (p. ej. 48 h), revocación y reemisión que invalida el anterior.
- Unique de membresía y normalización/validación de email centralizadas. El token no permite elegir otro correo ni elevar rol.

### Flujo mínimo

- `POST /admin/invitations`: `require_admin`, CSRF, validación de correo/org, límite de emisión y auditoría sin token. Crear/guardar hash y enviar enlace por un canal al correo invitado; para 10–20 docentes, entrega manual privada puede servir si se verifica destinatario y no se almacena el enlace en logs/chat grupal.
- `GET /invite/<token>`: validar forma/hash/expiración/revocación, **no consumir en GET** (escáneres de email abren enlaces). Mostrar alta sin recursos externos, `Cache-Control: no-store`, `Referrer-Policy: no-referrer`; redacción de ruta/token en access logs. Preferible canjear a contexto temporal de sesión y redirigir a una URL limpia sin consumir todavía.
- `POST /invite/accept`: CSRF + token/contexto de alta, nombre y contraseña. Correo y rol provienen de la invitación. Política razonable de longitud de contraseña, hash existente y rate limiting. En una transacción: actualizar condicionalmente invitación (`used_at IS NULL`, no revocada, no expirada) y exigir exactamente una fila; crear usuario y membresía o aplicar política segura para cuenta existente; commit. Rollback completo ante error/constraint.
- **Cuenta existente:** no sobrescribir password ni iniciar sesión solo porque existe una invitación para su email. Pedir login/reautenticación de esa cuenta para aceptar una nueva membresía, o implementar recuperación aparte con token de propósito distinto. Esto evita convertir una invitación a organización en reset/toma de cuenta.
- Tras alta nueva, sesión limpia con usuario activo y versión de revocación. Logout por POST, desactivación eficaz. No persistir token de invitación en cookie firmada legible si puede sustituirse por referencia temporal.
- Recuperación mínima operativa: nueva invitación para alta pendiente; reset de password de cuenta activa mediante flujo distinto de un solo uso, nunca contraseñas compartidas por el admin. No reutilizar un token para varios propósitos.

La BD soporta la atomicidad necesaria; para PostgreSQL se puede usar bloqueo de fila o UPDATE condicional, y para SQLite UPDATE condicional dentro de transacción. No confiar en un `SELECT` seguido de `INSERT` sin constraints: dos aceptaciones simultáneas deben producir un único éxito.

### Tests de aceptación de invitación (propuestos)

- No invitado local/OAuth: ninguna cuenta, sesión ni membresía nueva.
- Invitación válida: un usuario editor, una membresía, consumo único, sin GitHub.
- Caducada, revocada, manipulada y reusada: rechazo sin efectos parciales.
- Dos aceptaciones simultáneas: exactamente un éxito; segunda respuesta controlada.
- GET por escáner no consume; POST sin CSRF/origen permitido no funciona.
- El cliente no puede cambiar email/org/rol; emisor sin permisos rechazado.
- Cuenta existente: password y sesiones intactos hasta autenticación propia.
- Logs, Location y páginas posteriores no exponen token; cookie segura; rate limiting.
- Usuario desactivado o sesión revocada pierde acceso; homónimos obtienen workspaces distintos.

## Secuencia recomendada, solo rama/local

1. Preparar harness de tests aislado, sin `.env`, sin red y con señuelos; reproducir B01–B06 sin datos reales.
2. Corregir paths/XSS/creación/autorización y bloquear alta abierta. Añadir clave obligatoria, revocación efectiva, CSRF y GET de solo lectura.
3. Implementar invitación mínima con constraints y política de versiones publicadas. Probar matriz anónimo / editor A / editor B / gestor A / admin.
4. Añadir SHA esperado, aprobación atómica e idempotencia; escoger **un** proveedor para el piloto. Si es local, solo una copia dedicada, no el checkout compartido de desarrollo. Si es remoto, mocks contractuales antes de cualquier integración autorizada.
5. Revisar catálogo público y política de datos/atribución; tratar bootstrap como importación controlada, no borrado automático.
6. Solo tras validación y autorización separada preparar despliegue. Este informe no solicita ni realiza cambios en producción.
