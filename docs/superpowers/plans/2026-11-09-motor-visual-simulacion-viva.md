# Simulación viva: dibujos que se mueven en tiempo físico

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que los cinco dibujos físicos (`proyectil`, `pendulo`, `resorte`, `oscilador`, `pendulo_doble`) se muevan solos, con estela y vectores reactivos, respetando siempre el tiempo real de la física.

**Architecture:** El movimiento vive dentro del dibujo: `Dibujo` gana una pose pura `vivo(p)` con `p ∈ [0, 1]`, su `duracion` física y su `estela`. La escena sólo la recorre con un `ValueTracker` lineal; si la voz es más corta que la física, el movimiento se corta al final del paso y la revisión avisa. Los contratos YAML, la CLI y la persistencia no cambian.

**Tech Stack:** Python 3.12, Manim 0.22, manim-voiceover, Pydantic 2, SciPy, ffmpeg/ffprobe, uvx (ruff).

**Spec:** `docs/superpowers/specs/2026-11-09-motor-visual-simulacion-viva-design.md`

**Directorio de trabajo:** todos los comandos se ejecutan en `/Users/documentos/Downloads/tuprofeindustrial-videos`.

## Global Constraints

- **Sin commits, sin push y sin PR**: el árbol puede tener trabajo sin commitear de otras sesiones. Prohibido `git add`, `commit`, `push`, `reset`, `stash` o `checkout` sobre el repo.
- **No revertir** cambios ajenos en `dibujos.py`, `escena.py`, `visuales.py`, `revision.py` ni en los guiones.
- **No tocar** subproyectos B (álgebra: `TransformMatchingTex`, tangente, integral, halos) ni C (3D: `ThreeDScene`, `dibujos_3d.py`).
- **Sin campos YAML obligatorios nuevos.** `velocidad` del péndulo es una marca **opcional**; los 27 tipos siguen validando.
- **CLI, cola y persistencia intactas.** Nada de `tpi.py`, `cola.py` ni `lote.py`.
- **La física no se comprime nunca.** Si la voz se alarga, el dibujo se queda en su pose final; si la física es más larga, se corta y `revision.py` avisa (no bloquea).
- **TDD**: primero la prueba que falla, después el código mínimo, después la suite.
- **Sin subagente implementador**: el código se escribe en esta sesión. Si no hay revisión independiente, decirlo en el reporte final.
- **Nombres y comentarios en español**, con el estilo del repo (tuteo chileno, comentarios que explican el «por qué»).
- **Comandos exactos**:
  - Suite completa: `.venv/bin/python -m unittest discover -s pruebas -t .`
  - Render: `./tpi crear guiones/ejemplos/visuales_tres_tipos.yaml --voz silencio`
  - Formato: `uvx ruff format <archivos>` y `uvx ruff check <archivos>`
- **Cada tarea termina en verde.** Si una prueba existente se rompe, se arregla el código nuevo, no la prueba (salvo que la prueba codifique el comportamiento viejo que el usuario pidió cambiar).

---

### Task 0: Línea base reproducible

**Files:**
- Create: `/tmp/tpi-visual-baseline/` (fuera del repo, sólo para el diff atribuible)

**Interfaces:**
- Consumes: nada.
- Produces: copia de los cuatro módulos que se van a tocar y el estado de git de esas rutas.

- [ ] **Step 1: Guardar la línea base**

```bash
mkdir -p /tmp/tpi-visual-baseline
cp src/tpi_videos/dibujos.py src/tpi_videos/escena.py src/tpi_videos/visuales.py src/tpi_videos/revision.py /tmp/tpi-visual-baseline/
git status --short -- src/tpi_videos/dibujos.py src/tpi_videos/escena.py src/tpi_videos/visuales.py src/tpi_videos/revision.py pruebas/ guiones/ > /tmp/tpi-visual-baseline/estado.txt
```

- [ ] **Step 2: Correr la suite completa de partida**

Run: `.venv/bin/python -m unittest discover -s pruebas -t .`
Expected: termina en `OK` con ~702 pruebas. Anotar el número exacto en `/tmp/tpi-visual-baseline/estado.txt`.

- [ ] **Step 3: Confirmar que los cinco dibujos actuales son quietos**

Run:

```bash
.venv/bin/python -c "
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import analizar_proyectil
from tpi_videos.dibujos import proyectil, ALTO_DIBUJO
d = proyectil(analizar_proyectil('20 m/s', 30), [], ColoresTema(), 7.0, ALTO_DIBUJO)
print(d.vivo, d.duracion, d.estela)
"
```

Expected: `AttributeError: 'Dibujo' object has no attribute 'vivo'`. Es la línea base: todavía no existe el contrato.

---

### Task 1: Tiempo de movimiento (puro, sin Manim en la lógica)

**Files:**
- Modify: `src/tpi_videos/escena.py` (constantes y dos funciones nuevas antes de `class VideoEjercicio`)
- Test: `pruebas/test_tiempo_de_movimiento.py` (nuevo)

**Interfaces:**
- Consumes: nada.
- Produces:
  - `avance_de_movimiento(duracion: float, ventana: float) -> tuple[float, bool]`
  - `plan_de_movimiento(duracion: float, restante: float) -> tuple[float, float, float, bool]` → `(entrada, ventana, avance, se_corta)`

- [ ] **Step 1: Escribir la prueba que falla**

```python
"""El movimiento nunca comprime la física: o entra en la voz o se corta y se avisa."""

import unittest

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from tpi_videos.escena import avance_de_movimiento, plan_de_movimiento


@unittest.skipUnless(MANIM, "manim no está instalado")
class VentanaDeMovimientoTest(unittest.TestCase):
    def test_si_la_voz_alcanza_se_ve_toda(self):
        self.assertEqual(avance_de_movimiento(2.5, 6.0), (1.0, False))

    def test_si_la_voz_no_alcanza_se_corta_y_se_avisa(self):
        avance, cortado = avance_de_movimiento(10.0, 7.0)
        self.assertAlmostEqual(avance, 0.7)
        self.assertTrue(cortado)

    def test_una_duracion_absurda_no_divide_por_cero(self):
        self.assertEqual(avance_de_movimiento(0.0, 3.0), (1.0, False))

    def test_el_plan_reserva_un_cuarto_para_que_entre_el_dibujo(self):
        entrada, ventana, avance, cortado = plan_de_movimiento(10.0, 8.0)
        self.assertAlmostEqual(entrada, 2.0)
        self.assertAlmostEqual(ventana, 6.0)
        self.assertAlmostEqual(avance, 0.6)
        self.assertTrue(cortado)

    def test_el_plan_nunca_se_come_la_voz(self):
        for restante in (1.0, 1.4, 3.0, 8.0, 20.0):
            entrada, ventana, _, _ = plan_de_movimiento(5.0, restante)
            self.assertAlmostEqual(entrada + ventana, restante)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correrla y ver que falla**

Run: `.venv/bin/python -m unittest pruebas.test_tiempo_de_movimiento -v`
Expected: `ImportError: cannot import name 'avance_de_movimiento'`.

- [ ] **Step 3: Implementar**

En `src/tpi_videos/escena.py`, después de `deriva_desplazamiento(...)` y antes de las constantes del tablero partido:

```python
def avance_de_movimiento(duracion: float, ventana: float) -> tuple[float, bool]:
    """Cuánto de la simulación cabe en la voz, y si hubo que cortarla.

    La física manda: el reloj de la simulación corre a su ritmo real y la escena no lo estira
    ni lo apura. Si la voz se queda corta, se ve el principio y se avisa en la revisión.
    """
    if duracion <= 0 or ventana >= duracion:
        return 1.0, False
    return max(ventana / duracion, 0.0), True


def plan_de_movimiento(duracion: float, restante: float) -> tuple[float, float, float, bool]:
    """Reparte lo que queda de voz: un cuarto para que el dibujo entre y el resto para la física.

    Devuelve ``(entrada, ventana, avance, se_corta)``. ``entrada + ventana == restante``, así el
    paso nunca se pasa de la voz; cuando la física no cabe, ``avance`` dice dónde se corta.
    """
    entrada = max(restante * 0.25, 0.35)
    ventana = max(restante - entrada, 0.35)
    avance, se_corta = avance_de_movimiento(duracion, ventana)
    return entrada, ventana, avance, se_corta
```

- [ ] **Step 4: Verla pasar**

Run: `.venv/bin/python -m unittest pruebas.test_tiempo_de_movimiento -v`
Expected: 5 pruebas `ok`.

---

### Task 2: El contrato `Dibujo` vivo y sus ayudas

**Files:**
- Modify: `src/tpi_videos/dibujos.py` (imports, `Dibujo`, ayudas nuevas después de `_encajar`)
- Test: `pruebas/test_dibujos_vivos.py` (nuevo)

**Interfaces:**
- Consumes: nada.
- Produces:
  - `Dibujo.vivo: Callable[[float], None] | None`
  - `Dibujo.duracion: float | None`
  - `Dibujo.estela: Mobject | None`
  - `Dibujo.desplazamiento: list[np.ndarray]` (detalle interno, lo consulta la pose)
  - `_encaje(todo, ancho, alto) -> (fijo, desplazamiento)`
  - `_color_de_magnitud(col, fraccion) -> ManimColor`
  - `_apuntar(vector, origen, direccion, largo, color) -> None`
  - `_estela(punto, color, grosor) -> TracedPath`

- [ ] **Step 1: Escribir la prueba que falla**

```python
"""Los dibujos que se mueven: contrato, tiempo real y vectores reactivos."""

import unittest

import numpy as np

from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import (
    analizar_oscilador,
    analizar_pendulo,
    analizar_pendulo_doble,
    analizar_poligono,
    analizar_proyectil,
    analizar_resorte,
)

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from tpi_videos.dibujos import (
        ALTO_DIBUJO,
        oscilador,
        pendulo,
        pendulo_doble,
        poligono_regular,
        proyectil,
        resorte,
    )

ANCHO_HOJA = 7.0


@unittest.skipUnless(MANIM, "manim no está instalado")
class ContratoVivoTest(unittest.TestCase):
    def test_los_cinco_dibujos_declaran_su_tiempo_y_su_estela(self):
        figuras = [
            proyectil(analizar_proyectil("20 m/s", 30), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO),
            pendulo(analizar_pendulo("1 m", 20), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO),
            resorte(analizar_resorte("200 N/m", "10 cm"), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO),
            oscilador(
                analizar_oscilador("2 kg", "200 N/m", "10 cm"), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
            ),
            pendulo_doble(
                analizar_pendulo_doble("1 kg", "1 kg", "1 m", "1 m", 170.0, 170.0),
                [],
                ColoresTema(),
                ANCHO_HOJA,
                ALTO_DIBUJO,
            ),
        ]
        for dib in figuras:
            with self.subTest(estela=dib.estela is not None):
                self.assertIsNotNone(dib.vivo)
                self.assertGreater(dib.duracion or 0.0, 0.0)
                self.assertIsNotNone(dib.estela)
                self.assertIn(dib.estela, dib.mobs.submobjects)

    def test_un_dibujo_quieto_sigue_sin_movimiento(self):
        dib = poligono_regular(analizar_poligono(5, "12 cm"), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertIsNone(dib.vivo)
        self.assertIsNone(dib.duracion)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correrla y ver que falla**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos -v`
Expected: `AttributeError: 'Dibujo' object has no attribute 'vivo'`.

- [ ] **Step 3: Cambiar imports y `Dibujo`**

En `src/tpi_videos/dibujos.py`:

```python
from typing import Any, Callable
```

Dentro del bloque `from manim import (...)` agregar `TAU`, `TracedPath` y `ManimColor` (en orden alfabético, como el resto):

```python
    TAU,
    TracedPath,
    ManimColor,
```

(Fuera del orden alfabético real del bloque, respetar la posición que le corresponda a cada nombre.)

Reemplazar `Dibujo` por:

```python
@dataclass
class Dibujo:
    """Un dibujo listo para la escena: su grupo, cómo sale cada parte y, si se mueve, su pose."""

    mobs: VGroup
    trazo: list[Mobject] = field(default_factory=list)  # se dibujan con Create
    aparece: list[Mobject] = field(default_factory=list)  # aparecen con FadeIn
    vivo: Callable[[float], None] | None = None  # pinta la pose p ∈ [0, 1]
    duracion: float | None = None  # segundos de física que pide la pose
    estela: Mobject | None = None  # la traza que crece; la escena la agrega sola
    # Lo que ``place`` corre el dibujo: la pose lo consulta para no volver al origen.
    desplazamiento: list[np.ndarray] = field(default_factory=lambda: [np.zeros(3)], repr=False)

    def place(self, x: float, y: float) -> Dibujo:
        delta = np.array([x, y, 0.0]) - self.mobs.get_center()
        self.mobs.shift(delta)
        self.desplazamiento[0] = self.desplazamiento[0] + delta
        return self
```

- [ ] **Step 4: Agregar las ayudas**

Después de `_encajar`:

```python
def _encaje(
    todo: VGroup, ancho: float, alto: float
) -> tuple[Callable[[np.ndarray], np.ndarray], list[np.ndarray]]:
    """Encaja el grupo y devuelve cómo llevar un punto suyo al encuadre final.

    ``fijo`` deja un punto de la figura donde quedó dibujado: incluye el encogido y lo que después
    lo mueva ``place``. La caja de desplazamiento es la misma que guarda el ``Dibujo``, así la pose
    nunca vuelve al origen cuando el dibujo ya cambió de sitio.
    """
    centro = todo.get_center().copy()
    excedido = max(todo.width / ancho, todo.height / alto)
    _encajar(todo, ancho, alto)
    factor = 1.0 / excedido if excedido > 1.0 else 1.0
    desplazamiento = [np.zeros(3)]

    def fijo(p: np.ndarray) -> np.ndarray:
        return centro + (np.asarray(p, dtype=float) - centro) * factor + desplazamiento[0]

    return fijo, desplazamiento


def _color_de_magnitud(col: Any, fraccion: float) -> ManimColor:
    """Del tenue al acento y, sólo al tope, al error: la magnitud también se lee en el color."""
    f = min(max(fraccion, 0.0), 1.0)
    if f <= 0.5:
        return ManimColor(col.tenue).interpolate(ManimColor(col.acento), f * 2.0)
    return ManimColor(col.acento).interpolate(ManimColor(col.error), (f - 0.5) * 2.0)


def _apuntar(
    vector: Arrow, origen: np.ndarray, direccion: np.ndarray, largo: float, color: ManimColor
) -> None:
    """Reapunta una flecha en su sitio: la punta queda a ``largo`` del origen y el relleno sigue al color."""
    norma = float(np.linalg.norm(direccion))
    unitaria = direccion / norma if norma > 1e-9 else np.array([1.0, 0.0, 0.0])
    vector.put_start_and_end_on(origen, origen + unitaria * max(largo, 0.04))
    vector.set_color(color)


def _estela(punto: Mobject, color: str, grosor: float) -> TracedPath:
    """La traza que crece con el punto; se siembra en su posición para no nacer en el origen."""
    traza = TracedPath(punto.get_center, stroke_color=color, stroke_width=grosor)
    traza.set_points_as_corners([punto.get_center(), punto.get_center()])
    return traza
```

- [ ] **Step 5: Ver las pruebas de contrato**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos -v`
Expected: 2 pruebas `ok` (las cinco figuras todavía no tienen `vivo`; la prueba de los cinco fallará hasta las tareas 3–7). Para esta tarea, correr sólo:

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos.ContratoVivoTest.test_un_dibujo_quieto_sigue_sin_movimiento -v`
Expected: `ok`.

> La prueba `test_los_cinco_dibujos_declaran_su_tiempo_y_su_estela` queda **roja a propósito** hasta terminar la tarea 7; no se comenta ni se salta.

---

### Task 3: Proyectil vivo

**Files:**
- Modify: `src/tpi_videos/dibujos.py` (`proyectil`, constante nueva)
- Test: `pruebas/test_dibujos_vivos.py` (agregar clase)

**Interfaces:**
- Consumes: `Dibujo.vivo/duracion/estela`, `_encaje`, `_apuntar`, `_color_de_magnitud`, `_estela`.
- Produces: `proyectil(...)` con `vivo`, `duracion=figura.tiempo`, `estela`; bola `Dot`; `vx`/`vy` reactivas.

- [ ] **Step 1: Agregar la prueba que falla**

Al final de `pruebas/test_dibujos_vivos.py`, antes del `if __name__`:

```python
@unittest.skipUnless(MANIM, "manim no está instalado")
class ProyectilVivoTest(unittest.TestCase):
    def _dib(self, marcas=()):
        return proyectil(
            analizar_proyectil("20 m/s", 30), list(marcas), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
        )

    def _bola(self, dib):
        return min(
            (m for m in dib.mobs.get_family() if isinstance(m, Dot)),
            key=lambda m: m.get_center()[0],
        )

    def test_la_bola_sube_y_baja_en_el_orden_correcto(self):
        dib = self._dib()
        ys = []
        for p in (0.0, 0.25, 0.5, 0.75, 1.0):
            dib.vivo(p)
            ys.append(self._bola(dib).get_center()[1])
        self.assertLess(ys[0], ys[1])
        self.assertLess(ys[1], ys[2])
        self.assertGreater(ys[2], ys[3])
        self.assertGreater(ys[3], ys[4])
        self.assertAlmostEqual(ys[0], ys[4], places=3)

    def test_la_vy_se_apaga_y_se_invierte_en_la_bajada(self):
        def vertical(dib):
            return next(
                f
                for f in dib.mobs.get_family()
                if isinstance(f, Arrow) and abs((f.get_end() - f.get_start())[0]) < 1e-6
            )

        dib = self._dib(("componentes",))
        dib.vivo(0.0)
        arriba = vertical(dib).get_end()[1] - vertical(dib).get_start()[1]
        dib.vivo(0.9)
        abajo = vertical(dib).get_end()[1] - vertical(dib).get_start()[1]
        self.assertGreater(arriba, 0)
        self.assertLess(abajo, 0)
```

Agregar `Dot` al import de Manim del archivo de pruebas:

```python
    from manim import Arrow, Dot
```

- [ ] **Step 2: Correrla y ver que falla**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos.ProyectilVivoTest -v`
Expected: `TypeError: 'NoneType' object is not callable` (no hay `vivo`).

- [ ] **Step 3: Reemplazar `proyectil` completo**

```python
LARGO_COMPONENTE = 0.7  # el largo máximo de vx y vy dentro del dibujo


def proyectil(
    figura: Proyectil, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """El vuelo completo: la bola recorre la parábola en el tiempo real y la estela queda.

    La guía tenue deja ver hacia dónde va; las componentes de la velocidad crecen y cambian de color
    con la bola: ``vx`` no cambia nunca y ``vy`` se apaga hasta invertirse en la bajada.
    """
    # El 0,55 deja aire bajo el suelo para que la flecha de vy quepa cuando apunta hacia abajo.
    escala = min(ancho * 0.9 / figura.alcance, alto * 0.55 / figura.altura)
    gravedad = 2 * figura.vertical / figura.tiempo
    mitad = figura.alcance * escala / 2

    def posicion(t: float) -> np.ndarray:
        return np.array(
            [
                figura.horizontal * t * escala - mitad,
                (figura.vertical * t - gravedad * t * t / 2) * escala,
                0.0,
            ]
        )

    izquierda, derecha = posicion(0.0), posicion(figura.tiempo)
    cima = posicion(figura.tiempo / 2)

    suelo = Line(izquierda + LEFT * 0.3, derecha + RIGHT * 0.3, buff=0).set_stroke(col.tenue, 5)
    curva = VMobject().set_points_smoothly([posicion(figura.tiempo * i / 48) for i in range(49)])
    curva.set_stroke(col.tenue, 3)
    rayas: list = [suelo, curva]
    parches, rótulos = VGroup(), VGroup()

    def medida(texto: str, donde: np.ndarray, tam: float = 22) -> None:
        rotulo = c.texto(texto, tam, SEMIBOLD, col.texto).move_to(donde)
        fondo, rotulo = _parche(rotulo, papel, 0.16)
        parches.add(fondo)
        rótulos.add(rotulo)

    # La flecha del lanzamiento sale del punto de partida, con su ángulo contra el suelo.
    rad = float(np.arctan2(figura.vertical, figura.horizontal))
    direccion = np.array([np.cos(rad), np.sin(rad), 0.0])
    lanzamiento = Arrow(
        izquierda, izquierda + direccion * 1.1, buff=0, stroke_width=7, max_tip_length_to_length_ratio=0.25
    )
    lanzamiento.set_stroke(col.error, 7).set_fill(col.error, 1)
    rayas.append(lanzamiento)
    arco = Arc(radius=0.55, start_angle=0, angle=rad, arc_center=izquierda).set_stroke(col.tenue, 3)
    rayas.append(arco)
    medida(f"{_numero_latex(figura.angulo)}°", izquierda + np.array([0.95, 0.16, 0.0]))
    if "alcance" in marcas:
        medida(f"d ≈ {_numero_latex(figura.alcance)}{_sufijo_proyectil(figura)}", derecha + DOWN * 0.36, 24)
    if "altura_maxima" in marcas:
        bajada = DashedLine(cima, cima * np.array([1.0, 0.0, 1.0]), buff=0).set_stroke(col.acento, 4)
        rayas.append(bajada)
        medida(
            f"h ≈ {_numero_latex(figura.altura)}{_sufijo_proyectil(figura)}",
            cima + np.array([0.95, -0.3, 0.0]),
            24,
        )

    bola = Dot(radius=0.075).set_fill(col.acento, 1).set_stroke(width=0)
    aparece: list[Mobject] = [bola]
    vectores: list[Arrow] = []
    etiquetas = VGroup()
    if "componentes" in marcas:
        vx = Arrow(
            izquierda,
            izquierda + RIGHT * LARGO_COMPONENTE,
            buff=0,
            stroke_width=5,
            max_tip_length_to_length_ratio=0.22,
        )
        vy = Arrow(
            izquierda,
            izquierda + UP * LARGO_COMPONENTE,
            buff=0,
            stroke_width=5,
            max_tip_length_to_length_ratio=0.22,
        )
        vectores = [vx, vy]
        etiquetas = VGroup(
            c.texto("vx", 20, SEMIBOLD, col.texto),
            c.texto("vy", 20, SEMIBOLD, col.texto),
        )
        aparece.extend([*vectores, etiquetas])

    todo = VGroup(suelo, curva, *rayas[2:], *vectores, parches, etiquetas, bola)
    fijo, desplazamiento = _encaje(todo, ancho, alto)

    def vivo(p: float) -> None:
        t = p * figura.tiempo
        centro = fijo(posicion(t))
        bola.move_to(centro)
        if not vectores:
            return
        vx, vy = vectores
        vy_actual = figura.vertical - gravedad * t
        rapidez_x = abs(figura.horizontal) / figura.velocidad
        rapidez_y = abs(vy_actual) / figura.velocidad
        _apuntar(
            vx,
            centro,
            RIGHT * figura.horizontal,
            LARGO_COMPONENTE * rapidez_x,
            _color_de_magnitud(col, rapidez_x),
        )
        _apuntar(
            vy,
            centro,
            UP * (vy_actual if abs(vy_actual) > 1e-9 else 1.0),
            LARGO_COMPONENTE * rapidez_y,
            _color_de_magnitud(col, rapidez_y),
        )
        rotulo_vx, rotulo_vy = etiquetas
        rotulo_vx.move_to(centro + RIGHT * (LARGO_COMPONENTE * rapidez_x + 0.18))
        rotulo_vy.move_to(
            centro + UP * np.sign(vy_actual or 1.0) * (LARGO_COMPONENTE * rapidez_y + 0.18)
        )

    vivo(0.0)
    estela = _estela(bola, col.acento, 5)
    todo.add(estela)
    return Dibujo(
        mobs=todo,
        trazo=rayas,
        aparece=aparece,
        vivo=vivo,
        duracion=figura.tiempo,
        estela=estela,
        desplazamiento=desplazamiento,
    )
```

- [ ] **Step 4: Ver el proyecto de punta a punta**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos.ProyectilVivoTest pruebas.test_proyectil -v`
Expected: todo `ok`, incluidos `test_la_parabola_toca_el_suelo_en_la_salida_y_en_la_caída` y `test_las_componentes_son_una_flecha_horizontal_y_una_vertical`.

---

### Task 4: Péndulo vivo y la marca `velocidad`

**Files:**
- Modify: `src/tpi_videos/dibujos.py` (`pendulo`)
- Modify: `src/tpi_videos/visuales.py` (`MARCAS_PENDULO`)
- Test: `pruebas/test_dibujos_vivos.py` (agregar clase), `pruebas/test_optica_maquinas.py` (marca nueva)

**Interfaces:**
- Consumes: `_encaje`, `_apuntar`, `_estela`.
- Produces: `pendulo(...)` con `vivo`, `duracion=figura.periodo`, `estela`; bola `Dot(radius=0.15)`; flecha tangencial opcional con la marca `velocidad`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Al final de `pruebas/test_dibujos_vivos.py`:

```python
@unittest.skipUnless(MANIM, "manim no está instalado")
class PenduloVivoTest(unittest.TestCase):
    def _dib(self, marcas=()):
        return pendulo(analizar_pendulo("1 m", 20), list(marcas), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)

    def _bola(self, dib):
        return max((m for m in dib.mobs.get_family() if isinstance(m, Dot)), key=lambda m: m.radius)

    def test_una_vuelta_completa_dura_el_periodo(self):
        figura = analizar_pendulo("1 m", 20)
        self.assertAlmostEqual(self._dib().duracion, figura.periodo, places=6)

    def test_la_bola_cruza_la_vertical_a_media_vuelta(self):
        dib = self._dib()
        dib.vivo(0.0)
        x0 = self._bola(dib).get_center()[0]
        dib.vivo(0.5)
        self.assertGreater(self._bola(dib).get_center()[0], x0 + 0.2)

    def test_la_velocidad_se_mueve_solo_si_la_piden(self):
        self.assertFalse([m for m in self._dib().mobs.get_family() if isinstance(m, Arrow)])
        flechas = [m for m in self._dib(("velocidad",)).mobs.get_family() if isinstance(m, Arrow)]
        self.assertEqual(len(flechas), 1)

    def test_la_velocidad_es_maxima_en_el_punto_mas_bajo(self):
        dib = self._dib(("velocidad",))
        flecha = next(m for m in dib.mobs.get_family() if isinstance(m, Arrow))
        dib.vivo(0.0)
        quieta = flecha.get_length()
        dib.vivo(0.25)
        self.assertGreater(flecha.get_length(), quieta)
```

En `pruebas/test_optica_maquinas.py`, dentro de `GuionPenduloTest`, agregar:

```python
    def test_la_velocidad_es_una_marca_opcional_del_pendulo(self):
        visual = Visual(tipo="pendulo", longitud="1 m", angulo=20, anotar=["velocidad"])
        self.assertEqual(visual.anotar, ["velocidad"])
```

- [ ] **Step 2: Correrlas y ver que fallan**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos.PenduloVivoTest pruebas.test_optica_maquinas.GuionPenduloTest -v`
Expected: fallan por `vivo` ausente y porque `velocidad` no está en `MARCAS_PENDULO`.

- [ ] **Step 3: Agregar la marca**

En `src/tpi_videos/visuales.py`:

```python
MARCAS_PENDULO = ("periodo", "velocidad")
```

- [ ] **Step 4: Reemplazar `pendulo` completo**

```python
def pendulo(
    figura: Pendulo, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """El hilo que va y vuelve en su período real; la estela queda y, si se pide, la velocidad.

    La posición sale de ``θ(t) = θ₀·cos(2πt/T)``: el ángulo de la oscilación armónica, no una
    interpolación a ojo. La velocidad es tangente al arco y se apaga en los extremos, donde vale cero.
    """
    s = alto * 0.52
    uni = f" {figura.unidad}" if figura.unidad else ""
    t0 = np.radians(figura.angulo)
    pivote = np.array([0.0, s / 2, 0.0])

    apoyo = Line(pivote + [-0.4, 0, 0], pivote + [0.4, 0, 0]).set_stroke(col.formulas, 5)
    vertical = DashedLine(pivote, pivote + [0.0, -s, 0.0]).set_stroke(col.tenue, 3)
    vuelo = Arc(radius=s, start_angle=-PI / 2 - t0, angle=2 * t0, arc_center=pivote)
    vuelo.set_stroke(col.formulas, 2)
    hilo = Line(pivote, pivote + np.array([-s * np.sin(t0), -s * np.cos(t0), 0.0])).set_stroke(
        col.formulas, 4
    )
    angulo = Arc(radius=s * 0.30, start_angle=-PI / 2, angle=-t0, arc_center=pivote)
    angulo.set_stroke(col.acento, 3)
    bola = Dot(radius=0.15).set_fill(col.acento, 0.95).set_stroke(col.acento, 2)

    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"{_numero_latex(figura.angulo)}°",
        pivote
        + np.array(
            [(s * 0.30 + 0.38) * np.cos(-PI / 2 - t0 / 2), (s * 0.30 + 0.38) * np.sin(-PI / 2 - t0 / 2), 0.0]
        ),
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"L = {_numero_latex(figura.longitud)}{uni}",
        pivote + np.array([0.25, -s * 0.55, 0.0]),
        17,
        RIGHT,
    )
    if "periodo" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"T ≈ {_numero_latex(figura.periodo)} s",
            np.array([0.0, -s / 2 - 0.42, 0.0]),
            18,
        )

    velocidad = None
    if "velocidad" in marcas:
        velocidad = Arrow(
            pivote, pivote + RIGHT * 0.4, buff=0, stroke_width=5, max_tip_length_to_length_ratio=0.25
        )

    rayas = [apoyo, vertical, vuelo, hilo, angulo, *([velocidad] if velocidad else [])]
    todo = VGroup(*rayas, bola, parches, rótulos)
    fijo, desplazamiento = _encaje(todo, ancho, alto)

    def vivo(p: float) -> None:
        # Una vuelta completa: θ pasa de θ₀ a -θ₀ y vuelve. La pausa nunca congela la física.
        t = t0 * np.cos(TAU * p)
        centro = fijo(pivote + np.array([-s * np.sin(t), -s * np.cos(t), 0.0]))
        bola.move_to(centro)
        hilo.put_start_and_end_on(fijo(pivote), centro)
        if velocidad is None:
            return
        rapidez = abs(np.sin(TAU * p))
        sentido = 1.0 if np.sin(TAU * p) >= 0 else -1.0
        direccion = np.array([np.cos(t), -np.sin(t), 0.0]) * sentido
        _apuntar(velocidad, centro, direccion, s * 0.30 * rapidez, _color_de_magnitud(col, rapidez))
        velocidad.set_opacity(min(1.0, rapidez / 0.20))

    vivo(0.0)
    estela = _estela(bola, col.acento, 4)
    todo.add(estela)
    return Dibujo(
        mobs=todo,
        trazo=rayas,
        aparece=[bola, *rótulos],
        vivo=vivo,
        duracion=figura.periodo,
        estela=estela,
        desplazamiento=desplazamiento,
    )
```

- [ ] **Step 5: Ver verde**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos.PenduloVivoTest pruebas.test_optica_maquinas -v`
Expected: todo `ok` (incluye `test_el_pendulo_anota_su_periodo` con «2,0»).

---

### Task 5: Resorte que se estira de verdad

**Files:**
- Modify: `src/tpi_videos/visuales.py` (`DURACION_RESORTE`)
- Modify: `src/tpi_videos/dibujos.py` (`_puntos_espira`, `resorte`, import)
- Test: `pruebas/test_dibujos_vivos.py` (agregar clase)

**Interfaces:**
- Consumes: `_encaje`, `_color_de_magnitud`.
- Produces: `_puntos_espira(x_pared, x_fin, n) -> list[np.ndarray]`; `resorte(...)` con `vivo`, `duracion=DURACION_RESORTE`; espira, bloque y fuerza que crecen juntos.

- [ ] **Step 1: Escribir las pruebas que fallan**

En `src/tpi_videos/visuales.py`, junto a `HASTA_MAXIMA`:

```python
DURACION_RESORTE = 1.4  # s de estiramiento cuasiestático: el resorte no es un péndulo
```

En `pruebas/test_dibujos_vivos.py`, agregar `DURACION_RESORTE` al import de `tpi_videos.visuales` que ya está arriba; después, al final del archivo:

```python
@unittest.skipUnless(MANIM, "manim no está instalado")
class ResorteVivoTest(unittest.TestCase):
    def _dib(self):
        return resorte(
            analizar_resorte("200 N/m", "10 cm"),
            ["fuerza"],
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
        )

    def test_el_extremo_libre_avanza_de_la_reposo_a_la_estirda(self):
        dib = self._dib()
        espira = dib.trazo[2]
        dib.vivo(0.0)
        x0 = max(p[0] for p in espira.get_anchors())
        dib.vivo(1.0)
        x1 = max(p[0] for p in espira.get_anchors())
        self.assertGreater(x1, x0 + 0.2)

    def test_la_fuerza_crece_con_la_extension(self):
        dib = self._dib()
        dib.vivo(0.0)
        horizontales = [
            m
            for m in dib.mobs.get_family()
            if isinstance(m, Arrow) and abs(m.get_end()[1] - m.get_start()[1]) < 1e-6
        ]
        flecha = min(horizontales, key=lambda f: f.get_length())
        antes = flecha.get_length()
        dib.vivo(1.0)
        self.assertGreater(flecha.get_length(), antes + 0.1)

    def test_dura_lo_que_dice_la_constante(self):
        self.assertAlmostEqual(self._dib().duracion, DURACION_RESORTE)
```

- [ ] **Step 2: Correrlas y ver que fallan**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos.ResorteVivoTest -v`
Expected: `AttributeError`/`TypeError` por `vivo` ausente.

- [ ] **Step 3: Implementar**

Agregar `DURACION_RESORTE` al import `from .visuales import (...)` de `dibujos.py`.

Antes de `resorte`:

```python
def _puntos_espira(x_pared: float, x_fin: float, n: int) -> list[np.ndarray]:
    """La espira entre la pared y el extremo libre, con siempre las mismas vueltas."""
    largo = x_fin - x_pared
    paso = (largo - 0.30) / n
    pts = [np.array([x_pared, 0.0, 0.0]), np.array([x_pared + 0.15, 0.0, 0.0])]
    for i in range(n):
        x0 = x_pared + 0.15 + paso * i
        pts.append(np.array([x0 + paso / 2, 0.24 if i % 2 == 0 else -0.24, 0.0]))
        pts.append(np.array([x0 + paso, 0.0, 0.0]))
    pts.append(np.array([x_fin, 0.0, 0.0]))
    return pts
```

Reemplazar `resorte` completo:

```python
def resorte(
    figura: Resorte, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """La ley de Hooke en movimiento: la espira se estira y la fuerza crece con ella.

    La cota mide la extensión final que pide el guion y no se mueve; lo que se mueve es el extremo
    libre, el bloque y la flecha de la fuerza. El estiramiento es suave, como el de una mano.
    """
    x_pared = -ancho * 0.32
    largo = ancho * 0.38
    lado = min(alto * 0.30, ancho * 0.13)
    x_fin = x_pared + largo
    x_reposo = x_fin - min(largo * 0.26, 0.65)

    pared = Line([x_pared, -alto * 0.28, 0], [x_pared, alto * 0.28, 0]).set_stroke(col.formulas, 5)
    rayado = VGroup(
        *[
            Line([x_pared, y + alto * 0.28, 0], [x_pared - 0.22, y + alto * 0.28 - 0.22, 0])
            for y in np.arange(-0.20, alto * 0.56, 0.32)
        ]
    ).set_stroke(col.tenue, 3)

    espira = VMobject().set_points_as_corners(_puntos_espira(x_pared, x_reposo, 7))
    espira.set_stroke(col.acento, 5)

    bloque = Rectangle(width=lado, height=lado).move_to([x_reposo + lado / 2, 0.0, 0.0])
    bloque.set_fill(col.acento, 0.22).set_stroke(col.formulas, 4)

    # La flecha arranca con su largo final: así entra en la caja del dibujo y después sólo se acorta.
    estira = Arrow(
        [x_fin + lado, 0.0, 0.0],
        [x_fin + lado + ancho * 0.12, 0.0, 0.0],
        buff=0,
        stroke_width=5,
        max_tip_length_to_length_ratio=0.30,
    )
    estira.set_stroke(col.error, 5).set_fill(col.error, 1)

    guias = VGroup(
        DashedLine([x_reposo, 0.30, 0], [x_reposo, 0.60, 0]),
        DashedLine([x_fin, 0.30, 0], [x_fin, 0.60, 0]),
    ).set_stroke(col.tenue, 2)
    cota = Arrow(
        [x_reposo, 0.46, 0], [x_fin, 0.46, 0], buff=0, stroke_width=3, max_tip_length_to_length_ratio=0.35
    )
    cota.set_stroke(col.cuadricula, 4).set_fill(col.cuadricula, 1)

    parches, rótulos = VGroup(), VGroup()
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"x = {_numero_latex(figura.extension)} m",
        np.array([(x_reposo + x_fin) / 2, 0.78, 0.0]),
    )
    _cartela(
        col,
        papel,
        parches,
        rótulos,
        f"k = {_numero_latex(figura.constante)} N/m",
        np.array([x_pared + 0.2, alto * 0.34, 0.0]),
        17,
        RIGHT,
    )
    if "fuerza" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"F = k·x ≈ {_numero_latex(figura.fuerza)} N",
            np.array([x_fin + lado + ancho * 0.06, -0.80, 0.0]),
            18,
        )

    rayas = [pared, rayado, espira, guias, bloque]
    todo = VGroup(*rayas, cota, estira, parches, rótulos)
    fijo, desplazamiento = _encaje(todo, ancho, alto)

    def vivo(p: float) -> None:
        suave = p * p * (3.0 - 2.0 * p)  # la mano no arranca ni frena de golpe
        x_t = x_reposo + (x_fin - x_reposo) * suave
        espira.set_points_as_corners([fijo(q) for q in _puntos_espira(x_pared, x_t, 7)])
        bloque.move_to(fijo(np.array([x_t + lado / 2, 0.0, 0.0])))
        largo_fuerza = max(ancho * 0.12 * suave, 0.04)
        estira.put_start_and_end_on(
            fijo(np.array([x_t + lado, 0.0, 0.0])),
            fijo(np.array([x_t + lado + largo_fuerza, 0.0, 0.0])),
        )
        estira.set_color(_color_de_magnitud(col, suave))

    vivo(0.0)
    return Dibujo(
        mobs=todo,
        trazo=rayas,
        aparece=[cota, estira, *rótulos],
        vivo=vivo,
        duracion=DURACION_RESORTE,
        desplazamiento=desplazamiento,
    )
```

- [ ] **Step 4: Ver verde**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos.ResorteVivoTest pruebas.test_optica_maquinas -v`
Expected: todo `ok`, incluido `test_el_resorte_escribe_su_fuerza` («20 N»).

---

### Task 6: Oscilador con estela

**Files:**
- Modify: `src/tpi_videos/dibujos.py` (`oscilador`)
- Test: `pruebas/test_dibujos_vivos.py` (agregar clase)

**Interfaces:**
- Consumes: `_encaje`, `_estela`.
- Produces: `oscilador(...)` con `vivo`, `duracion=figura.hasta`, `estela`; curva completa tenue y punto que la recorre.

- [ ] **Step 1: Escribir las pruebas que fallan**

Al final de `pruebas/test_dibujos_vivos.py`:

```python
@unittest.skipUnless(MANIM, "manim no está instalado")
class OsciladorVivoTest(unittest.TestCase):
    def _dib(self):
        return oscilador(
            analizar_oscilador("2 kg", "200 N/m", "10 cm", "8 N·s/m", 4.0),
            ["regimen"],
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
        )

    def test_la_curva_guia_queda_tenue_y_el_punto_la_recorre(self):
        dib = self._dib()
        punto = max((m for m in dib.mobs.get_family() if isinstance(m, Dot)), key=lambda m: m.radius)
        dib.vivo(0.0)
        x0 = punto.get_center()[0]
        dib.vivo(0.5)
        self.assertGreater(punto.get_center()[0], x0)
        self.assertLessEqual(dib.trazo[2].get_stroke_width(), 3.5)

    def test_dura_los_segundos_integrados(self):
        figura = analizar_oscilador("2 kg", "200 N/m", "10 cm", "8 N·s/m", 4.0)
        self.assertAlmostEqual(self._dib().duracion, figura.hasta)
```

- [ ] **Step 2: Correrlas y ver que fallan**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos.OsciladorVivoTest -v`
Expected: `TypeError: 'NoneType' object is not callable`.

- [ ] **Step 3: Implementar**

En `oscilador`, cambiar el trazo de la curva y agregar el punto. Reemplazos puntuales:

```python
    curva = VMobject().set_points_smoothly([np.array([px(t), py(x), 0.0]) for t, x in zip(figura.t, figura.x)])
    curva.set_stroke(col.tenue, 3)  # la guía completa: se ve adónde va antes de llegar
```

Antes de `todo = VGroup(...)`:

```python
    punto = Dot(radius=0.09).set_fill(col.acento, 1).set_stroke(width=0)
```

Reemplazar el cierre:

```python
    todo = VGroup(eje_t, eje_x, curva, punto, *sobres, parches, rótulos)
    fijo, desplazamiento = _encaje(todo, ancho, alto)

    def vivo(p: float) -> None:
        t = figura.hasta * p
        punto.move_to(fijo(np.array([px(t), py(figura.sobre(t)), 0.0])))

    vivo(0.0)
    estela = _estela(punto, col.acento, 5)
    todo.add(estela)
    return Dibujo(
        mobs=todo,
        trazo=[eje_t, eje_x, curva],
        aparece=[punto, *sobres, *rótulos],
        vivo=vivo,
        duracion=figura.hasta,
        estela=estela,
        desplazamiento=desplazamiento,
    )
```

- [ ] **Step 4: Ver verde**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos.OsciladorVivoTest pruebas.test_oscilador_y_pendulo_doble -v`
Expected: todo `ok`.

---

### Task 7: Péndulo doble vivo

**Files:**
- Modify: `src/tpi_videos/dibujos.py` (`pendulo_doble`)
- Test: `pruebas/test_dibujos_vivos.py` (agregar clase)

**Interfaces:**
- Consumes: `_encaje`, `_estela`, `figura.brazos(i)`.
- Produces: `pendulo_doble(...)` con `vivo`, `duracion=figura.t[-1]-figura.t[0]`, `estela`; brazos y masas recorriendo la serie integrada; guía tenue completa.

- [ ] **Step 1: Escribir las pruebas que fallan**

Al final de `pruebas/test_dibujos_vivos.py`:

```python
@unittest.skipUnless(MANIM, "manim no está instalado")
class PenduloDobleVivoTest(unittest.TestCase):
    def _dib(self):
        return pendulo_doble(
            analizar_pendulo_doble("1 kg", "1 kg", "1 m", "1 m", 170.0, 170.0, duracion=3.0),
            [],
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
        )

    def test_los_brazos_se_mueven_con_la_integral(self):
        dib = self._dib()
        bola = max((m for m in dib.mobs.get_family() if isinstance(m, Dot)), key=lambda m: m.radius)
        dib.vivo(0.0)
        inicio = bola.get_center().copy()
        dib.vivo(0.5)
        self.assertGreater(float(np.linalg.norm(bola.get_center() - inicio)), 0.1)

    def test_la_duracion_es_el_tiempo_integrado(self):
        figura = analizar_pendulo_doble("1 kg", "1 kg", "1 m", "1 m", 170.0, 170.0, duracion=3.0)
        self.assertAlmostEqual(self._dib().duracion, figura.t[-1] - figura.t[0])
```

- [ ] **Step 2: Correrlas y ver que fallan**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos.PenduloDobleVivoTest -v`
Expected: `TypeError: 'NoneType' object is not callable`.

- [ ] **Step 3: Reemplazar `pendulo_doble` completo**

```python
def pendulo_doble(
    figura: PenduloDoble, marcas: list[str], col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> Dibujo:
    """Los dos brazos recorriendo el camino integrado, con la traza de la masa de abajo creciendo.

    La escala sale de la caja que ocupan **todas** las poses y la traza completa: así ningún
    instante del caos se sale de la franja, aunque el dibujo se vea en movimiento.
    """
    xs, ys = [], []
    for i in range(len(figura.t)):
        for x, y in figura.brazos(i):
            xs.append(x)
            ys.append(y)
    xs.extend(p[0] for p in figura.traza)
    ys.extend(p[1] for p in figura.traza)
    caja_x = max(max(xs) - min(xs), 0.2)
    caja_y = max(max(ys) - min(ys), 0.2)
    escala = min(alto * 0.86 / caja_y, ancho * 0.46 / caja_x)
    centro_x = (max(xs) + min(xs)) / 2.0
    centro_y = (max(ys) + min(ys)) / 2.0

    def punto(p: tuple[float, float]) -> np.ndarray:
        return np.array([(p[0] - centro_x) * escala, (p[1] - centro_y) * escala, 0.0])

    paso = max(1, len(figura.traza) // 240)
    camino = VMobject().set_points_as_corners([punto(p) for p in figura.traza[::paso]])
    camino.set_stroke(col.tenue, 3)

    anclaje, masa_1, masa_2 = figura.brazos(0)
    brazo_1 = Line(punto(anclaje), punto(masa_1)).set_stroke(col.formulas, 4)
    brazo_2 = Line(punto(masa_1), punto(masa_2)).set_stroke(col.formulas, 4)
    pivote = Dot(punto(anclaje), radius=0.06).set_fill(col.formulas, 1).set_stroke(width=0)
    bola_1 = Dot(punto(masa_1), radius=0.08).set_fill(col.formulas, 1).set_stroke(width=0)
    bola_2 = Dot(punto(masa_2), radius=0.10).set_fill(col.acento, 1).set_stroke(width=0)

    piezas = VGroup(camino, brazo_1, brazo_2, pivote, bola_1, bola_2)
    # La figura se pega al borde izquierdo y los datos arrancan a su derecha: así ningún rótulo cae
    # encima de la traza, que es lo único que el chico tiene que mirar.
    ancho_figura = caja_x * escala
    corrimiento = np.array([-ancho / 2.0 + ancho_figura / 2.0 + 0.10, 0.0, 0.0])
    piezas.shift(corrimiento)
    x_datos = -ancho / 2.0 + ancho_figura + 0.50

    def punto_final(p: tuple[float, float]) -> np.ndarray:
        return punto(p) + corrimiento

    parches, rótulos = VGroup(), VGroup()
    if "energia" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"E ≈ {_energia_redonda(figura.energia_inicial)} J",
            np.array([x_datos, alto * 0.18, 0.0]),
            17,
            RIGHT,
        )
    if "angulos" in marcas:
        _cartela(
            col,
            papel,
            parches,
            rótulos,
            f"desde {_numero_latex(figura.angulo_1[0])}° y {_numero_latex(figura.angulo_2[0])}°",
            np.array([x_datos, -alto * 0.16, 0.0]),
            16,
            RIGHT,
        )

    todo = VGroup(piezas, parches, rótulos)
    fijo, desplazamiento = _encaje(todo, ancho, alto)
    ultimo = len(figura.t) - 1

    def vivo(p: float) -> None:
        i = min(int(round(p * ultimo)), ultimo)
        a, m1, m2 = figura.brazos(i)
        brazo_1.put_start_and_end_on(fijo(punto_final(a)), fijo(punto_final(m1)))
        brazo_2.put_start_and_end_on(fijo(punto_final(m1)), fijo(punto_final(m2)))
        bola_1.move_to(fijo(punto_final(m1)))
        bola_2.move_to(fijo(punto_final(m2)))

    vivo(0.0)
    estela = _estela(bola_2, col.acento, 5)
    todo.add(estela)
    return Dibujo(
        mobs=todo,
        trazo=[camino],
        aparece=[brazo_1, brazo_2, pivote, bola_1, bola_2, *rótulos],
        vivo=vivo,
        duracion=figura.t[-1] - figura.t[0],
        estela=estela,
        desplazamiento=desplazamiento,
    )
```

- [ ] **Step 4: Ver verde (incluida la prueba de contrato de Task 2)**

Run: `.venv/bin/python -m unittest pruebas.test_dibujos_vivos pruebas.test_oscilador_y_pendulo_doble -v`
Expected: todo `ok`; `test_los_cinco_dibujos_declaran_su_tiempo_y_su_estela` por fin pasa.

---

### Task 8: La escena recorre la pose en tiempo real

**Files:**
- Modify: `src/tpi_videos/escena.py` (import `ValueTracker`, método nuevo `_mover_dibujo`, rama viva en `_trazar_dibujo`)
- Test: `pruebas/test_tiempo_de_movimiento.py` (agregar una prueba de integración con doble de escena)

**Interfaces:**
- Consumes: `plan_de_movimiento`, `Dibujo.vivo/duracion/estela`.
- Produces: `VideoEjercicio._mover_dibujo(dibujo, duracion, restante, camara)`.

- [ ] **Step 1: Escribir la prueba que falla**

Al final de `pruebas/test_tiempo_de_movimiento.py`, antes del `if __name__`:

```python
@unittest.skipUnless(MANIM, "manim no está instalado")
class ElDibujoVivoTest(unittest.TestCase):
    """La rama viva no toca la física: la recorre y deja la pose final puesta."""

    def test_la_rama_viva_usa_el_tiempo_fisico_y_no_el_de_la_voz(self):
        from types import SimpleNamespace

        from manim import VGroup

        from tpi_videos.dibujos import Dibujo
        from tpi_videos.escena import VideoEjercicio

        posiciones = []
        dib = Dibujo(mobs=VGroup(), vivo=posiciones.append, duracion=10.0)

        class _Trampa:
            jugadas = []

            def play(self, *animaciones, run_time=None, **_kwargs):
                self.jugadas.append(run_time)

            def add(self, *_mobs):
                pass

            def remove(self, *_mobs):
                pass

        trampa = _Trampa()
        VideoEjercicio._mover_dibujo(trampa, dib, 10.0, 8.0, [])
        self.assertIn(6.0, trampa.jugadas)  # la física entera, no los 8 s de voz
        self.assertEqual(posiciones[-1], 1.0)


if __name__ == "__main__":
    unittest.main()
```

> `posiciones.append` recibe el `p` de la pose; el último llamado es la pose final explícita.

- [ ] **Step 2: Correrla y ver que falla**

Run: `.venv/bin/python -m unittest pruebas.test_tiempo_de_movimiento.ElDibujoVivoTest -v`
Expected: `AttributeError: type object 'VideoEjercicio' has no attribute '_mover_dibujo'`.

- [ ] **Step 3: Implementar**

En el import de Manim de `escena.py`, agregar `ValueTracker` (orden alfabético, después de `UpdateFromAlphaFunc`).

Agregar el método justo antes de `_trazar_dibujo`:

```python
    def _mover_dibujo(
        self, dibujo: d.Dibujo, duracion: float, restante: float, camara: list[Animation]
    ) -> None:
        """Entra el dibujo con lo justo y después corre su física en el tiempo real.

        El reloj avanza lineal: la simulación dura lo que dura en el papel. Si la voz se queda
        corta, se recorre sólo el trozo que cabe y la revisión ya avisó del corte.
        """
        entrada, ventana, avance, _ = plan_de_movimiento(duracion, restante)
        animaciones: list[Animation] = [Create(m) for m in dibujo.trazo]
        if dibujo.aparece:
            animaciones.append(
                LaggedStart(*[FadeIn(m, shift=UP * 0.1) for m in dibujo.aparece], lag_ratio=0.12)
            )
        if animaciones:
            self.play(*animaciones, *camara, run_time=entrada)
        elif camara:
            self.play(*camara, run_time=entrada)
        if dibujo.estela is not None:
            self.add(dibujo.estela)
        reloj = ValueTracker(0.0)
        reloj.add_updater(lambda tracker: dibujo.vivo(tracker.get_value() * avance))
        self.add(reloj)
        self.play(
            reloj.animate.set_value(1.0),
            run_time=min(ventana, duracion),
            rate_func=rate_functions.linear,
        )
        reloj.clear_updaters()
        self.remove(reloj)
        dibujo.vivo(avance)
```

En `_trazar_dibujo`, justo después del bloque que arma `camara` y antes de `# El dibujo termina antes que la voz...`, insertar:

```python
        if dibujo.vivo is not None and dibujo.duracion:
            self._mover_dibujo(dibujo, dibujo.duracion, restante, camara)
            return dibujo
```

El resto del método (la rama de los dibujos quietos) queda tal cual.

- [ ] **Step 4: Ver verde**

Run: `.venv/bin/python -m unittest pruebas.test_tiempo_de_movimiento -v`
Expected: 6 pruebas `ok`.

Run: `.venv/bin/python -m unittest pruebas.test_camara pruebas.test_banda_del_gancho -v`
Expected: todo `ok` (la cámara y la banda no cambiaron).

---

### Task 9: Aviso de revisión cuando la física no cabe en la voz

**Files:**
- Modify: `src/tpi_videos/revision.py` (imports, `_duracion_de_movimiento`, aviso en `_avisos_de_visuales`)
- Test: `pruebas/test_revision_movimiento.py` (nuevo)

**Interfaces:**
- Consumes: `estimar_segundos(paso.voz)`, analizadores de `visuales`.
- Produces: `Aviso("advertencia", "paso N (visual)", ...)` no bloqueante cuando la duración física supera la voz estimada.

- [ ] **Step 1: Escribir la prueba que falla**

```python
"""Un péndulo doble de diez segundos no cabe en una voz de siete: se avisa antes del render."""

import unittest

from tpi_videos.guion import Guion
from tpi_videos.revision import revisar


def _guion(visual, voz="Mira cómo se mueve."):
    return Guion.model_validate(
        {
            "titulo": "El péndulo doble no repite su camino",
            "materia": "fisica",
            "gancho": {"texto": "¿Se repite?", "voz": "¿Se repite?"},
            "enunciado": {"texto": "Dos brazos.", "voz": "Dos brazos."},
            "pasos": [{"voz": voz, "visual": visual}],
            "resultado": {"tex": "E = 29", "voz": "Veintinueve joules."},
        }
    )


def _avisos(visual, voz="Mira cómo se mueve."):
    revision = revisar(_guion(visual, voz), "Sígueme.")
    return [a for a in revision.avisos if "visual" in a.donde]


DOBLE = {
    "tipo": "pendulo_doble",
    "masa_1": "1 kg",
    "masa_2": "1 kg",
    "longitud_1": "1 m",
    "longitud_2": "1 m",
    "angulo_1": 170,
    "angulo_2": 170,
}


class MovimientoLargoTest(unittest.TestCase):
    def test_el_doble_de_diez_segundos_no_cabe_en_una_voz_corta(self):
        avisos = _avisos(DOBLE, voz="Mira.")
        self.assertTrue(avisos)
        self.assertIn("10", avisos[0].mensaje)
        self.assertIn("no comprime", avisos[0].mensaje)

    def test_si_el_guion_pide_dos_segundos_cabe(self):
        self.assertEqual(_avisos({**DOBLE, "duracion": 2}, voz="Mira. " * 40), [])

    def test_un_dibujo_quieto_no_avisa_de_movimiento(self):
        self.assertEqual(
            _avisos({"tipo": "poligono_regular", "lados": 5, "lado": "12 cm"}, voz="Mira."), []
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correrla y ver que falla**

Run: `.venv/bin/python -m unittest pruebas.test_revision_movimiento -v`
Expected: la primera prueba falla (`AssertionError: False is not true`): todavía no hay aviso.

- [ ] **Step 3: Implementar**

En `revision.py`, cambiar los imports:

```python
from .guion import Guion, Visual
from .visuales import (
    DURACION_RESORTE,
    analizar_circuito,
    analizar_oscilador,
    analizar_pendulo,
    analizar_pendulo_doble,
    analizar_proyectil,
)
```

Agregar antes de `_avisos_de_visuales`:

```python
def _duracion_de_movimiento(visual: Visual) -> float | None:
    """Los segundos de física que pide el dibujo, o ``None`` si el dibujo es quieto."""
    if visual.tipo == "proyectil":
        return analizar_proyectil(visual.velocidad, visual.angulo or 0.0).tiempo
    if visual.tipo == "pendulo":
        return analizar_pendulo(visual.longitud or "", visual.angulo or 0.0).periodo
    if visual.tipo == "resorte":
        return DURACION_RESORTE
    if visual.tipo == "oscilador":
        return analizar_oscilador(
            visual.masa or "",
            visual.constante or "",
            visual.amplitud or "",
            visual.amortiguamiento or "",
            visual.duracion,
        ).hasta
    if visual.tipo == "pendulo_doble":
        figura = analizar_pendulo_doble(
            visual.masa_1 or "",
            visual.masa_2 or "",
            visual.longitud_1 or "",
            visual.longitud_2 or "",
            visual.angulo_1 or 0.0,
            visual.angulo_2 or 0.0,
            visual.duracion,
        )
        return figura.t[-1] - figura.t[0]
    return None
```

En `_avisos_de_visuales`, después de `donde = f"paso {i} (visual)"`:

```python
        fisica = _duracion_de_movimiento(v)
        if fisica is not None:
            voz = estimar_segundos(paso.voz)
            if fisica > voz:
                segundos = f"{fisica:.1f}".replace(".", ",")
                hablado = f"{voz:.1f}".replace(".", ",")
                avisos.append(
                    Aviso(
                        "advertencia",
                        donde,
                        f"el movimiento dura {segundos} s y la voz de este paso dura unos {hablado} s: "
                        "el motor no comprime la física, así que el recorrido se corta antes de terminar. "
                        "Alarga la voz del paso o baja la duración del visual.",
                    )
                )
```

- [ ] **Step 4: Ver verde**

Run: `.venv/bin/python -m unittest pruebas.test_revision_movimiento pruebas.test_revision_poligono -v`
Expected: todo `ok`.

---

### Task 10: Verificación completa, renders y diff

**Files:**
- Modify: ninguno (sólo verificación)
- Test: suite completa

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: evidencia de verde, renders, fotogramas medidos y diff resumido.

- [ ] **Step 1: Suite completa**

Run: `.venv/bin/python -m unittest discover -s pruebas -t .`
Expected: `OK`, sin fallos ni errores. Comparar el número con el de Task 0 (debe subir, no bajar).

- [ ] **Step 2: Formato y lint**

Run:

```bash
uvx ruff format src/tpi_videos/dibujos.py src/tpi_videos/escena.py src/tpi_videos/visuales.py src/tpi_videos/revision.py pruebas/test_dibujos_vivos.py pruebas/test_tiempo_de_movimiento.py pruebas/test_revision_movimiento.py
uvx ruff check src/tpi_videos/dibujos.py src/tpi_videos/escena.py src/tpi_videos/visuales.py src/tpi_videos/revision.py pruebas/test_dibujos_vivos.py pruebas/test_tiempo_de_movimiento.py pruebas/test_revision_movimiento.py
```

Expected: `All checks passed!` (o sólo avisos preexistentes de archivos no tocados).

- [ ] **Step 3: Render pedido por el usuario, sin audio**

Run: `./tpi crear guiones/ejemplos/visuales_tres_tipos.yaml --voz silencio`
Expected: termina sin traceback ni advertencia de Manim; imprime la ruta del MP4 final. Confirmar con `ffprobe` que es 1080×1920 y ~30 fps.

- [ ] **Step 4: Render del proyectil (el caso con más movimiento)**

Run: `./tpi crear guiones/el_tiro_que_nunca_cae_donde_apuntas.yaml --voz silencio`
Expected: termina sin traceback. La bola recorre la parábola y la estela queda; `vx`/`vy` cambian de largo y color.

- [ ] **Step 5: Render del péndulo doble (prueba del corte + aviso)**

Run: `./tpi crear guiones/el_pendulo_que_no_repite_su_camino.yaml --voz silencio`
Expected: termina sin traceback. El paso del péndulo doble muestra el movimiento durante la voz, se corta al final del paso y **la revisión del guion imprime el aviso nuevo** (es la función, no un fallo). Anotar el texto exacto del aviso para el reporte.

- [ ] **Step 6: Juzgar los videos viéndolos a tamaño completo**

Para cada MP4 renderizado:

```bash
MP4=salida/<carpeta>/<archivo>.mp4
ffprobe -v error -show_entries format=duration -show_entries stream=width,height,r_frame_rate -of default=nw=1 "$MP4"
ffmpeg -v error -i "$MP4" -vf freezedetect=n=0.003:d=1.0 -map 0:v -f null - 2>&1 | head -40
```

Y extraer fotogramas **a resolución completa** (nunca miniaturas) en los segundos que el `freezedetect` marque como movimiento, por ejemplo:

```bash
ffmpeg -v error -ss <t> -i "$MP4" -frames:v 1 /tmp/tpi-frame-<t>.png
```

Leer cada PNG con la herramienta de lectura de imágenes y comprobar, a ojo:

1. La bola/punto/brazos se mueve entre fotogramas consecutivos.
2. La estela crece y no nace en el origen ni cruza la banda de subtítulos.
3. Los vectores reactivos cambian de largo/dirección/color; no se salen de la franja.
4. La guía tenue no tapa la estela brillante.
5. El dibujo no invade `BANDA_SUBTITULO = 0.28` (medir el píxel inferior del dibujo y compararlo con el borde de la banda).

Si algo falla, corregir y repetir desde el Step 1.

- [ ] **Step 7: Diff resumido y atribuible**

```bash
git diff --no-index --stat /tmp/tpi-visual-baseline/dibujos.py src/tpi_videos/dibujos.py
git diff --no-index --stat /tmp/tpi-visual-baseline/escena.py src/tpi_videos/escena.py
git diff --no-index --stat /tmp/tpi-visual-baseline/visuales.py src/tpi_videos/visuales.py
git diff --no-index --stat /tmp/tpi-visual-baseline/revision.py src/tpi_videos/revision.py
git status --short -- src/tpi_videos/ pruebas/ guiones/ docs/superpowers/
```

(`git diff --no-index` sale con código 1 cuando hay diferencias: es lo esperado.)

Expected: sólo los cuatro módulos y las pruebas nuevas/modificadas; ningún archivo ajeno borrado ni revertido. **No commitear.**

- [ ] **Step 8: Reporte final al usuario**

Entregar, en español y en una tabla densa:

- Qué se movió en cada archivo (con `ruta:línea`).
- Comando exacto de la suite y su salida (`OK`, número de pruebas).
- Rutas de los MP4 y las marcas de tiempo de los fotogramas revisados.
- El texto del aviso nuevo del péndulo doble.
- Aclaración explícita: sin subagente implementador (no hubo revisión independiente) y **sin commits**.
