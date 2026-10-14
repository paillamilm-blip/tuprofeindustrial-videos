# Plan del motor de video (Sistema 2)

## Objetivo

Enunciado de Matemática / Física / Ingeniería → video vertical 9:16 de 30–75 s, con animaciones, voz
sintética chilena y subtítulos estilo CapCut, listo para TikTok, Reels y Shorts. Repo **solo Python**,
independiente de la web (Sistema 1).

## Arquitectura (v0.2)

```
enunciado (texto, foto o PDF) ─► redactor.py (Gemini escribe → motor valida → Gemini revisa) ─► guion.yaml
guion.yaml ─► guion.py (valida, errores en español) ─► revision.py (duración, gancho, pedagogía)
          ─► escena.py (Manim) ── voces.py (manim-voiceover: edge-tts / gTTS / silencio)
          │      └─ linea_de_tiempo.json  (inicio, texto exacto y marcas de cada bloque de voz)
          ─► subtitulos.py (tiempos por palabra: voz exacta > Whisper > estimado → archivo ASS)
          ─► postproduccion.py (FFmpeg + libass: quema subtítulos, −14 LUFS, H.264, faststart)
          ─► salida/<guion>/<guion>.mp4 + .srt
```

| Módulo | Responsabilidad |
|---|---|
| `cli.py` | Comandos `tpi` en español; errores sin trazas técnicas (`--debug` para verlas) |
| `redactor.py` / `ia.py` | `tpi redactar`: Gemini escribe el guion, el motor lo valida y Gemini lo revisa / clave y errores de la API |
| `guion.py` | Formato del guion (pydantic) y mensajes claros (incluye la trampa de comillas dobles con LaTeX) |
| `revision.py` | Reglas de guion corto y de pedagogía; estimación de duración calibrada con la voz es-CL |
| `voces.py` | Servicios de voz para manim-voiceover; edge-tts entrega la marca de tiempo de cada palabra |
| `escena.py` | Secciones del video: gancho, enunciado, datos, pizarra de pasos, resultado, verificación, reto, cierre |
| `componentes.py` | Diseño 9:16: zonas seguras, texto con líneas parejas, fórmulas divididas en partes, íconos |
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
| **API `generateContent`** | API Interactions (la nueva de Google) | Documentada para los modelos actuales y estable; migrar es cambiar un solo módulo (`redactor._pedir`) |

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
3. **Visuales por materia:** gráficos de funciones (parábolas, rectas), diagramas de física (caída libre,
   plano inclinado, fuerzas) y de electricidad (circuitos serie/paralelo).
4. **Producción:** música de fondo que baja cuando hay voz, portada/miniatura, título + descripción +
   hashtags para publicar, voz Azure o voz propia grabada.
5. **Escala:** crear varios videos en lote y una verificación automática de render en GitHub Actions.
