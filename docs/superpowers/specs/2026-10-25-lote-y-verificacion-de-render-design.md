# Diseño: Fase 8 · Escala (lote de videos + verificación de render)

Aprobado por el usuario el 25-10-2026 en esta conversación: opción 1 (lote secuencial que reutiliza
`producir`), "3 videos finales listos para publicar", render real en GitHub Actions sin bloquear el merge,
60 s de espera con dos intentos, y "si falla que quede en espera hasta donde llegue".

Rama: `feat/lote-y-verificacion`. Versión del paquete: **0.7.0**.

## Contexto: la Fase 7 quedó cerrada como decisión, no como código

`docs/PLAN.md` todavía describe el punto 7 como "música de fondo que baja cuando hay voz, voz Azure o voz
propia grabada". El usuario descartó la voz propia y la música dentro del mp4: la música la elige en TikTok o
Instagram al momento de subir, porque es lo que está en tendencia y ayuda a que el video corra. El motor ya
entrega videos con solo voz (en `postproduccion.py` se normaliza el volumen a -14 LUFS y se queman los
subtítulos), así que no hay nada que construir ahí. Este spec reescribe esa línea del PLAN como decisión
cerrada. La voz de Azure queda condicional: solo si algún día hace falta una licencia comercial garantizada.

## Qué hace esta fase

Dos cosas, y las dos se apoyan en código que ya está probado:

1. **Lote**: de un tema salen los 3 videos (guion + video final + kit) en una sola pasada, sin que el usuario
   tenga que esperar y apretar un botón tres veces.
2. **Verificación de render en GitHub Actions**: que un cambio de `escena.py`, `visuales.py` o
   `postproduccion.py` no le rompa los videos en silencio.

## 1 · El lote

**Nuevo módulo `src/tpi_videos/lote.py`** con una función pública que recorre las ideas y llama a lo que ya
existe. No duplica nada del pipeline: `ideas.producir()` ya escribe el guion, lo revisa, compila LaTeX,
renderiza el video final y arma el kit, y ya recibe `gancho`, `titulo` y `segundos` (la promesa de duración que
se arregló en v0.6.1). El lote pasa los tres campos de cada idea y listo.

- Los 3 videos salen **de uno en uno**, nunca a la vez. Los renders pelean por la misma CPU y el panel ya
  impone un trabajo a la vez (`tareas.py`, `ocupado()`); el lote es **un solo trabajo largo**, así que esa
  regla no se toca.
- Cada video se guarda en su propia carpeta `salida/<nombre-del-guion>/`. Los nombres no chocan porque
  `redactor._nombre_archivo()` agrega `_2`, `_3` cuando el archivo ya existe.
- Duración esperada de un lote completo: 9 a 10 minutos (3 videos finales).

**Avance.** El lote emite las mismas líneas `--progreso-json` que un video suelto (`etapa`, `avance`,
`detalle`), con dos cambios: `avance` es el progreso global del lote (`(i - 1 + avance_interno) / 3`) y el
`detalle` trae delante «Video 2 de 3 · …». Así la barra y la tarjeta del panel funcionan sin tocar `tareas.py`
y sin campos nuevos que el panel tendría que ignorar.

**Reintento con espera (por idea).** `INTENTOS_POR_IDEA = 2` con espera de `ESPERA_ENTRE_INTENTOS = 60`
segundos entre intentos, ajustable con `--espera` (`--espera 0` los salta). Se anuncia en el avance:
"Gemini está saturado · espero 60 s y reintento (intento 2 de 2)".

- Solo se reintenta lo que se arregla esperando: límite de cuota, corte del servicio, conexión caída. Para
  eso `ErrorMotor` (`errores.py`) gana el campo `transitorio: bool`, y `ia.py` lo pone en `True` en las ramas
  de 429, 5xx y sin conexión. Clave inválida, modelo inexistente, LaTeX que no compila o un render que revienta
  **no** se reintentan: esperar da el mismo error.
- Esta capa se suma a la que ya existe y no la reemplaza: `ia.py` ya reintenta 3 veces con espera de 2 a 20 s,
  y `voces.py` 3 veces con 1.5/3/4.5 s. Son esperas de segundos y un límite de cuota de Gemini se levanta en
  minutos.
- **El lote nunca se corta antes**: aunque la idea 1 falle dos veces, sigue con la 2 y la 3. Lo que alcanzó a
  salir queda en `salida/`; lo que no, se lista al final con su mensaje y su botón de reintento. Peor caso con
  la cuota agotada: unos 4 minutos de espera antes de que el lote termine.
- Un guion que termina con avisos sin resolver **no** es un fallo: el video sale y la fila se marca ⚠️.
- Cancelar (el botón del panel mata el proceso) interrumpe también la espera.

**Resultado.** El lote emite `etapa="resultado"` con una lista de tres ítems: título, guion, video, duración,
promesa de segundos, avisos pendientes y, si falló, el mensaje y la ayuda. En la terminal se imprime la tabla
con ✅ / ⚠️ / ❌ por fila y, debajo, los que faltan con la forma concreta de rehacerlos.

## 2 · Comando de terminal

`./tpi lote "Porcentajes"` — pide las 3 ideas a Gemini y produce las tres.

Flags que hereda de `producir`: `--materia`, `--nivel`, `--voz`, `--velocidad`, `--sin-subtitulos`,
`--sin-kit`, `--borrador`, `--modelo`, `--estilo`, `--sin-revision`. Agrega: `--espera` (60 s), `--evitar` (los
títulos ya vistos, igual que `tpi ideas`) y `--ideas-json`, oculto (`argparse.SUPPRESS`) y destinado al panel:
las 3 ideas visibles serializadas, para no volver a gastar cuota ni cambiar las tarjetas que el usuario tiene
delante. No hay `--cantidad`: Gemini siempre trae 3 ideas y el lote siempre hace las 3. `--progreso-json`
funciona como en el resto de los comandos.

Si la búsqueda de ideas falla, el lote no arranca y sale el aviso que ya existe ("repite el comando o usa un
tema más concreto").

## 3 · Panel (Crear → Ideas)

Debajo de las 3 tarjetas aparece un botón **«Hacer los 3 videos»**. Toma las ideas visibles (sin pedir nada a
Gemini), corre un solo trabajo `tpi lote --ideas-json …` y muestra la barra con el video en curso. Al terminar,
la tabla de los tres: cada fila se toca y abre ese video en «Mis videos», como hoy. Las ideas que fallaron
conservan su tarjeta con el botón «Hacer este video» de siempre para reintentar una por una.

El botón se deshabilita si hay un trabajo en curso, igual que «Hacer este video».

## 4 · Verificación de render en GitHub Actions

Nuevo `.github/workflows/render.yml` (el repo no tiene ningún workflow hoy). Se ejecuta en cada Pull Request y
en cada push a `main`, y **no bloquea el merge**: es un semáforo que avisa, no un portero. No usa secretos:
GitHub nunca tiene la clave de Gemini, así que la verificación no genera contenido, solo renderiza un guion que
ya está en el repo.

Pasos:

1. `ubuntu-latest`, Python 3.11, `uv`/`pip install -e .`
2. Dependencias de sistema, la equivalencia Linux de lo que `scripts/instalar_mac.sh` hace con Homebrew y
   `tlmgr`: TeX con `latex` + `dvisvgm` y los paquetes `standalone`/`preview`, FFmpeg con libass,
   `libcairo2-dev`, `libpango1.0-dev`, `pkg-config`.
3. `./tpi crear guiones/ejemplos/visuales_tres_tipos.yaml --borrador --voz silencio`. Es el ejemplo más
   completo: fórmula con LaTeX, gráfico de función con raíces y vértice, diagrama de fuerzas y circuito.
4. `ffprobe` y comprobar que el mp4 existe, mide **540×960** (la calidad `borrador` de `CALIDADES`) y dura más
   de 20 segundos. Si falta el archivo o las medidas no cuadran, el chequeo sale rojo con la última parte del
   log a la vista.
5. Corrida estimada: 12 a 18 minutos (instalar TeX es lo más lento). En un repo público no cuesta nada.

Las letras Comic Neue y Bangers no se instalan en el runner: el motor las registra en tiempo de ejecución con
`manimpango.register_font()` (`entorno.py`, `registrar_fuentes`).

El workflow se valida empujando la rama y leyendo la corrida real de Actions; se deja el enlace en el PR.

## 5 · Documentación y cierre de hoja de ruta

- `docs/PLAN.md`: el punto 7 pasa a lectura de decisión cerrada (sin música ni voz propia en el mp4; la música
  la pone TikTok/Instagram sobre el video silencioso; Azure solo si hace falta licencia comercial), y el punto 8
  se marca ✅ con `tpi lote` y el workflow.
- `README.md`: una sección de lote (qué tarda, qué pasa si una idea falla, `--espera`) y una nota de que los PR
  traen un chequeo de render automático.
- `pyproject.toml` y `tpi_videos.__version__`: 0.7.0.

## Cómo se verifica antes del PR

- **Lote de punta a punta** con el Gemini falso del sandbox: salen las 3 carpetas en `salida/` y se comprueba
  cada mp4 con `ffprobe` (ancho, alto, duración).
- **Reintento**: hacer que el Gemini falso falle en la idea 2 y confirmar que espera, reintenta, y que la idea 3
  igual sale; y que un error no transitorio no gasta espera.
- **Promesa de duración**: confirmar que las 3 ideas llevan sus `segundos` al redactor (se ve en el log de
  peticiones del servidor falso).
- **Calidad de código**: `./tpi revisar`, `ruff`, `./tpi doctor`.
- **Panel**: se ejerce en el navegador (`./tpi panel --puerto 8766 --no-abrir`), apretando «Hacer los 3» de
  verdad y leyendo la tabla final en el DOM. Regla del repo: un cambio de panel no está listo sin verse
  renderizado.
- **No probado aquí**: que Gemini real achique los guiones y cuánto tarda un lote en el Mac del usuario; se deja
  como prueba explícita del handoff.

## Fuera de alcance

Voz propia grabada y música dentro del mp4 (decisión de la Fase 7). Renders en paralelo. Publicación automática
en TikTok/Instagram. Lotes de guiones ya escritos o de enunciados propios: la entrada es un tema y las 3 ideas
de Gemini. El workflow no llama a Gemini ni a edge-tts.
