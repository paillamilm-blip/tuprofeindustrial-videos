---
inclusion: always
---

# Reglas del repo tuprofeindustrial-videos (Sistema 2)

- **Solo Python.** Stack: Python 3.11+ (el instalador usa 3.12), Manim Community Edition, manim-voiceover,
  Whisper, FFmpeg y LaTeX. Nada de Next.js, React, Node ni frontend en este repo.
- **100 % independiente de la web (Sistema 1, Sistema-omicrom).** No compartir código, dependencias,
  credenciales ni despliegues con la web.
- **Usuario no técnico, español de Chile.** Textos de la CLI, errores y documentación en español claro.
  Trabaja desde la Terminal de su Mac en `~/Downloads/tuprofeindustrial-videos`: dar siempre bloques para
  copiar/pegar y no pedir que abra editores de código.
- **Entrega en rama nueva + Pull Request a `main`** (nunca push directo a `main`). Incluir en la PR los pasos
  para probar en el Mac y para actualizar:
  `cd ~/Downloads/tuprofeindustrial-videos && git checkout main && git pull origin main`
- **Verificar renderizando**, no solo revisando código: crear el borrador de los 3 guiones de
  `guiones/ejemplos/` y mirar cuadros del video antes de abrir la PR.
- **Guiones:** `texto`/`tex` es lo que se ve y `voz` lo que se escucha; fórmulas LaTeX entre comillas simples.
- **Nunca subir videos ni audios** (`salida/` está en `.gitignore`).
- **Secretos:** la clave de Gemini vive solo en `.env` (ignorado por Git, permisos 600) o en la variable
  `GEMINI_API_KEY`. Nunca imprimirla, registrarla ni pedirla por el chat: el usuario la guarda con `./tpi clave`.
- **IA (`tpi redactar`):** las instrucciones del modelo están en `src/tpi_videos/plantillas/ia/`. La IA
  devuelve datos en un esquema JSON fijo (nunca código) y todo guion pasa por las validaciones del motor.
  Probar cambios con un servidor falso de Gemini (`GOOGLE_GEMINI_BASE_URL`) si no hay clave disponible.
