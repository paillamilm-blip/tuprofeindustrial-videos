# Diseño: Fase 10 · Ganchos que frenan el scroll + moldes virales

Aprobado por el usuario el 26-10-2026 en esta conversación, después de elegir **alcance (vistas nuevas)** como
meta de los próximos 3 meses, publicar **3–5 videos por semana** y descartar el registro manual de métricas.
Consecuencia de esa última decisión: el motor **no aprende de los resultados**; la mejora viene de hacer más
apuestas por idea (varios ganchos) y de usar estructuras que ya funcionan (moldes), no de un panel de analítica.

Rama: `feat/ganchos-y-moldes`. Versión del paquete: **0.9.0**.

## Contexto: el motor ya produce, pero apuesta una sola vez por idea

v0.8 deja tres videos por lote con ángulos y dificultades distintas y un kit de publicación. El cuello de
botella dejó de ser la producción. Lo que falta para el alcance es lo que decide la retención en TikTok, Reels y
Shorts:

- **Un solo gancho por video.** La tarjeta trae un gancho y el video sale con ese. En los primeros 1–3 segundos
  se gana o se pierde la vista, y no hay forma de comparar alternativas sin pedirle otra idea a Gemini.
- **Siempre los mismos tres ángulos.** `error_tipico`, `aplicacion_real` y `dato_curioso` son buenos, pero el
  formato narrativo no cambia: casi todo es «pregunta → pasos → resultado». Los formatos probados (mito vs
  realidad, tres errores, POV, reto, «nadie te enseñó esto») no existen en el catálogo.
- **Sin datos, no hay aprendizaje.** El usuario no quiere anotar métricas, así que el motor no puede saber qué
  funcionó. La selección queda en su criterio, pero puede elegir **viendo clips reales** en vez de leyendo texto.

## Qué hace esta fase

1. **Catálogo de moldes** (`src/tpi_videos/moldes.py`): cinco formatos con su estructura y sus reglas objetivas.
   Las 3 ideas de una búsqueda usan **moldes distintos**; el lote también.
2. **3–5 ganchos por idea**, cada uno con su estilo (dolor, curiosidad, error, reto, dato). El primero es el
   recomendado y sigue llamándose `gancho` para no romper nada.
3. **Laboratorio de ganchos**: `tpi ganchos` y el botón «Probar ganchos» renderizan un clip vertical de 4–6 s por
   gancho, con la hoja y la cabecera reales, para elegir con el ojo antes de gastar el video completo.
4. **El gancho elegido y sus alternativas quedan en el guion** (`gancho:` y `gancho_variantes:`), así se puede
   cambiar después sin volver a llamar a la IA.
5. **Todo opcional y compatible**: un guion antiguo se lee y se renderiza igual; el estilo «Pizarra nocturna»
   no cambia ni un cuadro.

No hay pipeline nuevo de producción: los clips son una escena corta que reutiliza `VideoEjercicio` y el mismo
sistema de voz. La Fábrica sigue siendo un campo y un botón.

## 1 · El catálogo de moldes

`moldes.py` contiene solo metadatos y funciones de normalización; no importa `guion.py` (evita el ciclo). La
validación estructural vive en `guion.py`, que sí puede leer el catálogo.

| Clave | Nombre visible | Estructura que pide a la IA | Regla objetiva del motor |
|---|---|---|---|
| `mito_realidad` | Mito vs realidad | Afirmación incorrecta → por qué falla → forma correcta → resultado | Al menos un paso `error: true` y un paso correcto después |
| `tres_errores` | 3 errores | Tres equivocaciones típicas seguidas → la forma correcta → resultado | Exactamente 3 pasos `error: true` y al menos un paso correcto después |
| `pov` | POV | «Estás en…» en segunda persona → resuelve con lo que tienes → resultado | Sin regla extra; el prompt exige segunda persona y una situación concreta |
| `reto` | Reto | Ejercicio resuelto → un desafío parecido para comentar | Bloque `reto:` obligatorio |
| `nadie_te_enseno` | Nadie te enseñó esto | Dato que contradice la intuición → se demuestra resolviendo → conclusión | Bloque `verificacion:` obligatorio |

- `MOLDE_POR_DEFECTO = "libre"`: no es un molde del catálogo, es la ausencia de molde. Los guiones escritos a
  mano y los antiguos no lo llevan y no se validan contra ninguna estructura.
- `normalizar_molde(valor)` acepta tildes, mayúsculas y guiones (`"3 Errores"`, `"tres-errores"`), igual que
  `dificultad_normal()`. Un valor desconocido no se inventa: se informa con las opciones válidas.
- El catálogo alimenta tres cosas: el texto para `ideas.md`, las etiquetas del panel y la regla que revisa
  `guion.py` (el campo `regla` de cada molde es `un_error`, `tres_errores`, `reto`, `verificacion` o vacío).
  Una sola fuente, para que el prompt y el validador no se contradigan.

## 2 · Datos: ideas, ganchos y guion

### 2.1 `GanchoIdea` (nuevo, en `ideas.py`)

```python
class GanchoIdea(BaseModel):
    texto: str          # 1–90 caracteres y ≤ 10 palabras
    estilo: Literal["dolor", "curiosidad", "error", "reto", "dato"]
    emoji: str = ""
    tex: str = ""       # opcional, fórmula corta bajo el gancho
    voz: str = ""       # opcional; si falta se usa texto
```

El modelo es **tolerante** (campos con valores por defecto): no rechaza la respuesta completa de Gemini por una
variante mala. La limpieza fuerte vive en `ideas._limpiar()` y se aplica variante por variante:

- `texto` no vacío y máximo 10 palabras (cualquier grupo separado por espacio cuenta como palabra).
- Sin emojis dentro de `texto` ni `voz` (van en `emoji`).
- `tex` con llaves balanceadas y sin caracteres de control de YAML (misma ayuda que `_validar_tex`).
- Estilo obligatorio, para que las variantes no sean cinco formas de la misma pregunta.

Una variante que falla se descarta sin ruido. Si a una idea le quedan menos de 3 variantes válidas, se descarta
la idea completa; si quedan menos de 3 ideas, se levanta el error amable de siempre.

### 2.2 `Idea` (se amplía)

- `molde: str = ""` y `ganchos: list[GanchoIdea] = []`.
- `gancho: str` se conserva como **texto del gancho recomendado**; si viene vacío y hay `ganchos`, se usa el
  primero.
- **Dos entradas, dos exigencias.** `proponer_ideas()` (respuesta nueva de Gemini) exige 3–5 ganchos y un molde
  conocido por idea. `ideas_desde_json()` (el panel reintenta una idea que ya mostró) acepta payloads antiguos:
  si no hay `ganchos`, sintetiza `[GanchoIdea(texto=gancho, estilo="curiosidad")]` y no exige molde. Así un
  lote guardado o una versión anterior del panel no se rompen.
- Validación de lo nuevo: entre 3 y 5 ganchos, textos distintos tras normalizar (sin tildes, minúsculas,
  espacios colapsados), al menos 2 estilos distintos, y los 3 moldes de una propuesta son distintos. Si una idea
  no cumple, se descarta en `_limpiar()`; si quedan menos de 3 ideas aprovechables, se levanta el mismo error
  amable de hoy («Gemini devolvió N ideas aprovechables…»).
- `_limpiar()` deja `gancho = ganchos[0].texto`, para que la tarjeta y `--gancho` sigan funcionando sin cambios.

### 2.3 `Guion` (se amplía)

- `molde: str | None = None` (se valida contra el catálogo solo si viene).
- `gancho_variantes: list[Gancho] = []`: **las alternativas, sin repetir el gancho elegido**. Máximo 5. Al
  cambiar de gancho con `--elegir`, el que salía entra a la lista y el elegido sale de ella, así nunca se pierde
  ninguno y no hay dos copias del mismo texto.
- `problemas_de_molde(guion)` devuelve mensajes en español claro y se suma a `problemas_de_formato()` en
  `redactor.redactar()`. No es un error fatal: entra al ciclo de corrección con Gemini y, si no se arregla,
  queda como «Por revisar» en el guion, igual que las otras observaciones. Un video con avisos sale igual.
- `a_yaml()` escribe `molde:` junto a `materia:`/`nivel:` y `gancho_variantes:` inmediatamente después de
  `gancho:`, solo si existen. `cargar_guion()` los lee sin cambios adicionales (Pydantic los recibe).
- Los guiones sin molde ni variantes se escriben y se leen byte a byte como hoy.

## 3 · IA: prompts y redacción

### 3.1 `plantillas/ia/ideas.md`

Se mantiene todo lo de ángulos y dificultad, y se agrega:

- La tabla de moldes con sus beats y una frase de ejemplo por molde.
- **Las 3 ideas usan moldes distintos** y, si el tema no da para un molde, no se fuerza: se elige otro del
  catálogo. `reto` siempre está disponible.
- **3 a 5 ganchos por idea**, cada uno con `texto`, `estilo`, `emoji` y, si aporta, `tex` y `voz`.
  - Estilos: `dolor` (lo que le cuesta al estudiante), `curiosidad` (brecha de información),
    `error` (la equivocación que casi todos cometen), `reto` (desafío con respuesta para comentar) y
    `dato` (un número que contradice la intuición).
  - Máximo 10 palabras, con el número clave en cifras si lo hay. Nunca revelan ni insinúan la respuesta.
    Nada de «Hola», «En este video» ni «Hoy veremos».
  - Al menos 2 estilos distintos por idea y ningún par de ganchos que diga lo mismo con otras palabras.
- El campo `gancho` de la idea se mantiene como el recomendado: el primero de la lista, el que la tarjeta
  muestra grande.
- `porque` nombra el imán del molde y del gancho recomendado.

### 3.2 `plantillas/ia/sistema.md`

- Nueva pista **MOLDE**: el guion debe respetar los beats y la regla del molde (por ejemplo, tres pasos
  `error: true` en `tres_errores`; bloque `reto:` en `reto`).
- Nueva pista **GANCHO ELEGIDO**: el texto, emoji y fórmula del gancho llegan fijos y se usan tal cual; la voz
  puede ajustarse para que suene natural.
- El modelo **no genera** `gancho_variantes`: las variantes las produce `ideas.py` y las escribe el motor.

### 3.3 `redactor.redactar()`

Firma nueva (todo opcional): `molde: str | None = None`, `gancho_variante: dict | None = None`,
`gancho_variantes: list[dict] | None = None`.

- `molde` y el gancho elegido entran a `pistas`.
- Después de `a_guion(respuesta)`, se **sobrescriben** `datos["gancho"]["texto"]`, `emoji` y `tex` con los de la
  variante elegida (la pista sola no basta: el modelo a veces reescribe el gancho). La `voz` solo se sobrescribe
  si la variante trae una; si no, se respeta la que escribió el modelo para el gancho elegido.
- `datos["molde"] = molde` y `datos["gancho_variantes"] = alternativas` (sin el elegido) se agregan antes de
  validar y escribir el YAML.
- El revisor de matemática no cambia: sigue revisando cálculos, no retención.

### 3.4 `ideas.producir()` y `lote`

- `producir(..., molde=None, gancho_variante=None, gancho_variantes=None)` pasa todo a `redactar()`.
- `lote._una_idea()` pasa `idea.molde`, el gancho recomendado como variante elegida y `idea.ganchos` completos.
- `ItemLote.como_dict()` agrega `"molde"`, para que la tabla de la Fábrica y la Terminal lo muestren.

## 4 · Los clips de gancho

### 4.1 Guion de vista previa

`ganchos.guion_de_vista_previa(idea, variante)` arma un `Guion` mínimo y válido con el título, materia, nivel y
el gancho de la variante; el enunciado es el de la idea y los pasos/resultado son marcadores que **no se
dibujan**. La escena corta solo ejecuta cabecera + gancho, así que no hay riesgo de mostrar el marcador.

### 4.2 Escena y render

- `OpcionesEscena` gana `solo_gancho: bool = False`. En `VideoEjercicio.construct()`, si es `True`: dibuja la
  cabecera, ejecuta `_gancho()` y espera 0,4 s. No toca el resto del flujo.
- `render.crear_clip_gancho(guion, calidad="borrador", voz=..., salida=...)` reutiliza la configuración de
  `renderizar_manim()` (540×960, 15 fps de borrador, misma hoja, fuentes y plantilla LaTeX), sin subtítulos, sin
  recodificación final. Devuelve la ruta del mp4.
- Voz: por defecto la de `marca.yaml` (o la de la idea, si trae). Con `--sin-voz` se usa `silencio` y la escena
  espera **3,2 s fijos** además de las animaciones, para que el clip no dure medio segundo. El clip con voz dura
  lo que dura la voz más 0,4 s; se mide con `ffprobe` para el manifiesto.
- Salida: `salida/ganchos/<slug-del-titulo-de-la-idea>/gancho-1.mp4 … gancho-5.mp4` y `clips.json` con
  `{texto, estilo, emoji, archivo, segundos}` por variante. Si dos ideas del mismo tema producen el mismo slug,
  se agrega `-2`, `-3` para no pisarse. `salida/` ya está ignorado por Git y el panel ya sirve esa carpeta.
- Costo: cada clip es una escena de 4–6 s en borrador; se estiman 10–20 s de render más la voz por variante.
  Cuatro variantes quedan en uno o dos minutos en el Mac, sin contar la primera compilación de LaTeX.

### 4.3 Cambiar el gancho de un guion ya escrito

- `tpi ganchos GUION.yaml` arma la lista `[gancho] + gancho_variantes`, renderiza los clips y muestra la tabla
  numerada. Con `--elegir N` **no renderiza**: pone la variante N como `gancho:`, mete el gancho anterior en
  `gancho_variantes:` y avisa que el video se recrea con `tpi crear`.
- Si el guion no tiene variantes, el comando funciona con el único gancho y sugiere volver a Crear → Ideas para
  tener alternativas.

## 5 · Panel y Terminal

### 5.1 Crear → Ideas

Cada tarjeta agrega, sin quitar nada de lo que ya muestra:

- Un chip con el **molde** y los 3–5 ganchos en un desplegable «Ver los N ganchos», con su estilo.
- Botón **«Probar ganchos»** (outline, para no competir con el CTA «Hacer este video»): corre
  `tpi ganchos --idea-json …` con `TAREAS` y muestra el avance. Al terminar, una fila de `ui.video` verticales
  con el texto y un botón **«Usar este»**; el elegido actualiza la tarjeta y es el que viaja a `tpi producir`.
- Un solo trabajo a la vez (regla de `TAREAS`): el botón se deshabilita mientras hay otro en curso; Cancelar
  detiene el render y los clips ya escritos quedan en `salida/ganchos/`.
- Los videos se sirven con `url_medio()` desde `salida/`; no se agregan rutas nuevas al servidor.

### 5.2 Fábrica

No gana controles: sigue siendo un campo y un botón. El lote usa un molde distinto por idea y el gancho
recomendado, y la fila de resultado muestra el molde junto a la dificultad. Si el usuario quiere alternativas,
«Crear → Ideas» es el laboratorio (la Fábrica ya enlaza ahí para «Elegirlas una por una»).

### 5.3 Terminal

| Comando | Cambio |
|---|---|
| `./tpi ideas "Tema"` | Muestra molde y gancho recomendado; `--ganchos` lista las 3–5 variantes con su estilo |
| `./tpi ganchos GUION.yaml` | Renderiza los clips de las variantes guardadas; `--sin-voz` para rapidez; `--elegir N` cambia el gancho sin renderizar |
| `./tpi ganchos --idea-json …` | Uso interno del panel: recibe una idea y devuelve el manifiesto de clips |
| `./tpi producir …` | Acepta `--molde`, `--gancho-json` (variante elegida) y `--ganchos-json` (todas); `--gancho` (texto suelto) sigue funcionando; sin los nuevos flags se comporta como hoy |
| `./tpi lote …` | Sin cambios de uso; internamente reparte moldes y guarda variantes |
| `./tpi revisar GUION.yaml` | Informa las reglas del molde que no se cumplen |

`--progreso-json` incluye los moldes, los ganchos y el manifiesto de clips, para que el panel no tenga que
leer archivos por su cuenta.

## 6 · Compatibilidad y lo que no debe cambiar

- Todos los campos nuevos son opcionales. Un guion v0.8 se carga, se revisa y se renderiza igual.
- El camino normal de la escena no cambia: `solo_gancho` es `False` por defecto y `construct()` conserva el
  orden actual. Regla del repo: con `--tema pizarra_nocturna --voz silencio --borrador` los ejemplos antiguos
  salen idénticos cuadro a cuadro a `main`, comparando con `PYTHONHASHSEED=0`.
- No se agregan dependencias: se reutilizan Manim, manim-voiceover, Pydantic, NiceGUI y FFmpeg.
- No se sirven rutas nuevas ni se toca `.env`; la clave de Gemini sigue solo en `.env`/`GEMINI_API_KEY`.
- Los clips y los manifiestos viven en `salida/`, que Git ignora. Nunca se suben videos ni audios.

## 7 · Riesgos y cómo se cubren

- **El modelo ignora el molde.** La pista lo pide, `problemas_de_molde()` lo comprueba y el ciclo de corrección lo
  devuelve a Gemini. Si aun así no lo cumple, el video sale con «Por revisar»: no se bloquea la producción.
- **Los clips suman tiempo.** Se renderizan en borrador, sin subtítulos, y con `--sin-voz` para rapidez; el
  usuario elige cuándo probarlos. La Fábrica no los genera, así que el flujo de un botón sigue corto.
- **Sin métricas, la elección es criterio.** Es una decisión del usuario (no quiere anotar nada). El clip reduce
  la incertidumbre porque muestra la hoja, la letra y el emoji reales, no solo el texto.
- **El catálogo se gasta.** Cinco moldes y 3–5 ganchos por idea dan variedad para semanas; si se repiten, se
  amplía el catálogo en una fase posterior sin cambiar el formato de datos.
- **Solo se prueba completo en Linux/CI.** El panel, la voz real y Finder se verifican en el Mac del usuario y se
  declaran como no probados en este entorno.

## 8 · Pruebas y verificación antes del PR

- **Código:** `ruff` y `python -c "import …"` de todos los módulos y páginas del panel.
- **Gemini falso** (`GOOGLE_GEMINI_BASE_URL`, servidor local que registra peticiones) con una respuesta de 3
  ideas, 3 moldes distintos y 3–5 ganchos: se comprueba que `_limpiar()` conserva las 3, que los moldes son
  distintos y que los ganchos no se repiten. Una variante de 11 palabras o con emoji dentro del texto se
  descarta; si a la idea le quedan menos de 3, se descarta la idea y el error final informa cuántas quedaron.
- **Pistas:** con el servidor falso se verifica que el molde y el gancho elegido llegan en la petición, que el
  gancho del YAML es exactamente el elegido (aunque el modelo devuelva otro) y que `gancho_variantes` queda
  escrito sin duplicar el elegido.
- **Reglas de molde:** un guion de cada molde, válido e inválido; `tpi revisar` nombra la regla incumplida y el
  ciclo de corrección la devuelve a Gemini. Si no se corrige, el video sale con el aviso «Por revisar».
- **Clips:** render real de un clip con `--voz silencio` en GitHub Actions; `ffprobe` comprueba 540×960 y
  duración entre 3 y 6 s; en local se miran cuadros del clip con voz para confirmar hoja, cabecera, letra,
  emoji y fórmula.
- **Render completo:** un ejemplo nuevo con molde (`guiones/ejemplos/moldes_virales.yaml`) se renderiza en CI
  con `--borrador --voz silencio` y se comprueba el mp4 como hoy.
- **Panel:** `./tpi panel --puerto 8766 --no-abrir` y un navegador real: buscar ideas, abrir «Ver los ganchos»,
  «Probar ganchos», ver la fila de clips, «Usar este», crear el video y confirmar que el mp4 y el YAML usan el
  gancho elegido. Cancelar a mitad de un render de clips. Revisar que ninguna ruta fuera de `guiones/`,
  `salida/`, `mis_ajustes/stickers` y `mis_ajustes/fondos` se sirva.
- **Fábrica:** lote de 3 ideas con moldes distintos; cada fila muestra su molde y el YAML guarda las variantes.
- **Regresión de estilo:** comparación de cuadros con `PYTHONHASHSEED=0` contra `main` en el ejemplo de
  `pizarra_nocturna`.
- **No probado en este entorno (Windows):** panel en el Mac del usuario, voz `es-CL` real, `open`/Finder y los
  tiempos de render en su máquina. Se listará explícitamente en el PR, con los pasos para probar en el Mac y
  para actualizar (`git checkout main && git pull origin main`).

## 9 · Documentación y versión

- `README.md`: en la sección de ideas, explicar moldes y «Probar ganchos»; agregar `tpi ganchos` a la tabla de
  comandos.
- `docs/GUIA_GUIONES.md`: documentar `molde:` y `gancho_variantes:` como campos opcionales, con un ejemplo.
- `docs/PLAN.md`: cerrar la fase como **v0.9 · Ganchos y moldes** en la hoja de ruta.
- `pyproject.toml`: versión **0.9.0**.
- `guiones/ejemplos/moldes_virales.yaml`: un ejemplo con molde, variantes y sus fórmulas, para el render de CI.

## 10 · Fuera de alcance

- Métricas automáticas o manuales, APIs de TikTok/Instagram/YouTube, A/B testing con datos y cualquier panel de
  analítica. El usuario eligió no registrar nada; automatizar las APIs es una fase futura y separada.
- Audios en tendencia, música dentro del mp4, publicación o programación automática.
- Series elegidas por comentarios, personaje recurrente y comunidad.
- Estilos visuales nuevos o cambios al estilo «Hoja de desarrollo»/«Pizarra nocturna».
- Selectores nuevos en la Fábrica: sigue siendo un campo y un botón.
