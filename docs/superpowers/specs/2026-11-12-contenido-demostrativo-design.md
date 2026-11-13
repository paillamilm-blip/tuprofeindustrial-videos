# El dibujo demuestra, no decora

Fecha: 12 de noviembre de 2026.
Base verificada: `main` en `889f618` (merge del PR #51, Estudio de una pantalla). Las líneas citadas son de esa base; volver a localizarlas por símbolo si se desplazan.
Destino: Kiro, implementación en el motor existente.
Estado: diseño propuesto para ejecutar el encargo del dueño; este documento no implementa funciones.
Plan asociado: ../plans/2026-11-12-contenido-demostrativo-kiro.md

## 1. Encargo y límite

Permitir que Matemática, Física e Ingeniería se expliquen como dato, mito, error, ejercicio o una combinación. El contenido determina la explicación; después se recomiendan herramientas visuales y una apariencia. No es otra aplicación ni una limpieza del catálogo.

Este diseño es la etapa siguiente que el propio diseño aprobado de la familia Consola deja pendiente (`2026-11-12-familia-consola-design.md`, sección «Pendiente»): «que el contenido decida cómo enseñar (dato, mito, error, ejercicio)… Primero un solo ejemplo para validar la idea». La familia Consola neón ya está implementada (PR #40/#41/#45): cinco variantes que hoy atan apariencia y herramientas. Este encargo separa esas dos cosas sin borrar la familia ni resucitar los 20 estilos archivados como catálogo.

Este diseño REEMPLAZA, únicamente para la prioridad 6, la propuesta de agrupar estilos del diseño y plan `2026-11-11-auditoria-prioridades*`. No ejecutar las tareas de agrupación de esos documentos para cumplir este encargo. Su numeración 5a/5b/5c tampoco describe los cambios de voz y gancho realizados en esta conversación. No borrar esos documentos históricos.

Fuera de alcance: borrar estilos, migrar todos los guiones, cambiar preferencias del dueño, reescribir los dibujos 3D, crear otros moldes masivamente, cambiar la web, instalar dependencias, prometer viralidad, añadir proveedores de IA o un sistema automático de publicación.

La corrección de «Solo el gancho» ya está en `main`: commit `5a10033` («fix: conservar ajustes en clips de gancho», PR #42). La rama antigua `fix/gancho-hereda-ajustes` (`449e48f`) es redundante: no fusionarla ni borrarla sin autorización. La base `889f618` ya incluye ese comportamiento; no reimplementarlo. Este plan no autoriza la implementación ni su publicación en main por parte del agente que redacta el documento.

## 2. Lo que pidió el dueño y lo que no debe inferirse

Instrucciones originales recuperadas y contrastadas en la conversación:

- 25 de octubre: «niveles de dificultad para los ejercicios o tips o datos».
- 27 de octubre: elegir libremente estructuras en un panel sencillo, con nombre, explicación y estilo sugerido; familias de retos/trampas, desarrollo dinámico, datos/historias visuales y cálculo mental.
- 28 de octubre: pregunta que cause curiosidad, respuesta y explicación del porqué.
- 29 de octubre: «todos los videos se ven iguales», procedimientos poco claros y tomas planas.
- 1 de noviembre: no alcanza a leer; algunos temas necesitan explicaciones más largas; recomienda estilo, materia, nivel y dificultad con posibilidad de cambiar.
- 9 de noviembre: «Respeta siempre el tiempo físico aunque la voz se alargue».
- 10 de noviembre: para un video concreto de número de oro, 60 segundos con más ejemplos visuales y comprobación del MP4 final.
- 11 de noviembre: aprender de la relación entre dibujos, explicación, tono y fluidez, no solo del fondo.
- 12 de noviembre: «una pantalla simple donde me pida la idea, el nivel, el tipo de contenido (mito, error u otro)…». Ese pedido ya se materializó en Estudio (PR #51): los chips de tipo eligen el MOLDE narrativo, no la intención educativa. Este encargo añade la intención sin confundirla con el molde ni con la apariencia.

No convertir un pedido de 60 segundos en duración universal. No atribuir al dueño una garantía de marketing ni un formato fijo de ejercicio para cada contenido. Las invitaciones a comentar narradas de pedidos antiguos no sustituyen las reglas actuales de la plantilla: no añadir bait a la voz.

## 3. Diagnóstico verificado

| Capa actual (base 889f618) | Hecho | Cambio necesario |
| --- | --- | --- |
| `guion.py:1158` `Resultado` | `tex: str = Field(min_length=1)` y `voz` obligatoria: la fórmula final es la barrera. | Añadir `Resultado.texto` opcional y relajar `tex` a `""` solo cuando el contenido no es ejercicio; conservar voz obligatoria. |
| `guion.py:1205` `Guion` | Requiere enunciado, pasos y resultado; no hay intención ni recursos. | Añadir `contenido` y `recursos` opcionales; conservar `llamado` (`guion.py:1227`) y los bloques actuales. |
| `guion.py:1098` `Paso` | `tex: str \| None` ya es opcional. | No cambiar: el paso solo hablado ya existe. |
| `escena.py:1410` | `if paso.tex is None:` ya dibuja un paso solo hablado. | Reutilizar esa rama; no crear otro camino para pasos sin fórmula. |
| `redactor.py:427` y `1618` | GuionIA clasifica solo `es_ejercicio`; redactar rechaza toda respuesta falsa. | Renombrar a `es_contenido_educativo`; aceptar contenido STEM suficiente, no solo ejercicios. |
| `redactor.py:126` `PasoIA.mapa` | Ya existe `mapa: list[MapaIA]` con validador semántico (`_mapa`, `redactor.py:927`). | Reutilizarlo; no incorporar un segundo formato de mapas. |
| `redactor.py:1203` y `1237` `a_guion` | Siempre escribe `tex` de paso y serializa `resultado` solo con `tex`/`voz`. | Omitir `tex` vacío; serializar `resultado.texto` cuando exista. |
| `ideas.py:94` `Idea` | Dato curioso y error son ángulos; el enunciado sigue descrito como «ejercicio completo y resoluble». | Persistir intención y objetivo; el enunciado pasa a ser premisa O afirmación según el contenido. |
| `temas.py:233` `Gramatica` | tabs/panel/mapa_color/micro son banderas del tema (`bool=False`). | Componer recursos por guion sobre el tema cargado, sin mutarlo. |
| `temas.py:263` `Tema` / familia Consola | Las cinco variantes atan herramientas: `consola_pasos` todas activas, `consola_mito` solo `mapa_color`. | La recomendación nace de la estructura real del guion, no de la variante; un mito+ejercicio puede llevar panel. |
| `render.py:202` y `354` | `estilo_video`/`estilo` se cargan con `cargar_tema(resolver_tema(...))`. | Componer la gramática efectiva en ese mismo punto, para video y clip de gancho. |
| `panel/paginas/estudio.py:82` y `panel/qc.py:198` | Estudio es la pantalla principal; la ficha de QC conserva el único selector de estilo (`cambiar_estilo:244`). | Mostrar intención y herramientas en Estudio y en la ficha de QC, sin segundo selector de apariencia. |
| `plantillas/temas/archivo/` | Los 20 estilos antiguos están archivados pero `cargar_tema` los encuentra por nombre. | No resucitarlos como catálogo; usar `hoja_de_desarrollo` archivada solo como prueba de regresión de capacidad. |

Las ubicaciones corresponden a la base `889f618`; volver a localizarlas por símbolo si se desplazan.

## 4. Diseño mínimo

### Cuatro dimensiones distintas

1. **Materia y público:** Matemática/Física/Ingeniería, nivel y carrera existentes. Dificultad continúa separada del curso; conservar la elección actual de Idea y sus pistas.
2. **Contenido:** intención educativa y objetivo concreto. Ejemplo: «mito + ejercicio: demostrar que duplicar la arista multiplica el volumen por ocho».
3. **Molde:** cómo se cuenta, con el catálogo existente. Un mito no exige obligatoriamente un cálculo incorrecto en pantalla; eso solo ocurre si se elige un molde que lo pide. Los chips de tipo de Estudio siguen eligiendo molde, no intención.
4. **Apariencia y herramientas:** la apariencia conserva su único selector en la ficha de QC. Progreso, resumen, relaciones por color y énfasis se deciden por contenido y se pueden cambiar sin cambiar de apariencia. La familia Consola sigue siendo el catálogo de apariencias; este encargo no la reemplaza.

### Esquema opcional y compatible

Añadir en `guion.py`, usando el `_Base` existente (`extra="forbid"`):

- `Contenido.intenciones`: lista no vacía, máximo cuatro, de `dato`, `mito`, `error`, `ejercicio`; sin duplicados y conservando el orden.
- `Contenido.objetivo`: texto no vacío de hasta 260 caracteres.
- `Guion.contenido: Contenido | None = None`.
- `RecursosDidacticos`: `tabs`, `panel`, `mapa_color`, `micro`, cada uno `StrictBool | None = None`.
- `Guion.recursos: RecursosDidacticos | None = None`.
- `Resultado.texto: str | None = None`, conclusión visible no matemática.
- `Resultado.tex: str = ""`; conservar `voz` obligatoria y los campos actuales (`emoji`, `destello`).

Interpretación de recursos: `true` activa; `false` desactiva; ausente/null usa la recomendación del nuevo contenido o hereda el tema si no hay contenido explícito. El escritor YAML omite los null, nunca los false.

**Sin contenido nuevo, el guion sigue siendo un ejercicio:** requiere `resultado.tex` no vacío y conserva exactamente la escena antigua. Con intención `ejercicio`, sola o combinada, también requiere fórmula final. Sin `ejercicio`, requiere conclusión visible en `resultado.texto` o `resultado.tex`, además de la voz y al menos un paso. Rechazar texto/fórmula compuestos solo de espacios.

Se conservan `enunciado`, `pasos`, `resultado`, `verificacion`, `reto`, `cierre`, `llamado` y la secuencia de voz. Para no-ejercicios, enunciado significa la premisa/contexto y resultado significa la conclusión. No añadir bloques vacíos, números de relleno ni LaTeX que solo disimule una oración. No hacer opcionales todos los bloques: sería una refactorización transversal innecesaria.

Una conclusión con fórmula y texto usa la fórmula como pieza principal y el texto como interpretación. Los guiones antiguos, sin texto de resultado, toman la rama de dibujo original sin modificaciones. El paso solo hablado (`paso.tex is None`) ya está soportado por `escena.py:1410`; no hay que inventarlo.

### Ejemplo del nuevo contrato

```yaml
titulo: "La tangente no es la curva"
materia: matematica
contenido:
  intenciones: [dato]
  objetivo: "Distinguir la curva de la recta que representa su pendiente local."
recursos:
  panel: false
  micro: false
gancho:
  texto: "¿Esta recta es la curva?"
  voz: "¿Esta recta es la curva?"
enunciado:
  texto: "Una tangente describe la pendiente de una curva en un punto."
  voz: "Compara la curva con la recta que la toca en un punto."
pasos:
  - nota: "Pendiente local"
    voz: "La tangente cambia mientras recorre la curva. Su pendiente es local."
    visual:
      tipo: grafico_funcion
      funcion: "x^2"
      rango: [-2, 2]
      eje_x: "x"
      eje_y: "y"
      movimiento: tangente
      desde: -1
      hasta: 1
resultado:
  texto: "La tangente muestra la pendiente en un punto."
  voz: "La recta no reemplaza la curva. Describe cómo cambia justo en ese punto."
```

El ejemplo debe validarse en la implementación; hoy el esquema no lo admite (`Resultado.tex` exige fórmula y no existe `contenido`). El tipo de dibujo es `grafico_funcion` (`guion.py:207`), no `grafico`. No se presenta como función disponible.

## 5. Recomendaciones y composición

Nuevo módulo pequeño `didactica.py`, sin dependencias de NiceGUI ni imports de Manim. Los modelos viven en `guion.py`; el módulo solo resuelve decisiones y una copia de Tema.

`RecursoDidactico`, dataclass congelada: `clave: str`, `activo: bool`, `sugerido: bool`, `razon: str`, `origen: str`. Origen: `guion`, `contenido`, `tema`.

`recursos_del_guion(guion: Guion, tema: Tema) -> list[RecursoDidactico]` devuelve en orden tabs/panel/mapa_color/micro.

Para contenido explícito, la sugerencia nace de la estructura real del guion (no de la variante de Consola):

| Recurso | Regla sugerida | Razón visible |
| --- | --- | --- |
| tabs | tres o más pasos | «N pasos: permite seguir el avance»; si menos, «Pocos pasos: el contador no aporta». |
| panel | dos o más fórmulas de pasos correctos | «Conserva las fórmulas correctas para comparar»; si no, «No hay suficientes fórmulas que resumir». |
| mapa_color | existe al menos un `paso.mapa` válido | «Relaciona las partes ya indicadas en el guion»; si no, «El guion no trae relaciones por color». |
| micro | false | «El énfasis continuo queda apagado; puedes activarlo». No apagar ni modificar el movimiento físico o la cámara existente. |

Así, un `mito + ejercicio` con fórmulas correctas recibe panel aunque su variante sea `consola_mito` (que hoy solo activa mapa_color); y un `dato` sin fórmulas no recibe panel aunque su variante sea `consola_pasos`. La apariencia no decide las herramientas.

Sin contenido explícito: sugerencia y estado base heredan las cuatro banderas del tema. Cualquier override no-null del guion manda. Las razones describen datos reales, no «la IA recomienda» sin explicación. Un mapa sin datos o panel sin fórmulas puede activarse, pero informar que no tendrá contenido; no inventar vínculos ni bloquear la producción.

Resolución por recurso (referencia):

```python
base = getattr(tema.gramatica, clave)
sugerido = recomendaciones[clave][0] if guion.contenido else base
manual = getattr(guion.recursos, clave) if guion.recursos else None
activo = sugerido if manual is None else manual
origen = "guion" if manual is not None else ("contenido" if guion.contenido else "tema")
```

`componer_tema(tema: Tema, guion: Guion) -> Tema` copia profundamente y aplica las banderas resueltas. No cambia nombre, colores, fuentes, fondo, marco, resplandor, animación de escritura ni paleta; no escribe archivos ni preferencias. Conserva la resolución de clave mediante `temas.resolver_tema` (`temas.py:140`), sin otro resolver de apariencia.

Cuando un override o nuevo contenido modifica la gramática, reservar geometría para panel y subtítulos. El caso heredado íntegro no reajusta layout. Con panel recién activado y banda ausente, usar `copia.layout.banda_panel or 1.6`; zona inferior inicial `max(y_actual, -2.2)`. Los pisos por marco están en `componentes._ZONAS` (`componentes.py:139`): pizarra -2.4, hoja -3.55. El contrato definitivo es geométrico: objetos completos dentro del cuadro; separación mínima 0,3 unidades entre desarrollo/conclusión, subtítulos y resumen en coordenadas normalizadas de pantalla, también con cámara acercada. Las pruebas de escena y MP4 mandan sobre la propuesta inicial; cualquier ajuste debe afectar solo composición explícita y acompañarse de prueba roja-verde.

## 6. IA y recorridos

GuionIA debe clasificar mediante `es_contenido_educativo: bool`, no el antiguo `es_ejercicio` (`redactor.py:427`). Cambiar a la vez todas las referencias: `redactor.py` (427, 428, 477, 555, 635, 711, 1618), `pruebas/ia_falsa.py` (16, 89) y el servidor falso `scripts/gemini_falso.py` (reutiliza `respuesta` de `pruebas/ia_falsa.py`); sin alias temporal. La clasificación permite contenido STEM suficiente para explicar; rechaza pedidos ajenos a STEM o incompletos. El parámetro opcional `contenido: Contenido | None` en `redactar` (`redactor.py:1545`, firma que hoy termina en `carrera`) manda sobre lo inferido, igual que materia/nivel/carrera; no fuerza aceptar una entrada imposible.

IA devuelve `contenido`, `resultado_texto`, fórmula opcional y datos del dibujo en el esquema fijo. `resultado_tex` (`redactor.py:454`) pasa a tener default `""`; se añade `resultado_texto`. No devuelve código. La salida pasa por Guion, LaTeX cuando hay fórmula, revisión de formato y revisor docente. Mantener las rondas de corrección y avisos. Los mapas de color se transmiten a través del `PasoIA.mapa: list[MapaIA]` que YA existe (`redactor.py:126`), con el mismo validador semántico de términos y destinos (`_mapa`, `redactor.py:927`); no incorporar un segundo formato de mapas.

`a_guion` (`redactor.py:1197`) debe omitir el `tex` de paso cuando quede vacío (hoy lo escribe siempre, línea 1203) y serializar `resultado.texto` cuando exista (hoy solo `tex`/`voz`, línea 1237). `errores_latex` (`redactor.py:1337`) solo valida cuando hay fórmula. La revisión de unidades (`revision.py:303-308`) lee `guion.resultado.tex` sin condición: debe saltarse cuando no hay fórmula, para no avisar sobre una conclusión textual.

La plantilla `plantillas/ia/sistema.md` se reescribe sobre su texto actual: la regla de rechazo `es_ejercicio=false` (línea 14), «Cada paso es UNA ecuación completa… Entre 2 y 6 pasos» (línea 21), «Máximo UN dibujo» (líneas 32 y 80, hoy solo prompt, sin validador en código), el dibujo `escala` (línea 50), el `mapa` (línea 71), «Entre todas las voces: de 150 a 260 palabras» (línea 104) y `#ejerciciosresueltos` (línea 136). Conservar la pedagogía XCris (porqué al inicio, idea clave con nombre, pasos numerados, qué/para qué, encadenar, símbolos con significado, una sola idea, cierre en palabras) y los campos `idea_central`/`confusion_tipica`. El límite de UN dibujo sigue siendo solo de prompt: un concepto puede llevar más de un ejemplo visual secuencial; los ejercicios conservan el límite. No añadir bait a la voz.

Idea incorpora `contenido: Contenido | None` (`ideas.py:94`). En generación nueva se exige ese campo a través de instrucciones y validación de la respuesta; ideas guardadas antiguas siguen cargando. La descripción del enunciado deja de ser solo «ejercicio completo y resoluble» y pasa a «premisa O afirmación» según el contenido. No exigir que los tres contenidos sean ejercicios ni que las tres ideas repitan una premisa con palabras distintas. Mantener ganchos válidos, diversidad de ángulo y molde, dificultad y materia/público elegidos. No cambiar `angulo` para duplicar `intenciones`. La plantilla `plantillas/ia/ideas.md` (sección 2) se reescribe en consecuencia.

Propagar contenido en CLI redactar/producir/ideas (`cli.py:387`, `448`, `591`), «Un video» (`_producir_desde_ajustes:806`), lote (`lote.py:591`), completar-niveles (`completar.py:83`, `93`) y previsualización de gancho (`ganchos.py:51`, `78`). `_idea_de_guion` (`cli.py:989`) debe añadir `contenido=guion.contenido`. Usar `--contenido-json` para los procesos existentes; no añadir un selector de estilo ni lanzar un segundo proceso concurrente. Los reintentos que ya poseen YAML lo recargan (`ideas.py:351-361`: «El guion ya estaba escrito: no se vuelve a llamar a la IA»): no vuelven a inferir ni sobrescriben decisiones explícitas. Modificar una sugerencia de intención después de redactar obliga a redacción/revisión, no basta cambiar una etiqueta sobre el mismo texto. Convivir con `--molde`, `crear --kit` y `redibujar` ya existentes.

En publicaciones, respetar `Guion.llamado` (`guion.py:1227`) y `publicar.aplicar_llamado` (`publicar.py:158`): los nuevos contenidos no reciben automáticamente «lo resolvemos», «ejercicios resueltos» o «¿lo resolviste igual?». Preservar el copy de los ejercicios antiguos; para nuevos tipos derivar del objetivo y de lo realmente explicado. No inventar porcentajes, récords, historia, fuentes ni supuestos tácitos; si faltan evidencias externas, dejar observación explícita para revisión humana. No implementar un verificador web ficticio.

## 7. Panel y persistencia

No crear pantalla nueva. La pantalla principal es Estudio (`panel/paginas/estudio.py:82`, PR #51); la ficha de Aprobación de Guiones (`panel/qc.py:198`) sigue disponible en la sala de siempre. Ambas muestran el contenido con paridad:

- Tarjeta **Qué enseña**: intenciones, objetivo, materia, público y dificultad disponible. Distinguir sugerencia de elección. Explicar cada concepto con texto breve.
- Tarjeta **Herramientas de la explicación**: valor efectivo, motivo y «Cambiar»; diálogo con tres estados por recurso: sugerido/activado/desactivado. Guardar y volver, sin cuatro CTA principales.
- Mantener tarjeta **Estilo del video** y su único selector en QC (`cambiar_estilo:244`). No mezclar intención con nombre de apariencia ni añadir un segundo selector en Estudio.
- Los chips de tipo de Estudio (`tpi-chip-tipo`, línea 149) siguen eligiendo MOLDE; no se cablean automáticamente a la intención. La intención viaja por `--contenido-json` desde `args_redactar` (`panel/estudio.py:163`).
- Acción principal sigue siendo **Aprobar y Enviar a Cola**. Cambiar contenido se hace mediante el editor/redacción existente; no etiquetar como mito un ejercicio sin reescribirlo.

Antes de implementar la composición de estas tarjetas, mostrar al dueño un mock en el chat y obtener su «dale». El plan no equivale a aprobación de un diseño visual no visto.

Editor (`panel/editor.py`: `a_formulario:142`, `desde_formulario:172`, `guardar:559`) conserva los campos nuevos, omite null de recursos, preserva false, y no convierte `resultado.texto` en `tex`. Guardar sin editar retiene comentarios y valores de la versión leída. Los setters de QC validan dentro de guiones propios, rechazan ejemplos/rutas externas, validan antes de reemplazar y escriben atómicamente. Un error deja los bytes originales intactos.

Cambio real de contenido/recursos invalida aprobación por huella (`qc.huella:43`); una operación sin cambios conserva estado y bytes. No modificar un lote previamente encolado: avisar que afecta la próxima producción. La elección de estilo sigue su política actual de conservar decisiones de QC, sin refactorizarla.

La línea de tiempo (`escena._guardar_linea_de_tiempo:1845`) incluye contenido y las cuatro decisiones efectivas con origen/motivo para contenidos nuevos o recursos explícitos; los renders heredados no reciben nuevos campos vacíos. No guardar secretos ni configuraciones de Gemini allí.

## 8. Verificación obligatoria y entrega

- Solo Python, NiceGUI existente, unittest; sin Node, React, JS/HTML propios ni dependencias nuevas.
- Runner: `.venv/bin/python -m unittest discover -s pruebas -t . -v`. No pytest.
- Campos nuevos opcionales. No cambiar `TEMA_POR_DEFECTO` (hoy `consola_pasos`), `mis_ajustes/marca.yaml`, `tema:` de guiones existentes, YAML incluidos de temas ni cursos/carreras/malla. No crear ni modificar YAML de temas incluidos para esta función.
- TDD en cada tarea; fixtures bajo TPI_RAIZ temporal; ninguna prueba toca guiones/ajustes del dueño.
- Código por Kiro en su sesión principal; sin subagente implementador. Revisión independiente solo lectura si está disponible; declarar si no la hubo.
- **Primero un solo ejemplo para validar la idea** (gate del diseño de familia Consola): el mito del cubo se produce y se revisa con el dueño antes de fabricar los otros tres. Reutilizar los datos reales de `guiones/caben_ocho_cubos.yaml` (arista 4 cm → 8 cm, dibujo `escala` con `lado: "4 cm"`, `factor: 2`, `dimension: 3`, `anotar: [contador, razon]`).
- Cuatro videos reales con variantes de la familia: mito del cubo (`consola_mito` + panel activado por override, comparar aristas/volúmenes), error de Pitágoras (`consola_error`, corrección), dato sobre tangente (`consola_dato`, conclusión textual, panel desactivado), ejercicio de tolva (`consola_pasos`, cálculo y despiece, micro desactivado). Al menos uno con hoja + recursos y otro con Consola neón + recurso desactivado.
- Regresión de capacidad archivada: `hoja_de_desarrollo` (archivada, carga por nombre) sigue dibujando con gramática; no se resucita como catálogo.
- Casos borde: contenido combinado; conclusión sin fórmula; solo un paso; fórmulas incorrectas excluidas del resumen; mapa vacío; false frente a null; muchos pasos; cámara; subtítulos de dos líneas; reintento y solo gancho; entrada no educativa.
- Comparación con base exacta de main, `PYTHONHASHSEED=0`, `--tema pizarra_nocturna --voz silencio --borrador`: mismos cuadros RGB decodificados y duraciones para ejemplos heredados. Cualquier excepción requiere evidencia y aprobación, no tolerancia inventada.
- Medir duración, silencios y cuadros repetidos; revisar fotogramas completos y reproducir el MP4 final a tamaño real. No comprimir tiempo físico ni estirar escenas para llenar una duración.
- Entrega de implementación: rama nueva y PR solo bajo autorización aplicable. No subir videos/audio, secretos, ajustes ni archivos temporales. Actualizar documentación existente afectada por hechos ya comprobados. Informar por separado pruebas de código y uso real del panel/video; lo no probado queda declarado.

## 9. Criterio de éxito

Con la misma apariencia se pueden crear una demostración conceptual, una corrección y un ejercicio sin forzar cálculos de relleno. El usuario ve qué se enseña, qué aporta cada herramienta y cómo cambiarlo; los guiones antiguos conservan su comportamiento. El MP4 muestra el porqué con dibujos correctos y legibles. No se mide el éxito por cantidad de estilos, flags, tests ni una promesa de viralidad.
