# Motor visual · Matemática viva (subproyecto B) — Plan de implementación

**Goal:** tangente viva, área viva y halo de cambio, todos opcionales y apagados por defecto.

**Architecture:** `Funcion` gana `derivada`/`area`; `grafico_funcion` gana `vivo` cuando el guion pide `movimiento`; `Dibujo` gana `fisico`; `_mover_dibujo` comprime a la voz si `fisico=False`; `componentes.py` gana `terminos_nuevos`/`halo_de`; `_pasos` dibuja el halo.

**Tech Stack:** Python 3.12, Manim 0.22, Pydantic 2, NumPy, `unittest`, `uvx ruff`.

**Spec:** `docs/superpowers/specs/2026-11-10-matematica-viva-design.md`

**Directorio de trabajo:** `/projects/sandbox/tuprofeindustrial-videos`

## Global Constraints

- Rama `feat/matematica-viva`, un PR a `main`. Nunca push a `main`.
- Todo campo YAML nuevo es opcional. Los 28 tipos validan igual.
- No tocar `dibujos_3d.py`, `ThreeDScene` ni nada de C; no tocar `tpi.py`/`cola.py`/`lote.py`; no cambiar `TransformMatchingTex` ni `avance_de_movimiento`.
- TDD: cada prueba se escribe y se ve fallar antes del código.
- Nombres, mensajes y docs en español de Chile.
- Los ejemplos antiguos deben salir idénticos a `main` (`PYTHONHASHSEED=0`).
- Si el entorno no permite renderizar (LaTeX/ffmpeg), decirlo en la PR; no declarar verificado lo que no se vio.

---

### Task 0: Línea base

- [ ] **Step 1:** `git checkout -b feat/matematica-viva` y `.venv/bin/python -m unittest discover -s pruebas -t .` (si no hay `.venv`, `uv sync`). Anotar cuántas pruebas pasan/fallan de antes.
- [ ] **Step 2:** si LaTeX y ffmpeg existen: `PYTHONHASHSEED=0 ./tpi crear guiones/ejemplos/visuales_tres_tipos.yaml --tema pizarra_nocturna --voz silencio --borrador` y extraer cuadros a `/tmp/tpi-b-base/` (misma receta que usó la Task 0 del plan de A). Si no existen, anotarlo.

### Task 1: `Funcion.derivada` y `Funcion.area`

**Files:** Modify `src/tpi_videos/visuales.py` · Test `pruebas/test_funcion_viva.py`
**Produces:** `Funcion.derivada(x) -> float | None`, `Funcion.area(a, b) -> float`

- [ ] **Step 1: prueba (falla)** — casos de la spec §6.1 usando `analizar_funcion("x^2", None, [-5, 5], [])`.
- [ ] **Step 2:** `derivada`: `h = 1e-5 * max(1, abs(x))`; `(f(x+h) − f(x−h)) / 2h`; `None` si algún `y` es `None`.
- [ ] **Step 3:** `area`: trapecio con 400 tramos sobre `y()`; lanza `ValueError` si algún punto es `None`.
- [ ] **Step 4:** correr la prueba → verde. `uvx ruff format` + `check`.

### Task 2: Esquema — campos y validación

**Files:** Modify `src/tpi_videos/guion.py`, `src/tpi_videos/visuales.py` (`MARCAS_FUNCION`, `CAMPOS`, `VISUALES["grafico_funcion"]`) · Test `pruebas/test_validacion_movimiento.py`

- [ ] **Step 1: prueba (falla)** — casos de spec §6.3 más: los guiones de `guiones/` y `guiones/ejemplos/` siguen validando.
- [ ] **Step 2:** `Visual`: `movimiento: Literal["", "tangente", "area"] = ""`, `desde: float | None`, `hasta: float | None`. `Paso`: `halo: list[str] = []` (con `_como_lista`), `resaltar_cambio: bool = False`.
- [ ] **Step 3:** en la rama `grafico_funcion` de `_campos_del_tipo`: validar `desde/hasta`, `duracion` (1–20, por defecto 4), `anotar` contra `MARCAS_FUNCION`, y muestreo finito en el tramo. Fuera de esa rama, `movimiento` no vacío → error.
- [ ] **Step 4:** catálogo: agregar `CampoVisual` de `movimiento` (opción), `desde`, `hasta`; sumar `movimiento`, `desde`, `hasta`, `duracion`, `anotar` a `campos` de `grafico_funcion` y `MARCAS_FUNCION` a `marcas`.
- [ ] **Step 5:** correr `test_visuales.py`, la prueba nueva y la suite → verde.

### Task 3: `Dibujo.fisico` y reloj

**Files:** Modify `src/tpi_videos/dibujos.py` (campo), `src/tpi_videos/escena.py` (`_mover_dibujo`) · Test `pruebas/test_tiempo_de_movimiento.py` (agregar casos)

- [ ] **Step 1: prueba (falla)** — función pura nueva `ventana_de_barrido(duracion, ventana) -> (run_time, avance)` en `escena.py`: devuelve `(ventana, 1.0)` siempre. Y un test de que los dibujos de A tienen `fisico is True`.
- [ ] **Step 2:** agregar `fisico: bool = True` al dataclass.
- [ ] **Step 3:** en `_mover_dibujo`: si `not dibujo.fisico` usar `run_time=ventana`, `avance=1.0`; si no, el código de A intacto.
- [ ] **Step 4:** suite → verde.

### Task 4: Tangente viva

**Files:** Modify `src/tpi_videos/dibujos.py` (`grafico_funcion`, `_dibujar_visual`) · Test `pruebas/test_grafico_vivo.py`

- [ ] **Step 1: prueba (falla)** — spec §6.2 (parte tangente) y que sin `movimiento` la geometría es igual a la actual (guardar `mobs.get_all_points()` de una función fija como referencia en la prueba, calculada antes del cambio en la línea base).
- [ ] **Step 2:** `grafico_funcion` recibe `movimiento`, `desde`, `hasta`, `duracion`, `marcas`. Cambiar `_encajar` por `_encaje` (conservando el resultado idéntico sin movimiento). Exponer `p` a través de `fijo`.
- [ ] **Step 3:** si `movimiento == "tangente"`: crear `Dot`, `Line` tangente (largo fijo ~35 % del ancho, recortada a la franja), rótulo `m = …` con `c.texto`; `vivo(p)` según spec §3.5; `vivo(0)`; `Dibujo(..., vivo=vivo, duracion=duracion, fisico=False, desplazamiento=…)`. La tangente se agrega a `aparece`.
- [ ] **Step 4:** pasar los campos desde `_dibujar_visual`.
- [ ] **Step 5:** prueba → verde; suite → verde.

### Task 5: Área viva

**Files:** Modify `src/tpi_videos/dibujos.py` · Test `pruebas/test_grafico_vivo.py`

- [ ] **Step 1: prueba (falla)** — spec §6.2 (parte área): `vivo(1)` rotula el valor de `Funcion.area(desde, hasta)`; bajo el eje el color es `error`.
- [ ] **Step 2:** `vivo(p)`: polígono con las muestras de la curva entre `desde` y `x(p)` cerrado sobre el eje (reasignar puntos con `set_points_as_corners`, sin crear mobjects nuevos); línea de barrido; rótulo `A ≈ valor` con coma decimal (`_numero_latex`).
- [ ] **Step 3:** prueba → verde; suite → verde.

### Task 6: Halo

**Files:** Modify `src/tpi_videos/componentes.py`, `src/tpi_videos/escena.py` (`_pasos`) · Test `pruebas/test_halo.py`

- [ ] **Step 1: prueba (falla)** — spec §6.4.
- [ ] **Step 2:** `terminos_nuevos(origen, destino)` reutilizando `_ESPACIOS_TEX` y `_TRIVIALES`. `halo_de(partes, color)`: 3 `RoundedRectangle` concéntricos (buff 0.08/0.16/0.26, opacidad de relleno 0.22/0.12/0.06), `z_index(0)`.
- [ ] **Step 3:** `_pasos`: después de `self.play(*aparecer, …)` y antes de `marcos`, construir halos según `paso.resaltar_cambio`/`paso.halo`, `FadeIn` en 0,4 s, `resaltes.append(halo)`. Cualquier otra rama del flujo queda intacta.
- [ ] **Step 4:** prueba → verde; confirmar con `PYTHONHASHSEED=0` que un guion sin halo sale idéntico (Task 9).

### Task 7: Revisión

**Files:** Modify `src/tpi_videos/revision.py` · Test `pruebas/test_revision_movimiento.py`

- [ ] **Step 1: prueba (falla)** — aviso de barrido rápido con voz muy corta; sin aviso con voz larga; aviso informativo de `halo` sin `tex`.
- [ ] **Step 2:** implementar en `_avisos_de_visuales`/`_avisos_de_pasos`; `_duracion_de_movimiento` sigue devolviendo `None` para estos.
- [ ] **Step 3:** suite → verde.

### Task 8: Ejemplo

**Files:** Create `guiones/ejemplos/matematica_viva.yaml`

- [ ] **Step 1:** guion corto con `grafico_funcion` + `movimiento: tangente` (`x^2`, `anotar: [pendiente]`), otro paso con `movimiento: area` (`desde: 0`, `hasta: 3`, `anotar: [area]`) y un paso `5x + 5x = 20` → `10x = 20` con `resaltar_cambio: true`.
- [ ] **Step 2:** `./tpi revisar guiones/ejemplos/matematica_viva.yaml` sin errores.

### Task 9: Verificación completa

- [ ] **Step 1:** suite completa en verde; `uvx ruff format --check` y `uvx ruff check`.
- [ ] **Step 2:** si hay LaTeX/ffmpeg: renderizar `matematica_viva.yaml` y `visuales_tres_tipos.yaml` con `--voz silencio --borrador`; mirar cuadros al 25/50/75 % de cada barrido y el halo; comparar los ejemplos antiguos con `/tmp/tpi-b-base/` (`PYTHONHASHSEED=0`). Si no hay herramientas, indicar qué quedó sin ver.
- [ ] **Step 3:** actualizar `docs/PLAN.md`/`README.md` con una línea de los campos nuevos.

### Task 10: Entrega

- [ ] Commit(s) en `feat/matematica-viva`, push, PR a `main` vía `gh api` con pasos para probar en el Mac y para actualizar, y lo que no se pudo probar.
