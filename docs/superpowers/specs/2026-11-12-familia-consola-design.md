# Familia Consola neón: una variante por forma de contenido — diseño

Fecha: 2026-11-12 · Estado: aprobado por el dueño («todo pasa a la familia, con lo mejor de cada
variante») · Repo: tuprofeindustrial-videos

## Por qué

Había 20 estilos y dos lugares que decidían cuál usar (`temas.py` y `formatos.yaml`), que no se
ponían de acuerdo. Por ejemplo, para «Mito vs realidad» uno decía `vineta_cine` y el otro
`neon_reja` o `rotulador`. Además, 21 de los 44 guiones no tienen molde, así que su estilo salía
de la materia y no de la forma de enseñar. De los 20 estilos, el motor solo sugería 10.

La gramática XCris (pasos numerados, panel de progreso, mapa de color, micro-movimiento) quedó
encerrada en un solo estilo, `consola_neon`. Era una herramienta para enseñar guardada donde se
decide la apariencia.

## Decisión

1. **La forma del contenido decide el estilo.** La materia y los dibujos ya no cambian la apariencia.
2. **Una sola familia: Consola neón.** Todos los videos comparten la estructura y la base visual;
   cada forma tiene su color y sus herramientas.
3. **Nada se borra.** Los 20 estilos anteriores pasan a `plantillas/temas/archivo/`. No se listan
   ni se sugieren, pero `cargar_tema` los encuentra por nombre: un guion con `tema:`, un `--tema`,
   un video viejo que se rehace o un `marca.yaml` propio siguen funcionando.

## La familia

Base común (lo mejor de cada estilo antiguo):

| Qué | Viene de |
|---|---|
| Gramática XCris: pasos numerados, panel, mapa de color, micro-movimiento | Consola neón |
| Brillo neón sobre los trazos (`resplandor`) | Neón sobre reja |
| Títulos escritos con plumón (`animacion.titulos: plumon`) | Hoja de desarrollo, Kraft y tiza, Neón sobre reja |
| Subtítulos CapCut de 3 palabras, palabra que suena en color, borde y sombra marcados | Neón sobre reja (con Montserrat Black, una sola letra) |
| Una sola letra: Montserrat gruesa en títulos, semigruesa en texto | Plano nocturno, Rotulador |
| Rótulo del tipo de video en el rincón superior derecho (`rotulo`) | El encabezado de las hojas («CLASE DE HOY») |
| Fondo oscuro con textura, incluido en el paquete | Los fondos de los estilos oscuros |

Variantes:

| Clave | Forma | Color | Fondo | Herramientas |
|---|---|---|---|---|
| `consola_pasos` | Paso a paso (molde POV y guiones sin molde) | Cian | Retícula de Plano nocturno | Pasos + panel + mapa |
| `consola_error` | Error (molde Tres errores y guiones con `error: true`) | Rojo | Reja de Neón sobre reja | Pasos + panel + mapa + contador «✗ 1 de 3» (receta del molde) |
| `consola_mito` | Mito vs realidad | Violeta | Reja de Neón uva | Mapa; tablero partido MITO/REALIDAD (receta); sin pasos ni panel |
| `consola_dato` | Dato («Nadie te enseñó esto») | Ámbar | Viñeta dorada | Mapa; resultado tapado (receta); sin pasos ni panel |
| `consola_reto` | Reto | Verde | Pizarra de Tiza verde | Pasos + panel + mapa; resultado tapado (receta) |

Regla (`temas.sugerir_tema`): 1° el molde → su variante · 2° si corrige un error → Error ·
3° todo lo demás → Paso a paso. `TEMA_POR_CATEGORIA` y `TEMA_POR_DIBUJO` se eliminan.
`formatos.yaml` apunta a las mismas variantes.

## Versión sobria (12-11-2026, pedido del dueño)

Tras ver el primer video, el dueño pidió colores y fondos más sobrios. Cambió solo la apariencia:
- Fondo: grafito liso con un degradado suave y un tinte mínimo del color de la variante. Se quitan
  las rejas neón, la viñeta dorada y la pizarra verde.
- Sin brillo neón (`resplandor: false`).
- Acentos apagados: azul acero `#6FA8DC` (paso a paso), rojo ladrillo `#D27A72` (error), lila
  `#A399C9` (mito), dorado mate `#D4B26A` (dato) y verde salvia `#7DB894` (reto).
- Subtítulos con borde y sombra más livianos.

Se mantienen la estructura, las herramientas de cada forma, el plumón, el rótulo y la regla de elección.

## Lo que no se pudo llevar y por qué

- Los fondos de papel claro (Rotulador, Cuadernos, Kraft claro, Cómic): mezclar claro y oscuro
  rompe la identidad de la familia.
- Las letras de cómic, cine y manuscritas (Bangers, Cinzel, Caveat, Shadows Into Light): varias
  letras es lo que hacía ver disparejo el canal.
- Rótulo + materia juntos en el rincón: se reemplaza la materia por el rótulo para no arriesgar que
  el chip choque con el nombre de la marca. La materia sigue en el kit de publicación.

## Pendiente (siguientes etapas)

- **Gemini no escribe el mapa de color** (`paso.mapa`): ningún guion lo usa todavía. Enseñárselo
  al redactor (`PasoIA` + `plantillas/ia/sistema.md`).
- **«El dibujo demuestra, no decora»**: que el contenido decida cómo enseñar (dato, mito, error,
  ejercicio o una combinación) y después las herramientas visuales y el tiempo. Ejemplo propuesto:
  el cubo de arista doble como mito (ocho cubos), error (comparar razonamientos) y ejercicio (la
  fórmula nace de la demostración). Primero un solo ejemplo para validar la idea.
- La auditoría de prioridades: el punto 6 (agrupar los 20 estilos) queda reemplazado por este diseño.

## Verificación

- Suite completa (`python -m unittest discover -s pruebas -t .`).
- CI: además del render de siempre (Paso a paso), renderiza un guion real por cada una de las otras
  cuatro variantes, comprueba que salió con su variante y guarda 3 cuadros de cada una en el
  artefacto `muestras-familia-consola`.
- En el Mac del dueño: `./tpi vista-previa --tema consola_<variante>` para mirar las cinco.
