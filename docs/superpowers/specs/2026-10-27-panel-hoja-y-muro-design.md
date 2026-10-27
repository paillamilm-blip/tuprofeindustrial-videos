# Diseño: Fase 12 · Formato, piel y muro: un panel que te deja elegir

Aprobado por el usuario el 27-10-2026 en esta conversación, en siete decisiones separadas: (1) el camino de
cuatro pasos sin candados, (2) la piel «muro + hoja», (3) que todo lo que decida la IA se muestre con su valor
y un «cambiar», (4) más estilos de impacto con explicación visual, (5) **sus cuatro familias de contenido**
como formatos del panel (las reemplazó a las que yo había inventado), (6) **el detalle al costado**, no debajo
de la tarjeta, y (7) **el área de ingeniería 3D**, que este spec había dejado afuera y él pidió de vuelta.

Rama: el árbol de trabajo viene sucio de la fase anterior (`dibujos.py`, `guion.py`, `redactor.py`,
`visuales.py` y el prueba de bloques/engranajes/Mohr sin terminar). Esta fase **no** toca esos archivos: el
primer hito empieza por cerrar o guardar ese trabajo pendiente.

## Contexto: el panel no se entiende porque no deja elegir

El diagnóstico se hizo con capturas reales del panel en marcha, no de memoria. Ocho fallas:

1. **Fábrica y Crear son la misma puerta dos veces.** Nadie sabe por cuál entrar.
2. **Crear es un scroll de ~4 pantallas** con tres secciones apiladas donde el paso 1 nunca se retira.
3. **Cuatro botones que todos se ven primarios.** No hay un solo «el siguiente paso es este».
4. **Nada cambia visiblemente al tocar.** El LaTeX se redibuja solo al perder el foco; el acordeón «Dibujo»
   no muestra ningún dibujo; el revisor dice «Sin observaciones» sin decir qué revisó.
5. **Jerga de programador en pantalla** (`tex`, `molde`, `kit`, `borrador`).
6. **Mis videos es un muro de ~24 tarjetas apiladas**, la mitad con el cuadro gris de portada fallida, sin
   buscador ni filtro.
7. **Estilos ofrece 5 acciones por estilo** y sus miniaturas usan una fórmula fija, no el contenido del autor.
8. **El encabezado de 5 links se corta en dos filas.**

La causa raíz de todo lo anterior es una sola, y es medible: el motor sabe hacer **24 dibujos**
(`guion.py:158-183`) y el panel ofrece **3** (`panel/editor.py:44`). El motor obedece **8 familias de letras**
(`tipografia.py:21-35`) y el panel ofrece **5** (`tipografia.py:38-39`). El motor acepta un PNG propio de
fondo, `nota.color`, `formulas_negrita`, `emojis` y el grosor del borde de subtítulo, y el panel no expone
nada de eso. **Un panel que no muestra una palanca no puede dejar que nadie la elija.**

## Qué hace esta fase

Cinco cosas, en este orden, cada una con su prueba:

1. Un **formato** por cada una de sus cuatro familias, que casa molde + estilo + dibujo y se puede cambiar.
2. El camino de **cuatro pantallas** (Idea → Formato → La hoja → Video) sin candados, con el detalle al
   costado.
3. **Los 24 dibujos en el editor**, con los campos de cada uno y una miniatura real de 0,2 s.
4. **Tres arreglos del motor** que hoy obligan a editar YAML a mano.
5. Un **área de ingeniería 3D** (`solido_3d`): pieza con relieve, cuatro vistas y corte, por el mismo camino
   rápido que las miniaturas.

## 1 · Formato = familia suya + molde + tema + dibujo

Hoy `molde` y `tema` son dos campos independientes que la IA elige por separado: un «dato» y un «problema»
se ven idénticos en pantalla. El formato los casa.

**Las cuatro familias las puso él, no yo** (27-10-2026). Son su taxonomía de contenido; el motor las casa con
los cinco moldes que ya existen (`moldes.py:24-79`):

| Familia (texto suyo) | Molde que le corresponde | Dibujos que suelen cargar la explicación |
|---|---|---|
| 1 · Desafíos y trampas cognitivas | `reto` · `mito_realidad` | `poligono_regular`, `venn`, `probabilidad`, `solido_3d` |
| 2 · Paso a paso dinámico | `pov` | `bloques`, `engranaje`, `viga`, `circuito` |
| 3 · Visualización de datos e historias | `nadie_te_enseno` | `barras`, `torta`, `tanque`, `energia` |
| 4 · Operaciones eficientes y hacks de cálculo mental | `tres_errores` · `mito_realidad` | `recta`, `grafico_funcion`, `pendulo`, `mohr` |

Cinco moldes para cuatro familias: ninguna familia tiene molde exclusivo, y por eso cada tarjeta muestra
**hasta dos moldes** con su «cambiar». Las cuatro familias siguen vivas en un solo lugar
(`plantillas/formatos.yaml`), con `nombre`, `que_es` (la ventana de comentario que él pidió), `moldes`,
`tema`, `dibujos` y `cta`.

**Qué promete su prompt y el motor NO puede hacer** (hay que decirlo antes, no después):

- *«Qué pedir en los comentarios para disparar el engagement»* narrado dentro del video: **prohibido por su
  propia regla** (memoria «Reglas IA en cada video»: el CTA-de-engaño va en el pie, no en el video). El campo
  `cta` de la familia se usa **solo en el kit de publicación**, y la tarjeta lo dice con esa letra.
- *Efectos de magia, tomas reales, escalas con objetos cotidianos filmados*: el motor dibuja vectores, no
  monta video. La «escala visual» se hace con un dibujo (`solido_3d`, `barras`), no con una toma.
- *«Retos de 5 segundos»*: sí se puede — `render.py` ya acepta `solo_gancho`, así que un video de 5 s es el
  gancho nada más. La tarjeta lo ofrece como duración, no como molde nuevo.

**Qué es un formato:** una entrada de `plantillas/formatos.yaml` (nuevo, versionado con el motor) con
`clave`, `nombre`, `que_es`, `moldes` (lista), `tema`, `dibujos` (lista) y `color`.

**Dónde puede sobrescribirlo el usuario:** `mis_ajustes/formatos.yaml`, con la misma regla que ya rige para
los temas propios (`temas.py:1-8`): Git ignora `mis_ajustes/`, así que actualizar el motor nunca choca con lo propio, y una clave repetida gana en la copia del usuario.

**Cómo se elige:** hoy **no existe** un clasificador barato: `ideas.py` llama a la IA y `moldes.py` solo
tiene sinónimos (`_OTRAS_PALABRAS`, `normalizar_molde`). El paso nuevo es un puntador de palabras de ~30
líneas en `formatos.py` —sin IA ni cuota— que lee la idea y marca la familia más probable (va ahí, no en
`moldes.py`, porque necesita las palabras clave de las familias y `moldes.py` se mantiene sin dependencias);
si no reconoce nada, no marca ninguna y las cuatro quedan igual de accesibles. Las cuatro tarjetas quedan
visibles con su portada y su botón «cambiar». Elegir una tarjeta **nunca** bloquea: si el autor prefiere otro
molde o otro estilo, los cambia por separado en la misma tarjeta.

## 2 · Las cuatro pantallas

El mockup aprobado (`visualizations/panel-seleccion-formatos.html`) fija el layout: **muro a la izquierda,
detalle al costado derecho**, pegajoso al hacer scroll. El detalle iba debajo de la tarjeta y él lo movió
(«al costado», 27-10-2026), así que es contrato de diseño, no preferencia mía.

- **Idea** — un solo campo de texto y un botón. Arriba, la frase que él escribió; abajo, el muro de las cuatro
  tarjetas (4 al ancho en escritorio) y **al costado** el panel de la familia activa: su miniatura 9:16, el
  «qué es», el molde sugerido con «cambiar», los dibujos sugeridos con «cambiar», el estilo con «cambiar» y
  el CTA (marcado como texto del pie, no del video).
- **Formato** — la tarjeta elegida queda en el panel del costado, en grande, con sus tres piezas (molde,
  estilo, dibujo) y un «cambiar» en cada una. Las otras tres tarjetas se retiran a una línea discreta.
- **La hoja** — la hoja de papel crema con **tres cosas**: el gancho, las cuentas y el cierre. Las tres
  fórmulas del paso se muestran **a la vez** (decisión del usuario: «mejor las 3 a la vez», se elimina el
  stepper ◀ paso 2 de 3 ▶). Cada bloque con su «cambiar». El LaTeX se redibuja **mientras se escribe**, con
  400 ms de freno, no al perder el foco.
- **Video** — el reproductor con la portada real, el kit de publicación y un botón «Otra vez con este estilo».

**Regla de diseño que manda sobre todo lo anterior** (memoria del usuario, 27-10-2026): todo lo que la IA
decide se muestra **con su valor puesto y un «cambiar»**; nada de eso le bloquea el paso siguiente. En
práctica: cada texto generado lleva una línea de origen («lo escribió la IA») y ningún botón primario se
deshabilita por no haber tocado una sugerencia.

## 3 · La piel: muro + hoja

Se entra por un **muro de portadas 9:16** (pantalla oscura #080A0D, tarjetas con la etiqueta del formato
arriba a la izquierda) y se edita sobre una **hoja crema** (#FBF7EC, renglón rojo al margen, tipografías ya
embebidas). El modo del panel es **Operate** (impeccable): la expresión vive en la portada y en la hoja, no
en los controles.

Tokens en un solo lugar: `panel/comun.py` pasa de constantes sueltas (`AZUL`, `ROJO`, `VERDE`) a un
`PIEL = {...}` con las claves que usan las cinco páginas, y un `DESIGN.md` en la raíz del repo que las
documenta. Las páginas no reciben colores nuevos: leen de `PIEL`.

Rejilla del muro y el costado (medida en el mockup aprobado): `minmax(0, 1fr)` para el muro + `392px` fijos
para el panel derecho, con la miniatura 9:16 de `78px` de ancho en la testera del costado. Bajo ~900 px el
costado pasa al ancho completo, debajo del muro.

## 4 · Los 24 dibujos en el editor

`_TIPOS_VISUAL` (`panel/editor.py:44`) se reemplaza por una tabla derivada del propio modelo. Tres correcciones
al plan original, verificadas en el código:

- `_campos_del_tipo` (`guion.py:288`) es un **`model_validator`**, no una tabla de campos: no se puede leer de
  él qué campo pertenece a qué tipo. La tabla nueva (`visuales.py`) se escribe a mano **una vez** y una prueba
  (`test_visuales.py`) exige que cubra los 24 tipos del `Literal` y que todo campo mencionado exista en
  `Visual.model_fields`. Así el editor nunca se vuelve a quedar en 3.
- `visuales.py:15 TIPOS_VISUAL` es un duplicado **viejo de 4 entradas que no importa nadie**: se borra, y la
  tabla nueva ocupa su nombre.
- `grafico_funcion`, `diagrama_fuerzas` y `circuito` están escritos a mano tres veces en el editor; pasan a
  generarse de la tabla.

- **Agrupación:** `ui.select` de NiceGUI 3.18 **no acepta `optgroup`**, así que la lista queda plana con la
  materia en la etiqueta («Matemática · Polígono regular»). Es un límite real del widget, no una flojera.
- **Miniatura real:** al elegir un tipo se dibuja **un fotograma, sin video**. Verificado en esta sesión:
  `dibujar_visual()` → medir el `VGroup` → armar la `Camera` con ese tamaño → `cam.get_image().save()` toma
  **0,2 s** y no gasta voz ni IA. Dos detalles que el spec anterior tenía mal: manim **no** tiene una ruta
  `--save_last_frame` en este proyecto (se usa como biblioteca con `tempconfig`), y la cámara **no** puede
  heredar el `frame_width=9 / frame_height=16` del render porque el dibujo queda minúsculo en el marco — hay
  que encuadrar desde `dibujo.mobs.width/height`, y `_encajar` no sirve porque solo achica.
  Se guarda en `salida/_miniaturas/<tipo>_<huella>.png`; la huella es el hash de los campos, así que si no
  cambian no se vuelve a dibujar. Si falla, la tarjeta muestra el nombre del dibujo y por qué falló, nunca un
  cuadro gris mudo.

### 4.1 · Área de ingeniería 3D (decisión 7: él la pidió de vuelta)

El spec la había dejado afuera. Verificado en esta sesión con un render de **0,4 s** (`/tmp/mini_3d.png`,
mirado, no supuesto): `ThreeDCamera` + `Cube`/`Cylinder`/`Sphere`/`Cone`/`Torus` sombrea de verdad y **no
necesita video**. Con eso el área 3D entra por la misma puerta rápida que las miniaturas.

Un solo tipo nuevo, no tres: **`solido_3d`**, con dos campos propios:

- `vista`: `frente` · `piso` · `ala` · `axonometrica` (default `axonometrica`) — los cuatro puntos de vista de
  dibujo técnico, resueltos como rotaciones fijas de la cámara.
- `corte`: `sin_corte` · `mitad` (default `sin_corte`) — la pieza se parte por la mitad y la cara de corte se
  sombrea en color de acento. **`mitad` sólo funciona con `figura: cubo`.**

> **Corregido después de medir (2026-10-27).** Este párrafo prometía `horizontal`/`vertical` para cualquier
> cuerpo. Al implementar el dibujo resultó que Manim no tiene z-buffer: pinta cara por cara en el orden que le
> dan (`painter's algorithm`) y para ordenar usa el **centroide proyectado** de cada cara. En un cubo eso
> funciona (los centroides de las 6 caras se ordenan bien). En un cilindro o un cono recortados, la cara plana
> del corte y las 48 tiras de la superficie tienen centroides que caen *dentro* de la silueta del cuerpo, así
> que no hay orden posible que las pinte correcto: el render salía con la tapa amarilla flotando adentro y el
> manto por encima. Medido y mirado en `/tmp/scono_*.png` y `/tmp/scilindro_*.png`. Por eso el corte se reduce
> a `mitad` y sólo para el cubo, que es donde sí se ve bien (`/tmp/w_cubo.png`). Preferimos un `corte` chico y
> honesto antes que cuatro valores que dibujan mal.

Reutiliza la matemática que ya existe: `analizar_solido()` (`visuales.py:538`) da volumen y área, así que las
mismas `anotar` de `solido` (`MARCAS_SOLIDO`, `visuales.py:55`) funcionan en 3D sin duplicar fórmulas. El tipo
`solido` plano **se queda** (es más barato y sirve para pizarra); `solido_3d` es la versión con relieve para
los videos de ingeniería. Las medidas dibujadas salen de los números del guion (un cilindro `r=1, h=4` se dibuja
esbelto y uno `r=3, h=5` pancigordo), no de proporciones fijas.

**La decisión de arquitectura que hace que quepa sin tocar la escena:** `VideoEjercicio` usa cámara 2D y
`dibujar_visual()` devuelve mobs 2D (`escena.py:416`). Metener mobs 3D en esa escena no funciona. Entonces el
3D se renderiza **fuera de línea a un PNG** (el mismo camino de 0,4 s ya probado) y `dibujar_visual()` lo
devuelve como `ImageMobject` dentro del `Dibujo`. Con eso `escena.py` no se toca, la miniatura y el video usan
el mismo dibujo, y el PNG queda cacheado por huella de campos.

El área 3D entra al catálogo **en el hito B, no al final**: la tabla `VISUALES` de `visuales.py` se diseña
previendo tipos nuevos, así que `solido_3d` es una fila más, no un parche. El hito D agrega el dibujo real.

## 5 · Vista previa con TU guion

`panel/paginas/estilos.py` hoy previsualiza con el guion fijo `plantillas/vista_previa.yaml`, cuya fórmula
`(a+b)²` no tiene nada que ver con lo que el autor está escribiendo. Cambio: la miniatura de cada estilo se
genera con **el guion abierto en el editor**, pidiendo tres cuadros (gancho, paso con dibujo, resultado). Si
no hay guion todavía, se usa la plantilla de siempre. Costo: un render corto por estilo visible; se calculan
solo los 4 formatos y se difiere el resto al abrir Estilos.

## 6 · Los 17 temas y dónde pasan a vivir

**Ya promocionados** (commit `677f195`, con su OK de «Sí a todo, adelante»): los 17 viven en
`src/tpi_videos/plantillas/temas/` y sus 14 texturas en `src/tpi_videos/assets/fondos/`, así que viajan con el
motor y las otras copias del repo (Kiro, Claude Code) los ven. Peso real medido: 14 MB de PNG. Se probó bajar
a 720×1280 con paleta de 256 colores: ahorra 6 MB pero borra el grano de la pizarra y aplana las viñetas, así
que quedan a 1080×1920.

`neon_reja`, `neon_cian`, `neon_uva`, `plano_azul`, `plano_noche`, `comic_semitono`, `comic_azul`,
`kraft_tiza`, `kraft_claro`, `vineta_cine`, `vineta_dorada`, `tiza_verde`, `tiza_azul`,
`cuaderno_con_sello`, `cuaderno_tinta_roja`, `rotulador`, `rotulador_fucsia`.

**Falla que deja la promoción** (hay que arreglarla en el hito C): `panel/app.py:59-61` sirve
`/medios/fondos` apuntando a `mis_ajustes/fondos`, que ahora está vacío para estos temas. Un estilo con
textura del paquete no muestra su fondo en el panel. Sale una ruta más (`/medios/fondos_paquete` →
`assets/fondos`) y el generador de URLs de tema la usa cuando la textura viene del paquete.

## 7 · Tres arreglos del motor que salen gratis

Descubiertos al escribir los 17 temas; sin ellos, estos estilos no se pueden elegir desde el panel:

1. **`hoja.etiqueta` se pinta en blanco fijo** (`componentes.py:579`): desaparece en los temas de papel claro.
   Pasa a elegirse por contraste contra `colores.fondo`, con `hoja.color` (papel) si el fondo es oscuro y
   `colores.tenue` si es claro.
   > **Corregido al medir (27-10-2026, al ejecutar A.2):** aquí decía «usa `tema.colores.tenue`» a secas. Al
   > renderizar `salida/_vistas/hoja_de_desarrollo/1_gancho.png` se vio que la etiqueta **no pisa el papel**:
   > va arriba y a la izquierda, sobre el fondo (el `#2A2A2C` difuminado), así que el `tenue` la dejaba gris
   > sobre gris — peor que el blanco de antes. De ahí la regla por luminancia, no un token fijo.
2. **El borde de los subtítulos es negro fijo** (`subtitulos.py:229`, `&H00000000`): con texto oscuro sobre
   crema se embarra. Sale un `subtitulos.color_borde: str` con default `#000000` (nadie cambia el default,
   los temas claros lo ponen en su color de fondo).
3. **El panel ofrece 5 de las 8 letras** (`tipografia.py:38-39`): `PARA_TITULOS` y `PARA_TEXTO` pasan a
   listarse desde `FAMILIAS`.

**Corrección a lo que decía este spec antes de verificar:** en `panel/paginas/estilos.py` **sí** están ya
`fondo.imagen` (`:278`), `formulas_negrita` (`:256`), `emojis` (`:266`) y la hoja (`:323`). Lo único que falta
en el editor de estilos es `nota` (el color de la nota al margen nunca se muestra ni se edita) y las tres
familias de letras que faltan. Y el cierre con CTA-de-engaño de `plantillas/vista_previa.yaml` **ya está
cambiado** (commit `8040180`), junto con `config.py`, `marca.yaml`, `guion_base.yaml` y `moldes.py`.

## 8 · Mis videos: muro con portada garantizada

`biblioteca.miniatura()` (`panel/biblioteca.py:88-106`) devuelve `None` ante cualquier error y la página
dibuja un cuadro gris. Ahora: si el cuadro falla, el panel arma una **portada de reserva** con el texto del
gancho sobre el color del tema (PIL, sin render). Además: buscador por título/materia, filtro
Todo/Borradores/Publicables, y grilla de 9:16 con la etiqueta del formato.

## 9 · Pruebas

Hoy el panel tiene **cero pruebas** (solo `pruebas/test_tareas.py` importa de `tpi_videos.panel`). Esta fase
prueba la lógica, no el widget:

- `test_formatos.py`: resolver `plantillas/formatos.yaml` + `mis_ajustes/formatos.yaml`, la del usuario gana,
  clave desconocida = error con opciones, y `formato_de_guion()` devuelve molde+tema+dibujo coherentes. Cada
  familia punta a un molde que **existe** en `MOLDES` y a dibujos que **existen** en el catálogo.
- `test_puntuar.py`: el puntador marca la familia correcta en las cuatro ideas de ejemplo, no marca ninguna
  con texto vacío o sin palabras de la materia, y **no llama a la IA** (se prueba que `proveedor` nunca se usa).
- `test_visuales.py`: la tabla cubre los 24 tipos del `Literal` de `Visual`, todo campo mencionado existe en
  `Visual.model_fields`, y ninguna clave de `SEGUNDOS_VISUAL` queda fuera. Es la prueba que evita que el editor
  vuelva a quedarse en 3.
- `test_miniaturas.py`: `dibujar_miniatura()` produce un PNG para cada tipo con valores de ejemplo (manim
  `skipUnless`), el encuadre llena el marco (un dibujo chico no puede quedar en 8 px), y la huella repite
  archivo cuando los campos no cambian.
- `test_solido_3d.py`: `solido_3d` valida `vista` y `corte` (y rechaza `corte: mitad` en los cuerpos redondos,
  con un aviso en español), reusa `analizar_solido()` para `volumen`/`area`, y dibuja con `ThreeDCamera` sin
  video: las 16 combinaciones figura×vista se renderizan, **no tocan ningún borde del cuadro** y dejan tinta
  suficiente para que se vea el cuerpo.
- `test_piel.py`: los dos arreglos del motor (etiqueta con `tenue`, `color_borde` llega al ASS), la ruta
  `/medios/fondos_paquete` resuelve una textura del paquete, y la portada de reserva se genera con un tema
  cualquiera.
- Protocolo manual obligatorio por hito: `./tpi revisar` de un guion propio, render de borrador y **inspección
  de los cuadros sacados con `extraer_cuadro`** (así se encontraron los 4 defectos de los 17 temas). Mirar los
  cuadros, no solo que el render termine.

## 10 · Orden de implementación

Cuatro hitos, cada uno termina con pruebas verdes, `ruff`, `./tpi revisar`, un render verificado **mirando los
cuadros** y un commit con `git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com'`:

0. **Cerrar la casa antes de mudarse:** rematar lo pendiente de la fase 11 y decidir los dos guiones sueltos
    (`guiones/centro_de_gravedad_en_una_placa.yaml` y `guiones/el_tanque_que_pierde.yaml`, que duplica un
    guion ya versionado). Nada de esta fase toca `dibujos.py` hasta terminar acá.
1. **Hito A · Motor:** los 3 arreglos de la sección 7 + `formatos.yaml` con sus 4 familias + el puntador, con
    pruebas.
2. **Hito B · Editor:** la tabla `VISUALES` (con fila reservada para `solido_3d`), los 24 dibujos con campos
    derivados, la miniatura real de 0,2 s y el LaTeX en vivo con freno de 400 ms.
3. **Hito C · Piel y muro:** tokens en `PIEL` + `DESIGN.md`, las cuatro pantallas con el detalle al costado,
    Mis videos con portada garantizada, la vista previa con el guion del autor y la ruta de fondos del paquete.
4. **Hito D · Ingeniería 3D:** `solido_3d` con `ThreeDCamera`, sus cuatro vistas y el corte a la mitad (sólo
    cubo, ver §4.1), más el dibujo en la hoja y en la miniatura.

## Fuera de alcance (explícito)

- **Tablero con estado nuevo** (opción «B» del diagnóstico): el usuario la rechazó. No se crea un sistema de
  seguimiento de proyectos.
- Marcos distintos de `pizarra`/`hoja`, glow que pulse y **movimiento de cámara animado**: requieren código de
  Manim que aún no existe (la fase de zoom y pantalla partida, tarea #18, sigue pausada por orden del
  usuario). El hito D usa **cámara fija** en cuatro puntos de vista, no una cámara que se mueve.
- Cualquier llamada a IA paga. Todo lo de esta fase se puede probar sin gastar cuota.
- Tomas reales, montaje de video y efectos de magia filmados: el motor dibuja vectores.
- Empujar o fusionar a la rama compartida: solo con su OK explícito (los ~15 commits pendientes quedan en su
  copia hasta que él diga).

## Riesgos

- **Costo de las miniaturas:** 17 temas × 3 cuadros ≈ 51 renders cortos si alguien abre Estilos sin filtro.
  Se calculan a lo sumo 4 por pantalla y se cachean por huella (`vista_previa._huella` ya hace esto).
- **`_huella(tema)` solo mira el tema** (`vista_previa.py:28`): en cuanto la vista previa use el guion del
  autor, el cache viejo mostraría el guion anterior. La huella pasa a incluir el hash del guion, y la prueba
  de `test_miniaturas.py` exige que cambiar el guion cambie la huella.
- **`ui.select` sin grupos** puede sentirse largo (24 entradas). Si molesta, se parte en dos selects
  (materia → dibujo) sin tocar el modelo.
- **El 3D puede verse distinto en el video y en la miniatura** porque uno va sobre el fondo del tema y otro
  sobre papel: se resuelve pasando el color de fondo a la función de dibujo, igual que ya hace el parámetro
  `papel`, y se comprueba mirando los dos cuadros.
- **`ThreeDCamera` no encuadra igual que la cámara 2D:** hay que medir el `VGroup` y ajustar la distancia de
  cámara, no el alto del marco. Verificado con el cuadro de prueba de 0,4 s.
