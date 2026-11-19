# 🎓 Lecciones Aprendidas y Reglas de Oro — @tuprofeindustrial

Este documento recopila las lecciones técnicas, visuales y de contenido derivadas de la producción, calibración y auditoría de los primeros lotes de videos PAES M1 (Videos 01 al 09). **Son de cumplimiento estricto para cualquier guion, render o agente futuro.**

---

## 1. 🎙️ Voz de Marca Institucional Intocable (Gemini TTS · Charon)
* **Regla:** La voz oficial del canal es **Charon** de Gemini TTS (`voz.proveedor: gemini`, `voz.nombre: "Charon"`). Es la voz cálida, pausada y natural de profesor chileno que define la identidad de la marca.
* **Prohibido:** No utilizar Edge TTS (`es-CL-LorenzoNeural`) para videos de parrilla oficial: su timbre robótico rompe la coherencia del canal.
* **Blindaje multi-modelo:** Ante límites de cuota diaria (429) en el nivel gratuito de `gemini-3.8-flash-tts`, el motor (`voz_gemini.py`) cuenta con fallback automático en cascada:
  1. `gemini-3.8-flash-tts`
  2. `gemini-3.8-flash-lite-tts`
  3. `gemini-3.1-flash-tts-preview`
  4. `gemini-2.5-flash-preview-tts`
  Esto asegura que **siempre se sintetice con Charon**, manteniendo la voz de marca sin degradar.

---

## 2. 🎨 Rotación Visual y los 5 Formatos Oficiales (Regla Anti-Clones)
* **Regla:** Desde el Video 04 en adelante, **ningún video consecutivo puede repetir estilo, color ni estructura narrativa** (a menos que el usuario solicite expresamente una trilogía).
* **Los 5 formatos oficiales y sus temas correspondientes:**
  1. **`PASO A PASO`** → `consola_pasos`: Fondo Azul Marino (`#0B0E14`) / Cian Eléctrico (`#38BDF8`). Chip superior: `PASO A PASO`.
  2. **`ERROR`** → `consola_error`: Fondo Carbón (`#0B0E14`) / Rojo Carmesí Eléctrico (`#EF4444`). Chip superior: `ERROR`.
  3. **`MITO`** → `consola_mito`: Fondo Obsidiana (`#0B0E14`) / Púrpura Cyber (`#A855F7`). Pantalla dividida Mito vs Realidad. Chip superior: `MITO`.
  4. **`RETO`** → `consola_reto`: Fondo Grafito (`#0B0F19`) / Verde Esmeralda Eléctrico (`#22C55E`). Chip superior: `RETO`.
  5. **`DATO`** → `pizarra_acrilica`: Fondo Blanco Hielo (`#F8FAFC`) / Azul Cobalto (`#2563EB`). Trazos tipo plumón de alta visibilidad. Chip superior: `DATO`.
* **Causa raíz evitada:** No aplicar `molde: mito_realidad` a todos los guiones por defecto. El molde y tema deben rotar armónicamente.

---

## 3. 📹 Cámara Quieta en Móvil Vertical (9:16)
* **Regla:** Todo guion de álgebra, aritmética o análisis conceptual debe declarar `camara: quieta`.
* **Motivo:** Los zooms dinámicos en formatos móviles de 9:16 recortan los extremos de ecuaciones largas, tarjetas de enunciados y títulos contra el borde de la pantalla.

---

## 4. 📐 Símbolos Matemáticos: Texto vs LaTeX
* **Regla:** Las tarjetas de texto (`enunciado.texto`, `verificacion.texto`, `reto.texto`) son renderizadas con la tipografía de marca (`c.parrafo`) y **no compilan código LaTeX**.
* **Prohibido:** Escribir cadenas raw como `\sqrt{100}` o `\sqrt{64}` en campos de texto (se leen literalmente como `\sqrt`).
* **Obligatorio:**
  * En campos de texto (`texto:`): Usar caracteres Unicode nativos: **`√`** (ej. `¿Cuánto es √100 - √64?`) y exponentes Unicode (`x²`).
  * En campos matemáticos (`tex:`): Usar LaTeX puro (`\sqrt{100}`, `x^2 = 5x`).

---

## 5. 🏷️ Jerarquía de Cabecera y Chip Superior (`rotulo`)
* **Chip superior derecho (`rotulo`):**
  * Debe indicar **exclusivamente uno de los 5 tipos/formatos de video**: `PASO A PASO`, `ERROR`, `MITO`, `RETO` o `DATO`.
  * **Prohibido terminantemente:** Mostrar nombres de materias escolares (como `GEOMETRÍA` o `ÁLGEBRA`) ni nombres técnicos de temas/materiales (como `ACRÍLICO`).
  * Cada tema define su rótulo por defecto en su YAML (ej. `pizarra_acrilica.yaml` define `rotulo: DATO`).
* **Quiebre de líneas en el título:**
  * Si el título lleva prefijo de examen (`PAES M1:`), la pregunta debe comenzar en una línea independiente debajo, para evitar cortes antiestéticos como `PAES M1: ¿SUMAS O` en la primera línea.
  * Formato estándar en YAML:
    ```yaml
    titulo: |-
      PAES M1:
      ¿Sumas o restas en Pitágoras?
    ```

---

## 6. 🎬 Animaciones Contextuales Obligatorias ("Cero Fórmulas Desnudas")
* **Regla de Contexto:** La animación dinámica (`visual:`) **depende 100% de la materia y el contexto del problema**. Jamás usar gráficos estadísticos de barras para problemas de geometría donde se describe una figura real:
  * **Geometría plana y Pitágoras:** **OBLIGATORIO `tipo: triangulo_rectangulo`**. Dibuja la figura geométrica real con su ángulo recto ($\llcorner$), catetos ($a$ y $b$) e hipotenusa ($c$). La incógnita entra destacada (ej. `b = ¿?` en rojo) y al resolverse transiciona al valor exacto (`b = 8`).
  * **Álgebra y funciones cuadráticas:** **OBLIGATORIO `tipo: grafico_funcion`**. Traza la parábola viva con sus raíces marcadas en el eje ($x_1=0$, $x_2=5$), demostrando visualmente que cancelar una variable elimina un punto de corte real en el plano cartesiano.
  * **Aritmética y raíces numéricas:** `tipo: barras` para comparar magnitudes abstractas (ej. $\sqrt{9} + \sqrt{16} = 7$ vs la trampa errónea $5$).
  * **Cero fórmulas desnudas:** Queda terminantemente prohibido dejar un paso algebraico sin su correspondiente representación gráfica en la parte inferior.

---

## 7. 💼 Estrategia de Embudo y Reglas Comerciales
* **Prohibido en audio:** No decir precios en pesos (`$18.000`) ni dictar números de teléfono en el guion hablado para evitar penalización y shadowban algorítmico en TikTok e Instagram Reels.
* **Llamado a la acción (CTA) unificado:**
  * Audio: *"Háblame directo al WhatsApp que está en mi perfil"* / *"Enlace en bio"*.
  * Copy escrito (`publicacion.md`): Información detallada de clases particulares PAES M1, cupos y link de bio.
  * Historias de soporte (20:35 y 21:15): Story Quiz interactivo con encuesta A vs B y story directa de WhatsApp.

---

## 8. 📐 Sincronía Estricta entre Dibujo y Locución (Continuidad y Rótulos Explícitos)
* **Regla de Coherencia 1:1:** Cada término o lado mencionado en la locución y en la fórmula debe estar **explícitamente rotulado en el dibujo**.
  * Si la fórmula dice $a^2 + b^2 = c^2$ y la voz menciona "cateto a", "cateto b" e "hipotenusa c", el triángulo **no puede mostrar números huérfanos** (como `6` o `10`). Debe rotular con precisión:
    * Base: `a = 6 m`
    * Altura: `b = ¿?` (incógnita en rojo `col.error`)
    * Hipotenusa: `c = 10 m`
* **Continuidad del dibujo (Cero Parpadeos ni Vacíos):**
  * El dibujo que entra en el enunciado como ancla **se hereda de forma continua al paso 1** (`escena.py`), evitando que se desvanezca y vuelva a trazarse desde cero mientras la voz ya habla.
  * **Prohibido bloques intermedios redundantes de `datos:`** que repitan el enunciado y borren el dibujo dejando la mitad de la pantalla vacía.
* **Identidad matemática en transiciones (`acompanar.py`):**
  * La función `_identidad` para figuras geométricas debe calcular la identidad por dimensiones matemáticas resueltas y no por textos temporales de incógnitas.
  * Cuando el paso 4 calcula $b = 8\text{ m}$, el triángulo no se destruye ni parpadea: el rótulo de la incógnita `b = ¿?` muta suavemente a **`b = 8 m` en verde esmeralda (`col.exito`)**, confirmando visualmente la resolución del ejercicio.
