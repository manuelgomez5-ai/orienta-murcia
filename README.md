# Orienta Murcia · versión automatizada corregida

> **Importante:** Canva solo puede mostrar una copia estática de esta web. No ejecuta Python, GitHub Actions ni la lectura automática de PDF. Para la actualización real hay que publicarla desde este repositorio mediante GitHub Pages, Vercel o Netlify.


Aplicación web pública para seguir **vacantes, adjudicaciones, exclusiones y vacantes anuladas** de la especialidad **0590018 · Orientación Educativa** en la Región de Murcia.

Los visitantes solo necesitan abrir el enlace de la web. No tienen que descargar ni instalar ningún programa.

## Qué hace automáticamente

1. Revisa cada 15 minutos las páginas oficiales de Recursos Humanos de la CARM.
2. Detecta documentos nuevos de Secundaria y otros cuerpos.
3. Descarga los PDF y extrae únicamente las filas de Orientación Educativa.
4. Actualiza los archivos JSON que utiliza la web.
5. Guarda la fecha, el tipo de documento y el enlace oficial.
6. Publica los cambios al estar conectado el repositorio con GitHub Pages, Vercel o Netlify.

El sistema diferencia entre:

- vacantes completas y parciales;
- adjudicaciones provisionales y definitivas;
- adjudicaciones de interinos y de funcionarios de carrera;
- exclusiones;
- vacantes anuladas;
- posición oficial y posición activa estimada.


## Botón «Comprobar actualización»

La cabecera incluye un botón para volver a descargar, sin caché, los archivos JSON ya publicados. El botón no rastrea la CARM desde el navegador: comprueba si el proceso automático del servidor ya ha publicado una versión más reciente.

Por seguridad, el botón público no ejecuta directamente el rastreador de la CARM ni contiene credenciales. La descarga y lectura de nuevos PDF se realiza mediante GitHub Actions cada hora o mediante la ejecución manual del flujo `Sincronizar CARM`.

## Publicación más sencilla: GitHub Pages

1. Crea un repositorio nuevo en GitHub.
2. Sube todo el contenido de esta carpeta a la raíz del repositorio.
3. En **Settings → Actions → General**, permite que GitHub Actions tenga permiso de lectura y escritura.
4. En **Settings → Pages**, selecciona **GitHub Actions** como origen.
5. Abre la pestaña **Actions** y ejecuta una vez `Sincronizar CARM` y `Publicar web`.

La web quedará disponible en una dirección parecida a:

`https://TU-USUARIO.github.io/orienta-murcia/`

A partir de ahí, el flujo `Sincronizar CARM` revisará las fuentes cada 15 minutos. Cuando haya cambios, hará un nuevo commit y GitHub Pages volverá a publicar la web.

## Publicación con Vercel o Netlify

También puedes importar el repositorio desde Vercel o Netlify. Como es una web estática:

- no necesita comando de compilación;
- el directorio de publicación es la raíz del proyecto (`.`);
- cada commit automático del bot provocará una nueva publicación.

## Importar el ranking completo

La versión entregada incluye la relación definitiva completa de 2026/2027: 457 personas, 196 del Bloque 1 y 261 del Bloque 2. Para sustituirla manualmente por otra lista futura:

1. Crea la carpeta `input` si no existe.
2. Coloca el Excel como `input/ranking.xlsx`.
3. El Excel debe incluir una hoja `Ranking completo` con estas columnas: `Puesto global`, `Bloque`, `Puesto bloque`, `Nº lista`, `DNI`, `Apellidos, nombre` y `Puntos`.
4. Ejecuta el flujo `Sincronizar CARM` o, localmente, `python scripts/import_ranking_xlsx.py`.

Por seguridad, `input/ranking.xlsx` está excluido de Git. El script genera `data/ranking.json`, que es el archivo público que utiliza la web. El sincronizador también está preparado para detectar nuevas relaciones provisionales o definitivas publicadas por la CARM.

## Ejecutar una comprobación manual

Requisitos: Python 3.12 y Poppler (`pdftotext`).

```bash
pip install -r requirements.txt
python scripts/import_ranking_xlsx.py
python scripts/sync.py
```

Para probar la web en el ordenador:

```bash
python -m http.server 8000
```

Después abre `http://localhost:8000`.

## Archivos principales

- `index.html`: estructura de la web.
- `styles.css`: diseño adaptable a móvil y ordenador.
- `app.js`: filtros, tablas, buscador y cálculo de posición.
- `data/bundle.js`: datos que carga el navegador.
- `scripts/sync.py`: descubrimiento y sincronización de publicaciones.
- `scripts/parsers.py`: lectura de los distintos formatos PDF.
- `.github/workflows/sync.yml`: revisión automática cada 15 minutos.
- `.github/workflows/pages.yml`: publicación de la web.

## Control y límites

La aplicación muestra un aviso cuando un PDF cambia de formato o no puede interpretarse. La posición activa es orientativa: las resoluciones oficiales prevalecen siempre, y pueden existir perfiles, jornadas, renuncias justificadas o correcciones que no impliquen un avance lineal.

El proyecto es independiente y no pertenece a la Consejería de Educación. Los enlaces a los PDF oficiales se conservan para que cada dato pueda verificarse.
