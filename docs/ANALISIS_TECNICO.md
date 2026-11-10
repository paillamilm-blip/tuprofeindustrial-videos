# Motor de video de Tu Profe Industrial — contexto técnico

<!-- sobretitulo: Documento técnico · Sistema 2 -->
<!-- cifras: 48 | guiones YAML en el repo ; 33 | tipos de dibujo animado ; 19 | estilos visuales ; 21 | comandos de terminal ; 885 | pruebas automáticas (3 sistemas) ; 28.773 | líneas de Python en `src/` -->
<!-- pie: Motor de video Tu Profe Industrial · Sistema 2 · Análisis técnico -->

**Para:** lectura por un modelo de lenguaje (Gemini) como documento de contexto. No requiere acceso al código.
**Repositorio:** `tuprofeindustrial-videos`
**Rama:** `main` · commit `7869cd7` (después del PR #37)
**Versión del paquete:** 0.10.1
**Fecha del análisis:** 10 de noviembre de 2026
**Entorno:** macOS Apple Silicon, Python 3.12 (el del usuario). La integración continua (CI) corre en Ubuntu 24.04, macOS y Windows, todos con Python 3.12.

## Cómo usar este documento

- Describe un repositorio completo sin adjuntar el código: todo lo que no esté aquí no se puede deducir de otro lado. Si falta un dato, conviene decirlo en vez de suponerlo.
- Las cifras fueron medidas sobre el repositorio en la fecha indicada (líneas, archivos, pruebas, tiempos). Las versiones de librerías son las declaradas en `pyproject.toml` y fijadas en `uv.lock`.
- Los nombres de archivo son reales y relativos a la raíz del repositorio. Los nombres de función y módulo también.
- No contiene secretos, claves ni credenciales.
- Si se propone un cambio de arquitectura, conviene contrastarlo con la sección 9: hay decisiones que el autor no quiere tocar.

---

## 1. Resumen

El repositorio es **un solo programa Python** que convierte un ejercicio de Matemática, Física o Ingeniería en un video vertical 9:16 para TikTok, Reels y Shorts. Sirve a **dos públicos**: enseñanza media (1° a 4° medio) y universidad de ingeniería (1° a 4° año de Ing. Civil Industrial, Civil Eléctrica y en Obras Civiles). No usa web, base de datos ni servicios propios: todo el estado vive en archivos (`guiones/`, `salida/`, `mis_ajustes/`).

Hay tres entradas y una sola salida:

```text
tema o nivel vacío ──IA (ideas)──┐
enunciado (texto / foto / PDF) ──IA──┐
                                     ├─► guion.yaml (pydantic) ─► QC (aprobar, estilo) ─► cola
guion.yaml escrito a mano ───────────┘                                                   │
                                     escena Manim + voz ◄───────────────────────────────┘
                                        ├─► linea_de_tiempo.json (contrato)
                                        ├─► ASS/SRT ─► FFmpeg ─► mp4 final + portada.jpg
                                        └─► kit de publicación (metadatos del guion o IA)
```

| Dimensión | Estado |
|---|---|
| Lenguaje | Python 3.12 (`.python-version`); CI también en 3.12 |
| Tamaño | 28.773 líneas en `src/` (20.809 en el motor y 7.964 en el panel) + 11.059 en `pruebas/` |
| Pruebas | 83 archivos, 885 pruebas con `unittest` (~45 s en CI); el CI además renderiza un video real |
| Interfaces | CLI `./tpi` (21 comandos) + panel local NiceGUI en `127.0.0.1:8765` (3 pestañas) |
| Salida | MP4 1080×1920 (o 540×960 en borrador), SRT, ASS, `portada.jpg`, portada del kit, miniatura y textos de publicación |
| Contenido | 48 guiones YAML (40 propios + 8 ejemplos), 33 tipos de dibujo animado, 19 estilos visuales, 8 niveles en 2 públicos |

**Lectura rápida:** el diseño está sano y bien separado. Desde el análisis del 9 de noviembre se resolvieron el lockfile, las dependencias escondidas, los globales de estilo, el layout fijo en código, la falta de paralelismo y el caché sin poda. Lo que queda es el entorno Mac atado a mano, el CI que no prueba la voz de Microsoft ni el Gemini real, y el panel que repite banderas de la CLI.

---

## 2. Tecnologías, lenguajes y librerías

### 2.1 Base y empaquetado

| Pieza | Versión | Para qué | Definido en |
|---|---|---|---|
| Python | ≥3.11 (se usa 3.12) | lenguaje único del motor | `pyproject.toml`, `.python-version` |
| setuptools | ≥69 | build backend, paquete en `src/` | `pyproject.toml` |
| uv + `uv.lock` | — | versiones exactas; el CI comprueba que el lock siga al día | `uv.lock`, `.github/workflows/render.yml` |
| Entrada CLI | — | `tpi = tpi_videos.cli:main` | `pyproject.toml` |
| Lanzador | bash | añade LaTeX y `ffmpeg-full` al PATH, fija `TPI_RAIZ` | `tpi` |
| Ruff | line-length 110 | lint (E, F, I, B, UP) y formato | `pyproject.toml` |

### 2.2 Librerías por rol

| Rol | Librería | Versión | Dónde se usa |
|---|---|---|---|
| Animación | Manim | `>=0.22,<0.23` | `escena.py`, `dibujos.py`, `dibujos_3d.py` |
| Voz sincronizada | manim-voiceover `[gtts]` | 0.4.x | `escena.py` (hablar por bloque), `voces.py` |
| Voz neural | edge-tts | `>=7.3.1,<8` | `voces.EdgeTTSService` (envuelto por `ServicioConPausas`) |
| IA | google-genai | `>=2.30.1,<3` | `ia.py`, `redactor.py`, `ideas.py`, `publicar.py` |
| Panel | NiceGUI | `>=3.18,<4` | `panel/` |
| Modelos de datos | pydantic | `>=2.10,<3` | `guion.py`, `config.py`, `temas.py`, `publicar.py` |
| Configuración | PyYAML + python-dotenv | ≥6.0 / ≥1.0 | `guion.py`, `config.py`, `malla.py`, `ia.py` |
| Consola | Rich | ≥13 | `cli.py` |
| Matemática | SciPy, numpy | ≥1.13 / ≥1.26 (declaradas) | `simulacion.py` (oscilador, péndulo doble, calor, flujo) |
| Matemática simbólica | SymPy | 1.12–1.x | `visuales.py` (raíces, vértice, tangente, área) |
| Video | PyAV (`av`) | ≥11 (declarada) | `postproduccion.duracion()`, `extraer_cuadro()` (portadas) |
| Imágenes | Pillow | `<13` (pin forzado) | PNG del caché 3D, portadas; Manim 0.22 choca con Pillow 13 |
| Audio | pydub | transitiva (manim-voiceover) | `voces.ServicioConPausas` (une trozos con silencio) |
| Transcripción (opcional) | openai-whisper | — | `whisper_sync.py`; arrastra PyTorch (~1 GB) |

### 2.3 Requisitos del sistema (fuera de pip)

| Requisito | Para qué | Quién lo instala o detecta |
|---|---|---|
| `ffmpeg-full` con libass | quemar subtítulos y normalizar volumen | `scripts/instalar_mac.sh`, `entorno.ffmpeg_con_libass()` |
| BasicTeX + `standalone`, `preview`, `dvisvgm` | fórmulas LaTeX de Manim | instalador + `doctor._probar_latex()`; `entorno.latex_disponible()` |
| `cairo`, `pango`, `pkg-config` | dibujo vectorial de Manim | `brew` en el instalador |
| `sox` | utilidades de audio de manim-voiceover | `brew` en el instalador |
| `uv` | crear el entorno virtual e instalar desde el lock | `brew` en el instalador |
| 13 fuentes TTF | títulos, cuerpo y subtítulos (Bangers, Comic Neue, Montserrat…) | `assets/fuentes/`, registradas por `tipografia.py` |
| 62 emojis 3D | stickers de la escena | `assets/emojis/` |
| macOS `osascript` / `xattr` | ícono del panel en el Escritorio | `icono.py` |

---

## 3. APIs externas

| API | Uso concreto | Archivo | Riesgo |
|---|---|---|---|
| Gemini (Google AI Studio) | ideas, redactar guion, segunda revisión, completar niveles, textos de publicación | `ia.py`, `redactor.py`, `ideas.py`, `completar.py`, `publicar.py` | MEDIO: los nombres de modelo rotan; hay cadena de respaldo y reintentos ante 429/5xx. En CI se usa un Gemini falso (`scripts/gemini_falso.py`, `pruebas/ia_falsa.py`) |
| edge-tts (Read Aloud de Edge) | voz `es-CL-LorenzoNeural` / `es-CL-CatalinaNeural` con marcas por palabra | `voces.py` | ALTO: cliente no oficial; si Microsoft cambia el endpoint, la voz se cae (respaldo: `gtts` o `silencio`) |
| HTTP local NiceGUI | panel, estáticos de fuentes/emojis/marca, medios de `salida/` | `panel/app.py` | BAJO: solo escucha en `127.0.0.1` |
| FFmpeg (CLI) | quemar ASS, `loudnorm` a −14 LUFS, H.264/AAC, faststart | `postproduccion.py` | MEDIO: exige una build con libass |
| LaTeX + dvisvgm (CLI) | compilar cada fórmula de la escena | `tex.py`, `entorno.py` | MEDIO: la ruta de MacTeX/BasicTeX se inyecta a mano |
| Whisper (local, opcional) | tiempos de subtítulos cuando la voz no trae marcas | `whisper_sync.py` | BAJO: pesa ~1 GB y se carga solo si hace falta |

El modelo de IA por defecto se define en la constante `ia.MODELO_POR_DEFECTO`; no conviene fijarlo en la documentación porque cambia con frecuencia.

---

## 4. Arquitectura interna

Ocho capas, cada una con un contrato claro hacia la siguiente. La UI nunca importa el render: lo lanza como subproceso.

| Capa | Módulos (líneas aproximadas) | Responsabilidad |
|---|---|---|
| Entrada y dominio | `guion.py` (1.771), `ideas.py` (489), `formatos.py`, `moldes.py`, `rodaje.py`, `revision.py` (463), `niveles.py`, `malla.py` | esquema pydantic del guion, normalización, reglas de formato, recetas de rodaje, validación, piso de lectura (2,5 s), los dos públicos y su malla |
| IA | `ia.py`, `redactor.py` (1.628), `completar.py`, `plantillas/ia/*.md` | prompt de sistema, JSON estructurado, hasta 2 rondas de corrección, comprobación de LaTeX, pista de la malla en niveles universitarios |
| Dibujo y análisis | `visuales.py` (1.991), `dibujos.py` (3.157), `dibujos_3d.py` (1.140), `simulacion.py` (396), `componentes.py` (845) | modelos por tipo de visual, 33 dibujos Manim, 3D en órbita con despiece y caché PNG, simulaciones con SciPy, primitivas de texto y cajas |
| Escena | `escena.py` (1.694), `voces.py`, `pausas.py`, `subtitulos.py`, `temas.py` (372), `tipografia.py` | línea de tiempo, cámara, voz por bloque con pausas, ASS/SRT, la regla del estilo sugerido |
| Render y salida | `render.py` (351), `postproduccion.py`, `publicar.py`, `vista_previa.py`, `ganchos.py`, `icono.py` | Manim a mp4, `portada.jpg`, quema de subtítulos, kit de publicación, laboratorio de ganchos, 3 cuadros por estilo |
| Lote y estado | `lote.py` (636), `cola.py` (534), `mantenimiento.py` | producción en serie o en paralelo (`--workers`), reintentos con espera creciente, cola JSON con candado `O_EXCL` e hitos, poda del caché |
| Supervisión | `panel/qc.py` (284), `panel/para_hoy.py` (197), `panel/supervision.py` | aprobaciones con huella del archivo (`salida/.cola/qc.json`), estilo de cada guion, «Para hoy», columnas de la cola |
| UI local | `panel/paginas/tablero.py` (1.283), `crear.py`, `un_video.py`, `estilos.py`, `ajustes.py`, `videos.py`, `tareas.py` | lanza `python -m tpi_videos … --progreso-json` y lee eventos; un trabajo a la vez |

**Frontera clave:** el panel no calcula nada del video. Construye argumentos de CLI, abre un subproceso y refleja el avance que llega por líneas JSON. Las decisiones que sí toma el panel (aprobar, elegir el estilo) escriben archivos que la CLI lee: `salida/.cola/qc.json` y la línea `tema:` del guion.

**Una sola regla del estilo:** `temas.sugerir_tema` decide el estilo de un video que nadie eligió (1° molde, 2° dibujos —circuito → Plano azul, piezas industriales → Plano nocturno—, 3° si corrige un error → Cuaderno con sello, 4° materia, 5° `marca.yaml`). `resolver_tema` aplica la cascada `--tema` > `tema:` del guion > sugerido. En el panel se elige en un solo lugar, la ficha del guion en QC (`qc.cambiar_estilo` → `guion.fijar_tema`).

---

## 5. Pipeline paso a paso

### 5.1 Un video desde un guion ya escrito

1. `tpi crear guion.yaml` carga y valida el guion: materia, categoría, molde, nivel, carrera, velocidad y visuales se normalizan (`guion.cargar_guion`).
2. Se resuelve el estilo (`temas.resolver_tema`) y la voz (bandera > guion > `marca.yaml`).
3. Manim arranca con `tempconfig`: 540×960 a 15 fps en borrador, 1080×1920 a 30 fps en final, siempre con `disable_caching=True` porque manim-voiceover lo exige.
4. `VideoEjercicio.construct` arma la escena en orden fijo: fondo → gancho → enunciado → datos → pasos → resultado → verificación → reto → cierre.
5. Cada bloque abre `hablar(texto)`: TTS con caché en `manim/voiceovers/`; las pausas `<break>` se resuelven con silencio real (`ServicioConPausas`); palabras y tiempos van al manifiesto, con el piso de lectura de 2,5 s para cada fórmula.
6. Manim deja el **mp4 intermedio** y se escribe `linea_de_tiempo.json` (bloques, palabras, silencio de lectura, `tema_clave`).
7. Subtítulos: la fuente de tiempos por bloque es **marcas exactas de edge → Whisper → estimado**; salen `.ass` y `.srt`.
8. FFmpeg quema el ASS, normaliza a −14 LUFS, codifica H.264 CRF 18 y deja `+faststart`.
9. Se extrae **`portada.jpg`** del video sin subtítulos, al final del gancho, acotado entre los segundos 2 y 4.
10. Con `tpi publicar` (o en el lote) se arma el kit: si el guion trae `metadatos:` se usan tal cual; si no, Gemini o plantilla.

Medida real en CI (Ubuntu): un borrador de 56 s con voz edge-tts tardó 1 min 9 s de proceso.

### 5.2 Un video desde un enunciado o un tema (con IA)

```text
tpi redactar / tpi producir / panel «Crear a mano»
enunciado ──► Gemini (GuionIA) ──► limpieza (emoji, LaTeX, visuales, pausas)
          ──► Guion válido ──► revisión IA + reglas
          ──► hasta 2 rondas de corrección ──► guion.yaml (con metadatos)
tpi completar-niveles / «Pedírselo a la IA»
hueco nivel × materia ──► ramo de la malla (+ carrera) ──► 3 ideas ──► redactar la primera ──► guion.yaml
```

En niveles universitarios, `redactar` agrega la pista «PÚBLICO UNIVERSITARIO» con los ramos de ese año, materia y carrera, para que el ejercicio no sea de media.

### 5.3 Supervisión, cola y panel

- **«Para hoy»** (`panel/para_hoy.py`): agrupa los guiones por revisar por nivel y materia y propone uno por materia del mismo nivel. Ordena por: no repetir carrera ni molde del último video, traer metadatos, tener vista previa al día y antigüedad.
- **QC** (`panel/qc.py`): aprobar llama a `cli.encolar_guion` (equivale a `tpi lote <guion> --solo-encolar`) y guarda la decisión con la huella del archivo; editar el guion lo devuelve a «por revisar», cambiar el estilo no.
- **Lote:** `producir_lote` produce de a uno (o `--workers N` a la vez), reintenta si el error es transitorio y guarda hitos en `salida/.cola/trabajos.json` para reanudar sin repetir lo hecho.
- **Panel:** `TAREAS.lanzar` abre un subproceso con `--progreso-json`, parsea cada línea y actualiza la pantalla; un trabajo a la vez. Vista Previa Rápida es `tpi crear <guion> --borrador` dentro de la tarjeta.
- **Laboratorio de ganchos:** renderiza solo cabecera + gancho (3–6 s), con su dibujo, para elegir el primer segundo.

### 5.4 Dentro de la escena

| Bloque | Qué aporta | Cámara / dibujo |
|---|---|---|
| Gancho | pregunta grande, destacados por voz, emoji, fórmula o dibujo | plano entero; si hay visual, la banda baja hasta el subtítulo |
| Enunciado | título y datos del problema | sin dibujo |
| Pasos | pila o ancla de fórmulas, error típico tachado, halo, cambio resaltado, nota y emoji | golpes de cámara según `camara:`; visual del paso en la banda (tangente, área, 3D en órbita, simulaciones) |
| Resultado | fórmula final con su caja, «explica» y destello opcional | primer plano controlado |
| Verificación / reto / cierre | comprobación, desafío al espectador y marca | limpieza de tablero |

Las zonas del encuadre (`y_cabecera`, `y_zona_enunciado`, `y_zona_pasos`, `banda_subtitulo`, `aire_dibujo`) se pueden fijar en el `layout` del YAML del tema; si faltan, valen los de `componentes._ZONAS` (banda de subtítulo y aire del dibujo 0,28). El dibujo nunca debe invadir la banda de subtítulos.

---

## 6. Contratos de datos

Lo que no se puede romper sin migrar los archivos existentes.

| Archivo o carpeta | Formato | Quién lo lee |
|---|---|---|
| `guiones/*.yaml` | `Guion` pydantic: gancho, enunciado, datos, pasos, resultado, verificación, reto, cierre; opcionales `molde`, `tema`, `camara`, `carrera`, `categoria` (calza con la materia), `gancho_variantes`, `metadatos` | CLI, redactor, panel |
| `marca.yaml` + `mis_ajustes/marca.yaml` | `Marca`, fusión profunda (lo de `mis_ajustes` gana); incluye `publico` (materia, nivel, dificultad) | todo el motor |
| `plantillas/temas/*.yaml` + `mis_ajustes/temas/` | `Tema`: colores, tipografía, `marco`, `layout`, hoja, subtítulos, resplandor | escena, postproducción, panel |
| `plantillas/malla.yaml` + `mis_ajustes/malla.yaml` | nivel → materia → ramos (Ingeniería por carrera desde 3° año) | redactor, completar |
| `salida/<slug>/linea_de_tiempo.json` | bloques con tiempos y palabras, `silencio_de_lectura`, guion, `tema_clave`, materia, molde, intermedio | subtítulos, panel, kit |
| `salida/<slug>/` | mp4, srt, ass, `manim/`, `portada.jpg`, `portada.png` (kit), `miniatura.jpg` (panel), `publicacion.json/md` | publicación, panel |
| `salida/_3d/<figura>_<hash>.png` + `.json` | caché 3D; el hash incluye vista, ángulos, colores, papel, resolución y aspecto | dibujos 3D, `tpi podar` |
| `salida/.cola/trabajos.json` | `version: 1`, lotes, videos, hitos y candado `lote.lock` (`O_EXCL`) | lote, panel |
| `salida/.cola/qc.json` | decisión por guion (estado, huella, fecha, `cola_id` o nota) | panel (QC, «Para hoy») |
| `.env` | `GEMINI_API_KEY`, permisos 600 | `ia.py` |

---

## 7. Dependencias críticas y acoplamientos manuales

### 7.1 Lo que ya se resolvió (desde el 9-11-2026)

| Punto | Cómo quedó |
|---|---|
| Sin lockfile | `uv.lock` en el repo; el CI corta si `pyproject.toml` cambia sin regenerarlo |
| `av` y `numpy` no declarados | declarados en `pyproject.toml` |
| Estado global de estilo | `componentes.usar_estilo` usa una variable de contexto (`ContextVar`) con su `restablecer_estilo` |
| Zonas del layout en Python | el tema puede fijarlas en su `layout`; `_ZONAS` queda como valor por defecto |
| Gancho de laboratorio sin dibujo | `ganchos.py` conserva el `visual` de cada variante |
| Cola sin versión y candado frágil | `version: 1` y candado exclusivo con `O_EXCL` que se renueva al guardar |
| Caché 3D sin poda | `tpi podar` limpia `salida/_3d` por antigüedad y cuota, y los audios de voz sin uso |
| CI distinto de la Mac (versión) | CI en Python 3.12, en Ubuntu, macOS y Windows |
| Estilo elegido en siete lugares | una regla (`sugerir_tema`) y un lugar (QC) |

### 7.2 Lo que sigue pendiente

| Punto | Evidencia | Por qué duele | Severidad |
|---|---|---|---|
| Entorno Mac específico | `tpi` inyecta `/Library/TeX/texbin` y `ffmpeg-full` al PATH; fija `TPI_RAIZ` | si cambia Homebrew (Intel/ARM) o BasicTeX, nada arranca; los caminos están en dos lugares (lanzador y `doctor`) | ALTO |
| CI no prueba lo de Microsoft ni de Google | el render del CI usa `--voz silencio`; la IA es un Gemini falso; macOS y Windows corren sin TeX (11 pruebas se saltan) | el verde no garantiza la voz edge-tts ni la calidad de Gemini en la Mac | ALTO |
| Panel duplica la CLI | las páginas arman argumentos a mano; protocolo `--progreso-json` y tabla `ETAPAS` | agregar una bandera obliga a tocar CLI, panel y sugerencia | MEDIO |
| Cola en JSON reescrita entera | `cola.py` reescribe el archivo completo al guardar (escritura atómica) | con muchos lotes el archivo crece; sin índice | BAJO |
| Cancelar en Windows | `panel/tareas.py` usa `os.killpg` | en Windows, cancelar desde el panel fallaría (el motor se usa en Mac) | BAJO |
| La malla es genérica | `plantillas/malla.yaml` es una malla típica chilena | puede no calzar con la universidad del público; se corrige en `mis_ajustes/malla.yaml` | BAJO |

---

## 8. Cuellos de botella

| Cuello | Medida o evidencia | Impacto |
|---|---|---|
| Render Manim por bloque | borrador de 56 s en 1 min 9 s en CI; finales de 32 a 50 s entre 50 y 286 s en la Mac (cola de producción) | es el 80–90 % del tiempo total |
| LaTeX por fórmula | cada `MathTex` compila con dvisvgm; el CI reserva 40 min de margen | el primer render en frío es el peor caso |
| Voz por bloque | edge-tts es red; las pausas sintetizan trozos por separado; el caché mitiga | sin internet no hay voz (queda `silencio`) |
| Doble codificación | Manim escribe el intermedio y FFmpeg recodifica a CRF 18 + `loudnorm` | ~2× tiempo de encode; `loudnorm` va en una sola pasada |
| Un trabajo a la vez en el panel | `TAREAS` corre un subproceso por vez (el lote puede usar `--workers`) | mientras se renderiza, Vista Previa y «Pedírselo a la IA» esperan |
| Completar niveles | cada guion nuevo son 2 a 6 consultas a Gemini; la cuenta gratuita tiene límite por minuto y por día | completar los 15 huecos de hoy toma varias pasadas de `--maximo 3` |

---

## 9. Veredicto y orden de modernización

**Veredicto:** el motor está sano y bien separado: dominio → escena → postproducción, con contratos en archivos y 885 pruebas rápidas en tres sistemas. La deuda del 9 de noviembre (lock, dependencias escondidas, globales, layout en código, caché sin poda) está saldada. El riesgo mayor hoy es externo: que edge-tts o los modelos de Gemini cambien sin que el CI lo note, porque el CI no los llama.

Orden propuesto:

1. **Una prueba con servicios reales, a demanda.** Un workflow manual (no en cada PR) que renderice con edge-tts y redacte un guion con Gemini usando un secreto de GitHub. Avisa a tiempo si Microsoft o Google cambian algo.
2. **Un solo lugar para las banderas.** Que el panel arme los argumentos desde la definición de la CLI (o un esquema compartido), para que agregar una opción no obligue a tocar tres archivos.
3. **Entorno sin rutas fijas.** Que `tpi` y `doctor` lean las rutas de LaTeX y FFmpeg de un solo lugar (detectadas una vez y guardadas en `mis_ajustes/`).

**Lo que no se tocaría:**

- La frontera panel ↔ CLI por subproceso: es lo que mantiene el panel simple y reanudable.
- El esquema pydantic del guion: es el contrato con los 48 guiones existentes (todo campo nuevo es opcional).
- La salida en archivos planos: para un solo usuario en una Mac es más robusta que cualquier base de datos.
- La regla única del estilo (`sugerir_tema`) y el selector único en QC.

---

## 10. Anexo: mapa de archivos y verificación

### Archivos que mandan

| Archivo | Qué define |
|---|---|
| `pyproject.toml` / `uv.lock` | dependencias, entrypoint, lint, datos del paquete / versiones exactas |
| `tpi` | PATH de LaTeX y FFmpeg, `TPI_RAIZ` |
| `scripts/instalar_mac.sh` | Homebrew, ffmpeg-full, BasicTeX, uv, venv, Whisper |
| `marca.yaml` / `mis_ajustes/` | identidad visual y sonora, público; lo de `mis_ajustes` gana |
| `src/tpi_videos/plantillas/temas/*.yaml` | 19 estilos |
| `src/tpi_videos/plantillas/malla.yaml` | ramos por nivel, materia y carrera |
| `src/tpi_videos/plantillas/ia/*.md` | instrucciones de la IA (sistema, ideas, revisor, publicar) |
| `src/tpi_videos/temas.py` | estilos y la regla del estilo sugerido |
| `src/tpi_videos/niveles.py` | los dos públicos, los 8 niveles y las 3 carreras |
| `src/tpi_videos/escena.py` | línea de tiempo, cámara, voz, dibujo en escena |
| `src/tpi_videos/render.py` | configuración de Manim, video final y `portada.jpg` |
| `src/tpi_videos/panel/paginas/tablero.py` | las 3 pestañas del panel, «Para hoy», QC |
| `.github/workflows/render.yml` | lock al día, pruebas en 3 sistemas y render real en CI |
| `DESIGN.md` | contrato visual del panel (colores, rejillas, tipografías) |
| `docs/superpowers/` | especificaciones y planes de cada fase |

### Cómo verificar que el análisis sigue vigente

```bash
# entorno completo
./tpi doctor

# pruebas (885, ~45 s)
.venv/bin/python -m unittest discover -s pruebas -t .

# un video de prueba sin internet
./tpi crear guiones/ejemplos/visuales_tres_tipos.yaml --borrador --voz silencio

# qué niveles faltan
./tpi completar-niveles --simular
```

---

Documento generado a partir del código y de los artefactos del repositorio el 10 de noviembre de 2026, rama `main`, commit `7869cd7`.
