# Motor visual · Matemática viva (subproyecto B)

Fecha: 2026-11-10
Estado: borrador para revisión. Nada de esto está implementado.

## 1. Contexto y alcance

El subproyecto A (simulación viva, ya en `main`) dejó el contrato `Dibujo.vivo/duracion/estela` y el
reloj `plan_de_movimiento`. B lo usa para la matemática y mejora cómo se ve el cambio entre
fórmulas. Son tres piezas, todas **opcionales y apagadas por defecto**:

1. **Tangente viva**: en un `grafico_funcion`, un punto recorre la curva y arrastra su tangente;
   la pendiente se lee en vivo.
2. **Área viva**: en un `grafico_funcion`, el área bajo la curva se rellena de `desde` a `hasta`;
   el valor acumulado se lee en vivo.
3. **Halo de cambio**: en una pizarra de pasos, los términos que *aparecen nuevos* en una
   transformación (y los que el guion pida con `halo`) se iluminan con un halo suave.

Hoy no existe nada de esto: el repo no tiene visual de derivada ni de integral (la «tangente» de
`circulo_trig` es un segmento estático) y el único énfasis es `SurroundingRectangle` (`destacar`).
`TransformMatchingTex` ya existe en `_pasos` y `_resultado` y **no se cambia**.

Fuera de alcance: `ThreeDScene`, `dibujos_3d.py` y todo lo 3D (subproyecto C); cámara; los cinco
dibujos físicos de A; CLI, cola, persistencia y panel (salvo leer el catálogo ampliado).

## 2. Decisiones

| # | Decisión | Motivo |
|---|----------|--------|
| D1 | Tangente y área son un campo opcional `movimiento` de `grafico_funcion`, no tipos nuevos | Evita tocar `Literal`, `TipoVisual`, `SEGUNDOS_VISUAL` y el despacho; el gráfico estático queda igual |
| D2 | Todo campo nuevo es opcional y vacío por defecto | Regla del repo; los guiones viejos validan y renderizan idéntico |
| D3 | El reloj de la matemática **sí se ajusta a la voz** | No hay tiempo físico que respetar: barrer una tangente en 3 s o en 5 s dice lo mismo. Se usa `Dibujo.fisico=False` |
| D4 | Los valores en vivo (pendiente, área) se calculan numéricamente de la función real | Honestos: el número que se ve es el de la curva dibujada, no uno inventado |
| D5 | El halo es un mobject nuevo detrás de la fórmula, no un cambio a `TransformMatchingTex` | La regla de oro del repo: ejemplos antiguos idénticos cuadro a cuadro |
| D6 | Un halo es opt-in: `resaltar_cambio: true` (automático) o `halo: [...]` (manual) | Nada se ilumina solo en guiones existentes |
| D7 | Si la función no es derivable/integrable en el tramo, falla la **validación** con mensaje claro | Mejor un error en español que un frame con NaN |

## 3. Contrato

### 3.1 Guion (`guion.py`)

`Visual` (solo tiene sentido con `tipo: grafico_funcion`):

```yaml
movimiento: tangente      # o: area      (vacío = gráfico estático de siempre)
desde: -1                 # x donde empieza el barrido / el área (opcional; por defecto el inicio del rango)
hasta: 3                  # x donde termina (opcional; por defecto el fin del rango)
duracion: 4               # reutiliza el campo existente: segundos que dura el barrido (por defecto 4; 1–20)
anotar: [pendiente]       # tangente: pendiente · area: area  (el valor en vivo)
```

`Paso`:

```yaml
halo: ["x^2"]             # términos a iluminar (mismo criterio de búsqueda que `destacar`)
resaltar_cambio: true     # ilumina los términos nuevos que trae esta transformación
```

Reglas del validador:

- `movimiento` con otro `tipo` → error.
- `desde < hasta`, ambos dentro del rango de la función.
- `anotar` en `grafico_funcion` solo acepta `MARCAS_FUNCION = ("pendiente", "area")`; `pendiente`
  exige `movimiento: tangente` y `area` exige `movimiento: area`.
- La función debe dar valores finitos en todo `[desde, hasta]` (muestreo); si no, error que
  nombra el punto problemático.
- `halo` y `resaltar_cambio` no exigen `tex`… pero sin `tex` no hacen nada y la revisión avisa.

### 3.2 `Funcion` (`visuales.py`)

```python
def derivada(self, x: float) -> float | None       # diferencia central con h relativo; None si no existe
def area(self, a: float, b: float) -> float        # trapecio con 400 tramos; con signo
```

`derivada` usa `evaluar`; no depende de sympy.

### 3.3 `Dibujo` (`dibujos.py`)

Gana `fisico: bool = True`. Con `False`, la escena **comprime o estira** el barrido a la ventana de
voz (avance siempre 1.0). Con `True` se comporta exactamente como en A.

### 3.4 Reloj (`escena.py`)

`_mover_dibujo` lee `dibujo.fisico`. Si es `False`: `run_time = ventana` y `avance = 1.0`; `vivo(1)` es
la pose final. La función pura `avance_de_movimiento` no cambia (los dibujos de A siguen igual).

### 3.5 Pose

- **Tangente** `vivo(p)`: `x = desde + p·(hasta − desde)`. Mueve un punto sobre la curva, una
  recta tangente de largo fijo en pantalla (recortada a la franja), y el rótulo `m = f'(x)`. Color
  por pendiente: `tenue` cerca de 0, `acento` si sube, `error` si baja. `vivo(0)` y `vivo(1)`
  dejan poses finitas y distintas.
- **Área** `vivo(p)`: polígono relleno entre el eje y la curva de `desde` a `x(p)`, una línea
  vertical de barrido y el rótulo `A ≈ valor` (coma decimal). Área bajo el eje se pinta en `error`.
- `grafico_funcion` pasa a usar `_encaje` (hoy usa `_encajar`) para que la pose use la misma
  escala y centro finales. Sin `movimiento`, la salida es la de hoy.

### 3.6 Halo (`componentes.py` + `escena.py`)

```python
def terminos_nuevos(origen: MathTex, destino: MathTex) -> list[Mobject]
def halo_de(partes: list[Mobject], color: str) -> VGroup   # 3 rectángulos redondeados concéntricos, opacidad decreciente
```

- `terminos_nuevos`: partes del destino cuyo texto normalizado no existe en el origen y no es trivial
  (`_TRIVIALES`). Si no hay origen devuelve `[]`.
- En `_pasos`, tras el `play` de la fórmula: si `paso.resaltar_cambio` y hay `fuente`, se crea el
  halo de los términos nuevos; si `paso.halo`, el de `partes_por_tex`. Entra con `FadeIn` (0,4 s)
  y se suma a `resaltes`, así sale con el paso siguiente como hoy los `marcos`.
- Los pasos `error` y las fórmulas sin fuente: `resaltar_cambio` no hace nada; `halo` sí funciona.
- `z_index` debajo de la fórmula para no taparla.

## 4. Revisión (`revision.py`)

- Paso con `movimiento` y ventana de voz estimada < 1,5 s: `Aviso("advertencia", ...)` «el barrido
  de la tangente/área va muy rápido».
- Paso con `halo`/`resaltar_cambio` sin `tex`: aviso informativo.
- No bloquea render ni esquema. `_duracion_de_movimiento` devuelve `None` para estos (no cortan).

## 5. Compatibilidad

- Cero campos obligatorios nuevos. Los 28 tipos validan igual.
- `grafico_funcion` sin `movimiento` produce el mismo dibujo (se prueba igualando geometría).
- Ejemplos antiguos con `--tema pizarra_nocturna --voz silencio --borrador` salen idénticos cuadro a
  cuadro (`PYTHONHASHSEED=0`).
- Catálogo: `grafico_funcion` suma los campos `movimiento`, `desde`, `hasta`, `duracion`, `anotar`
  y `MARCAS_FUNCION`; la prueba «todo campo del modelo está en el catálogo» debe seguir pasando.
- Plantillas de IA (`plantillas/ia/`): **no** se amplía el esquema en B; la IA no genera estos
  campos todavía (decisión explícita, se revisa tras ver el resultado).

## 6. Pruebas (TDD)

1. `pruebas/test_funcion_viva.py`: `derivada` de `x^2` en 3 ≈ 6; de `sin(x)` en 0 ≈ 1; `None` en una
   asíntota. `area` de `x` en [0, 2] ≈ 2; `x^2` en [0, 3] ≈ 9; signo negativo bajo el eje.
2. `pruebas/test_grafico_vivo.py`: sin `movimiento` → `vivo is None` y geometría igual a la actual;
   con `tangente` y `area` → `vivo` y `duracion > 0`, `fisico is False`; `vivo(0/0.5/1)` finito y
   distinto; la pendiente mostrada coincide con `derivada`; el área mostrada en `vivo(1)` coincide
   con `area`; todo cae dentro de la franja.
3. `pruebas/test_validacion_movimiento.py`: `movimiento` en otro tipo falla; `desde ≥ hasta` falla;
   función con asíntota en el tramo falla; `anotar` incompatible falla; guiones viejos validan.
4. `pruebas/test_halo.py`: `terminos_nuevos` en `5x + 5x = 20` → `10x = 20`; `[]` sin términos
   nuevos; `halo_de` devuelve 3 capas con opacidad decreciente.
5. `pruebas/test_tiempo_de_movimiento.py` (existente): sigue verde sin cambios.
6. `pruebas/test_revision_movimiento.py`: aviso de barrido rápido; sin aviso con voz larga.
7. Suite completa.

## 7. Verificación end-to-end

- `.venv/bin/python -m unittest discover -s pruebas -t .` en verde.
- Nuevo ejemplo `guiones/ejemplos/matematica_viva.yaml` (tangente en `x^2`, área en `x^2`, halo en
  una transformación de ecuación): `./tpi crear … --voz silencio --borrador`; ver cuadros al 25 %,
  50 % y 75 % del barrido y el halo.
- Control de regresión: `guiones/ejemplos/visuales_tres_tipos.yaml` y los ejemplos antiguos idénticos
  a `main` con `PYTHONHASHSEED=0`.

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Cambiar `_encajar` por `_encaje` mueve el gráfico estático | Prueba de geometría idéntica sin `movimiento` |
| Tangente casi vertical o función con salto | Validación por muestreo y recorte de la recta a la franja |
| Halo tapa la fórmula o choca con `destacar` | `z_index` bajo la fórmula; si un término ya tiene marco, el halo lo envuelve sin duplicar |
| `fisico=False` mal usado en dibujos de A | Valor por defecto `True`; prueba de que los cinco de A siguen con reloj real |
| Rótulo en vivo cambia de ancho y salta | Ancho fijo con `\\,` y alineación a la izquierda; prueba de que el rótulo no se sale |
| Subir complejidad del catálogo/panel | Campos opcionales; prueba de catálogo existente |
