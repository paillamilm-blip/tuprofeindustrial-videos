# Motor de video de Tu Profe Industrial — contexto técnico

**Para:** lectura por un modelo de lenguaje (Gemini) como documento de contexto. No requiere acceso al código.
**Repositorio:** `tuprofeindustrial-videos`
**Rama:** `feat/piso-de-lectura` · commit `60024d8`
**Versión:** 0.10.1
**Fecha del análisis:** 9 de noviembre de 2026
**Entorno medido:** macOS Apple Silicon, Python 3.12. La integración continua (CI) corre en Ubuntu con Python 3.11.

## Cómo usar este documento

- Describe un repositorio completo sin adjuntar el código: todo lo que no esté aquí no se puede deducir de otro lado. Si falta un dato, conviene decirlo en vez de suponerlo.
- Las cifras fueron medidas sobre el repositorio en la fecha indicada (líneas, archivos, pruebas, tiempos). Las versiones de librerías son las declaradas en `pyproject.toml`.
- Los nombres de archivo son reales y relativos a la raíz del repositorio. Los nombres de función y módulo también.
- No contiene secretos, claves ni credenciales.
- Si se propone un cambio de arquitectura, conviene contrastarlo con la sección 9: hay tres decisiones que el autor no quiere tocar.

---

## 1. Resumen

El repositorio es **un solo programa Python** que convierte un ejercicio de Matemática, Física o Ingeniería en un video vertical 9:16 para TikTok, Reels y Shorts. No usa web, base de datos ni servicios propios: todo el estado vive en archivos (`guiones/`, `salida/`, `mis_ajustes/`).

Hay dos entradas y una sola salida:

```text
enunciado (texto / foto / PDF) ──IA──┐
                                     ├─► guion.yaml (pydantic) ─► escena Manim + voz ─► mp4 intermedio
guion.yaml escrito a mano ───────────┘                                  │
                                                                        ├─► linea_de_tiempo.json (contrato)
                                                                        ├─► ASS/SRT ─► FFmpeg ─► mp4 final
                                                                        └─► portada + kit de publicación (IA)
```

| Dimensión | Estado |
|---|---|
| Lenguaje | Python 3.12 local (`.python-version`); CI en 3.11 |
| Tamaño | 22.521 líneas en `src/` (16.451 en el paquete base) + 7.508 en `pruebas/` |
| Pruebas | 59 archivos, 664 pruebas con `unittest`, ~24 s; el CI además renderiza un video real |
| Interfaces | CLI `./tpi` (19 comandos) + panel local NiceGUI en `127.0.0.1:8765` |
| Salida | MP4 1080×1920 (o 540×960 en borrador), SRT, ASS, portada PNG, miniatura JPG y textos de publicación |
| Contenido | 46 guiones YAML, 28 tipos de dibujo animado, 19 estilos visuales |

**Lectura rápida:** el diseño está sano y bien separado. Lo que lo frena no es la arquitectura, sino el entorno Mac atado a mano, el render secuencial y la falta de lockfile.

---

## 2. Tecnologías, lenguajes y librerías

### 2.1 Base y empaquetado

| Pieza | Versión | Para qué | Definido en |
|---|---|---|---|
| Python | ≥3.11 (local 3.12) | lenguaje único del motor | `pyproject.toml`, `.python-version` |
| setuptools | ≥69 | build backend, paquete en `src/` | `pyproject.toml` |
| Entrada CLI | — | `tpi = tpi_videos.cli:main` | `pyproject.toml` |
| Lanzador | bash | añade LaTeX y `ffmpeg-full` al PATH, fija `TPI_RAIZ` | `tpi` |
| Ruff | line-length 110 | lint (E, F, I, B, UP) | `pyproject.toml` |

### 2.2 Librerías por rol

| Rol | Librería | Versión | Dónde se usa |
|---|---|---|---|
| Animación | Manim | `>=0.22,<0.23` | `escena.py`, `dibujos.py`, `dibujos_3d.py` |
| Voz sincronizada | manim-voiceover `[gtts]` | 0.4.x | `escena.py` (hablar por bloque), `voces.py` |
| Voz neural | edge-tts | `>=7.3.1,<8` | `voces.EdgeTTSService` |
| IA | google-genai | `>=2.30.1,<3` | `ia.py`, `redactor.py`, `publicar.py` |
| Panel | NiceGUI | `>=3.18,<4` | `panel/` |
| Modelos de datos | pydantic | `>=2.10,<3` | `guion.py`, `config.py`, `temas.py`, `publicar.py` |
| Configuración | PyYAML + python-dotenv | ≥6.0 / ≥1.0 | `guion.py`, `config.py`, `ia.py` |
| Consola | Rich | ≥13 | `cli.py` |
| Matemática | SciPy | ≥1.13 | `simulacion.py` (oscilador, péndulo doble) |
| Matemática simbólica | SymPy | 1.12–1.x | `visuales.py` (raíces, vértice) |
| Imágenes | Pillow | `<13` (pin forzado) | PNG del caché 3D; Manim 0.22 choca con Pillow 13 |
| Transcripción (opcional) | openai-whisper | — | `whisper_sync.py`; arrastra PyTorch (~1 GB) |
| Video (no declarada) | PyAV (`av`) | transitiva | `postproduccion.duracion()`, `postproduccion.resolucion()` |
| Base de Manim (no declaradas) | numpy, matplotlib, cairo, pango | transitivas | render, tipografías, SVG |

### 2.3 Requisitos del sistema (fuera de pip)

| Requisito | Para qué | Quién lo instala o detecta |
|---|---|---|
| `ffmpeg-full` con libass | quemar subtítulos y normalizar volumen | `scripts/instalar_mac.sh`, `entorno.ffmpeg_con_libass()` |
| BasicTeX + `standalone`, `preview`, `dvisvgm` | fórmulas LaTeX de Manim | instalador + `doctor._probar_latex()` |
| `cairo`, `pkg-config` | dibujo vectorial de Manim | `brew` en el instalador |
| `sox` | utilidades de audio de manim-voiceover | `brew` en el instalador |
| `uv` | crear el entorno virtual e instalar el paquete | `brew` en el instalador |
| 13 fuentes TTF | títulos, cuerpo y subtítulos (Bangers, Comic Neue, Montserrat…) | `assets/fuentes/`, registradas por `tipografia.py` |
| 63 emojis 3D | stikers de la escena | `assets/emojis/` |
| macOS `osascript` / `xattr` | ícono del panel en el Escritorio | `icono.py` |

---

## 3. APIs externas

Cinco servicios fuera del repositorio: dos por internet, tres por línea de comandos.

| API | Uso concreto | Archivo | Riesgo |
|---|---|---|---|
| Gemini (Google AI Studio) | redactar guion, segunda revisión, ideas del lote, textos de publicación | `ia.py`, `redactor.py`, `publicar.py`, `ideas.py` | MEDIO: los nombres de modelo rotan; hay cadena de respaldo y reintentos ante 429/5xx |
| edge-tts (Read Aloud de Edge) | voz `es-CL-LorenzoNeural` / `es-CL-CatalinaNeural` con marcas por palabra | `voces.py` | ALTO: cliente no oficial; si Microsoft cambia el endpoint, la voz se cae |
| HTTP local NiceGUI | panel, estáticos de fuentes/emojis/marca, medios de `salida/` | `panel/app.py` | BAJO: solo escucha en `127.0.0.1` |
| FFmpeg (CLI) | quemar ASS, `loudnorm` a −14 LUFS, H.264/AAC, faststart, extraer cuadros | `postproduccion.py` | MEDIO: exige una build con libass |
| LaTeX + dvisvgm (CLI) | compilar cada fórmula de la escena | `tex.py`, `entorno.py` | MEDIO: la ruta de MacTeX/BasicTeX se inyecta a mano |
| Whisper (local, opcional) | tiempos de subtítulos cuando la voz no trae marcas | `whisper_sync.py` | BAJO: pesa ~1 GB y se carga solo si hace falta |

El modelo de IA por defecto se define en la constante `ia.MODELO_POR_DEFECTO`; no conviene fijarlo en la documentación porque cambia con frecuencia.

---

## 4. Arquitectura interna

Siete capas, cada una con un contrato claro hacia la siguiente. La UI nunca importa el motor: lo lanza como subproceso.

| Capa | Módulos (líneas aproximadas) | Responsabilidad |
|---|---|---|
| Entrada y dominio | `guion.py` (1.325), `ideas.py` (488), `formatos.py`, `moldes.py`, `rodaje.py`, `revision.py` (408) | esquema pydantic del guion, normalización, reglas de formato, recetas de rodaje, validación y piso de lectura (2,5 s) |
| IA | `ia.py`, `redactor.py` (1.193), `plantillas/ia/*.md` | prompt de sistema, JSON estructurado, hasta 2 rondas de corrección, comprobación de LaTeX |
| Dibujo y análisis | `visuales.py` (1.634), `dibujos.py` (2.383), `dibujos_3d.py` (521), `simulacion.py`, `componentes.py` (735) | modelos matemáticos por tipo de visual, 28 dibujos Manim, caché PNG para 3D, primitivas de texto y cajas |
| Escena | `escena.py` (1.540), `voces.py`, `subtitulos.py`, `temas.py`, `tipografia.py` | línea de tiempo, cámara, voz por bloque, generación de ASS/SRT |
| Render y salida | `render.py` (301), `postproduccion.py`, `publicar.py`, `vista_previa.py`, `ganchos.py`, `icono.py` | Manim a mp4, quema de subtítulos, kit de publicación, laboratorio de ganchos, 3 cuadros por estilo |
| Lote y estado | `lote.py` (481), `cola.py` (469) | producción en serie, reintentos con espera creciente, cola JSON con candado por PID e hitos reanudables |
| UI local | `panel/`: `app.py`, `tareas.py`, `sugerencia.py`, 7 páginas | lanza `python -m tpi_videos … --progreso-json` y lee eventos; un trabajo a la vez |

**Frontera clave:** el panel no calcula nada del video. Construye argumentos de CLI, abre un subproceso y refleja el avance que llega por líneas JSON. Eso lo hace simple y reanudable, pero obliga a mantener el protocolo de eventos en dos lados.

---

## 5. Pipeline paso a paso

### 5.1 Un video desde un guion ya escrito

1. `tpi crear guion.yaml` carga y valida el guion: materia, molde, velocidad y visuales se normalizan (`guion.cargar_guion`).
2. Se resuelve estilo y voz con precedencia **flag > guion > marca.yaml** (`render.crear_video`).
3. Manim arranca con `tempconfig`: 540×960 a 15 fps en borrador, 1080×1920 a 30 fps en final, siempre con `disable_caching=True` porque manim-voiceover lo exige.
4. `VideoEjercicio.construct` arma la escena en orden fijo: fondo → gancho → enunciado → datos → pasos → resultado → verificación → reto → cierre.
5. Cada bloque abre `hablar(texto)`: TTS con caché en `manim/voiceovers/`, palabras y tiempos al manifiesto, y el piso de lectura de 2,5 s para cada fórmula.
6. Manim deja el **mp4 intermedio** y se escribe `linea_de_tiempo.json` (bloques, palabras, silencio de lectura).
7. Subtítulos: la fuente de tiempos por bloque es **marcas exactas de edge → Whisper → estimado**; se agrupan y salen `.ass` y `.srt`.
8. FFmpeg quema el ASS con `fontsdir` relativo, normaliza a −14 LUFS, codifica H.264 CRF 18 y deja `+faststart`.
9. Se genera portada, miniatura y kit de publicación (plantilla o Gemini). El kit declara contenido generado con IA y voz sintética; no promete servicios ni respuestas que el video no entregue.

### 5.2 Un video desde un enunciado (con IA)

```text
tpi redactar / tpi producir / panel «Crear»
enunciado ──► Gemini (GuionIA) ──► limpieza (emoji, LaTeX, visuales)
          ──► Guion válido ──► revisión IA + reglas
          ──► hasta 2 rondas de corrección ──► guion.yaml
          ──► pipeline 5.1 ──► kit
```

La segunda revisión y las rondas de corrección evitan que un guion con LaTeX roto o con un visual imposible llegue al render.

### 5.3 En serie y desde el panel

- **Lote:** `producir_lote` produce una idea a la vez, reintenta si el error es transitorio (cuota de IA) y guarda hitos en `salida/.cola/trabajos.json` para reanudar sin repetir lo hecho.
- **Panel:** `TAREAS.lanzar` abre un subproceso con `--progreso-json`, parsea cada línea y actualiza la tarjeta; si se cierra la pestaña el video sigue; al abrir el panel se retoma la cola pendiente.
- **Laboratorio de ganchos:** renderiza solo cabecera + gancho (3–6 s) para elegir el primer segundo antes del video completo. Hoy no incluye el dibujo del gancho: la variante se arma sin `visual`.

### 5.4 Dentro de la escena

| Bloque | Qué aporta | Cámara / dibujo |
|---|---|---|
| Gancho | pregunta grande, destacados por voz, emoji o fórmula | plano entero; si hay visual, la banda baja hasta el subtítulo |
| Enunciado | título y datos del problema | sin dibujo |
| Pasos | pila o ancla de fórmulas, error típico tachado, nota y emoji | golpes de cámara; visual del paso en la banda |
| Resultado | fórmula final con su caja y «explica» | primer plano controlado |
| Verificación / reto / cierre | comprobación, desafío al espectador y marca | limpieza de tablero |

Constantes de encuadre relevantes: `BANDA_SUBTITULO = 0.28`, `AIRE_DIBUJO = 0.28`, escala base 0.97 en estilo suave. El dibujo nunca debe invadir la banda de subtítulos.

---

## 6. Contratos de datos

Lo que no se puede romper sin migrar los archivos existentes.

| Archivo o carpeta | Formato | Quién lo lee |
|---|---|---|
| `guiones/*.yaml` | `Guion` pydantic: gancho, enunciado, datos, pasos, resultado, verificación, reto, cierre | CLI, redactor, panel |
| `marca.yaml` + `mis_ajustes/marca.yaml` | `Marca`, fusión profunda (lo de `mis_ajustes` gana) | todo el motor |
| `plantillas/temas/*.yaml` + `mis_ajustes/temas/` | `Tema`: colores, tipografía, `marco`, hoja, subtítulos, resplandor | escena, postproducción, panel |
| `salida/<slug>/linea_de_tiempo.json` | bloques con tiempos y palabras, `silencio_de_lectura`, guion, tema, intermedio | subtítulos, panel, kit |
| `salida/_3d/<figura>_<hash>.png` + `.json` | caché 3D; el hash incluye vista, ángulos, colores, papel, resolución y aspecto | dibujos 3D |
| `salida/.cola/trabajos.json` | lotes, videos, hitos y candado con PID | lote, panel |
| `salida/<slug>/` | mp4, srt, ass, `manim/`, `portada.png`, `miniatura.jpg`, `publicacion.json/md` | publicación, panel |
| `.env` | `GEMINI_API_KEY`, permisos 600 | `ia.py` |

---

## 7. Dependencias críticas y acoplamientos manuales

Lo que hoy exige memoria humana, rutas fijas o edición de código para un cambio que debería ser configuración.

| Punto | Evidencia | Por qué duele | Severidad |
|---|---|---|---|
| Entorno Mac específico | `tpi` inyecta `/Library/TeX/texbin` y `ffmpeg-full` al PATH; fija `TPI_RAIZ` | si cambia Homebrew (Intel/ARM) o BasicTeX, nada arranca; los caminos están en dos lugares (lanzador y `doctor`) | ALTO |
| Sin lockfile | el instalador usa `uv pip install -e .` | dos Macs pueden resolver Manim/Pillow distinto; el pin de Pillow `<13` ya es un parche por incompatibilidad | ALTO |
| Dependencia transitiva no declarada | `import av` en `postproduccion.py` | un cambio de Manim puede sacar PyAV y romper la duración sin tocar este repositorio | MEDIO |
| Estado global de estilo | `componentes.usar_estilo` fija tipografía y zonas en globales | dos escenas en el mismo proceso se pisan; las pruebas dependen del orden; no hay tema inyectado | MEDIO |
| Zonas del layout en Python | `_ZONAS` con `Y_CABECERA`, `Y_ZONA_*` y constantes 0,15 / 0,28 | el YAML del tema elige colores y letra, pero no puede mover nada: cada ajuste visual es un cambio de código | MEDIO |
| Panel duplica la CLI | las páginas arman argumentos a mano; protocolo `--progreso-json` y tabla `ETAPAS` | agregar una bandera obliga a tocar CLI, panel y sugerencia | MEDIO |
| Gancho de laboratorio sin dibujo | `ganchos.idea_desde_guion` pierde el campo `visual` | lo que se previsualiza no es exactamente lo que sale | BAJO |
| Cola en JSON con candado PID | `cola.py` reescribe todo el archivo en cada hito | dos procesos pueden pisarse si el candado queda huérfano; no hay versión de esquema | MEDIO |
| CI distinto de la Mac | Ubuntu 3.11, TeX de apt, `--voz silencio` | no prueba edge-tts, ni macOS, ni `ffmpeg-full`: el verde no garantiza la Mac | ALTO |
| `salida/` dentro del repositorio | 269 archivos en `_3d`, renders completos | crece sin poda; ya hubo que retirar 372 MB | MEDIO |

---

## 8. Cuellos de botella

Con medidas reales donde existen; los tiempos salen de la cola de producción del propio repositorio.

| Cuello | Medida o evidencia | Impacto |
|---|---|---|
| Render Manim por bloque | 50 a 286 s de proceso para videos de 32 a 50 s (`salida/.cola/trabajos.json`) | es el 80–90 % del tiempo total |
| LaTeX por fórmula | cada `MathTex` compila con dvisvgm; el CI reserva 40 min de margen | el primer render en frío es el peor caso |
| Voz por bloque | edge-tts es red; reintentos de 1,5 s por intento; el caché mitiga | sin internet no hay voz (queda `silencio`) |
| Doble codificación | Manim escribe CRF 12 y FFmpeg recodifica a CRF 18 + `loudnorm` | ~2× tiempo de encode; `loudnorm` va en una sola pasada |
| Serie, no paralelo | `producir_lote` va de a una idea; el panel permite un solo trabajo | la Mac queda tomada; no se usan los núcleos |
| Caché 3D sin poda | hash largo; los PNG viejos nunca se borran | repos y respaldos engordan |
| Whisper opcional | PyTorch ~1 GB; se carga solo si hace falta | instalación y RAM |

---

## 9. Veredicto y orden de modernización

**Veredicto:** el motor está sano y bien separado para lo que hace: dominio → escena → postproducción, con contratos JSON claros y 664 pruebas rápidas. Lo que lo frena no es el diseño: es el entorno Mac atado a mano, el render secuencial y la falta de lockfile. El riesgo mayor hoy es que una actualización de Manim, Pillow o PyAV rompa sin que el CI lo note, porque el CI no reproduce la Mac.

Orden propuesto:

1. **Lockfile y dependencias honestas.** Fijar versiones exactas, declarar `av` y numpy, subir el CI a Python 3.12. Es barato y elimina la clase de fallo más probable.
2. **Zonas del layout al YAML del tema.** Mover `_ZONAS` y las constantes de posición al archivo del estilo y quitar los globales de `componentes`. Es el acoplamiento que hoy obliga a tocar código para algo visual.
3. **Paralelizar el lote y podar el caché.** Dos o tres workers por proceso con la cola como fuente de verdad, y limpieza por antigüedad en `salida/_3d`. Ataca el 90 % del tiempo y el crecimiento de disco.

**Lo que no se tocaría:**

- La frontera panel ↔ CLI por subproceso: es lo que mantiene el panel simple y reanudable.
- El esquema pydantic del guion: es el contrato con los 46 guiones existentes.
- La salida en archivos planos: para un solo usuario en una Mac es más robusta que cualquier base de datos.

---

## 10. Anexo: mapa de archivos y verificación

### Archivos que mandan

| Archivo | Qué define |
|---|---|
| `pyproject.toml` | dependencias, entrypoint, lint, datos del paquete |
| `tpi` | PATH de LaTeX y FFmpeg, `TPI_RAIZ` |
| `scripts/instalar_mac.sh` | Homebrew, ffmpeg-full, BasicTeX, uv, venv, Whisper |
| `marca.yaml` / `mis_ajustes/` | identidad visual y sonora; lo de `mis_ajustes` gana |
| `src/tpi_videos/plantillas/temas/*.yaml` | 19 estilos (Hoja de desarrollo incluido) |
| `src/tpi_videos/escena.py` | línea de tiempo, cámara, voz, dibujo en escena |
| `src/tpi_videos/render.py` | configuración de Manim y encadenado del video final |
| `.github/workflows/render.yml` | pruebas + render real en CI |
| `DESIGN.md` | contrato visual del panel (colores, rejilla, tipografías) |

### Cómo verificar que el análisis sigue vigente

```bash
# entorno completo
./tpi doctor

# pruebas (664, ~24 s)
.venv/bin/python -m unittest discover -s pruebas -t .

# un video de prueba sin internet
./tpi crear guiones/ejemplos/visuales_tres_tipos.yaml --borrador --voz silencio
```

---

Documento generado a partir del código y de los artefactos del repositorio el 9 de noviembre de 2026, rama `feat/piso-de-lectura`, commit `60024d8`.
