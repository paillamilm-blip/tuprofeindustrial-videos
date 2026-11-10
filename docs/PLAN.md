# Plan del motor de video (Sistema 2)

## Objetivo

Enunciado de Matemática / Física / Ingeniería → video vertical 9:16 de 30–75 s, con animaciones, voz
sintética chilena y subtítulos estilo CapCut, listo para TikTok, Reels y Shorts. Repo **solo Python**,
independiente de la web (Sistema 1).

## Arquitectura (actual)

```
tema ("Teorema de Pitágoras") ─► ideas.py (Gemini propone 3 ángulos) ─► el profe elige una ─┐
enunciado (texto, foto o PDF) ─► redactor.py (Gemini escribe → motor valida → Gemini revisa) ─► guion.yaml
   └─ niveles.py + malla.yaml: en la universidad, la pista con los ramos del año y la carrera
guion.yaml ─► guion.py (valida, errores en español) ─► revision.py (duración, gancho, pedagogía, piso de lectura)
          ─► temas.py (estilo: --tema > tema: del guion > sugerir_tema: molde, dibujos, error, materia > marca.yaml)
          ─► escena.py (Manim) ── voces.py + pausas.py (edge-tts / gTTS / silencio, pausas <break> con silencio real)
          │      ├─ visuales.py + dibujos.py + dibujos_3d.py + simulacion.py (33 dibujos, 3D y simulaciones)
          │      └─ linea_de_tiempo.json  (inicio, texto exacto y marcas de cada bloque de voz, tema_clave)
          ─► subtitulos.py (tiempos por palabra: voz exacta > Whisper > estimado → archivo ASS)
          ─► postproduccion.py (FFmpeg + libass: quema subtítulos, −14 LUFS, H.264, faststart)
          ─► salida/<guion>/<guion>.mp4 + .srt + portada.jpg ─► publicar.py (portada + textos) ─► kit
lote.py + cola.py ─► salida/.cola/trabajos.json (estado, fase, hitos, reanudación; --workers N en paralelo)
completar.py ─► huecos de nivel × materia ─► ideas + redactar ─► guiones nuevos para QC
panel/ (NiceGUI, solo 127.0.0.1): Cola de Producción («Para hoy») · Aprobación de Guiones (QC) · Avanzado
   └─ ejecuta los mismos comandos `tpi … --progreso-json`, uno a la vez, en procesos aparte
```
`ideas.py` + `producir` encadenan todo: de un tema al video final con su kit, sin escribir el enunciado.

| Módulo | Responsabilidad |
|---|---|
| `cli.py` | Comandos `tpi` en español (21); errores sin trazas técnicas (`--debug` para verlas) |
| `redactor.py` / `ia.py` | `tpi redactar`: Gemini escribe el guion, el motor lo valida y Gemini lo revisa / clave, modelos de respaldo y errores de la API |
| `ideas.py` | `tpi ideas` (3 ángulos distintos para un tema, con el ejercicio ya numerado) y `tpi producir` (guion → video → kit en un solo paso) |
| `lote.py` / `cola.py` | `tpi lote` (3 videos, también desde guiones con `--solo-encolar`, `--workers`) / cola persistente con escritura atómica, candado `O_EXCL`, hitos y reanudación |
| `completar.py` | `tpi completar-niveles`: encuentra los niveles sin las tres materias y los completa con la IA |
| `niveles.py` / `malla.py` | Los dos públicos (8 niveles y 3 carreras) con lectura tolerante del texto / ramos por nivel, materia y carrera (`plantillas/malla.yaml`) |
| `guion.py` | Formato del guion (pydantic): campos opcionales nuevos (`molde`, `camara`, `carrera`, `metadatos`, `categoria`…), validadores estrictos y `fijar_tema` |
| `revision.py` | Reglas de guion corto y de pedagogía; estimación de duración calibrada con la voz es-CL; piso de lectura de cada fórmula |
| `voces.py` / `pausas.py` | Servicios de voz para manim-voiceover / `<break time="1.5s"/>` convertido en silencio real con cualquier voz |
| `escena.py` | Secciones del video: gancho, enunciado, datos, pizarra de pasos (con «error típico», halo, tachado y destello), resultado, verificación, reto, cierre |
| `visuales.py` / `dibujos.py` / `dibujos_3d.py` / `simulacion.py` | Modelos y validación de los 33 dibujos / su trazado en Manim / piezas 3D con órbita y despiece (caché PNG) / oscilador, péndulo doble, calor y flujo integrados con SciPy |
| `componentes.py` | Diseño 9:16: zonas seguras por marco (del `layout` del tema), texto con líneas parejas, fórmulas divididas en partes, fondos, hoja, emojis |
| `temas.py` | Estilos visuales (`plantillas/temas/` y `mis_ajustes/temas/`) y **la regla del estilo sugerido** (`sugerir_tema`, `resolver_tema`) |
| `formatos.py` / `moldes.py` / `rodaje.py` | Familias de contenido / moldes narrativos / recetas de cámara y animación por molde |
| `ganchos.py` | Laboratorio de ganchos: clips de cabecera + gancho (con su dibujo) para elegir el primer segundo |
| `tipografia.py` / `emojis.py` | Letras incluidas / emojis 3D y stickers propios |
| `render.py` / `postproduccion.py` | Manim → mp4, `portada.jpg` automática / FFmpeg, duración, cuadros |
| `publicar.py` / `vista_previa.py` | Kit de publicación (usa `metadatos:` si el guion los trae) / 3 cuadros de muestra por estilo |
| `mantenimiento.py` | `tpi podar`: limpia el caché 3D y los audios de voz que nadie usa |
| `panel/` | Sala de producción: `paginas/tablero.py` (las 3 pestañas, «Para hoy», QC, Vista Previa Rápida), `qc.py` (aprobaciones y el estilo de cada guion), `para_hoy.py`, `supervision.py`, `tareas.py` (comandos `tpi` con progreso en JSON) y las páginas de Crear a mano, Estilos, Ajustes y Biblioteca |
| `icono.py` | Ícono del panel en el Escritorio (`.command`) con la imagen de la marca |
| `tex.py` | Plantilla LaTeX mínima, coma decimal chilena, división de fórmulas para `TransformMatchingTex` |
| `subtitulos.py` / `whisper_sync.py` | Alineación texto-audio y estilo CapCut (ASS) / transcripción con Whisper |
| `entorno.py`, `doctor.py`, `config.py` | Rutas de Homebrew/LaTeX, diagnóstico, `marca.yaml` + `mis_ajustes/` |

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
| **Estilo sugerido por el motor, elegido en un solo lugar** (QC) | Un selector en cada pantalla; un estilo fijo por materia | Siete selectores sin acuerdo entre sí hacían que el estilo dependiera de por dónde se creaba el video. Una sola regla (`temas.sugerir_tema`: molde → dibujos → error → materia) y un solo lugar para cambiarla, que escribe `tema:` en el guion |
| **Sala de supervisión** (Cola · QC · Avanzado) | Seguir con el panel de creación manual | La IA ya escribe y el motor ya produce: la persona supervisa. Lo manual queda plegado, no se borra |
| **Dos públicos con malla en YAML** | Solo enseñanza media; ramos fijos en el prompt | El canal habla a media y a la universidad (Industrial, Eléctrica, Obras Civiles). La malla es dato: se ajusta a una universidad concreta en `mis_ajustes/malla.yaml` sin tocar código |
| **Lockfile `uv.lock` + CI en tres sistemas** | Resolver dependencias en cada Mac; CI solo Ubuntu | Dos Macs resolvían Manim/Pillow distinto. El CI comprueba el lock, corre la suite en Ubuntu, macOS y Windows y renderiza un video real |
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
12. ✅ **v0.10.1 · Resiliencia de la cola:** el candado (`lote.lock`) es exclusivo de verdad (se crea con
    `O_EXCL`, se renueva al guardar y solo lo libera su propio proceso), así que dos lotes ya no se pisan y un
    candado huérfano se recupera solo. Sacar un video de la cola se bloquea mientras hay un lote trabajando. Una
    cola dañada se aparta y se avisa (en la terminal y en Fábrica) en vez de fallar en silencio, y el aviso del
    kit ya no hace retroceder la barra del video.
    Spec: `docs/superpowers/specs/2026-10-26-cola-y-progreso-design.md`.
13. ✅ **Guiones del profe y «Un video»** (#16–#21): los guiones propios entran al repo; «Un video» es una sola
    pantalla que arma todo (familia, molde, estilo, voz, duración, gancho, rodaje) con su «cambiar»; los seis temas
    llegan a su familia; el panel pasa a 3 vistas; ideas en vivo sin bloqueo.
14. ✅ **Piso de lectura y modernización** (#22, 9-11-2026): ninguna fórmula se va antes de poder leerse (2,5 s).
    Además: `uv.lock`, `av` y `numpy` declarados, estilo por contexto (sin globales), zonas del layout en el YAML
    del tema, `--workers` para producir en paralelo y `tpi podar` para el caché.
15. ✅ **Motor visual vivo** (#25): tangente y área que recorren la curva con su valor en vivo, álgebra con halo y
    tachado, destello del resultado, sólidos 3D en órbita con despiece.
    Specs: `2026-11-09-motor-visual-simulacion-viva-design.md`, `2026-11-10-matematica-viva-design.md`,
    `2026-11-10-3d-cinematico-design.md`.
16. ✅ **Sólidos industriales** (#26): tolva, tubería con bridas y eje escalonado en 3D; calor en una placa; flujo
    entre placas (Poiseuille y Couette).
17. ✅ **La IA usa el motor vivo** (#27): reglas por disciplina y tres ejemplos completos en las instrucciones;
    Gemini de prueba (`scripts/gemini_falso.py`) para verificar sin clave.
18. ✅ **Metadatos, pausas y blindaje** (#28): `metadatos:` para redes en el guion, pausas `<break>` con silencio
    real y validadores estrictos (campos verdadero/falso, movimientos coherentes).
19. ✅ **Sala de supervisión** (#29, #30): Cola de Producción, Aprobación de Guiones (QC) y Avanzado; aprobar envía a
    la cola (`tpi lote --solo-encolar`); todo se puede tocar.
20. ✅ **Estilo por materia, insignias y Vista Previa Rápida** (#31): insignia de color por materia en QC y el
    borrador del guion dentro de su tarjeta.
21. ✅ **Portada automática** (#32): `portada.jpg` junto a cada video (final y borrador), y la prueba de fuego de tres
    pasos (suite, redactar, render) verificada en CI.
22. ✅ **CI en tres sistemas** (#33): suite verde en Ubuntu, macOS y Windows; acciones en Node 24; Ubuntu fijo.
23. ✅ **Estilo en un solo lugar** (#34, #35): la regla `sugerir_tema` (molde → dibujos → error → materia) y el
    selector único en la ficha de QC; «Todos al sugerido» de una vez.
24. ✅ **«Para hoy»** (#36): un video al día, elegido entre tres del mismo nivel, uno por materia.
25. ✅ **Dos públicos** (#37): enseñanza media y universidad de ingeniería (Industrial, Eléctrica, Obras Civiles),
    malla por año y carrera, campo `carrera`, `tpi completar-niveles` y «Pedírselo a la IA».
    Spec: `docs/superpowers/specs/2026-11-10-dos-publicos-design.md`.

## Lo que sigue

- Escribir con la IA los guiones que faltan para que los 8 niveles tengan sus tres materias
  (`./tpi completar-niveles`), y revisar en el Mac la calidad de los de universidad con el Gemini real.
- Ajustar `malla.yaml` a la malla concreta de la universidad que se quiera seguir.
- Probar en el Mac el Gemini real con las instrucciones nuevas (en CI se usa un Gemini de prueba).
