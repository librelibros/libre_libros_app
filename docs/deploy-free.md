# Despliegue gratuito para pruebas

## Repositorios

El proyecto ya esta separado en dos repositorios publicos:

- Aplicacion: `https://github.com/librelibros/libre_libros_app`
- Libros: `https://github.com/librelibros/libre_libros_content`

Los remotos locales apuntan a `librelibros`, no a `libre-libros`. Antes de subir cambios, confirma si esa es la organizacion correcta o si hay que migrar los remotos.

## Opcion recomendada: Render Free

Render es la opcion mas directa para una prueba publica porque puede desplegar el `Dockerfile` del repositorio y usar `render.yaml`. El plan gratuito tiene horas mensuales y se duerme con inactividad; sirve para demo, no para produccion.

Pasos:

1. Conecta Render con GitHub y selecciona `librelibros/libre_libros_app`.
2. Usa el blueprint incluido en `render.yaml`.
3. Define estas variables cuando Render las pida:

```text
LIBRE_LIBROS_INIT_ADMIN_EMAIL=tu-correo
LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_ID=client-id-de-github
LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_SECRET=client-secret-de-github
```

La URL de callback para la OAuth App de GitHub sera:

```text
https://TU-SERVICIO.onrender.com/auth/github/callback
```

Con esa configuracion, la app arranca con SQLite efimero y sincroniza el catalogo desde el repositorio publico `librelibros/libre_libros_content`. Para evitar limites de la API de GitHub en infraestructura compartida, configura tambien `LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_TOKEN` aunque el repositorio sea publico. Si el token solo tiene lectura, los libros se pueden consultar; para editar y crear pull requests desde la app necesitara permisos de escritura.

## Para persistir usuarios y comentarios

SQLite en servicios gratuitos suele ser efimero. Para que usuarios, comentarios y revisiones sobrevivan a reinicios, crea una base Postgres gratuita externa y cambia:

```text
LIBRE_LIBROS_DATABASE_URL=postgresql+psycopg://USUARIO:PASSWORD@HOST:5432/DB?sslmode=require
```

Neon o Supabase encajan para una demo pequena. Mantener los libros en GitHub sigue siendo la fuente de verdad para el contenido.

## Para permitir edicion contra GitHub

Crea un token fino en GitHub para el repositorio de libros. Para solo probar lectura, basta con permiso de lectura de contenidos. Para editar desde Libre Libros, anade lectura/escritura de contenidos, issues y pull requests. Despues configura:

```text
LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_TOKEN=ghp_o_token_fino
```

No guardes ese token en el repositorio. Configuralo solo como secreto del proveedor de hosting.

## Alternativa: Koyeb Free

Koyeb ofrece una instancia web gratuita pequena, pero su almacenamiento local tambien es efimero y los volumenes persistentes no estan disponibles en instancias `free`. Usalo con la misma estrategia: app en contenedor, libros en GitHub y base Postgres externa si quieres persistencia.
