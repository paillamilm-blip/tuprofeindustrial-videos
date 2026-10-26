# Diseño: Fase 11 · Cola persistente, progreso por video y reanudación si la IA se cae

Aprobado por el usuario el 26-10-2026 en esta conversación. La idea nació de un problema concreto: la IA
se cae seguido, el panel no dice en qué fase va cada video y, al cerrar o recargar, no se sabe si quedaron
videos pendientes ni si ya se hicieron.

Rama: `feat/cola-y-progreso`. Versión del paquete: **0.10.0**.

## Contexto: el lote funciona, pero es una caja negra

v0.9 deja tres videos por lote con moldes y ganchos. El lote ya informa un avance global y una fila por
video, pero:

- Solo hay **una barra global**: no se ve cuánto falta de cada video ni en qué fase está.
- El reintento de Gemini es **una sola vez a los 60 s**. Si la IA sigue caída, el video se marca como
  fallido y el trabajo se pierde.
- El estado vive **solo en memoria** (`TAREAS.actual`) y en el proceso hijo. Si se cierra el panel, no
  queda constancia de qué se estaba haciendo.
- Después de un fallo no hay una pantalla que responda «¿quedó algo pendiente o ya se hizo?».

## Qué hace esta fase

1. **Cola persistente** en `salida/.cola/trabajos.json`: cada lote y cada video guardan estado, fase,
   avance e hitos (guion, video, kit).
2. **Progreso por video** en la Fábrica: barra propia, fase visible y estado («En cola», «Animando»,
   «Pendiente de conexión», «Listo»…).
3. **Espera inteligente de la IA**: los errores transitorios no abandonan el video; se reintenta con
   espera creciente y el video queda **Pendiente de conexión** hasta que vuelva.
4. **Reanudación al abrir el panel**: lo pendiente de conexión se retoma solo; lo interrumpido a mitad de
   render se muestra con un botón **Reanudar**.
5. **Reutilización de hitos**: si ya hay guion, no se vuelve a llamar a la IA; si ya hay video, solo se
   rehace el kit.
6. **Terminal y panel comparten la cola**: `tpi lote --reanudar` hace lo mismo que el botón.

No hay un proceso nuevo que corra siempre. La cola es un archivo; el panel la lee y lanza el mismo
`tpi lote` de siempre.

## 1 · El archivo de cola (`src/tpi_videos/cola.py`)

Módulo nuevo, sin dependencias de NiceGUI ni de Manim. Usa `entorno.raiz_proyecto()`, así los tests
pueden apuntar a una carpeta temporal con `TPI_RAIZ`.

### 1.1 Ubicación y escritura

- Ruta: `salida/.cola/trabajos.json` (la carpeta empieza con punto: no aparece en «Mis videos»).
- `salida/` ya está en `.gitignore`; la cola nunca se sube al repositorio.
- Se escribe **completo y de una vez**: `trabajos.json.tmp` y después `os.replace`. Si el proceso muere a
  mitad, el archivo anterior queda intacto.
- Si el JSON está corrupto o no se puede leer: se renombra a `trabajos.json.roto-<fecha>` (no se borra),
  se empieza con una cola vacía y se avisa una vez. Los videos ya renderizados no se tocan.
- `version: 1` en la raíz. Una versión futura desconocida se lee sin modificar y el panel muestra un aviso
  en vez de sobrescribirla.
- **Escrituras con freno**: los avances de render se guardan al cambiar de fase y, dentro de una misma
  fase, como máximo cada 5 s (el render emite decenas de eventos). Los hitos y los cambios de estado se
  guardan siempre. Así una cola de 3 videos no reescribe el archivo en cada fotograma.

### 1.2 Forma del archivo

```json
{
  "version": 1,
  "lotes": [
    {
      "id": "20261026-153000-a1b2",
      "tema": "Porcentajes",
      "creado": "2026-10-26T15:30:00",
      "actualizado": "2026-10-26T15:31:12",
      "estado": "en_curso",
      "fase": "pensando_ideas",
      "error": null,
      "ayuda": null,
      "intentos": 0,
      "proximo_intento": null,
      "ajustes": {
        "materia": null, "nivel": null, "dificultad": null, "modelo": "gemini-3.8-flash",
        "calidad": "final", "estilo": null, "proveedor": null, "voz": null,
        "subtitulos": true, "con_kit": true
      },
      "videos": [
        {
          "id": "20261026-153000-a1b2-1",
          "posicion": 1,
          "idea": { "titulo": "…", "angulo": "…", "molde": "…", "ganchos": [] },
          "estado": "en_cola",
          "fase": "en_cola",
          "avance": 0.0,
          "detalle": "En espera",
          "hitos": {},
          "error": null,
          "ayuda": null,
          "intentos": 0,
          "proximo_intento": null,
          "actualizado": "2026-10-26T15:30:00"
        }
      ]
    }
  ]
}
```

- `lotes` se ordena por `creado`; el panel muestra primero los que tienen algo pendiente.
- `hitos` guarda lo que ya se produjo y sirve para reanudar:
  - `guion`: `{ruta, pendientes, supuestos, rondas, modelo, revisado_por_ia}`.
  - `video`: `{video, carpeta, duracion, segundos_proceso, srt, fuentes_tiempo, tema}`.
  - `kit`: `{carpeta, portada, publicacion, texto_kit, aviso}`.
- `hitos` es la única fuente para reconstruir un resultado: no se guarda una copia aparte. El hito
  `video` trae duración, tema, srt y fuentes; el hito `kit` trae portada, publicación, textos y avisos.
- `idea` es el `model_dump()` de `ideas.Idea`, igual que hoy en `ItemLote.como_dict()`.

### 1.3 Estados

Lote (`estado`):

| Estado | Significado |
|---|---|
| `pensando_ideas` | La IA todavía no devolvió las 3 ideas |
| `en_curso` | Hay videos produciéndose |
| `pendiente_ia` | Se detuvo esperando a que vuelva la IA |
| `interrumpido` | El panel o el proceso se cerró a mitad |
| `listo` | Todos los videos terminaron |
| `fallo` | Terminó con errores que la espera no arregla |
| `descartado` | El usuario lo sacó de la cola |

Video (`estado`):

| Estado | Significado | Barra |
|---|---|---|
| `en_cola` | Aún no empieza | 0 % |
| `redactando` | La IA escribe el guion | 5 % fijo |
| `animando` | Manim dibuja el video | 25–90 % |
| `subtitulos` | Se alinean las palabras | 90 % |
| `kit` | Portada y textos de publicación | 95 % |
| `pendiente_ia` | Esperando conexión/cuota de Gemini | Se congela en la última fase |
| `interrumpido` | Se cerró a mitad de una fase | Se congela |
| `listo` | Video y kit en `salida/` | 100 % |
| `fallo` | Error no transitorio (LaTeX, matemática, disco) | Se congela |
| `descartado` | El usuario lo sacó de la cola | — |

Reglas de transición:

- Al crear el lote, los videos nacen `en_cola`.
- `en_cola → redactando → animando → subtitulos → kit → listo`.
- Cualquier estado activo → `pendiente_ia` si el error es transitorio de Gemini (ver §3).
- Cualquier estado activo → `fallo` si el error no es transitorio.
- Cualquier estado activo → `interrumpido` al normalizar una cola cuyo proceso ya no existe.
- `pendiente_ia` y `interrumpido` pueden volver a la fase que tocaba; los hitos ya guardados se saltan.

El **estado del lote se deriva de sus videos** al normalizar; nunca se adivina:

| Situación del lote | Estado resultante |
|---|---|
| `pensando_ideas` sin videos | `pendiente_ia`: hay que volver a pedir las ideas |
| Tenía videos activos (`redactando`…`kit`) y el proceso murió | `interrumpido` |
| Tenía un video `pendiente_ia` | `pendiente_ia` |
| Todos `listo` | `listo` |
| Todos `listo` o `fallo`, al menos uno `fallo` | `fallo` |
| Algunos `en_cola` y ninguno activo | `interrumpido` (el lote quedó a medias) |

La normalización de un video activo (`redactando`, `animando`, `subtitulos`, `kit`) lo deja
`interrumpido` y conserva su `fase` y su `avance`: la fila puede decir «Se interrumpió animando (55 %)».

### 1.4 Funciones públicas

- `cargar() -> dict` y `guardar(datos)` (atómicos).
- `nuevo_lote(tema, ajustes, ideas=None) -> str` (id).
- `agregar_videos(lote_id, ideas)`.
- `actualizar_lote(lote_id, **campos)` y `actualizar_video(video_id, **campos)`.
- `hito(video_id, nombre, datos)`.
- `pendientes_ia() -> list[dict]`: lotes con estado `pendiente_ia` o con videos en ese estado.
- `interrumpidos() -> list[dict]`.
- `normalizar_interrumpidos()`: convierte estados activos en `interrumpido` al arrancar el panel, **solo si
  el candado de §1.5 está libre** (si hay un `tpi lote` vivo, no se toca nada).
- `ultimo_lote()` y `lotes_visibles()`: lo que muestra la tarjeta de cola.
- `podar()`: conserva todos los lotes con algo pendiente y los **últimos 20 videos terminados**; el resto
  se elimina del archivo (los videos siguen en `salida/`). Los lotes descartados se eliminan al podar.
- `descartar_lote(lote_id)`: no descarta un lote con el candado tomado (`en_curso`/`pensando_ideas`); el
  panel muestra «Espera a que termine o cancela el trabajo» en vez de borrarlo bajo los pies del proceso.

### 1.5 Candado del lote (`salida/.cola/lote.lock`)

Un solo lote escribe la cola a la vez. El archivo guarda el PID y la hora de inicio.

- `tomar_candado() -> bool`: crea el archivo si no existe o si el PID guardado ya no está vivo (en ese
  caso lo reemplaza). Devuelve `False` si hay otro proceso vivo.
- `soltar_candado()`: lo borra; se llama siempre al terminar (con `try/finally`).
- Un candado con más de 12 h de antigüedad se considera abandonado aunque el PID exista (PID reciclado).
- Si no se puede tomar el candado, `tpi lote --reanudar` termina con un mensaje claro y código 0: el panel
  ya evita lanzar dos trabajos, así que esto solo pasa si el profesor abrió dos terminales.
- El panel **no toma el candado** para leer ni para escribir avances: solo lo consulta antes de normalizar
  y de lanzar un trabajo.

## 2 · Hitos y reanudación en `producir`

`ideas.producir()` gana dos argumentos opcionales; sin ellos se comporta exactamente como hoy:

```python
Hito = Callable[[str, dict[str, Any]], None]

def producir(..., reanudar: dict[str, Any] | None = None, hito: Hito | None = None) -> ResultadoProduccion:
```

- `reanudar` es el diccionario `hitos` del video en la cola.
- `hito(nombre, datos)` se llama **después** de cada etapa terminada, con `nombre` en `guion`, `video`,
  `kit` y datos serializables a JSON.

Comportamiento:

1. **Guion**: si `reanudar["guion"]["ruta"]` existe y el archivo está, se carga con `cargar_guion()` y se
   reconstruye `ResultadoRedaccion` con los datos guardados (`pendientes`, `supuestos`, `rondas`,
   `modelo`, `revisado_por_ia`). No se llama a Gemini. Si no existe, se ejecuta `redactar()` como hoy y
   se llama `hito("guion", …)`.
2. **Video**: si `reanudar["video"]["video"]` existe y el archivo está, se reconstruye `ResultadoVideo`
   con la duración, tema, srt y fuentes guardadas. No se renderiza de nuevo. Si no, se ejecuta
   `crear_video()` y se llama `hito("video", …)`.
3. **Kit**: si `con_kit` es `False`, no se hace nada. Si `reanudar["kit"]["publicacion"]` existe y el
   archivo está, se reconstruye el kit desde el propio hito (portada, publicación, texto y aviso) sin
   llamar a la IA. Si no, se ejecuta `crear_kit()` y se llama `hito("kit", …)`.
4. Si un archivo guardado desapareció (el usuario borró `salida/`), el hito se ignora y esa etapa se
   rehace. Un hito roto nunca bloquea el video.
5. Un error de `crear_kit()` deja el video ya guardado: el hito `video` existe, así que el reintento hace
   solo el kit.
6. `ResultadoProduccion` se arma igual que hoy; en modo reanudado, `segundos_proceso` puede ser 0 y
   `historial` de la redacción queda vacío.

La ventana entre crear un archivo y guardar su hito es de milisegundos. Si el proceso muere justo ahí, esa
etapa se repite; no se corrompe nada.

## 3 · Espera de la IA y reintentos (`src/tpi_videos/lote.py`)

### 3.1 Cuándo se espera

Solo para `ErrorMotor.transitorio is True` (sin conexión, timeout, 429 de cuota, 5xx de Gemini). Los demás
errores no mejoran esperando: pasan a `fallo` con el mensaje y la ayuda actuales.

### 3.2 Secuencia de espera

- Primera espera: `espera` (por defecto **60 s**, igual que hoy; `--espera` la cambia).
- Después: 2 min, 5 min y luego **cada 5 min**, sin límite, mientras el proceso viva.
- Antes de cada espera se actualiza la cola: `estado="pendiente_ia"`, `fase="esperando_ia"`,
  `intentos += 1`, `proximo_intento` con la hora.
- Se emite progreso con la fase `esperando_ia` y el detalle «Sin conexión con la IA: reintento en 2 min».
  El avance del video no retrocede ni avanza: se queda en la última fase completada.
- `espera=0` (uso de tests y de quien no quiere esperar) marca `pendiente_ia` y devuelve el control sin
  dormir.
- `reintentos=None` (producción) = sin límite. Un entero (tests) corta después de N intentos y deja el
  video `pendiente_ia`.
- El sueño se hace con `dormir` inyectable (por defecto `time.sleep`); así los tests no esperan de verdad.
- Ctrl-C y el botón **Cancelar** del panel matan el proceso; al arrancar de nuevo, la normalización de
  §1.4 convierte la fase activa en `interrumpido`.

### 3.3 Qué pasa con el resto del lote

- Un video pendiente **pausa el lote**: no tiene sentido seguir con los otros si Gemini no responde.
  Los demás quedan `en_cola` y el lote queda `pendiente_ia`.
- Cuando la IA vuelve, se termina ese video y se sigue con los demás en orden.
- Un video `fallo` no corta el lote: se anota y se sigue, como hoy.

### 3.4 Ideas del lote

El lote guarda su ficha **antes** de pedir las 3 ideas (`estado="pensando_ideas"`). Si la IA falla en ese
paso:

- Se reintenta con la misma secuencia y el lote queda `pendiente_ia`.
- Si el panel se cierra, la ficha queda guardada y al abrir se vuelven a pedir las ideas del mismo tema.
- Cuando llegan, `agregar_videos()` crea las 3 fichas y el lote pasa a `en_curso`.

`--ideas-json` (el panel ya tiene las ideas, o «Intentar solo este») crea el lote directamente con esas
ideas, sin llamar a Gemini.

## 4 · Progreso por video (`--progreso-json`)

Se mantienen los campos actuales `etapa`, `avance` (global 0–1) y `detalle`. Se agregan, cuando el evento
es de un video:

| Campo | Ejemplo | Para qué |
|---|---|---|
| `video` | `2` | Número de video dentro del lote |
| `total` | `3` | Videos del lote |
| `video_avance` | `0.55` | Avance de ese video (0–1) |
| `fase` | `animando` | Fase visible |
| `estado` | `pendiente_ia` | Estado de la ficha |

- El avance global pasa a ser la suma del avance de cada video: `(posicion - 1 + video_avance) / total`.
  Así la barra general avanza parejo y no a saltos de un tercio.
- Mapa de `video_avance`:
  - `redactando`: `0.05`.
  - `preparando`/`animacion`: `0.25 + 0.65 * avance_render` (0.25–0.90).
  - `subtitulos`: `0.90`.
  - `video final`: `0.93`.
  - `kit`: `0.95` al empezar, `1.0` al terminar.
  - `esperando_ia`: se mantiene el último valor.
- Los eventos del lote sin video (pensando ideas) no llevan `video`; el panel los muestra como detalle
  global.
- Un evento con `video_avance` menor al actual se ignora en el panel (no se retrocede).

## 5 · Panel (`src/tpi_videos/panel/`)

### 5.1 Al arrancar

En `app.iniciar()`, después de registrar las páginas, un `app.on_startup`:

1. Si el candado de §1.5 está tomado (un `tpi lote` de la terminal sigue vivo), no se normaliza ni se
   lanza nada: la tarjeta solo lee la cola.
2. `cola.normalizar_interrumpidos()` (el proceso anterior ya no existe).
3. Si `TAREAS` está libre, hay una clave de Gemini configurada y existe un lote `pendiente_ia` (aunque
   todavía no tenga videos, porque faltan las ideas) o con videos `pendiente_ia`/`en_cola` **y ningún video
   `interrumpido`**, lanza `tpi lote --reanudar --solo-pendientes` con nombre **«Reanudar cola»**.
4. Si no hay clave, no lanza nada: la tarjeta de cola muestra el pendiente y el enlace a Ajustes.
5. Si el lote pendiente tiene videos `interrumpido`, **no** se lanza solo: la tarjeta lo muestra con el
   botón **Reanudar**.

`PROPIOS` en `fabrica.py` incluye «Reanudar cola» para que la pantalla siga el trabajo al recargar.

### 5.2 `Tarea` y los eventos

- `Tarea` gana `videos: dict[int, dict]` con `{estado, fase, avance, detalle, video_id}` y `cola_id`.
- `Tareas._aplicar()` guarda esos datos cuando el evento trae `video`; si no, se comporta como hoy.
- `texto_etapa` sigue igual para el detalle global.

### 5.3 Fábrica: mientras trabaja

- Cada fila de video gana una barra propia (`ui.linear_progress`, altura fina) y una etiqueta de fase.
- La fila muestra, según `estado`:
  - `en_cola`: «En espera».
  - `redactando`: «La IA está escribiendo…».
  - `animando`/`subtitulos`/`kit`: nombre de la fase y su detalle.
  - `pendiente_ia`: «Pendiente de conexión · reintento en 2 min» en naranja.
  - `interrumpido`: «Se interrumpió» en naranja.
  - `listo`: «Listo» en verde.
  - `fallo`: «Falló» en rojo, con el mensaje.
- El detalle global muestra «Video 2 de 3 · …» como hoy.
- La barra global sigue arriba.

### 5.4 Fábrica: tarjeta «Cola de videos»

- Se dibuja al entrar a la página y después de cada trabajo, leyendo `cola.lotes_visibles()`.
- Muestra el último lote y los lotes anteriores que tengan algo pendiente (no los terminados viejos).
- Por cada lote: tema, fecha, estado y una fila por video con título, estado, fase, barra y, si está listo,
  **Ver video**.
- Botones del lote: **Reanudar** (lanza `tpi lote --reanudar --cola-id <id>`), **Descartar** (con
  confirmación) y, si terminó bien, **Abrir carpeta**.
- Cuando la cola acumula más de 20 videos terminados, los más viejos se van de la cola, pero siguen en
  «Mis videos».
- Si hay un trabajo en curso, la tarjeta se oculta (la pantalla de trabajo ya muestra lo mismo).

### 5.5 Errores y estados raros

- Un lote `fallo` muestra el error y el botón «Intentar solo este» por cada video fallido, reusando
  `_arrancar_uno()`.
- Si la cola no se puede escribir (disco lleno o permisos), el trabajo sigue en memoria y el panel avisa
  una vez: «No pude guardar la cola; si cierras el panel, este trabajo no se podrá reanudar».
- Si dos procesos intentan reanudar el mismo lote, el candado de §1.5 deja pasar a uno solo; el segundo
  sale con «Ya hay un lote en curso». El panel ya impide lanzar dos trabajos a la vez.

## 6 · Terminal (`src/tpi_videos/cli.py`)

- `tpi lote --reanudar`: procesa el lote no terminado más antiguo. Si no hay nada, imprime «No hay videos
  pendientes.» y sale con 0.
- `--reanudar` **ignora** el tema y las opciones de estilo de la línea de comandos: usa los `ajustes`
  guardados en la ficha del lote (materia, nivel, dificultad, modelo, calidad, estilo, proveedor, voz,
  subtítulos y kit). Así el botón del panel reproduce exactamente lo que se estaba haciendo.
- `--reanudar` junto con un tema o con `--ideas-json` es un error de uso: «Para reanudar no indiques tema
  ni ideas; usa `--cola-id` si quieres elegir un lote.»
- `tpi lote --reanudar --solo-pendientes` (oculto): solo lotes `pendiente_ia` (tengan o no videos, porque
  pueden faltar las ideas) o con videos `pendiente_ia`/`en_cola`, y **sin ningún video `interrumpido`**. Un
  lote con render interrumpido se salta entero: reanudar un render a medias es decisión del profesor, no del
  arranque automático. Lo usa el panel al arrancar.
- `tpi lote --reanudar --cola-id <id>` (oculto): un lote específico, para el botón de la tarjeta. Acepta
  lotes `interrumpido`.
- `--espera` sigue existiendo; ahora es la **primera** espera de la secuencia (por defecto 60 s).
- Los mensajes de espera dicen el próximo intento y la fase: «Sin conexión con la IA; reintento en 2 min
  (video 2 de 3)».
- El resultado final incluye los videos que quedaron pendientes, con su motivo y su `cola_id`, para que
  el panel los muestre.

## 7 · Compatibilidad

- Sin cola, sin hitos y sin eventos nuevos, todo funciona como en v0.9: los campos son opcionales y el
  panel ignora los que no conoce.
- Los guiones, estilos y videos no cambian: esta fase no toca `escena.py`, `render` visual ni temas.
- `tpi crear`, `tpi producir`, `tpi ideas` y `tpi ganchos` no usan la cola (siguen siendo trabajos de un
  solo paso). La cola es del **lote** y de la Fábrica.
- Los tests actuales deben pasar sin cambios; los que usen `espera=0` se ajustan a la nueva semántica
  (marcar pendiente, no fallar).

## 8 · Pruebas

Unitarias (stdlib `unittest`, sin Manim ni NiceGUI):

- `pruebas/test_cola.py`
  - Crear, actualizar y releer un lote y sus videos.
  - Escritura atómica: el archivo anterior sigue válido si falla el reemplazo.
  - JSON corrupto: se renombra a `.roto-*` y se empieza vacío.
  - `podar()` conserva pendientes y los últimos 20 terminados.
  - `normalizar_interrumpidos()` convierte `redactando`/`animando`/`kit` en `interrumpido` y deriva el
    estado del lote según la tabla de §1.3.
  - `normalizar_interrumpidos()` no toca nada si el candado está tomado.
  - `podar()` y `descartar_lote()` respetan el candado.
  - `pendientes_ia()` encuentra lotes con ideas pendientes y videos pendientes.
- `pruebas/test_lote_cola.py`
  - Un error transitorio marca `pendiente_ia`, guarda `proximo_intento` y no pasa al siguiente video.
  - Con `dormir` falso y `reintentos=3`, la secuencia de esperas es 60, 120, 300.
  - Al volver la IA, el video se termina y el lote sigue con los demás.
  - Un error no transitorio marca `fallo` y no reintenta.
  - Un lote sin ideas guarda `pensando_ideas` y las pide de nuevo al reanudar.
  - `--reanudar` usa los `ajustes` guardados y rechaza que se le pase un tema o `--ideas-json`.
  - `--solo-pendientes` se salta un lote que tiene videos `interrumpido`.
- `pruebas/test_producir_reanudar.py`
  - Con hito `guion`, no se llama a `redactar`.
  - Con hito `video`, no se llama a `crear_video`.
  - Con hito `kit`, no se llama a `crear_kit`.
  - Si el archivo del hito no existe, esa etapa se rehace.
  - `hito()` se llama en el orden guion → video → kit.
- `pruebas/test_tareas.py`
  - Un evento con `video`, `video_avance` y `fase` actualiza `Tarea.videos` y no retrocede.
  - Un evento sin `video` mantiene el comportamiento actual.

En CI:

- Agregar un paso «Pruebas del motor» antes del render:
  `python -m unittest discover -s pruebas -t . -v`.
- El render de ejemplo y los clips de gancho siguen igual; nada de esto toca la escena.

Manual en el Mac (el panel no corre en CI):

1. Lanzar un lote y ver las 3 barras y sus fases.
2. Cortar el internet durante la redacción: el video queda «Pendiente de conexión».
3. Reconectar: el mismo video sigue sin volver a pedir el guion si ya lo tenía.
4. Cerrar el panel mientras espera y volver a abrirlo: se reanuda solo.
5. Cerrar el panel a mitad de un render y volver a abrirlo: aparece «Se interrumpió» con **Reanudar**.
6. Terminar un lote y comprobar que la tarjeta de cola muestra los videos listos con **Ver video**.

## 9 · Fuera de alcance

- Un proceso o servicio que corra siempre en segundo plano.
- Varios renders al mismo tiempo (sigue siendo uno a la vez).
- Reanudar un render a nivel de fotograma o de animación: se rehace la etapa de video completa.
- Notificaciones del sistema operativo, correo o mensajes.
- Métricas, publicación automática o APIs de redes sociales.
- Cola para videos sueltos creados con `tpi crear` o `tpi producir` (solo el lote/Fábrica).
- Cambios visuales, de estilo o de contenido de los videos.
