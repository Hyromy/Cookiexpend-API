# Variables de entorno

El proyecto se ejecuta por defecto en modo desarrollo `PRODUCTION=False` con una configuración minima para funcionar.

Para configurar manualmente dichas variables, crea una copia del archivo `.env.example` y en la raíz del proyecto renombralo como `.env`. A continuación se detallan las variables disponibles y su propósito:

## Configuración general 

### `PRODUCTION`

Define el modo de ejecución del proyecto entre desarrollo (`False`) y producción (`True`).

_Por defecto, toma el valor de `False`_.

### `DJANGO_SECRET_KEY`

Secret de seguridad para protecciones y criptografía del proyecto. Se recomienda configurar un secret con caracteres combinados y de al menos 64 caracteres de longitud.

_Por defecto, se establece una secret insegura_.

## Red y seguridad

### `HOSTS`

Hosts permitidos para ser el anfitrión del proyecto. Puede definirse más de uno separandolo por comas (`,`).

_Por defecto, en desarrollo se permiten todos los hosts (`"*"`)_.

> Ejemplo
>
> HOSTS=site.example.com, other.site.com

### `CORS_ALLOWED`

Hosts externos (frontend) que pueden solicitar información al proyecto. Puede definirse más de uno separandolo por comas (`,`).

Generalmente se esperan tener los mismos valores que [CSRF_TRUSTED](#csrf_trusted).

> Ejemplo
>
> CORS_ALLOWED=https://my.site.com, https://super_web.com

### `CSRF_TRUSTED`

Hosts externos (frontend) que pueden enviar información o formularios al proyecto. Puede definirse más de uno separandolo por comas (`,`).

Generalmente se espera tener los mismos valores que [CORS_ALLOWED](#cors_allowed)

> Ejemplo
>
> CSRF_TRUSTED=https://my.site.com, https://super_web.com

### `SESSION_DOMAIN`

Define el alcance de las cookies dentro de los dominios y subdominios del frontend y la API.

_Por defecto, en desarrollo se obvia localhost_.

> Ejemplo
>
> ```txt
> # url frontend -> https://dasboard.super-web.com
> # url de la API -> https://api.super-web.com
> ```
>
> SESSION_DOMAIN=super-web.com

### `USE_SSL`

Indica si se deben forzar el uso de conexiones HTTPS.

_Por defecto, toma el valor de `False`_.

## Configuración de base de datos

> [!Warning]
>
> Todas las variables de esta sección son obligatorias si el proyecto se ejecuta en modo producción

### `DB_NAME`

Nombre de la base de datos a conectarse.

### `DB_USER`

Usuario de la base de datos a conectarse.

### `DB_PASS`

Contraseña del usuario de base de datos a conectarse.

### `DB_HOST`

Host o anfitrión de la base de datos.

### `DB_PORT`

Puerto de la base de datos.

## Redis

### `REDIS_URL`

URL de conexión al servidor de Redis. Se utiliza como bus de mensajes para la sincronización en tiempo real (Pub/Sub) entre la API y otros sistemas.

_Por defecto, en desarrollo toma el valor de `"redis://localhost:6379/0"`_.
