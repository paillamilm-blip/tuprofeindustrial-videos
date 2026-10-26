# Diseño: Fase 9 · Fábrica (un tema, un botón) + dificultad repartida

Aprobado por el usuario el 25-10-2026 en esta conversación, sobre el prototipo `fabrica-v3` mostrado en el
chat: «un solo campo y un solo botón», «que la IA reparta la dificultad sola», **cero selectores nuevos de
opciones**, calidad final (no borradores), y que el panel le entregue la carpeta donde quedan los videos.
Antes de escribir código pidió un mock minimalista y moderno; al verlo dijo «NO DEJEMOSLO COMO ESTABA».

Rama: `feat/fabrica-y-dificultad`. Versión del paquete: **0.8.0**.

## Contexto: el lote ya existe, pero está escondido

v0.7 dejó `tpi lote "Tema"` y el botón «Hacer los 3 videos» **dentro de la pestaña Crear → Ideas**, que es la
pantalla del editor de guiones: cuatro solapas, tarjetas, estilos, botones de borrador. Para una profesora que
no programa, eso es un laboratorio, no una fábrica. Cada vez que quiere contenido tiene que entrar al sitio
donde se revisan los detalles y buscar el botón grande.

Lo segundo: las ideas no tenían nivel. El campo `nivel` es el **curso** («2° medio»), y la IA lo usaba para
el vocabulario, no para cuán difícil es el ejercicio. Resultado: tres ideas del mismo nivel de dificultad, y
ella no puede publicar una secuencia que empiece fácil y termine desafiante.

## Qué hace esta fase

1. **Pantalla Fábrica** (`src/tpi_videos/panel/paginas/fabrica.py`), que pasa a ser la portada del panel (`/`):
   un campo, un botón, el avance por video y los resultados con sus carpetas. «Crear» baja a `/crear` y sigue
   siendo el laboratorio para quien quiera revisar todo a mano.
2. **`dificultad` en la idea** (`facil` / `media` / `dificil`): la IA las reparte distintas en las 3 ideas y el
   redactor recibe la pista de hasta dónde llegar. `--dificultad` las fuerza las 3 cuando ella quiere una serie
   de un solo nivel.

No hay pipeline nuevo: la Fábrica arma el comando `tpi lote -- "Tema"` y lo corre con `TAREAS`, el mismo
mecanismo del v0.7.

## 1 · La pantalla

Tres zonas en la misma página, una visible a la vez, para que no haya saltos ni recargas:

- **Entrada:** título, un `ui.input` de Tema, seis temas sugeridos que rellenan el campo (no son opciones: son
  atajos), un solo botón primario rojo «Crear los 3 videos», y un enlace para «Elegirlas una por una» si
  prefiere el editor. Si falta la clave de Gemini, aparece un aviso arriba con enlace a Ajustes; sin clave el
  lote igual funciona porque `redactor` cae a la plantilla, así que es aviso, no bloqueo.
- **Trabajo:** barra, porcentaje, el detalle que manda el lote y **una fila por video**. El lote ya prefixes
  cada aviso con «Video 2 de 3 · …», así que la fila se arma con ese número: terminado / trabajando ahora /
  en espera. El título real de la idea se levanta del aviso «Voy con «…»», que también manda el lote. Cancelar
  queda visible y el aviso de los 60 s de espera también.
- **Resultado:** «N de 3 videos listos», botón **«Abrir la carpeta»** (Finder en `salida/`), y una fila por
  video con su duración, ángulo y dificultad, la ruta corta del mp4, «Ver el video», «Kit de publicación» y, si
  corresponde, los «Por revisar» y el enlace «Achicar el guion» → `/crear?guion=…`.

**Error por video, no por lote.** Si una idea falla, la fila roja trae el motivo, la ayuda y **«Intentar solo
este»**, que relanza `tpi lote --ideas-json` con esa idea suelta. Por eso `ItemLote.como_dict()` ahora incluye
`"idea"`: el panel reintenta sin volver a pedirle ideas a Gemini.

**Si el trabajo entero se cae** (Gemini sin clave real, motor que no arranca), la pantalla de resultado muestra
la tarjeta roja «Nada salió» con el motivo, «Volver a intentar» y «Revisar Ajustes». Cancelar vuelve a la
pantalla de entrada con un aviso: lo que ya terminó queda en `salida/`.

## 2 · La dificultad

- `ideas.py`: `DIFICULTADES` (las etiquetas que se muestran), `DIFICULTAD_PISTA` (qué le pedimos al redactor en
  cada nivel) y `dificultad_normal()`, que acepta lo que Gemini escriba (`"Fácil"`, `"básico"`, `"muy
  avanzado"`) y devuelve `facil`/`media`/`dificil`, o `""` si no la reconoce. Nunca inventa un nivel.
- La plantilla `ia/ideas.md` define los tres niveles y dice que **las 3 ideas usan dificultades distintas**, y
  que la dificultad no es el curso: subir el nivel son más pasos o una trampa, no un tema de un año superior.
- `proponer_ideas(..., dificultad=)` fuerza las 3 (para `--dificultad`), `producir(..., dificultad=)` le pasa la
  pista al redactor, y `lote`/`cli` conectan ambos. `tpi ideas`, `tpi producir` y `tpi lote` aceptan
  `--dificultad facil|media|dificil`.
- Donde se muestra: `_mostrar_ideas`/`_mostrar_lote` en la Terminal y la fila de resultado en el panel.

## 3 · Navegación

`PAGINAS` pasa a 5 entradas: **Fábrica** (`/`), **Crear** (`/crear`), **Mis videos**, **Estilos**, **Ajustes**.
Se conserva «Crear» en el menú aunque la Fábrica lo reemplace en el uso diario: ahí está el editor de guiones,
y la Fábrica enlaza a él para achicar un guion. Los enlaces previos a `/` desde otras páginas (`videos.py` →
«Ir a Crear`) apuntan ahora a `/crear`.

## Diseño y accesibilidad

El mock usaba la tipografía ideal de la marca; el panel real va con los tokens que ya existen en `comun.py`
(`.tpi-hoja`, `.tpi-titulo`, iconos Material Symbols) para que la Fábrica se vea hermana de las otras páginas.
Dos cosas del mock sí entran al código: **un solo CTA primario por pantalla** y ningún emoji como icono. Los
estados (hover, deshabilitado, error, vacío) son los de NiceGUI. Se añade `GRIS = "#6B6B6B"` para el texto
secundario sobre blanco: el gris que estaba en uso daba 3,2:1.

## Pruebas

- Ruff y `python -c "import ..."` de todas las páginas.
- Gemini falso (`fake_gemini.py`, puerto 8899) con las 3 ideas de `dificultad` `media`, `Fácil` y un valor
  inventado: se comprueba que la tabla imprime Media / Fácil / vacío, y que `--dificultad dificil` fuerza las 3.
- Lote de borradores real (`tpi lote --borrador`) para ver la forma del payload que consume el panel.
- Panel en el navegador con el lote de verdad: apretar el botón, ver las tres filas moverse, Cancelar, y en el
  resultado abrir carpeta, «Intentar solo este» y «Achicar el guion». Se prueba con la voz de `marca.yaml` en
  `silencio` para que el render no dependa de internet (y se revierte antes de commitear).

## Fuera de alcance

Publicación programada, calendario, métricas (eso es lo que sigue), y cualquier selector de ángulo, materia o
nivel en la Fábrica: la regla es un campo y un botón.
