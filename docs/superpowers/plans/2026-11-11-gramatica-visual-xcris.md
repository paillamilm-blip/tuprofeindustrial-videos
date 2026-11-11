# Gramática visual XCris — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir al motor tpi_videos un tema opt-in `consola_neon` que active la gramática visual de XCris (tabs numerados, panel persistente, mapa de color, micro-movimiento y glow) sin cambiar la salida de los temas/guiones actuales.

**Architecture:** Enfoque A del spec: un bloque opcional `gramatica` en `temas.Tema` (defaults apagados) + cuatro componentes puros en `componentes.py` + cableado en `escena.py` detrás de flags + un ajuste de una línea en `render.py` para levantar el subtítulo sobre el panel. Todo lo visual lo decide el tema, como hoy.

**Tech Stack:** Python 3.12, Manim + manim-voiceover, Pydantic v2, PyYAML, FFmpeg; pruebas con `unittest` (NO pytest).

**Spec:** `docs/superpowers/specs/2026-11-11-gramatica-visual-xcris-design.md`

## Global Constraints

- Runner de pruebas: `.venv/bin/python -m unittest discover -s pruebas -t . -v` (venv en `/Users/documentos/Downloads/tuprofeindustrial-videos/.venv`). Una sola: `.venv/bin/python -m unittest pruebas.test_<nombre> -v`. NO usar pytest.
- Nombres de pruebas y mensajes en español; archivos de prueba en `pruebas/test_*.py`.
- TDD estricto: escribir la prueba, verla FALLAR por la razón esperada, implementar lo mínimo, verla pasar.
- Compatibilidad: todo campo nuevo con default apagado/vacío; `extra="forbid"` se mantiene; los YAML viejos deben seguir validando y produciendo la misma salida.
- Opt-in: NO cambiar `TEMA_POR_DEFECTO`, ni `mis_ajustes/marca.yaml`, ni el `tema:` de ningún guion existente.
- NO tocar los guiones sin trackear: `altura_maxima_en_tiro_parabolico.yaml`, `balance_de_masa_en_tolva_de_inyeccion.yaml`, `derivada_de_funcion_cuadratica_paso_a_paso.yaml`.
- Commits: SOLO si el dueño lo pide explícitamente; si no, dejar los cambios sin commit (los pasos de commit abajo son condicionales).
- Sin subagente implementador: el código se escribe en la sesión principal.
- Verificación final: render e2e de un guion existente con `consola_neon`, medir silencios y MIRAR fotogramas a tamaño completo antes de declarar listo.

## File Structure

- Modify `src/tpi_videos/temas.py`: modelo `Gramatica`, `Tema.gramatica`, `Layout.banda_panel`.
- Modify `src/tpi_videos/guion.py`: modelo `MapaColor`, `Paso.mapa` + validación de término.
- Modify `src/tpi_videos/componentes.py`: componentes `tabs_de_pasos`, `panel_persistente`, `mapa_de_color`, `micro_movimiento`, `activar_tab`, `gramatica_activa`.
- Modify `src/tpi_videos/escena.py`: `gramatica_de(tema, n)` puro + cableado en `construct` y `_pasos`.
- Modify `src/tpi_videos/render.py`: levantar `posicion_y` del subtítulo cuando hay panel.
- Create `plantillas/temas/consola_neon.yaml`: el tema opt-in.
- Create pruebas: `test_gramatica_tema.py`, `test_mapa_guion.py`, `test_tabs_pasos.py`, `test_panel_persistente.py`, `test_mapa_color.py`, `test_micro_movimiento.py`, `test_escena_gramatica.py`.

---

### Task 1: Contrato de tema (Gramatica + banda_panel)

**Files:**
- Modify: `src/tpi_videos/temas.py` (tras `class Animacion`, y en `Layout` y `Tema`)
- Test: `pruebas/test_gramatica_tema.py`

**Interfaces:**
- Produces: `temas.Gramatica` con `tabs/panel/mapa_color/micro: bool=False`, `paleta_pasos: list[str]=[]`, método `paleta(colores: ColoresTema) -> list[str]`; `Tema.gramatica: Gramatica`; `Layout.banda_panel: float=0.0`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_gramatica_tema.py
import unittest
from pydantic import ValidationError
from tpi_videos.temas import Tema, Gramatica, ColoresTema


class GramaticaTemaTest(unittest.TestCase):
    def test_defaults_apagados(self):
        t = Tema(nombre="prueba")
        self.assertFalse(t.gramatica.tabs)
        self.assertFalse(t.gramatica.panel)
        self.assertFalse(t.gramatica.mapa_color)
        self.assertFalse(t.gramatica.micro)
        self.assertEqual(t.gramatica.paleta_pasos, [])
        self.assertEqual(t.layout.banda_panel, 0.0)

    def test_paleta_vacia_cicla_colores_del_tema(self):
        g = Gramatica(tabs=True)
        c = ColoresTema()
        self.assertEqual(g.paleta(c), [c.acento, c.cuadricula, c.exito, c.error, c.tenue])

    def test_paleta_propia_se_respeta(self):
        g = Gramatica(paleta_pasos=["#FF0000", "#00FF00"])
        self.assertEqual(g.paleta(ColoresTema()), ["#FF0000", "#00FF00"])

    def test_hex_invalido_falla(self):
        with self.assertRaises(ValidationError):
            Gramatica(paleta_pasos=["no-es-hex"])

    def test_banda_panel_fuera_de_rango_falla(self):
        with self.assertRaises(ValidationError):
            Tema(nombre="prueba", layout={"banda_panel": 9.0})

    def test_yaml_viejo_sigue_validando(self):
        t = Tema.model_validate({"nombre": "viejo", "marco": "pizarra"})
        self.assertFalse(t.gramatica.tabs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_gramatica_tema -v`
Expected: FAIL con `ImportError: cannot import name 'Gramatica'` (o AttributeError).

- [ ] **Step 3: Write minimal implementation**

En `temas.py`, añadir tras `class Animacion`:

```python
class Gramatica(_Base):
    """La gramática visual estilo XCris; apagada por defecto para no tocar los temas de hoy."""

    tabs: bool = False
    panel: bool = False
    mapa_color: bool = False
    micro: bool = False
    paleta_pasos: list[str] = Field(default_factory=list)

    _hex = field_validator("paleta_pasos")(classmethod(lambda cls, v: [_validar_hex(c) for c in v]))

    def paleta(self, colores: ColoresTema) -> list[str]:
        return self.paleta_pasos or [colores.acento, colores.cuadricula, colores.exito, colores.error, colores.tenue]
```

En `Layout` añadir: `banda_panel: float = Field(default=0.0, ge=0.0, le=2.0)`.
En `Tema` añadir: `gramatica: Gramatica = Gramatica()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest pruebas.test_gramatica_tema -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit (solo si el dueño lo pide)**

```bash
git add src/tpi_videos/temas.py pruebas/test_gramatica_tema.py
git commit -m "feat: contrato de gramatica visual en Tema (opt-in)"
```

---

### Task 2: Contrato de guion (MapaColor + Paso.mapa)

**Files:**
- Modify: `src/tpi_videos/guion.py` (antes de `class Paso`, y dentro de `Paso`)
- Test: `pruebas/test_mapa_guion.py`

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `guion.MapaColor` con `termino: str`, `concepto: str`, `color: str|None=None`; `Paso.mapa: list[MapaColor]=[]`; validación de que `termino` está en `tex`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_mapa_guion.py
import unittest
from pydantic import ValidationError
from tpi_videos.guion import Paso, MapaColor


class MapaGuionTest(unittest.TestCase):
    def test_mapa_vacio_por_defecto(self):
        p = Paso(voz="hola")
        self.assertEqual(p.mapa, [])

    def test_mapa_con_termino_presente_valida(self):
        p = Paso(voz="hola", tex="x = 150 + 780 t", mapa=[{"termino": "780", "concepto": "velocidad"}])
        self.assertEqual(p.mapa[0].concepto, "velocidad")
        self.assertIsNone(p.mapa[0].color)

    def test_mapa_con_termino_ausente_falla(self):
        with self.assertRaises(ValidationError):
            Paso(voz="hola", tex="x = 150", mapa=[{"termino": "999", "concepto": "nada"}])

    def test_mapa_sin_tex_falla(self):
        with self.assertRaises(ValidationError):
            Paso(voz="hola", mapa=[{"termino": "780", "concepto": "velocidad"}])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_mapa_guion -v`
Expected: FAIL con `ImportError: cannot import name 'MapaColor'`.

- [ ] **Step 3: Write minimal implementation**

En `guion.py`, antes de `class Paso`:

```python
class MapaColor(_Base):
    """Une un término de la fórmula con su concepto mediante un color (gramática XCris)."""

    termino: str = Field(min_length=1)
    concepto: str = Field(min_length=1)
    color: str | None = None
```

En `Paso` añadir campo: `mapa: list[MapaColor] = []`.
En el validador `_algebra_coherente` (o uno nuevo `@model_validator(mode="after")` `_mapa_coherente`) añadir:

```python
    @model_validator(mode="after")
    def _mapa_coherente(self) -> Paso:
        if self.mapa and not self.tex:
            raise ValueError("el mapa de color ilumina la fórmula: este paso necesita «tex»")
        formula = _ESPACIOS_TEX.sub("", self.tex or "")
        for m in self.mapa:
            if _ESPACIOS_TEX.sub("", m.termino) not in formula:
                raise ValueError(
                    f"el término «{m.termino}» del mapa no aparece en la fórmula del paso ({self.tex})"
                )
        return self
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest pruebas.test_mapa_guion -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit (solo si el dueño lo pide)**

```bash
git add src/tpi_videos/guion.py pruebas/test_mapa_guion.py
git commit -m "feat: mapa de color concepto-formula por paso (opt-in)"
```

---

### Task 3: Componente tabs_de_pasos + activar_tab

**Files:**
- Modify: `src/tpi_videos/componentes.py` (sección Formas, al final)
- Test: `pruebas/test_tabs_pasos.py`

**Interfaces:**
- Consumes: `chip`, `texto` (existentes).
- Produces: `tabs_de_pasos(n: int, activo: int, paleta: list[str]) -> VGroup`; `activar_tab(tabs: VGroup, activo: int) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_tabs_pasos.py
import unittest
from tpi_videos import componentes as c
from tpi_videos.temas import Tema


class TabsPasosTest(unittest.TestCase):
    def setUp(self):
        self.token = c.usar_estilo(Tema(nombre="prueba"))

    def tearDown(self):
        c.restablecer_estilo(self.token)

    def test_un_tab_por_paso(self):
        tabs = c.tabs_de_pasos(4, 1, ["#FFC72C", "#38BDF8"])
        self.assertEqual(len(tabs), 4)

    def test_activo_brilla_mas_que_el_resto(self):
        tabs = c.tabs_de_pasos(3, 2, ["#FFC72C"])
        self.assertGreater(tabs[1][0].get_fill_opacity(), tabs[0][0].get_fill_opacity())
        self.assertGreater(tabs[1][0].get_fill_opacity(), tabs[2][0].get_fill_opacity())

    def test_activar_tab_cambia_el_brillo(self):
        tabs = c.tabs_de_pasos(3, 1, ["#FFC72C"])
        c.activar_tab(tabs, 3)
        self.assertGreater(tabs[2][0].get_fill_opacity(), tabs[0][0].get_fill_opacity())

    def test_paleta_cicla(self):
        tabs = c.tabs_de_pasos(5, 1, ["#FF0000", "#00FF00"])
        self.assertEqual(len(tabs), 5)  # no revienta con mas pasos que colores
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_tabs_pasos -v`
Expected: FAIL con `AttributeError: module ... has no attribute 'tabs_de_pasos'`.

- [ ] **Step 3: Write minimal implementation**

En `componentes.py` (sección Formas):

```python
def tabs_de_pasos(n: int, activo: int, paleta: list[str]) -> VGroup:
    tabs = VGroup()
    for k in range(1, n + 1):
        color = paleta[(k - 1) % len(paleta)]
        tab = chip(str(k), color, tam=16)
        if k != activo:
            tab.set_opacity(0.35)
        tabs.add(tab)
    tabs.arrange(RIGHT, buff=0.18)
    return tabs


def activar_tab(tabs: VGroup, activo: int) -> None:
    for k, tab in enumerate(tabs, 1):
        tab.set_opacity(1.0 if k == activo else 0.35)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest pruebas.test_tabs_pasos -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit (solo si el dueño lo pide)**

```bash
git add src/tpi_videos/componentes.py pruebas/test_tabs_pasos.py
git commit -m "feat: tabs numerados por paso con color y brillo"
```

---

### Task 4: Componente panel_persistente

**Files:**
- Modify: `src/tpi_videos/componentes.py`
- Test: `pruebas/test_panel_persistente.py`

**Interfaces:**
- Consumes: `texto`, `ecuacion`, `tarjeta`.
- Produces: `panel_persistente(total: int, cerrados: list[str], paleta: list[str], ancho: float, relleno: str, borde: str) -> VGroup`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_panel_persistente.py
import unittest
from tpi_videos import componentes as c
from tpi_videos.temas import Tema


class PanelPersistenteTest(unittest.TestCase):
    def setUp(self):
        self.token = c.usar_estilo(Tema(nombre="prueba"))

    def tearDown(self):
        c.restablecer_estilo(self.token)

    def _panel(self, cerrados):
        return c.panel_persistente(4, cerrados, ["#FFC72C"], 6.0, "#141A24", "#2A3444")

    def test_vacio_muestra_paso_1_de_n(self):
        panel = self._panel([])
        self.assertIn("paso 1 de 4", panel[1][0].text)

    def test_acumula_sin_resetear(self):
        uno = self._panel(["a"])
        dos = self._panel(["a", "b"])
        self.assertIn("paso 3 de 4", dos[1][0].text)
        self.assertGreaterEqual(len(dos[1][2]), len(uno[1][2]))

    def test_mini_formulas_tope_tres(self):
        panel = self._panel(["a", "b", "c", "d"])
        self.assertEqual(len(panel[1][2]), 3)

    def test_barra_crece_con_pasos(self):
        vacio = self._panel([])
        lleno = self._panel(["a", "b"])
        self.assertGreater(lleno[1][1][1].width, vacio[1][1][1].width)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_panel_persistente -v`
Expected: FAIL con `AttributeError: ... 'panel_persistente'`.

- [ ] **Step 3: Write minimal implementation**

```python
def panel_persistente(
    total: int, cerrados: list[str], paleta: list[str], ancho: float, relleno: str, borde: str
) -> VGroup:
    k = len(cerrados)
    color = paleta[k % len(paleta)] if paleta else "#FFFFFF"
    contador = texto(f"paso {min(k + 1, total)} de {total}", 16, ULTRABOLD, color)
    pista = Rectangle(width=ancho - 1.2, height=0.12).set_fill(borde, 0.5).set_stroke(width=0)
    lleno = Rectangle(width=max(0.02, pista.width * (k / total if total else 0.0)), height=0.12)
    lleno.set_fill(color, 0.95).set_stroke(width=0)
    lleno.align_to(pista, LEFT).align_to(pista, UP)
    mini = VGroup(*[ecuacion(t, 20, "#FFFFFF", ancho_max=ancho - 1.2) for t in cerrados[-3:]])
    mini.arrange(DOWN, buff=0.12, aligned_edge=LEFT)
    contenido = VGroup(contador, VGroup(pista, lleno), mini).arrange(DOWN, buff=0.16, aligned_edge=LEFT)
    return tarjeta(contenido, ancho, relleno, borde)
```

(Nota: `tarjeta` devuelve `VGroup(VGroup(sombra,caja), contenido)`; por eso el contenido vive en `panel[1]`: `[0]`=contador, `[1]`=barra, `[2]`=mini.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest pruebas.test_panel_persistente -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit (solo si el dueño lo pide)**

```bash
git add src/tpi_videos/componentes.py pruebas/test_panel_persistente.py
git commit -m "feat: panel persistente que acumula pasos"
```

---

### Task 5: Componente mapa_de_color

**Files:**
- Modify: `src/tpi_videos/componentes.py`
- Test: `pruebas/test_mapa_color.py`

**Interfaces:**
- Consumes: `partes_por_tex`, `chip`, `ecuacion`; `guion.MapaColor`.
- Produces: `mapa_de_color(eq: MathTex, mapa: list[MapaColor], paleta: list[str]) -> VGroup`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_mapa_color.py
import unittest
from tpi_videos import componentes as c
from tpi_videos.guion import MapaColor
from tpi_videos.temas import Tema


class MapaColorTest(unittest.TestCase):
    def setUp(self):
        self.token = c.usar_estilo(Tema(nombre="prueba"))

    def tearDown(self):
        c.restablecer_estilo(self.token)

    def test_una_flecha_por_termino_presente(self):
        eq = c.ecuacion("x = 150 + 780 t")
        mapa = [MapaColor(termino="780", concepto="velocidad")]
        grupo = c.mapa_de_color(eq, mapa, ["#38BDF8"])
        self.assertEqual(len(grupo), 1)

    def test_termino_ausente_se_omite(self):
        eq = c.ecuacion("x = 150")
        mapa = [MapaColor(termino="999", concepto="nada")]
        self.assertEqual(len(c.mapa_de_color(eq, mapa, ["#38BDF8"])), 0)

    def test_color_propio_manda(self):
        eq = c.ecuacion("x = 150 + 780 t")
        mapa = [MapaColor(termino="780", concepto="velocidad", color="#FF0000")]
        grupo = c.mapa_de_color(eq, mapa, ["#38BDF8"])
        self.assertEqual(len(grupo), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_mapa_color -v`
Expected: FAIL con `AttributeError: ... 'mapa_de_color'`.

- [ ] **Step 3: Write minimal implementation**

```python
def mapa_de_color(eq: MathTex, mapa: list, paleta: list[str]) -> VGroup:
    grupo = VGroup()
    for j, m in enumerate(mapa):
        color = m.color or paleta[j % len(paleta)]
        partes = partes_por_tex(eq, m.termino)
        if not partes:
            continue
        objetivo = VGroup(*partes)
        etiqueta = chip(m.concepto, color, tam=15)
        etiqueta.next_to(objetivo, DOWN, buff=0.6)
        flecha = Arrow(etiqueta.get_top(), objetivo.get_bottom(), buff=0.12, color=color, stroke_width=4)
        grupo.add(VGroup(etiqueta, flecha))
    return grupo
```

(Añadir `Arrow` al import de manim en `componentes.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest pruebas.test_mapa_color -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit (solo si el dueño lo pide)**

```bash
git add src/tpi_videos/componentes.py pruebas/test_mapa_color.py
git commit -m "feat: mapa de color concepto-formula con flechas"
```

---

### Task 6: Componente micro_movimiento + gramatica_activa

**Files:**
- Modify: `src/tpi_videos/componentes.py`
- Test: `pruebas/test_micro_movimiento.py`

**Interfaces:**
- Consumes: `visto`.
- Produces: `micro_movimiento(tipo: str, objetivo: Mobject) -> Animation`; `gramatica_activa(tema) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_micro_movimiento.py
import unittest
from manim import Animation, Rectangle
from tpi_videos import componentes as c
from tpi_videos.temas import Tema


class MicroMovimientoTest(unittest.TestCase):
    def test_tipos_devuelven_animacion(self):
        obj = Rectangle()
        for tipo in ("cursor", "tick", "barra", "contador"):
            self.assertIsInstance(c.micro_movimiento(tipo, obj), Animation)

    def test_tick_dibuja_un_visto(self):
        anim = c.micro_movimiento("tick", Rectangle())
        self.assertIsNotNone(anim.mobject)

    def test_gramatica_activa_apagada_por_defecto(self):
        self.assertFalse(c.gramatica_activa(Tema(nombre="prueba")))

    def test_gramatica_activa_con_un_flag(self):
        t = Tema(nombre="prueba", gramatica={"tabs": True})
        self.assertTrue(c.gramatica_activa(t))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_micro_movimiento -v`
Expected: FAIL con `AttributeError: ... 'micro_movimiento'`.

- [ ] **Step 3: Write minimal implementation**

```python
def micro_movimiento(tipo: str, objetivo: Mobject) -> Animation:
    if tipo == "tick":
        return Create(visto("#22C55E").next_to(objetivo, RIGHT, buff=0.15))
    if tipo == "barra":
        return GrowFromEdge(objetivo, LEFT)
    if tipo == "contador":
        return FadeIn(objetivo, shift=UP * 0.2)
    return Write(objetivo)


def gramatica_activa(tema) -> bool:
    g = tema.gramatica
    return bool(g.tabs or g.panel or g.mapa_color or g.micro)
```

(Añadir `Create, FadeIn, GrowFromEdge, Write` al import de manim.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest pruebas.test_micro_movimiento -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit (solo si el dueño lo pide)**

```bash
git add src/tpi_videos/componentes.py pruebas/test_micro_movimiento.py
git commit -m "feat: micro-movimiento con proposito y predicado de gramatica"
```

---

### Task 7: Cableado en escena + tema consola_neon + subtítulo sobre el panel

**Files:**
- Modify: `src/tpi_videos/escena.py` (función pura `gramatica_de` + `construct` + `_pasos`)
- Modify: `src/tpi_videos/render.py:246-249`
- Create: `plantillas/temas/consola_neon.yaml`
- Test: `pruebas/test_escena_gramatica.py`

**Interfaces:**
- Consumes: componentes de Tasks 3-6, `Tema.gramatica`, `Paso.mapa`.
- Produces: `escena.gramatica_de(tema, n_pasos: int) -> tuple[VGroup|None, VGroup|None]`; tema `consola_neon` listado en el panel.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_escena_gramatica.py
import unittest
from tpi_videos import escena
from tpi_videos.temas import Tema, cargar_tema
from tpi_videos.config import Marca


class EscenaGramaticaTest(unittest.TestCase):
    def test_tema_viejo_no_construye_gramatica(self):
        tabs, panel = escena.gramatica_de(Tema(nombre="viejo"), 3)
        self.assertIsNone(tabs)
        self.assertIsNone(panel)

    def test_tema_con_gramatica_construye_tabs_y_panel(self):
        t = Tema(nombre="g", gramatica={"tabs": True, "panel": True})
        tabs, panel = escena.gramatica_de(t, 3)
        self.assertEqual(len(tabs), 3)
        self.assertIsNotNone(panel)

    def test_consola_neon_existe_y_activa_gramatica(self):
        t = cargar_tema("consola_neon", Marca())
        self.assertTrue(t.gramatica.tabs)
        self.assertTrue(t.gramatica.panel)
        self.assertTrue(t.resplandor)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_escena_gramatica -v`
Expected: FAIL con `AttributeError: module ... escena has no attribute 'gramatica_de'` / tema inexistente.

- [ ] **Step 3: Write minimal implementation**

En `escena.py`, función pura a nivel de módulo:

```python
def gramatica_de(tema, n_pasos: int):
    g = tema.gramatica
    if not c.gramatica_activa(tema):
        return None, None
    paleta = g.paleta(tema.colores)
    tabs = c.tabs_de_pasos(n_pasos, 1, paleta) if g.tabs else None
    panel = (
        c.panel_persistente(n_pasos, [], paleta, c.ancho_util_de(tema), tema.colores.panel, tema.colores.borde)
        if g.panel
        else None
    )
    return tabs, panel
```

En `construct`, tras `self.add(self.fondo)`:

```python
        self.tabs_gram, self.panel_gram = gramatica_de(self.tema, len(self.guion.pasos))
        self.cerrados_gram: list[str] = []
        if self.tabs_gram is not None:
            self.tabs_gram.move_to([0, c.Y_ZONA_SUPERIOR + 0.5, 0])
            self.add(self.tabs_gram)
        if self.panel_gram is not None:
            self.panel_gram.to_edge(DOWN, buff=0.25)
            self.add(self.panel_gram)
            if self.tema.gramatica.micro:
                self.play(c.micro_movimiento("cursor", self.panel_gram), run_time=0.6)
```

En `_pasos`, dentro de `with self.hablar(...) as tr:` al inicio del cuerpo:

```python
                if self.tabs_gram is not None:
                    c.activar_tab(self.tabs_gram, i)
                    if self.tema.gramatica.micro and i > 1:
                        self.play(c.micro_movimiento("tick", self.tabs_gram[i - 2]), run_time=0.4)
```

y tras construir `eq` (cuando `paso.tex` no es None), añadir el mapa y acumular el panel:

```python
                if self.tema.gramatica.mapa_color and paso.mapa:
                    mapa = c.mapa_de_color(eq, paso.mapa, self.tema.gramatica.paleta(self.col))
                    self.play(FadeIn(mapa), run_time=0.5)
                    extras_vivos.append(mapa)
                if self.panel_gram is not None and paso.tex:
                    self.cerrados_gram.append(paso.tex)
                    nuevo = c.panel_persistente(
                        len(self.guion.pasos), self.cerrados_gram,
                        self.tema.gramatica.paleta(self.col), c.ancho_util_de(self.tema),
                        self.col.panel, self.col.borde,
                    ).to_edge(DOWN, buff=0.25)
                    self.play(Transform(self.panel_gram, nuevo), run_time=0.5)
                    self.panel_gram = nuevo
```

En `render.py` (sitio ~246), levantar el subtítulo sobre el panel:

```python
        estilo = estilo_video.subtitulos
        if estilo_video.gramatica.panel and estilo_video.layout.banda_panel > 0:
            from manim import config as mconfig
            estilo = estilo.model_copy(
                update={"posicion_y": estilo.posicion_y - estilo_video.layout.banda_panel / mconfig.frame_height}
            )
```

Crear `plantillas/temas/consola_neon.yaml`:

```yaml
nombre: Consola neón
descripcion: Gramática XCris: tabs numerados, panel persistente, mapa de color y micro-movimiento con glow.
marco: pizarra
resplandor: true
colores:
  fondo: "#0B0E14"
  panel: "#141A24"
  borde: "#2A3444"
  titulos: "#F5F7FA"
  texto: "#F5F7FA"
  formulas: "#F5F7FA"
  tenue: "#8A94A6"
  acento: "#FFC72C"
  exito: "#22C55E"
  cuadricula: "#38BDF8"
  error: "#EF4444"
fondo:
  tipo: color
tipografia:
  titulos: {familia: Montserrat, grosor: HEAVY, mayusculas: true}
  texto: {familia: Montserrat, grosor: SEMIBOLD}
layout:
  banda_subtitulo: 0.28
  banda_panel: 1.6
  y_zona_pasos: -2.2
gramatica:
  tabs: true
  panel: true
  mapa_color: true
  micro: true
  paleta_pasos: ["#FFC72C", "#38BDF8", "#A78BFA", "#22C55E", "#F472B6", "#EF4444"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest pruebas.test_escena_gramatica -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Regression + suite completa**

Run: `.venv/bin/python -m unittest discover -s pruebas -t . -v`
Expected: todo en verde (los temas viejos no activan gramática).

- [ ] **Step 6: Commit (solo si el dueño lo pide)**

```bash
git add src/tpi_videos/escena.py src/tpi_videos/render.py plantillas/temas/consola_neon.yaml pruebas/test_escena_gramatica.py
git commit -m "feat: tema consola_neon opt-in con gramatica visual XCris"
```

---

### Task 8: Verificación end-to-end (render + medir + mirar)

**Files:**
- Ninguno nuevo; usa un guion existente trackeado (p.ej. `guiones/el_error_al_pasar_m2_a_cm2.yaml`).

- [ ] **Step 1: Render con el tema nuevo**

Run:
```bash
.venv/bin/python -c "from pathlib import Path; from tpi_videos.render import crear_video; r=crear_video('guiones/el_error_al_pasar_m2_a_cm2.yaml', calidad='final', carpeta_salida=Path('/tmp/gramatica_e2e'), tema='consola_neon'); print('VIDEO', r.video)"
```
(En segundo plano; esperar notificación, no sondear.)

- [ ] **Step 2: Medir audio**

Run: `ffmpeg -i <video> -af silencedetect=n=-35dB:d=0.6 -f null -` → esperado 0 silencios largos; `volumedetect` pico ≈ −1.5 dB.

- [ ] **Step 3: Mirar fotogramas a tamaño completo**

Extraer 4-6 fotogramas (`ffmpeg -ss T -i <video> -frames:v 1`) y LEERLOS: confirmar tabs numerados con el activo brillante, panel inferior persistente que acumula, subtítulo sin pisar el panel, glow/neón coherente. Si algo se pisa, ajustar `banda_panel`/`y_zona_pasos` del YAML y re-renderizar.

- [ ] **Step 4: Confirmar no-regresión visual de un tema viejo**

Renderizar el mismo guion con el tema por defecto y confirmar que se ve igual que antes (sin tabs/panel).

- [ ] **Step 5: Reportar al dueño**

Tabla con métricas + fotogramas + veredicto; declarar que no hubo revisión independiente por subagente.