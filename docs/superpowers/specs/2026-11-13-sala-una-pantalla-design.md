# Sala de producción: una sola pantalla, con % y check por etapa

Fecha: 13-11-2026 · Rama: `feat/sala-una-pantalla`

## Por qué

La sala (`/cola`) tenía tres pestañas, cuatro cifras, tres columnas y «Para hoy» arriba de todo. El profe pidió una
sola pantalla, minimalista y fácil de entender para su gente, y que **cada proceso tenga su porcentaje y su check**
para ver cómo avanza cada video.

## La pantalla (`/cola`)

1. Título + resumen («1 produciendo · 2 en espera · 5 listos») y un solo botón: **Producir videos**
   (Detener y el registro del motor solo aparecen mientras algo trabaja).
2. Aviso «N guiones esperan tu aprobación» (solo si hay) → `/qc`.
3. Lista por grupos: Produciendo ahora · En espera · Con problemas · Listos (4 a la vista, «Ver los N listos»).
4. Cada video: título, avance total y **cuatro etapas**: Guion → Animación → Video → Kit, cada una con su %.
   Check verde = lista; anillo ámbar con su % = trabajando; «!» rojo = falló ahí; anillo vacío = espera.
5. Abajo, plegado, «Idea para hoy»; y los enlaces a Aprobar guiones y Herramientas avanzadas.

## Cómo se calcula (`panel/etapas.py`, sin NiceGUI)

Los cortes del avance son los de `lote._traducir`: guion 0–0,25 · animación 0,25–0,90 · video 0,90–0,95 · kit 0,95–1.
Una etapa queda lista si su hito (`guion`, `video`, `kit`) está en la cola o si el avance ya pasó su corte. El 100 %
es solo del check (mientras trabaja, tope 99 %). Un fallo marca la etapa donde quedó. `Ficha.etapas` las trae.

## Reglas de diseño

Colores solo desde `PIEL`; sin animaciones en bucle; accesible (`role="img"` + `aria-label` por etapa, objetivos ≥ 44 px
en botones). `/qc`, `/avanzado` y las rutas antiguas siguen igual.

## Pruebas

`pruebas/test_etapas.py`: etapas por estado, fallo, hitos tras reiniciar, límites, redondeo y `columnas()`.

## Aprobar guiones (`/qc`): el mismo lenguaje

Antes: lista lateral con vistas previas + seis tarjetas apiladas. Ahora, una sola columna y **un guion a la vez**:

1. Encabezado: «Aprobar guiones», cuántos faltan, «Ver todos», flechas «1 de N» y «Ver la lista» (diálogo).
2. Tarjeta del guion: insignia, título, **chequeos** (`panel/revision.py`: guion válido, texto para la voz,
   título y hashtags, estilo listo, dudas de la IA), lo que dice la voz, Vista Previa Rápida y el estilo en una
   línea con «Cambiar» (sigue siendo el único lugar donde se elige el estilo).
3. Plegados (recuerdan si estaban abiertos): Qué enseña y herramientas · Para redes · Detalles técnicos.
4. Barra fija abajo: **Rechazar o editar** y **Aprobar y enviar a la cola**. Al aprobar pasa solo al siguiente.

Sin hashtags es un aviso (el kit los escribe), no un error. `pruebas/test_revision.py` cubre los chequeos.

## Borrar un video desde la sala

Cada tarjeta lleva un tacho (nunca en un video que está produciéndose: ahí va «Detener»), siempre con confirmación:

- **En espera / con problemas:** «Quitar de la cola» → `cola.descartar_video`. Saca solo ese video; los demás de su
  lote siguen. Los archivos que ya salieron no se tocan.
- **Listos:** «Enviar a la Papelera» → `biblioteca.borrar` (Papelera de macOS, recuperable desde Finder) y después
  `descartar_video`. Fuera de macOS el motor lo explica y no borra nada.
- El botón no abre el detalle de la tarjeta (`click.stop`). `pruebas/test_descartar_video.py` cubre la cola.

## Borrar un guion en «Aprobar guiones»

Botón «Borrar guion» a la izquierda de la barra fija, con confirmación. `qc.borrar_guion` lo manda a la Papelera de
macOS (`biblioteca.enviar_a_papelera`, el mismo mecanismo que usa «Mis videos»; nunca borra de verdad). Solo guiones
de `guiones/` (no ejemplos). Uno **aprobado** no se borra: está en la cola de producción; primero se quita su video
de la Sala. `pruebas/test_borrar_guion.py` lo cubre con una Papelera simulada.

## Avanzado → «Herramientas» (`/avanzado`)

Antes: cinco plegables apilados («todo plegado hasta que lo necesites»). Ahora: **una pantalla con cinco tarjetas**
(`panel/herramientas.py`): Crear a mano · Cola por lotes · Mis videos · Estilos visuales · Ajustes. Tocas una y esa
herramienta se abre sola (con «← Herramientas» para volver); nunca hay dos a la vez. Las tarjetas se alcanzan con
teclado (Tab y Enter). Las rutas antiguas (`/crear`, `/fabrica`, `/videos`, `/motor`, `/estilos`, `/ajustes`) abren
directo su herramienta (`herramienta_de`). Los tres destinos (`/cola`, `/qc`, `/avanzado`) ya no tienen pestañas.

**Pendiente (a propósito):** por dentro, las herramientas (editor, estilos, ajustes) conservan su piel clara y su
contenido; rediseñarlas una por una es un paso aparte. `pruebas/test_herramientas.py` cubre las claves y las rutas.
