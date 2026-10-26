# Plan del motor de video (Sistema 2)

## Objetivo

Enunciado de Matemática / Física / Ingeniería → video vertical 9:16 de 30–75 s, con animaciones, voz
sintética chilena y subtítulos estilo CapCut, listo para TikTok, Reels y Shorts. Repo **solo Python**,
independiente de la web (Sistema 1).

## Arquitectura (v0.4)

```
tema ("Teorema de Pitágoras") ─► ideas.py (Gemini propone 3 ángulos) ─► el profe elige una ─┐
enunciado (texto, foto o PDF) ─► redactor.py (Gemini escribe → motor valida → Gemini revisa) ─► guion.yaml
guion.yaml ─► guion.py (valida, errores en español) ─► revision.py (duración, gancho, pedagogía)
          ─► temas.py (estilo: --tema > guion > marca.yaml) ─► tipografia.py · emojis.py
          ─► escena.py (Manim) ── voces.py (manim-voiceover: edge-tts / gTTS / silencio)
          │      └─ linea_de_tiempo.json  (inicio, texto exacto y marcas de cada bloque de voz)
          ─► subtitulos.py (tiempos por palabra: voz exacta > Whisper > estimado → archivo ASS)
          ─► postproduccion.py (FFmpeg + libass: quema subtítulos, −14 LUFS, H.264, faststart)
          ─► salida/<guion>/<guion>.mp4 + .srt ─► publicar.py (portada + textos con IA) ─► kit
panel/ (NiceGUI, solo 127.0.0.1) ─► los mismos comandos `tpi … --progreso-json`, uno a la vez, en procesos aparte
```
`ideas.py` + `producir` encadenan todo: de un tema al video final con su kit, sin escribir el enunciado.

| Módulo | Responsabilidad |
|---|---|
| `cli.py` | Comandos `tpi` en español; errores sin trazas técnicas (`--debug` para verlas) |
| `redactor.py` / `ia.py` | `tpi redactar`: Gemini escribe el guion, el motor lo valida y Gemini lo revisa / clave y errores de la API |
| `ideas.py` | `tpi ideas` (3 ángulos distintos para un tema, con el ejercicio ya numerado) y `tpi producir` (guion → video → kit en un solo paso) |
| `cola.py` | Cola persistente (`salida/.cola/trabajos.json`): estado, fase, avance e hitos de cada video, candado de proceso y reanudación |
| `guion.py` | Formato del guion (pydantic) y mensajes claros (incluye la trampa de comillas dobles con LaTeX) |
| `revision.py` | Reglas de guion corto y de pedagogía; estimación de duración calibrada con la voz es-CL |
| `voces.py` | Servicios de voz para manim-voiceover; edge-tts entrega la marca de tiempo de cada palabra |
| `escena.py` | Secciones del video: gancho, enunciado, datos, pizarra de pasos (con «error típico»), resultado, verificación, reto, cierre |
| `componentes.py` | Diseño 9:16: zonas seguras por marco, texto con líneas parejas, fórmulas divididas en partes, fondos, hoja, emojis |
| `temas.py` | Estilos visuales (`plantillas/temas/` y los propios en `mis_ajustes/temas/`): marco, colores, letras, fondo, subtítulos y animación |
| `tipografia.py` / `emojis.py` | Letras incluidas (grosor más cercano, medición igual a lo que se dibuja) / emojis 3D y stickers propios |
| `publicar.py` / `vista_previa.py` | Kit de publicación (portada del gancho + título, descripción y hashtags con Gemini o plantilla) / 3 cuadros de muestra por estilo |
| `panel/` | Panel de control: páginas Crear, Mis videos, Estilos y Ajustes; `tareas.py` ejecuta los comandos `tpi` con progreso en JSON |
| `icono.py` | Ícono del panel en el Escritorio (`.command`) con la imagen de la marca; lo muestra en Finder |
| `tex.py` | Plantilla LaTeX mínima, coma decimal chilena, división de fórmulas para `TransformMatchingTex` |
| `subtitulos.py` / `whisper_sync.py` | Alineación texto-audio y estilo CapCut (ASS) / transcripción con Whisper |
| `postproduccion.py`, `entorno.py`, `doctor.py` | FFmpeg, rutas de Homebrew/LaTeX, diagnóstico |

## Decisiones y por qué

| Decisión | Alternativas consideradas | Por qué |
|---|---|---|
| **Plantillas fijas + guion YAML** | Que una IA escriba código Manim por video | Código generado falla seguido y cada video se ve distinto; con plantillas, el contenido cambia y el diseño queda consistente y probado |
| **Subtítulos ASS quemados con FFmpeg** | Subtítulos dibujados dentro de Manim; Remotion (JS) | Separado de la animación (se pueden reestilizar sin re-renderizar), sirve para cualquier video (`tpi subtitular`) y respeta la regla "solo Python" |
| **Tiempos: voz exacta > Whisper > estimado** | Siempre Whisper | edge-tts entrega el tiempo exacto de cada palabra; Whisper (mediana ±40 ms en pruebas) se usa cuando la voz no lo trae. Siempre se muestra el texto exacto del guion |
| **Voz edge-tts `es-CL` por defecto** | gTTS, Gemini TTS, Azure, ElevenLabs | Gratis, neural y con acento chileno. gTTS queda de respaldo y `silencio` para revisar sin internet |
| **Plantilla LaTeX mínima (amsmath)** | Plantilla por defecto de Manim | La de Manim exige ~20 paquetes; esta funciona con BasicTeX + `standalone preview dvisvgm` |
| **`ffmpeg-full` de Homebrew** | `ffmpeg` normal | Desde 2025 el `ffmpeg` de Homebrew no trae libass (sin él no se pueden quemar subtítulos) |
| **Python 3.12** | 3.11 / 3.13 | PyAV 19 trae binarios desde 3.12; 3.13 obliga a parches de audio (audioop) |
| **La IA entrega datos, no código** (`tpi redactar`) | Que genere código Manim o YAML libre | Responde en un JSON con esquema fijo; el motor lo convierte al formato del guion. Así el resultado siempre se puede validar y renderizar |
| **Validación en capas** | Confiar en una sola respuesta | 1) esquema del guion, 2) LaTeX compilado de verdad, 3) reglas de `tpi revisar`, 4) segunda pasada de Gemini como revisor que rehace los cálculos, 5) hasta 2 rondas de corrección y 6) revisión humana del borrador |
| **Gemini 3.8 Flash** por defecto | Gemini 4 Argon, otros proveedores | Estable y con cuenta gratuita; razonamiento `high` para la matemática. `--modelo` permite usar otro (ej. Argon, de pago) |
| **API `generateContent`** | API Interactions (la nueva de Google) | Documentada para los modelos actuales y estable; migrar es cambiar un solo módulo (`redactor.pedir_json`) |
| **Temas en YAML** con «Hoja de desarrollo» por defecto | Un solo diseño fijo; CSS/HTML | El estilo de Instagram del profe pasa a ser el principal sin perder el original: `pizarra_nocturna` sale idéntico cuadro a cuadro (comparado contra los videos de `main`) |
| **Emojis Noto 3D en PNG** | Emojis 2D, Twemoji, emojis de la letra del sistema | Se ven modernos, tienen licencia libre (OFL) y no dependen de las letras del Mac (Manim no dibuja emojis de color dentro de un texto) |
| **Paso «error típico»** (`error: true`) | Solo pasos correctos | Es el formato de los posts con más alcance del canal («¿Resuelves así?»): mostrar el error y tacharlo engancha y enseña |
| **Ajustes del usuario en `mis_ajustes/`** | Editar `marca.yaml` | Git lo ignora: actualizar el motor nunca choca con lo que personaliza el profe |
| **Panel con NiceGUI**, local | Gradio o Streamlit; app nativa; web en internet | Es Python (regla del repo), se ve como una app y no un formulario, no cuesta ni expone nada: escucha solo en `127.0.0.1` (NiceGUI escucha en toda la red si no se indica) |
| **El panel ejecuta los comandos `tpi`** en procesos aparte (`--progreso-json`) | Llamar al motor dentro del panel | Si un video falla, el panel sigue vivo; cancelar detiene también LaTeX y FFmpeg; lo que hace el panel es exactamente lo que hacen los comandos |
| **Ícono `.command` con imagen propia** (AppleScript-ObjC vía `osascript`, el método de `fileicon`) | Una app `.app` con `osacompile`; instalar `fileicon` | Sin instalar nada (viene con macOS) y conserva la ventana de la Terminal para cerrar el panel. Se revisa que macOS guardó el ícono (setIcon responde «sí» aunque falle); si no, el ícono igual funciona |
| **Bucle `asyncio` estándar** en el panel | uvloop (el que trae uvicorn) | Con uvloop, lanzar un comando mientras otro hilo trabajaba (miniaturas) podía congelar el panel; con el bucle estándar no pasa |

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| edge-tts es un servicio no oficial (puede cambiar o tener límites de uso comercial) | Reintentos + mensajes claros; respaldo `--voz gtts`. **Fase 4:** voz Azure (mismas voces, licencia comercial) |
| Error matemático en un guion | Revisión humana antes de publicar; `./tpi revisar`; el borrador permite ver todo en ~20 s |
| Cambios en Manim / manim-voiceover | Versiones acotadas en `pyproject.toml` (`manim 0.22.x`, `manim-voiceover 0.4.x`) |
| Mac sin Whisper (algunos Intel) | El motor funciona sin Whisper; `doctor` lo informa |
| La IA resuelve mal un ejercicio | Revisor automático independiente + advertencias en el archivo + aviso de revisar siempre el borrador |
| Límites de la cuenta gratuita de Gemini | Reintentos automáticos ante saturación; mensaje claro si se agota la cuota |
| Cambios de modelos de Gemini | Modelo configurable con `--modelo`; errores de "modelo no existe" con la solución |

## Hoja de ruta (cada fase = una rama + un Pull Request)

1. ✅ **v0.1:** motor completo guion → video, 3 ejemplos, instalador para Mac, diagnóstico.
2. ✅ **v0.2 · Redactar guiones desde el enunciado:** `tpi redactar` (texto, foto o PDF) con Gemini, validación
   en capas y `--crear` para obtener el borrador en un solo comando.
3. ✅ **v0.3 · Estilo «Hoja de desarrollo»:** temas, letras Comic Neue + Bangers, emojis 3D, stickers propios,
   paso «error típico» y gancho con fórmula.
4. ✅ **v0.4 · Panel de control local** (NiceGUI, solo en el Mac), kit de publicación (portada + textos con IA)
   y vista previa de estilos.
5. ✅ **v0.5 · De un tema al video completo:** `tpi ideas` (Gemini propone 3 ángulos y el profe elige) y
   `tpi producir` (guion revisado → video final → kit). En el panel: pestaña **Crear → Ideas**.
6. ✅ **v0.6 · Visuales por materia:** `visual:` en un paso — gráfico de función (con raíces y vértice
   marcados por SymPy), diagrama de fuerzas (bloque o bola, con plano inclinado) y circuito serie/paralelo.
   Se trazan en el pie de la hoja, en los dos estilos, los pide la IA y se editan en el panel.
   Ejemplo: `guiones/ejemplos/visuales_tres_tipos.yaml`.
7. ✅ **Producción (decisión cerrada, sin código):** el video se entrega **solo con voz** (volumen ya
   normalizado a -14 LUFS) y **sin música**. La música la pone el profesor desde TikTok o Instagram al subir,
   usando un audio en tendencia, que es lo que empuja el alcance; incrustarla en el mp4 pelearía con ese audio.
   La voz sigue siendo la sintética de `marca.yaml`. Voz Azure solo si algún día hace falta una licencia
   comercial garantizada: es cambiar de proveedor en `voces.py`, no una fase.
8. ✅ **v0.7 · Escala:** `tpi lote "Tema"` y el botón **Crear → Ideas → «Hacer los 3 videos»** producen los
   3 videos (guion + video final + kit) en un solo trabajo, de uno en uno, con reintento y espera si Gemini está
   saturado. Verificación automática de render en GitHub Actions: cada PR renderiza un guion de ejemplo y
   comprueba el mp4, sin claves y sin llamar a la IA.
9. ✅ **v0.8 · Fábrica y dificultad:** la portada del panel es **Fábrica** (`/`): un campo y un botón, sin
   opciones que elegir, con la barra de avance por video y al final la carpeta, el video y el kit a un clic
   («Intentar solo este» si uno falla). Cada idea trae `dificultad` (`facil` / `media` / `dificil`) y la IA las
   reparte distintas en el lote; `--dificultad` las fuerza las 3. «Crear» baja a `/crear`.
   Spec: `docs/superpowers/specs/2026-10-25-fabrica-y-dificultad-design.md`.
10. ✅ **v0.9 · Ganchos y moldes:** cada idea trae un molde narrativo (`mito_realidad`, `tres_errores`,
   `pov`, `reto`, `nadie_te_enseno`) y de 3 a 5 ganchos. `tpi ganchos` renderiza solo cabecera + gancho de
   cada variante (`--elegir N` fija uno) y el panel lo ofrece con **«Probar ganchos»**. Todo campo nuevo es
   opcional: los guiones v0.8 y el estilo original no cambian.
   Spec: `docs/superpowers/specs/2026-10-26-ganchos-y-moldes-virales-design.md`.
11. ✅ **v0.10 · Cola y progreso:** cada video del lote tiene su barra, su fase y su estado en la Fábrica.
    El estado vive en `salida/.cola/trabajos.json` (escritura atómica y candado), los hitos (guion, video,
    kit) evitan repetir trabajo y la IA se espera con 60 s, 2 min, 5 min y luego cada 5 min, sin límite.
    Al reabrir el panel se retoma solo lo pendiente de conexión; un render interrumpido se reanuda con un
    botón. `tpi lote --reanudar` hace lo mismo desde la terminal.
    Spec: `docs/superpowers/specs/2026-10-26-cola-y-progreso-design.md`.
