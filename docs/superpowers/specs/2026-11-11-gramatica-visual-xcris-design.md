# Gramática visual XCris en tpi_videos — diseño

Fecha: 2026-11-11 · Estado: aprobado por el dueño (alcance 1–6, enfoque A, opt-in) · Repo: tuprofeindustrial-videos

## Objetivo

Cerrar la brecha de "se ve profesional" entre los videos del motor y el referente @xcris222,
copiando su **gramática visual** (no su toolchain): coherencia de diseño, pasos numerados
sincronizados, un panel persistente que acumula, mapeo por color concepto↔fórmula,
micro-movimiento con propósito y glow/neón sobre los dibujos existentes (incluidos los 3D).

Evidencia del referente (3 videos medidos): 0 silencios largos, ~47–55% de fotogramas
"congelados" pero nunca muertos (cama continua + panel vivo), tabs numerados con color por
paso, dos paneles sincronizados, voz masculina expresiva ~129–145 Hz / ~144–159 wpm.
XCris dibuja en 2D plano con `skia-python` + `ffmpeg`; **su impacto no viene del 3D** sino de
la gramática. Por eso este diseño NO porta a skia ni rehace los dibujos: extiende el tema.

## No-objetivos (fuera de alcance)

- No portar a skia ni reemplazar Manim.
- No cambiar el estilo por defecto del repo ni `mis_ajustes/marca.yaml` (opt-in por video).
- No tocar la cama musical ni la voz (ya implementadas y verificadas por separado).
- No publicar ni subir a redes.
- No rehacer `dibujos_3d.py`; solo aplicarles el estilo/neón del tema.

## Enfoque elegido (A)

Tema nuevo + campos opcionales de `Tema` + componentes nuevos detrás de flags.
Sigue el patrón existente: todo lo visual lo decide el tema (`temas.py`), la escena
(`escena.py`) lo dibuja, los componentes compartidos viven en `componentes.py`.
Con cualquier tema actual, la salida es byte-idéntica a hoy.

Descartados: (B) un tercer `marco` "consola" con camino de layout separado (duplica
layout/cámara y sube mantenimiento); (C) overlay FFmpeg en postproducción (no puede
sincronizarse al ritmo de cada paso ni hacer micro-movimiento ligado a la narración).

## Arquitectura y componentes

Tema nuevo `plantillas/temas/consola_neon.yaml` (id `consola_neon`), seleccionable en el
panel → Estilos y por `tema:` del guion. Fondo oscuro, paneles redondeados, tipografía
consistente, `resplandor: true` (glow de postproducción ya existente).

Cuatro componentes nuevos en `componentes.py`, cada uno una función pura que devuelve un
`VGroup`/`Animation` de Manim y se prueba por separado. `escena.py` los construye y actualiza
**solo si `tema.gramatica` los activa**:

1. `tabs_de_pasos(n: int, activo: int, paleta: list[str]) -> VGroup` — fila de tabs numerados
   (número en círculo + rótulo), un color por paso desde `paleta`; el activo con glow, el resto
   tenue. Se actualiza al entrar cada bloque de voz de paso.
2. `panel_persistente(total: int, cerrados: list[str], paleta: list[str]) -> VGroup` — banda
   inferior redondeada que nunca se resetea: contador "paso k de n", barra de progreso y las
   **últimas 3** mini-fórmulas de los pasos cerrados (las más recientes, para que quepan).
   Equivalente al terminal acumulativo de XCris pero con matemática.
3. `mapa_de_color(paso: Paso) -> VGroup` — flechas + etiquetas del mismo color que unen un
   término de la fórmula con su concepto, según `paso.mapa`.
4. `micro_movimiento(tipo: Literal["cursor", "tick", "barra", "contador"], objetivo: Mobject)
   -> Animation` — animaciones con propósito ligadas a la transición de paso: cursor que
   escribe en el panel, tick al cerrar un tab, barra que se llena, contador que sube. No son
   giros de cámara.

Glow sobre 3D: `tema.resplandor` (postproducción) + `dibujos_3d.py` tomando colores/bordes
del tema vía `componentes.usar_estilo`, sin rehacer la geometría.

Layout: `temas.Layout` gana `banda_panel` (alto de la banda inferior). Orden de bandas de
arriba a abajo: cabecera → escenario (`y_zona_enunciado`..`y_zona_pasos`) → `banda_subtitulo`
→ `banda_panel` (el panel queda al fondo, el subtítulo justo encima, como en XCris). Las
bandas existentes se respetan para que nada se pise.

## Contrato de datos y compatibilidad

- `temas.Tema` gana `gramatica: Gramatica` con defaults apagados:
  `tabs: bool = False`, `panel: bool = False`, `mapa_color: bool = False`,
  `micro: bool = False`, `paleta_pasos: list[str] = []` (hex validados con `_validar_hex`).
  Si `tabs` está activo y `paleta_pasos` viene vacía, se cicla una paleta por defecto derivada
  del tema (acento, cuadricula, exito, error, tenue). `Layout` gana `banda_panel: float` con
  rango validado.
- `guion.Paso` gana `mapa: list[MapaColor] = []`, `MapaColor = {termino, concepto, color?}`.
  Validación: `termino` debe aparecer en `paso.tex` (mismo criterio que `halo`); si no, error
  señalando el paso.
- `extra="forbid"` se mantiene: los YAML viejos (sin estos campos) siguen validando porque
  todo tiene default. Los temas viejos no activan gramática → componentes ni se construyen.
- Opt-in: el tema se elige por video (panel Estilos / `tema:` del guion / QC). No se cambia
  `TEMA_POR_DEFECTO` ni el `tema:` de marca.
- No-regresión: prueba que construye la escena con un tema actual y exige layout idéntico y
  ausencia de componentes de gramática.

## Flujo de datos

guion.pasos + tema.gramatica → `escena.VideoEjercicio.construct` arma tabs y panel →
cada bloque de voz de paso actualiza tab activo, panel y micro-anim →
`linea_de_tiempo.json` (existente) marca límites de paso → postproducción aplica
`resplandor` → subtítulo quemado en su banda, sin pisar el panel.

## Errores

- Hex inválido en `paleta_pasos` → `ValidationError` con mensaje claro (patrón `_validar_hex`).
- `mapa.termino` ausente de `paso.tex` → error de validación indicando el paso.
- `banda_panel` fuera de rango → validación con rango (ge/le).
- Tema sin gramática → ningún componente se construye; no hay ruta de crash.

## Pruebas (TDD)

- Unit por componente: tabs cuentan y activan el color correcto; panel acumula y nunca se
  resetea; mapa une solo términos presentes; micro-movimiento produce `Animation`.
- Validación: defaults de gramática apagados; paleta hex; `mapa` con término inexistente
  falla; YAML de tema viejo sigue validando.
- Regresión: escena con tema actual sin componentes nuevos y layout idéntico.
- End-to-end: renderizar un guion existente (no los guiones sin trackear) con `consola_neon`;
  medir silencios (0 largos) y mirar fotogramas a tamaño completo confirmando tabs + panel +
  glow; suite completa en verde antes de declarar listo.

## Criterio de éxito

Un guion existente renderizado con `consola_neon` muestra, en fotogramas a tamaño completo:
fila de tabs numerados con el paso activo brillante, panel inferior persistente que acumula,
y glow/neón coherente; sin silencios largos; y los temas/guiones viejos producen exactamente
la misma salida que antes.