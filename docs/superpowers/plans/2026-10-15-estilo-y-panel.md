# Plan de implementación: estilo "Hoja de desarrollo" + panel

**Objetivo:** temas (con "Hoja de desarrollo" por defecto), emojis 3D, paso "error típico" y, en una segunda
PR, el panel local con su kit de publicación.

**Arquitectura:** un tema (`Tema`, pydantic) define marco, colores, tipografía, fondo, subtítulos y
animación. `componentes.usar_estilo()` aplica el tema a nivel de módulo; cada video se renderiza en su propio
proceso. El panel (NiceGUI) ejecuta los mismos comandos `tpi` en procesos aparte.

**Diseño:** `docs/superpowers/specs/2026-10-15-estilo-y-panel-design.md`

**Verificación (regla del repo):** se verifica renderizando, no con pruebas unitarias. Los videos de control
de `main` con `--voz silencio` deben salir idénticos con `--tema pizarra_nocturna`.

## Restricciones globales

- Solo Python ≥ 3.11. Nada de Next.js, React ni Node.
- Textos al usuario en español de Chile, sin trazas técnicas.
- Campos nuevos del guion siempre opcionales.
- Panel ligado a `127.0.0.1`.
- Datos del usuario en `mis_ajustes/`, ignorado por Git.

## Etapa 1

1. **Recursos:** en `assets/fuentes/` (carpeta plana), Comic Neue Regular y Bold, Bangers, Cinzel y Caveat
   (estáticas), Patrick Hand y Luckiest Guy, con sus licencias en `assets/fuentes/licencias/`. En
   `assets/emojis/`, la selección 3D de 224 px y `LICENCIA-Noto-Emoji-OFL.txt`. En `assets/fondos/`,
   `difuminado.png`.
2. **`tipografia.py`:** catálogo de familias → archivos por grosor, con respaldo al grosor más cercano.
   Funciones `archivo(familia, grosor)` y `unidades_por_pixel(familia, grosor)`.
3. **`temas.py`** y `plantillas/temas/*.yaml`: modelo `Tema`, `cargar_tema(nombre, marca)`, `listar_temas()`.
   `pizarra_nocturna` con `usar_marca: true`.
4. **`componentes.py`:** `usar_estilo(tema)` fija la tipografía y las `Zonas`. Las funciones `texto` y
   `parrafo` reciben `mayus` y los anchos se calculan al llamar. Se agregan `fondo_tema`, `marco_hoja`,
   `imagen_emoji` y `tachado`; `partes_por_tex` acepta varias partes seguidas (`'5x + 5x'`).
5. **`emojis.py`:** catálogo `EMOJIS` (carácter → archivo y nombre). `resolver(valor)` devuelve la ruta del
   PNG o el sticker del usuario.
6. **`guion.py`:** `Guion.tema`, `Gancho.tex` y `emoji` en gancho, paso, resultado, verificación, reto y
   cierre. `Paso.error`. Avisos nuevos en `revision.py` (emoji inexistente o dentro de un texto, tema que no
   existe, error típico al final).
7. **`escena.py`:** colores por rol (titulos, texto, formulas), marco por tema, escritura con plumón, emojis
   en cada sección y paso de error con tachado y temblor. El último paso correcto es el origen de la
   transformación siguiente.
8. **`render.py` / `cli.py`:** se resuelve el tema y de ahí salen la plantilla TeX (negrita), el color de fondo
   y los subtítulos. Se agregan `crear --tema`, `subtitular --tema`, `tpi temas` y `tpi emojis`. En
   `subtitulos.py`, la opción `resaltar`. El intermedio de Manim usa `preset veryfast` (2× más rápido) salvo en
   el estilo original, que conserva su configuración para salir idéntico.
9. **`redactor.py` y sus instrucciones:** `emoji` y `error` en el esquema, validados contra el catálogo.
10. **Ejemplos:** emojis en los 3 actuales y el nuevo `matematica_error_binomio.yaml`.
11. **Verificación:**
    - Los controles antiguos con `pizarra_nocturna` deben dar cero diferencias.
    - Los 4 ejemplos se crean con `hoja_de_desarrollo` y se revisan sus cuadros.
    - Se repasan los comandos `revisar`, `nuevo`, `redactar` (con Gemini simulado), `subtitular` y `doctor`.
    - `ruff` sin observaciones.
12. **Documentación:** README, GUIA_GUIONES y PLAN. Rama `feat/estilo-hoja-de-desarrollo` y su PR a `main`.

## Etapa 2

13. **CLI:** `--progreso-json` en `crear` y `redactar`. Comandos nuevos `tpi vista-previa` (3 cuadros por
    tema), `tpi publicar` (portada y textos con IA), `tpi panel` e `tpi icono`.
14. **`panel/`:** `app.py` (arranque en 127.0.0.1), `tareas.py` (un proceso a la vez, con cancelación y
    progreso), `editor.py` (tarjetas ↔ guion y vista previa LaTeX) y `paginas/` (crear, videos, estilos,
    ajustes).
15. **Instalador y `doctor`:** dependencia `nicegui` y revisión de que el panel carga.
16. **Verificación:**
    - Recorrido del panel con Playwright en el sandbox: crear desde texto con Gemini simulado, editar, crear
      borrador, ver el video, cambiar tema con vista previa y armar el kit de publicación. Capturas en la PR.
    - Los comandos siguen iguales.
17. **Documentación y PR** (base `main`, depende de la PR de la Etapa 1).
