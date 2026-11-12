# Auditoría de prioridades (puntos 1–8) — diseño

Fecha: 2026-11-11 · Estado: propuesto, falta la aprobación del dueño · Repo: tuprofeindustrial-videos

## Origen

Tabla de 8 prioridades que entregó el dueño. Los puntos 1 a 4 ya tienen commits en `main`
(`2c76c83`, `928d274`, `0f6c89a`). El 11-11-2026 se revisaron leyendo el código, ejecutando
las funciones de cálculo y comparando los modelos campo por campo. No se pudo correr la suite
porque el sandbox no tenía PyPI.

| # | Hallazgo | Estado al escribir este diseño |
|---|---|---|
| 1 | Unidades: 36 km/h no se convertía a 10 m/s | ✅ Arreglado. Verificado ejecutando `analizar_proyectil` y `analizar_solido`. |
| 2 | Al reescribir un guion se pierden decisiones | ⚠️ Casi: falta **`enunciado.etiqueta`**, que vuelve a «PROBLEMA». Afecta a `guiones/f_3_mas_1_no_es_10.yaml` y `guiones/tu_gps_te_miente.yaml`. |
| 3 | Editor de estilos | ✅ Arreglado. Los 4 estilos con degradado de un color abren bien. Las materias ya no se igualan. |
| 4 | Borrado irreversible | ✅ Arreglado. Va a la Papelera de macOS y, si falla, no borra nada. |
| 5 | Mezcla de responsabilidades en `_pasos`; reglas de voz distintas | Pendiente |
| 6 | 20–21 estilos sin orden (dos estructuras: `marco: pizarra` ×15 y `marco: hoja` ×5) | Pendiente |
| 7 | 8 copias archivadas en `_promovidos` | Pendiente. **La carpeta no está en el repo**: vive en el Mac del dueño. |
| 8 | 1,1 GB en `salida/_vistas` dentro de unos 3,7 GB generados | Pendiente. `tpi podar` hoy no toca `_vistas`. |

## Objetivo

Cerrar el punto 2 y resolver los puntos 5 a 8 **sin reconstruir nada**. Cada cambio es chico,
tiene su prueba `unittest` y deja los videos de los ejemplos idénticos cuadro a cuadro, salvo
el cambio de voz del clip del gancho, que es intencional (punto 5a).

## Decisiones

### 2 · Etiqueta del enunciado
`a_yaml` (`guion.py`, función interna `bloque`) escribe `etiqueta` cuando no es la de fábrica
(«PROBLEMA»). Es un solo lugar y sirve para el editor del panel, `elegir_gancho` y `redactar`.

### 5a · Una sola regla de voz
Hoy `render.crear_video` y `render.crear_clip_gancho` deciden la voz cada uno por su lado:

| Regla | Video final | Clip del gancho |
|---|---|---|
| voz | `voz or guion.voz or marca` | `voz or marca` (ignora el guion) |
| velocidad | `velocidad or guion.velocidad or marca` | `velocidad or marca` |
| tono | `tono or marca.voz.tono` | **no se pasa** (queda `+0Hz`) |
| silencio | sin atajo | `proveedor` o `voz` = «silencio» ⇒ ambos «silencio» |

Se crea `src/tpi_videos/voz_elegida.py` con `elegir_voz(...)`, que no depende de Manim y
reúne las cuatro reglas. Los dos caminos la usan. El piso de lectura **sigue siendo distinto
a propósito**: 0 en el clip del gancho. Por eso el piso no forma parte de la regla.

Cambios de comportamiento, intencionales:
- El clip del gancho ahora usa el tono de `marca.yaml`, igual que el video final, para que
  el laboratorio de ganchos suene como el video que se publica.
- En el video final, `--voz silencio` también deja el proveedor en «silencio».

`ganchos.guion_de_vista_previa` deja de copiar `voz or texto` a mano: pasa `voz` tal cual y
el guion usa `Gancho.voz_final`, la misma propiedad que usa el video final.

### 5b · Un solo tiempo de escritura
`escena.py:1498` usa `np.clip(tr.duration * 0.45, 0.8, 1.6)`, y `revision.py` copia esas
mismas constantes «a mano» (`FRACCION_DE_ESCRITURA`, `ESCRITURA_MIN`, `ESCRITURA_MAX`). Se
crea `revision.tiempo_de_escritura(segundos)` y lo usan los dos lugares.

### 5c · Acomodo de la pila fuera de la escena
El bucle `while True` de `_pasos` (`escena.py` ~1415–1425) decide cuántas líneas viejas
salen midiendo Mobjects. La decisión pasa a una función pura,
`acomodo.lineas_que_salen(alturas, alto_nueva, alto_zona, separacion)`, en un módulo sin
Manim. La escena solo mide alturas y aplica el resultado. Mismo resultado y mismos cuadros.

No se tocan cámara, fórmulas ni dibujos. Separar más queda para otra fase, si el dueño lo pide.

### 6 · Grupos de estilos (solo presentación)
- Se agrega `GRUPOS_DE_ESTILO` en `temas.py`, una tabla en código, junto a las demás `TEMA_POR_*`.
- **No** se usa la palabra «familia», que ya significa formatos y tipografías.
- **No** se tocan `sugerir_tema` ni `resolver_tema`, ni ningún YAML de `plantillas/temas/`.
- No se agregan selectores: el estilo se sigue eligiendo solo en la ficha de QC.
- Se agrupan las tres vistas del catálogo: el diálogo de QC, la página Estilos y `./tpi temas`.
- Los estilos propios del usuario van al grupo «Tus estilos».
- `consola_neon` se mantiene con su id y sus funciones, dentro de «Neón».

Grupos propuestos (20 estilos; el dueño puede renombrar o mover):

| Grupo | Estilos |
|---|---|
| Hoja y cuaderno | hoja_de_desarrollo, cuaderno_con_sello, cuaderno_tinta_roja, rotulador, rotulador_fucsia |
| Pizarra y tiza | pizarra_nocturna, tiza_verde, tiza_azul |
| Neón | neon_cian, neon_reja, neon_uva, consola_neon |
| Planos técnicos | plano_azul, plano_noche |
| Cómic y viñeta | comic_azul, comic_semitono, vineta_cine, vineta_dorada |
| Kraft | kraft_claro, kraft_tiza |

### 7 · `_promovidos`
No hay código que cree ni lea `_promovidos`. Ni `listar_temas` (`glob("*.yaml")` no recursivo)
ni la biblioteca (que salta carpetas que empiezan con `_`) lo cargan. **No se escribe código.**
El plan deja un paso manual para el dueño en su Mac: ubicar la carpeta, confirmar que las
copias son idénticas con `shasum` y enviarla a la Papelera desde Finder.

### 8 · Poda de `_vistas` y de los trozos de Manim
Se amplía `mantenimiento.podar_temporales` y su comando `./tpi podar`, que ya pregunta antes
de borrar y tiene modo de prueba con `aplicar=False`:
- **`salida/_vistas/<estilo>/<subcarpeta>/`**: el video borrador completo de la vista previa.
  Se borra si todo lo de adentro tiene más de `dias`. Se **conservan** los 3 PNG y `huella.txt`,
  que es todo lo que necesita `vista_previa.en_cache`. La vista previa guardada sigue apareciendo
  en el panel.
- **`salida/<video>/manim/videos/*/partial_movie_files/`**: los trozos que Manim ya unió en
  `animacion.mp4`. Se borran si tienen más de `dias`. **No** se toca `animacion.mp4`, porque
  `linea_de_tiempo.json` lo usa como `intermedio` para la miniatura y la portada.
- Nunca se tocan los videos finales o borradores (`<video>.mp4`, `<video>_borrador.mp4`),
  `.srt`, `.ass`, `linea_de_tiempo.json`, `publicacion.json`, `miniatura.jpg` ni `portada.png`.
- Nunca se siguen enlaces simbólicos. Las carpetas que quedan vacías se quitan.

## No-objetivos
- Reescribir `escena.py` o separar la cámara.
- Cambiar qué estilo se sugiere.
- Borrar estilos.
- Tocar `mis_ajustes/`.
- Borrar algo de `salida/` que no se pueda regenerar.

## Verificación
- Toda la suite: `.venv/bin/python -m unittest discover -s pruebas -t . -v`.
- Comparación cuadro a cuadro de los ejemplos con `pizarra_nocturna`, como exige la regla del
  repo, antes y después.
- `./tpi podar` en el Mac del dueño: primero ver la lista, después borrar.
