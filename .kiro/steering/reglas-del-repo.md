---
inclusion: always
---

# Reglas del repo tuprofeindustrial-videos (Sistema 2)

- **Solo Python.** Stack: Python 3.11+ (el instalador usa 3.12), Manim Community Edition, manim-voiceover,
  Whisper, FFmpeg y LaTeX. Nada de Next.js, React, Node ni frontend en este repo.
- **El panel de control** (`src/tpi_videos/panel/`) es Python con NiceGUI: sin JavaScript ni HTML propios,
  sin Node ni npm. Escucha solo en `127.0.0.1` y ejecuta los comandos `tpi … --progreso-json` en procesos
  aparte (uno a la vez). Toda ruta que llega desde el navegador se valida (solo `guiones/`, `salida/`,
  `mis_ajustes/stickers` y `mis_ajustes/fondos`); nunca servir `.env`. Verificarlo con Playwright y capturas.
- **Lo propio del Mac** (`osascript`, `open`, `xattr`, `.command`) no se puede probar en el sandbox Linux:
  simularlo con comandos falsos que registren sus argumentos, y decir en la PR qué quedó sin probar en un Mac.
- **100 % independiente de la web (Sistema 1, Sistema-omicrom).** No compartir código, dependencias,
  credenciales ni despliegues con la web.
- **Usuario no técnico, español de Chile.** Textos de la CLI, errores y documentación en español claro.
  Trabaja desde la Terminal de su Mac en `~/Downloads/tuprofeindustrial-videos`: dar siempre bloques para
  copiar/pegar y no pedir que abra editores de código.
- **Entrega en rama nueva + Pull Request a `main`** (nunca push directo a `main`). Incluir en la PR los pasos
  para probar en el Mac y para actualizar:
  `cd ~/Downloads/tuprofeindustrial-videos && git checkout main && git pull origin main`
- **Verificar renderizando**, no solo revisando código: crear el borrador de los guiones de
  `guiones/ejemplos/` y mirar cuadros del video antes de abrir la PR.
- **No romper el estilo original:** con `--tema pizarra_nocturna --voz silencio --borrador`, los ejemplos
  antiguos deben salir idénticos cuadro a cuadro a los de `main`. Comparar con `PYTHONHASHSEED=0` en ambos
  lados (`TransformMatchingTex` recorre conjuntos y el orden de dibujo cambia entre procesos).
- **Estilos y datos del usuario:** el estilo por defecto es `hoja_de_desarrollo`; todo campo nuevo del guion o
  del tema es opcional. Lo que personaliza el usuario va en `mis_ajustes/` (ignorado por Git), nunca en
  archivos del repo.
- **Guiones:** `texto`/`tex` es lo que se ve y `voz` lo que se escucha; fórmulas LaTeX entre comillas simples.
  Los emojis van solo en el campo `emoji:` (nunca en `texto` ni `voz`).
- **Nunca subir videos ni audios** (`salida/` está en `.gitignore`).
- **Secretos:** la clave de Gemini vive solo en `.env` (ignorado por Git, permisos 600) o en la variable
  `GEMINI_API_KEY`. Nunca imprimirla, registrarla ni pedirla por el chat: el usuario la guarda con `./tpi clave`.
- **IA (`tpi redactar`):** las instrucciones del modelo están en `src/tpi_videos/plantillas/ia/`. La IA
  devuelve datos en un esquema JSON fijo (nunca código) y todo guion pasa por las validaciones del motor.
  Probar cambios con un servidor falso de Gemini (`GOOGLE_GEMINI_BASE_URL`) si no hay clave disponible.
