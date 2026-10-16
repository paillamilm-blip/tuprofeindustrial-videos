# Diseño: estilo "Hoja de desarrollo" + panel de control

Aprobado por el usuario el 15-10-2026 ("sí, títulos 1, luego sigue con la etapa dos, agrégale emojis y
algo más innovador: tú decide y sorpréndeme").

## Decisiones del usuario

- El estilo principal del motor es su **"Hoja de desarrollo"** (el de sus videos de @tuprofeindustrial).
- Títulos: **Comic Neue** en mayúsculas. Subtítulos: **Bangers**, modernos: pocas palabras y la que suena en amarillo.
- Mismas animaciones paso a paso que hoy.
- **Panel de control obligatorio**, local en su Mac.
- Emojis y "algo innovador" a criterio de Kiro.
- Regla que se mantiene: repo solo Python. El panel es Python (NiceGUI), sin Next.js, React ni Node, y no se
  mezcla con la web (Sistema 1).

## Etapa 1 · Estilo en el motor (PR propio)

**Temas.** Un tema define todo lo visual. Los incluidos son:
- `hoja_de_desarrollo`, el tema por defecto: fondo gris difuminado, "Notas" y "Fecha:", y una hoja blanca
  cuadriculada con el encabezado "HOJADEDESARROLLO". Títulos Comic Neue Bold en mayúsculas, azul marino,
  con destacados en rojo; explicaciones en Comic Neue y fórmulas negras de grosor normal. Los títulos y
  las notas se escriben como con plumón. Subtítulos Bangers.
- `pizarra_nocturna`: el estilo actual, idéntico cuadro a cuadro. Usa los colores y subtítulos de `marca.yaml`.

**Prioridad para elegir el tema:** `--tema` > `tema:` del guion > `mis_ajustes/marca.yaml` > `marca.yaml`.
Los temas propios del usuario viven en `mis_ajustes/temas/`.

**Emojis 3D** (Noto Emoji 3D, licencia OFL), en una selección de 62 útiles para clases. El campo
`emoji:` admite tres valores: el emoji mismo ("🤯"), su nombre ("explota") o una imagen propia del usuario
("robot", que se busca en `mis_ajustes/stickers/robot.png`). Puede ir en el gancho, en cada paso, en el
resultado, en la verificación, en el reto y en el cierre. Aparece con un salto y un pequeño balanceo.

**Sorpresa 1, el paso "error típico"** (`error: true`): la fórmula equivocada aparece, se tacha con una ✗
roja, tiembla y salta 🚨. El paso siguiente se transforma desde la última fórmula correcta. Reproduce el
formato de sus videos con más vistas ("EL 90% SE EQUIVOCA", "¿RESUELVES ASÍ?").

**Gancho con fórmula** (`gancho.tex`): una fórmula bajo la pregunta, como "(x+5)² = x²+25".

**La IA (`tpi redactar`)** elige los emojis de la lista y agrega un paso de error típico cuando existe uno famoso.

**Compatibilidad**
- Todos los campos nuevos son opcionales y los guiones actuales siguen sirviendo.
- Con `pizarra_nocturna`, los ejemplos antiguos dan videos idénticos: se comparan cuadro a cuadro y el audio
  muestra por muestra.
- `marca.yaml` gana el campo `tema:`. Las preferencias del panel van en `mis_ajustes/`, que Git ignora, así
  bajar una versión nueva nunca choca con los cambios del usuario.

## Etapa 2 · Panel de control (PR propio, sobre la Etapa 1)

- `./tpi panel` abre el panel en el navegador, solo en el Mac: escucha únicamente en 127.0.0.1, ni siquiera
  la red WiFi puede entrar. `./tpi icono` crea un ícono en el Escritorio que se abre con doble clic.
- **Crear:** un enunciado escrito, una foto o un PDF entra a "Escribir con IA" o a un guion en blanco. El guion
  se edita como tarjetas, con vista previa de cada fórmula, selector de emoji, paso de error y avisos de
  revisión. Luego se elige tema y se pulsa "Borrador" o "Video final", con barra de progreso y reproductor.
- **Mis videos:** miniaturas para ver, descargar, mostrar en Finder, rehacer con otro tema o borrar.
- **Estilos:** temas incluidos y propios. Se pueden duplicar y editar colores, letras, fondo (incluida una foto
  propia, que se oscurece y difumina sola), los textos de la hoja, los subtítulos y la escritura con plumón.
  Una vista previa de 3 cuadros se genera en pocos segundos.
- **Ajustes:** clave de Gemini (solo muestra "configurada"), voz con muestra ▶, tema por defecto, logo o
  stickers propios y diagnóstico.
- **Sorpresa 2, el kit de publicación:** por cada video, una **portada** (PNG del gancho) y, con IA, título,
  descripción y hashtags para TikTok, Reels y YouTube Shorts, con botones de copiar. También existe en la
  Terminal: `tpi publicar`.
- El panel ejecuta los mismos comandos `tpi` en procesos aparte, con progreso en JSON (`--progreso-json`). Si
  un video falla, el panel no se cae, y lo que hace el panel es exactamente lo que hacen los comandos.

## Fuera de alcance

Música con ducking, subtítulos karaoke, otros formatos de video, gráficos por materia y uso desde internet.

## Riesgos y cómo se cubren

| Riesgo | Cobertura |
|---|---|
| Romper el estilo actual | Comparación cuadro a cuadro de `pizarra_nocturna` contra los videos de control |
| Letras sin tildes | Solo letras revisadas con á é í ó ú ñ ¿ ¡ en mayúscula y minúscula |
| Fondos con foto que se leen mal | Oscurecido y difuminado automáticos |
| Panel expuesto en la red | `host=127.0.0.1` siempre (NiceGUI escucha en 0.0.0.0 por defecto) |
| Conflictos al actualizar | Datos del usuario en `mis_ajustes/` (ignorado por Git) |
| Peso de los emojis en el repo | PNG de 224 px optimizados, solo una selección |
