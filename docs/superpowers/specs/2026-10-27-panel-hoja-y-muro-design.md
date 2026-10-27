# Diseño: Fase 12 · Formato, piel y muro: un panel que te deja elegir

Aprobado por el usuario el 27-10-2026 en esta conversación, en cuatro decisiones separadas: (1) el camino de
cuatro pasos sin candados, (2) la piel «muro + hoja», (3) que todo lo que decida la IA se muestre con su valor
y un «cambiar», y (4) más estilos de impacto con explicación visual.

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

Cuatro cosas, en este orden, cada una con su prueba:

1. Un **formato** que casa molde + estilo + dibujo y se puede cambiar.
2. El camino de **cuatro pantallas** (Idea → Formato → La hoja → Video) sin candados.
3. **Los 24 dibujos en el editor**, con los campos de cada uno y una miniatura real.
4. **Tres arreglos del motor** que hoy obligan a editar YAML a mano.

## 1 · Formato = molde + tema + dibujo

Hoy `molde` y `tema` son dos campos independientes que la IA elige por separado: un «dato» y un «problema»
se ven idénticos en pantalla. El formato los casa.

**Qué es un formato:** una entrada de `plantillas/formatos.yaml` (nuevo, versionado con el motor) con
`clave`, `nombre`, `molde`, `tema`, `dibujo_sugerido`, `etiqueta_corta` y `color`. Los cuatro formatos de la
primera pantalla son los moldes que ya existen:

| Formato | Molde real (`moldes.py`) | Dibujo que suele cargar la explicación |
|---|---|---|
| Un dato que engaña | `nadie_te_enseno` | `poligono_regular`, `tanque`, `circulo_trig` |
| Un problema vivido | `pov` | `circuito`, `proyectil`, `pendulo` |
| Un error de la materia | `mito_realidad` / `tres_errores` | `diagrama_fuerzas`, `viga`, `optica` |
| Un ejercicio resuelto | `reto` | `barras`, `torta`, `probabilidad` |

**Dónde puede sobrescribirlo el usuario:** `mis_ajustes/formatos.yaml`, con la misma regla que ya rige para
los temas propios (`temas.py:1-8`): Git ignora `mis_ajustes/`, así que actualizar el motor nunca choca con lo propio, y una clave repetida gana en la copia del usuario.

**Cómo se elige:** hoy **no existe** un clasificador barato: `ideas.py` llama a la IA y `moldes.py` solo
tiene sinónimos (`_OTRAS_PALABRAS`, `normalizar_molde`). El paso nuevo es un puntador de palabras de ~30
líneas en `moldes.py` —sin IA ni cuota— que lee la idea y marca la tarjeta más probable; si no reconoce nada,
no marca ninguna y las cuatro quedan igual de accesibles. Las cuatro tarjetas quedan visibles con su
portada y su botón «cambiar». Elegir una tarjeta **nunca** bloquea: si el autor prefiere otro molde o otro
estilo, los cambia por separado en la misma tarjeta.

## 2 · Las cuatro pantallas

- **Idea** — un solo campo de texto y un botón. Arriba, la frase que él escribió; abajo, las cuatro tarjetas.
- **Formato** — la tarjeta elegida queda arriba a la izquierda, en grande, con sus tres piezas (molde,
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

## 4 · Los 24 dibujos en el editor

`_TIPOS_VISUAL` (`panel/editor.py:44`) se reemplaza por una tabla derivada del propio modelo:
`_campos_del_tipo` y `Visual.model_fields` (`guion.py`) ya dicen qué campos tiene cada tipo y cuál es su
valor por defecto. El editor deja de mantener su propia copia de esa información (hoy `grafico_funcion`,
`diagrama_fuerzas` y `circuito` están escritos a mano tres veces).

- **Agrupación:** `ui.select` de NiceGUI 3.18 **no acepta `optgroup`**, así que la lista queda plana con la
  materia en la etiqueta («Matemática · Polígono regular»). Es un límite real del widget, no una flojera.
- **Miniatura real:** al elegir un tipo, se encola un trabajo `TAREAS` que corre manim con
  `--save_last_frame` (≈4 s, sin voz ni IA) y guarda `salida/_miniaturas/<tipo>_<huella>.png`. La huella es
  el hash de los campos: si no cambian, no se vuelve a renderizar. Si el render falla, la tarjeta muestra el
  nombre del dibujo y por qué falló, nunca un cuadro gris mudo.

## 5 · Vista previa con TU guion

`panel/paginas/estilos.py` hoy previsualiza con el guion fijo `plantillas/vista_previa.yaml`, cuya fórmula
`(a+b)²` no tiene nada que ver con lo que el autor está escribiendo. Cambio: la miniatura de cada estilo se
genera con **el guion abierto en el editor**, pidiendo tres cuadros (gancho, paso con dibujo, resultado). Si
no hay guion todavía, se usa la plantilla de siempre. Costo: un render corto por estilo visible; se calculan
solo los 4 formatos y se difiere el resto al abrir Estilos.

## 6 · Los 17 temas y dónde pasan a vivir

Ya están escritos y **renderizados uno por uno** en esta sesión, en `mis_ajustes/temas/` (8 de impacto y 9
variantes) con sus 13 texturas en `mis_ajustes/fondos/`:

`neon_reja`, `neon_cian`, `neon_uva`, `plano_azul`, `plano_noche`, `comic_semitono`, `comic_azul`,
`kraft_tiza`, `kraft_claro`, `vineta_cine`, `vineta_dorada`, `tiza_verde`, `tiza_azul`,
`cuaderno_con_sello`, `cuaderno_tinta_roja`, `rotulador`, `rotulador_fucsia`.

**Decisión que hay que tomar con él (esta fase no la impone):** si le gustan, se promueven a
`src/tpi_videos/plantillas/temas/` y sus PNG a `src/tpi_videos/assets/fondos/`, para que viajen con el motor
y las otras copias del repo (Kiro, Claude Code) los vean. Hoy viven en `mis_ajustes/`, que Git ignora: son
solo de esta máquina. Peso: ~6 MB de PNG.

## 7 · Tres arreglos del motor que salen gratis

Descubiertos al escribir los 17 temas; sin ellos, estos estilos no se pueden elegir desde el panel:

1. **`hoja.etiqueta` se pinta en blanco fijo** (`componentes.py:579`): sobre papel claro desaparece. Pasa a
   usar `tema.colores.tenue`.
2. **El borde de los subtítulos es negro fijo** (`subtitulos.py:229`, `&H00000000`): con texto oscuro sobre
   crema se embarra. Sale un `subtitulos.color_borde: str` con default `#000000` (nadie cambia el default,
   los temas claros lo ponen en su color de fondo).
3. **El panel ofrece 5 de las 8 letras** (`tipografia.py:38-39`): `PARA_TITULOS` y `PARA_TEXTO` pasan a
   listarse desde `FAMILIAS`, y se agregan al selector de Estilos `fondo.imagen`, `nota.color`,
   `formulas_negrita`, `emojis` y el borde del subtítulo.

## 8 · Mis videos: muro con portada garantizada

`biblioteca.miniatura()` (`panel/biblioteca.py:88-106`) devuelve `None` ante cualquier error y la página
dibuja un cuadro gris. Ahora: si el cuadro falla, el panel arma una **portada de reserva** con el texto del
gancho sobre el color del tema (PIL, sin render). Además: buscador por título/materia, filtro
Todo/Borradores/Publicables, y grilla de 9:16 con la etiqueta del formato.

## 9 · Pruebas

Hoy el panel tiene **cero pruebas** (solo `pruebas/test_tareas.py` importa de `tpi_videos.panel`). Esta fase
prueba la lógica, no el widget:

- `test_formatos.py`: resolver `plantillas/formatos.yaml` + `mis_ajustes/formatos.yaml`, la del usuario gana,
  clave desconocida = error con opciones, y `formato_de_guion()` devuelve molde+tema+dibujo coherentes.
- `test_editor_visual.py`: la tabla de tipos del editor se deriva de `Visual` (24 tipos, campos correctos,
  ida y vuelta formulario↔YAML sin perder datos) — es la prueba que evita que el editor vuelva a quedarse en 3.
- `test_piel.py`: los dos arreglos del motor (etiqueta con `tenue`, `color_borde` llega al ASS) y que la
  portada de reserva se genera con un tema cualquiera.
- Protocolo manual obligatorio por hito: `./tpi revisar` de un guion propio, render de borrador y **inspección
  de los cuadros sacados con `extraer_cuadro`** (así se encontraron los 4 defectos de los 17 temas).

## 10 · Orden de implementación

Cuatro hitos, cada uno termina con pruebas verdes, `ruff`, `./tpi revisar`, un render verificado y un commit:

1. **Cerrar la casa antes de mudarse:** rematar o aparcar lo pendiente de la fase 11 (bloques/engranajes/Mohr).
2. **Motor:** los 3 arreglos de la sección 7 + `formatos.yaml` con sus 4 formatos y pruebas.
3. **Editor:** los 24 dibujos con campos derivados, miniatura real y LaTeX en vivo.
4. **Piel y muro:** tokens en `PIEL` + `DESIGN.md`, las cuatro pantallas, Mis videos con portada garantizada y
   la vista previa con el guion del autor.

## Fuera de alcance (explícito)

- **Tablero con estado nuevo** (opción «B» del diagnóstico): el usuario la rechazó. No se crea un sistema de
  seguimiento de proyectos.
- Marcos distintos de `pizarra`/`hoja`, glow que pulse y movimiento de cámara: requieren código de Manim que
  aún no existe (la fase de zoom y pantalla partida, pausada por orden del usuario).
- Cualquier llamada a IA paga. Todo lo de esta fase se puede probar sin gastar cuota.
- El cierre «Sígueme para más ejercicios» de `plantillas/vista_previa.yaml:33` es el CTA-de-engaño que el
  usuario prohibió en sus videos. Se cambia a una línea neutra **solo con su OK**, porque sale en cada
  fotograma de las vistas previas.

## Riesgos

- **Costo de las miniaturas:** 17 temas × 3 cuadros ≈ 51 renders cortos si alguien abre Estilos sin filtro.
  Se calculan a lo sumo 4 por pantalla y se cachean por huella (`vista_previa._huella` ya hace esto).
- **`ui.select` sin grupos** puede sentirse largo (24 entradas). Si molesta, se parte en dos selects
  (materia → dibujo) sin tocar el modelo.
- **Los temas con textura pesan:** un PNG 1080×1920 con ruido llega a 3 MB. Las texturas se guardan como
  JPEG de calidad 80 dentro de `assets/fondos/` si el peso molesta en el paquete.
