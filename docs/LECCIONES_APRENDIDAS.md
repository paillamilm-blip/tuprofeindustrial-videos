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

## 2. 🎨 Rotación Visual Estricta (Regla Anti-Clones)
* **Regla:** Desde el Video 04 en adelante, **ningún video consecutivo puede repetir estilo, color ni estructura narrativa** (a menos que el usuario solicite expresamente una trilogía).
* **Los 5 estilos oficiales:**
  1. `consola_pasos`: Azul Marino (`#020617`) / Cian Eléctrico (`#38BDF8`) — Rótulo: `PASO A PASO`
  2. `consola_error`: Carbón (`#09090B`) / Rojo Carmesí (`#EF4444`) — Rótulo: `ERROR`
  3. `pizarra_acrilica`: Blanco Hielo (`#F8FAFC`) / Azul Cobalto (`#2563EB`) — Rótulo configurable (`GEOMETRÍA`, etc.)
  4. `consola_mito`: Obsidiana (`#090514`) / Morado Cyber (`#A855F7`) — Rótulo: `MITO` (pantalla dividida)
  5. `consola_reto`: Grafito (`#0B0F19`) / Verde Esmeralda (`#22C55E`) — Rótulo: `RETO`
* **Causa raíz evitada:** No aplicar `molde: mito_realidad` a todos los guiones por defecto, ya que fuerza la pantalla dividida morada. El molde narrativo debe variar según el objetivo didáctico.

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

## 5. 🏷️ Jerarquía de Cabecera y Quiebre de Titulares
* **Chip superior derecho (`rotulo`):**
  * Debe indicar la materia o categoría didáctica (`GEOMETRÍA`, `ÁLGEBRA`, `PASO A PASO`, `ERROR`, `RETO`, `MITO`).
  * **Prohibido:** Mostrar nombres de materiales técnicos o temas internos como `ACRÍLICO`.
  * El guion puede sobreescribir el chip usando `rotulo: "GEOMETRÍA"` en el YAML.
* **Quiebre de líneas en el título:**
  * Si el título lleva prefijo de examen (`PAES M1:`), la pregunta debe comenzar en una línea independiente debajo, para evitar cortes antiestéticos como `PAES M1: ¿SUMAS O` en la primera línea.
  * Formato estándar en YAML:
    ```yaml
    titulo: |-
      PAES M1:
      ¿Sumas o restas en Pitágoras?
    ```

---

## 6. 💼 Estrategia de Embudo y Reglas Comerciales
* **Prohibido en audio:** No decir precios en pesos (`$18.000`) ni dictar números de teléfono en el guion hablado para evitar penalización y shadowban algorítmico en TikTok e Instagram Reels.
* **Llamado a la acción (CTA) unificado:**
  * Audio: *"Háblame directo al WhatsApp que está en mi perfil"* / *"Enlace en bio"*.
  * Copy escrito (`publicacion.md`): Información detallada de clases particulares PAES M1, cupos y link de bio.
  * Historias de soporte (20:35 y 21:15): Story Quiz interactivo con encuesta A vs B y story directa de WhatsApp.
