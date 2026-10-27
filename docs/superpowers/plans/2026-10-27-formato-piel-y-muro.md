# Fase 12 · Formato, piel, muro e ingeniería 3D — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) o
> superpowers:executing-plans para ejecutar este plan tarea por tarea. Los pasos van con casillas (`- [ ]`).

**Meta:** que @tuprofeindustrial elija libremente el formato de sus videos (sus 4 familias), vea los 24 dibujos
que el motor sabe hacer con su miniatura real, y tenga un área de ingeniería 3D — todo en un panel que no le
bloquea ningún paso.

**Arquitectura:** un catálogo (`formatos.yaml` + la tabla `VISUALES`) es la única fuente de verdad; el motor, el
editor y el muro leen de ahí. Las miniaturas se dibujan **fuera de línea a un PNG** (0,2 s, sin video, sin voz,
sin IA) y el 3D entra por el mismo camino e se inserta como `ImageMobject`, así la escena 2D no se toca.

**Tecnología:** Python 3.12 (`.venv`), Manim Community 0.22, NiceGUI 3.18, pydantic v2, PIL, FFmpeg, LaTeX.

**Spec:** `docs/superpowers/specs/2026-10-27-panel-hoja-y-muro-design.md` (leerla antes de tocar nada).

## Reglas de todo el plan

- Repo: `/Users/documentos/Downloads/tuprofeindustrial-videos`. **El cwd de la shell se resetea en cada
  comando: siempre `cd /Users/documentos/Downloads/tuprofeindustrial-videos &&` delante.**
- Pruebas: `.venv/bin/python -m unittest discover -s pruebas -t .` (292 OK hoy).
  **Nunca el `python3` del sistema: no tiene PIL.**
- Lint: `uvx ruff@0.12 check src pruebas` y `uvx ruff@0.12 format src pruebas` (largo de línea 110).
  **En el árbol de hoy ese comando falla con 10 hallazgos anteriores a la fase 12:** la Tarea 0.0 los limpia
  primero. Desde ahí, cualquier salida de ruff es culpa de la tarea que la produjo.
- Commit **siempre** con la identidad en la misma línea:
  `git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m '...'`.
  **Jamás** `git config`.
- **Sin push y sin merge** sin OK explícito del usuario (ya hay ~15 commits sin empujar).
- **Ninguna llamada a IA paga ni cuota de Gemini.** Todo se prueba con guiones escritos a mano.
- Sin sondeos: si un render largo va en background, **se espera su notificación**. Nada de `sleep`, nada de
  `grep`/`sed` en la shell (usar Read/Grep/Edit).
- Antes de decir «listo» en cualquier tarea: **mirar el cuadro**. Un render que termina no prueba que se vea
  bien; los 4 defectos de los 17 temas se encontraron así.
- Estilo del repo: español en todo lo que ve el usuario, comentarios solo si el *por qué* no es obvio, sin
  compatibilidades muertas, sin validaciones de escenarios imposibles.
- Convención de pruebas: archivo `pruebas/test_<algo>.py`, `import unittest`, `from tpi_videos.<modulo> import
  ...` (el paquete está instal editable en `.venv`, no hace falta tocar `sys.path`), y para lo que necesite
  manim:

```python
try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:
    MANIM = False
```

con `@unittest.skipUnless(MANIM, "manim no esta instalado")` en la clase que dibuja.

---

## Hito 0 — Cerrar la casa antes de mudarse

### Tarea 0.0 · Dejar el lint en verde (10 hallazgos anteriores a la fase 12)

**Archivos:** modificar `src/tpi_videos/ganchos.py:17`, `src/tpi_videos/ideas.py:126`,
`src/tpi_videos/lote.py:266`, `src/tpi_videos/panel/paginas/crear.py:236`,
`src/tpi_videos/panel/paginas/fabrica.py:299` y `:305`, `src/tpi_videos/redactor.py:21` y `:875-877`.

**Carácter:** **ninguna tarea de este plan puede comprobarse sin esto.** Todos los pasos de commit terminan con
`uvx ruff@0.12 check src pruebas && ...`, y hoy ese comando **ya falla en el árbol limpio** con 10 hallazgos
que no son de la fase 12. Sin esta tarea, el primer `&&` corta antes del commit y el ejecutor empieza a
inventar atajos. Medido el 2026-10-27 con `uvx ruff@0.12 check src` sobre `HEAD`:

```
ganchos.py:17      F401  import de Gancho que nadie usa
ideas.py:126       UP037  comillas sobrantes en la anotación
lote.py:266        B023  la lambda lee seguir/paso de la última vuelta del bucle
crear.py:236       B023  la lambda lee elegido_label de la última tarjeta
fabrica.py:299,305 E741  nombre «l» ambiguo
redactor.py:21     UP035  Callable se importa de collections.abc
redactor.py:875,6  F541  f-string sin placeholders
```

Los dos **B023 son bugs reales**, no ruido: en `crear.py`, `elegido_label` es la etiqueta de la tarjeta y la
lambda se resuelve al hacer clic, así que con 3 ideas en pantalla el botón «Probar ganchos» de la primera
reescribe el gancho de la última. Atar el valor con un argumento por defecto lo arregla y no cambia nada más.

- [ ] **Paso 1 — Aplicar los diez arreglos**

```python
# ganchos.py:17 — quitar Gancho del import (nadie lo trae desde .ganchos; cli.py y las pruebas
# solo usan elegir_gancho / idea_desde_guion / renderizar_ganchos / guion_de_vista_previa)
from .guion import Guion, a_yaml, cabecera_de, cargar_guion, sin_tildes

# ideas.py:126 — sin comillas
def _gancho_y_ganchos(self) -> Idea:

# lote.py:266 — atar las dos variables del bucle
esperar=lambda intento, segundos, _s=seguir, _p=paso: _esperar_ia(_s, _p, intento, segundos),

# crear.py:236 — atar la etiqueta de ESTA tarjeta, no la última
on_click=lambda i=idea, e=elegido_label: self._probar_ganchos(i, e),

# fabrica.py:299 y :305 — «l» es ilegible y ruff lo marca
on_click=lambda lt=lote: self._reanudar_lote(lt["id"]),
on_click=lambda lt=lote: self._confirmar_descarte(lt),

# redactor.py:21 — Callable del sitio correcto
from collections.abc import Callable
from typing import Any, Literal

# redactor.py:875-877 — las tres líneas son texto fijo; solo la 874 tiene placeholder
ayuda="El cupo se reinicia de madrugada (medianoche hora del Pacífico): mira cuánto "
"te queda con ./tpi cuota. Si apura, escribe el guion a mano y créalo igual: "
"./tpi crear guiones/<archivo>.yaml",
```

- [ ] **Paso 2 — Verde, y la suite sin daños**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3
```

Esperado: ruff sin salida (exit 0) y `OK` con 292 pruebas. Si alguna prueba de `test_ganchos.py` o
`test_lote.py` se cae, la corrección tocó semántica: **revisar el dif antes de seguir**, no ajustar la prueba.

- [ ] **Paso 3 — Comprobar el bug del panel en la pantalla**

`./tpi panel` → pantalla Crear con 3 ideas y clic en «Probar ganchos» de la **primera**: la etiqueta que cambia
es la de esa tarjeta. (Antes del arreglo cambiaba la de la última.)

- [ ] **Paso 4 — Commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
git add src/tpi_videos/ganchos.py src/tpi_videos/ideas.py src/tpi_videos/lote.py \
        src/tpi_videos/redactor.py src/tpi_videos/panel/paginas/crear.py \
        src/tpi_videos/panel/paginas/fabrica.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'Limpieza: el lint del repo queda en verde y el botón de ganchos usa su propia tarjeta'
```

---

### Tarea 0.1 · Dejar el árbol pendiente en claro

**Archivos:** `guiones/centro_de_gravedad_en_una_placa.yaml` (sin versionar),
`guiones/el_tanque_que_pierde.yaml` (sin versionar, duplica a `guiones/el_tanque_que_se_llena_y_pierde.yaml`).

**Carácter:** esta tarea **no** toca `dibujos.py`, `guion.py` ni `visuales.py`. Nada de la fase 12 puede
pisar el trabajo de la fase 11 mientras quede sin cerrar.

- [ ] **Paso 1 — Estado de partida, medido, no recordado**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && git status --short && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3
```

Esperado: los dos guiones como `??` y `Ran 292 tests ... OK`. Si los tests no están en verde **separa el plan
aquí**: el resto asume una base verde.

- [ ] **Paso 2 — Revisar los dos guiones con el motor, sin IA**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && ./tpi revisar guiones/centro_de_gravedad_en_una_placa.yaml && \
./tpi revisar guiones/el_tanque_que_pierde.yaml
```

Esperado: `Sin observaciones` en ambos, o la lista de errores en español del revisor.

- [ ] **Paso 3 — Decidir (con el usuario, en una sola pregunta, sin bloquear nada)**

El duplicado se resuelve así: si `el_tanque_que_pierde.yaml` no aporta un enunciado distinto, **se archiva**
fuera del árbol de trabajo, no se borra:

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && mkdir -p fuera_de_uso && \
mv guiones/el_tanque_que_pierde.yaml fuera_de_uso/ && ls guiones/ | head
```

`centro_de_gravedad_en_una_placa.yaml` **se versiona** (es contenido nuevo del canal, no basura).

- [ ] **Paso 4 — Commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && git add guiones/centro_de_gravedad_en_una_placa.yaml && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'Centro de gravedad: el guion de ingeniería que faltaba'
```

---

## Hito A — Motor: las cuatro familias y tres arreglos gratis

### Tarea A.1 · `formatos.yaml` + `formatos.py` (catálogo y puntador, sin IA)

**Archivos:**
- Crear: `src/tpi_videos/plantillas/formatos.yaml`
- Crear: `src/tpi_videos/formatos.py`
- Probar: `pruebas/test_formatos.py`

**Producción (lo que usan las tareas siguientes, con nombres exactos):**

```python
formatos.FORMATO_POR_DEFECTO: str
formatos.cargar_formatos() -> dict[str, Formato]
formatos.formato(clave: str | None) -> Formato           # ErrorMotor con opciones si no existe
formatos.puntuar_idea(texto: str) -> str | None
formatos.formato_de_guion(guion: Guion) -> Formato | None
formatos.Formato  # dataclass congelada: clave, nombre, que_es, moldes, tema, dibujos, color, cta, gancho_corto
```

- [ ] **Paso 1 — Escribir la prueba que falla**

`pruebas/test_formatos.py`:

```python
import unittest

from tpi_videos.errores import ErrorMotor
from tpi_videos.formatos import (
    cargar_formatos,
    formato,
    formato_de_guion,
    puntuar_idea,
)
from tpi_videos.moldes import MOLDES


class CatalogoTest(unittest.TestCase):
    def test_las_cuatro_familias_del_autor_estan_y_son_coherentes(self):
        familias = cargar_formatos()
        self.assertEqual(set(familias), {"trampas", "paso_a_paso", "datos", "hacks"})
        for f in familias.values():
            self.assertTrue(f.nombre and f.que_es and f.cta)
            self.assertTrue(f.moldes, f"{f.clave} sin molde")
            for molde in f.moldes:
                self.assertIn(molde, MOLDES, f"{f.clave} apunta a un molde que no existe")
            for dibujo in f.dibujos:
                self.assertRegex(dibujo, r"^[a-z_]+$", f"{f.clave} con dibujo mal escrito")
            self.assertRegex(f.color, r"^#[0-9A-Fa-f]{6}$")

    def test_clave_desconocida_dice_cuales_son(self):
        with self.assertRaises(ErrorMotor) as sube:
            formato("nada_de esto")
        self.assertIn("trampas", str(sube.exception))

    def test_formato_de_guion_devuelve_la_familia_de_su_molde(self):
        from tpi_videos.guion import Guion

        import yaml
        from pathlib import Path

        ruta = Path("src/tpi_videos/plantillas/vista_previa.yaml")
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        datos["molde"] = "reto"
        guion = Guion.model_validate(datos)
        self.assertEqual(formato_de_guion(guion).clave, "trampas")


class PuntadorTest(unittest.TestCase):
    def test_cada_idea_de_ejemplo_marca_su_familia(self):
        casos = {
            "32 por 11 sin lápiz: un atajo de dos segundos": "hacks",
            "¿Encuentras el error sutil en esta división?": "trampas",
            "POV: tienes que calcular la caída antes del timbre": "paso_a_paso",
            "Una parada de bus con datos de la ciudad": "datos",
        }
        for idea, esperado in casos.items():
            self.assertEqual(puntuar_idea(idea), esperado, idea)

    def test_texto_vacio_o_sin_palabras_no_marca_nada(self):
        for idea in ("", "   ", "hola", "la materia es difícil"):
            self.assertIsNone(puntuar_idea(idea), idea)

    def test_no_llama_a_ningun_proveedor_de_ia(self):
        import inspect

        from tpi_videos import formatos

        fuente = inspect.getsource(formatos)
        self.assertNotIn("ideas.", fuente)
        self.assertNotIn("redactor", fuente)


class ResolucionTest(unittest.TestCase):
    def test_la_copia_del_autor_gana_sobre_la_del_motor(self):
        from unittest import mock

        import yaml
        from tpi_videos import formatos as mod

        propio = yaml.safe_load((mod.PLANTILLA).read_text(encoding="utf-8"))
        propio["hacks"]["nombre"] = "Trucos míos"
        texto = yaml.safe_dump(propio, allow_unicode=True)
        with mock.patch.object(mod, "_ruta_usuario", lambda: mock_path(texto)):
            self.assertEqual(mod.cargar_formatos()["hacks"].nombre, "Trucos míos")


def mock_path(texto: str):
    import tempfile
    from pathlib import Path

    ruta = Path(tempfile.mkdtemp()) / "formatos.yaml"
    ruta.write_text(texto, encoding="utf-8")
    return ruta
```

- [ ] **Paso 2 — Correr y ver que falla**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_formatos -v 2>&1 | tail -5
```

Esperado: `ModuleNotFoundError: No module named 'tpi_videos.formatos'`.

- [ ] **Paso 3 — Escribir `plantillas/formatos.yaml`**

Las cuatro familias son **textuales de él** (27-10-2026). El `cta` **nunca** se narra en el video: va al pie
del post (así lo fija su regla de CTA-de-engaño). `solido_3d` aparece en la familia 1 solo a partir de la
tarea D.2; en esta tarea se pone `solido` para que el catálogo sea válido desde el día uno.

```yaml
# Las cuatro familias de contenido del canal (decisión del autor, 27-10-2026).
#   moldes: claves de src/tpi_videos/moldes.py
#   tema:   clave de plantillas/temas/  (el estilo que sugiere la tarjeta)
#   dibujos: tipos de Visual            (los que suelen cargar la explicación)
#   cta:    SOLO para el pie del post. En el video no se pide seguir ni comentar.
#   gancho_corto: la tarjeta ofrece el clip de gancho suelto (crear_clip_gancho) como video de ~5 s.

trampas:
  nombre: Desafíos y trampas cognitivas
  que_es: >-
    Un reto de cinco segundos, un error sutil que hay que encontrar o un resultado que parece magia.
    El espectador se queda para comprobar si tenía razón.
  moldes: [reto, mito_realidad]
  tema: neon_reja
  dibujos: [poligono_regular, venn, probabilidad, solido]
  color: "#FF3B5C"
  cta: "¿Lo viste o te engañó? Cuéntame en el pie."
  gancho_corto: true

paso_a_paso:
  nombre: Paso a paso dinámico
  que_es: >-
    Una explicación cronometrada: el método tradicional contra la forma rápida, o POV escribiéndolo en la
    hoja. Sirve cuando lo que se enseña es un procedimiento.
  moldes: [pov]
  tema: kraft_tiza
  dibujos: [bloques, engranaje, viga, circuito]
  color: "#FDE047"
  cta: "¿Qué paso te tomaría más tiempo a ti?"
  gancho_corto: false

datos:
  nombre: Visualización de datos e historias
  que_es: >-
    Una paradoja famosa, una escala visual o las cuentas de algo que ya conoce. El dibujo carga el peso:
    primero se ve, después se explica.
  moldes: [nadie_te_enseno]
  tema: plano_azul
  dibujos: [barras, torta, tanque, energia]
  color: "#38BDF8"
  cta: "¿Con qué número te quedas?"
  gancho_corto: false

hacks:
  nombre: Operaciones eficientes y hacks de cálculo mental
  que_es: >-
    Un truco exprés, un atajo numérico o una comprobación en dos segundos. Se vende como lo que no te
    enseñaron en la sala.
  moldes: [tres_errores, mito_realidad]
  tema: rotulador
  dibujos: [recta, grafico_funcion, pendulo, mohr]
  color: "#A78BFA"
  cta: "¿Cuál usabas tú antes de esto?"
  gancho_corto: false
```

- [ ] **Paso 4 — Escribir `src/tpi_videos/formatos.py`**

```python
"""Las familias de contenido del canal: molde + estilo + dibujo en una sola elección.

Se leen de ``plantillas/formatos.yaml`` (viaja con el motor) y de ``mis_ajustes/formatos.yaml`` (las del
autor, que ganan porque Git ignora esa carpeta). ``puntuar_idea()`` es un conteo de palabras: sin IA y sin
cuota, y si no reconoce nada no marca ninguna familia.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .entorno import PLANTILLAS_DIR, raiz_proyecto
from .errores import ErrorMotor

PLANTILLA = PLANTILLAS_DIR / "formatos.yaml"
FORMATO_POR_DEFECTO = "datos"


@dataclass(frozen=True)
class Formato:
    clave: str
    nombre: str
    que_es: str
    moldes: tuple[str, ...]
    tema: str
    dibujos: tuple[str, ...]
    color: str
    cta: str
    gancho_corto: bool = False


def _ruta_usuario() -> Path:
    return raiz_proyecto() / "mis_ajustes" / "formatos.yaml"


def _una(clave: str, datos: dict, origen: Path) -> Formato:
    try:
        return Formato(
            clave=clave,
            nombre=str(datos["nombre"]),
            que_es=" ".join(str(datos["que_es"]).split()),
            moldes=tuple(datos["moldes"]),
            tema=str(datos["tema"]),
            dibujos=tuple(datos["dibujos"]),
            color=str(datos["color"]),
            cta=str(datos["cta"]),
            gancho_corto=bool(datos.get("gancho_corto", False)),
        )
    except KeyError as e:
        raise ErrorMotor(f"La familia {clave} de {origen.name} no tiene el campo {e}.") from e


def _leer(ruta: Path) -> dict[str, Formato]:
    if not ruta.exists():
        return {}
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return {clave: _una(clave, valor, ruta) for clave, valor in datos.items() if isinstance(valor, dict)}


def cargar_formatos() -> dict[str, Formato]:
    """Las familias del motor, con las propias encima si repiten clave."""
    salida = _leer(PLANTILLA)
    salida.update(_leer(_ruta_usuario()))
    return salida


def formato(clave: str | None) -> Formato:
    claves = cargar_formatos()
    if clave in claves:
        return claves[clave]
    raise ErrorMotor(
        f"No conozco la familia «{clave}».",
        ayuda=f"Opciones: {', '.join(claves)} (o «tpi formatos»).",
    )


def _limpio(texto: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", texto.casefold())
        if not unicodedata.combining(c)
    )


# Palabras que delatan cada familia. Se cuentan apariciones, no ocurrencias: una idea corta no debe
# empatar con otra por casualidad (por eso el margen de puntuar_idea).
_PISTAS: dict[str, tuple[str, ...]] = {
    "trampas": ("trampa", "reto", "desafio", "magia", "sutil", "engana", "encuentra", "truco de magia"),
    "paso_a_paso": ("paso a paso", "pov", "cronometro", "tradicional", "procedimiento", "paso por paso"),
    "datos": ("dato", "datos", "grafico", "porcentaje", "escala", "paradoja", "historia", "poblacion",
              "promedio", "cultura", "datos de"),
    "hacks": ("truco", "hacks", "hack", "atajo", "atalajo", "mental", "rapido", "sin calculadora",
              "comprobacion", "expres"),
}
_PISTAS["hacks"] = tuple(dict.fromkeys(_PISTAS["hacks"] + ("minuto", "dos segundos")))


def puntuar_idea(texto: str) -> str | None:
    """La familia con más palabras clave; None si none destaca o si dos empatan."""
    limpio = _limpio(texto or "")
    if not limpio.strip():
        return None
    puntos = {
        clave: sum(limpio.count(palabra) for palabra en palabras)
        for clave, palabras in _PISTAS.items()
    }
    mejor = max(puntos, key=lambda clave: puntos[clave])
    if puntos[mejor] < 2:
        return None
    if list(puntos.values()).count(puntos[mejor]) > 1:
        return None
    return mejor


def formato_de_guion(guion) -> Formato | None:
    """La familia que carga con el molde elegido en el guion, o None si el guion va libre."""
    if not guion.molde:
        return None
    for familia in cargar_formatos().values():
        if guion.molde in familia.moldes:
            return familia
    return None


def tabla_para_ia() -> str:
    """Las familias como tabla, para el prompt del productor de ideas."""
    lineas = ["| clave | familia | moldes | estilo |", "|---|---|---|---|"]
    for f in cargar_formatos().values():
        lineas.append(f"| `{f.clave}` | {f.nombre} | {', '.join(f.moldes)} | {f.tema} |")
    return "\n".join(lineas)
```

Nota de diseño: `_PISTAS` es la **única** parte de este plan que hay que ajustar con datos propios. Si al
usuario una idea suya le sale mal puntuada, se agrega esa palabra a `_PISTAS`, no se cambia el puntador.

- [ ] **Paso 5 — Correr la prueba**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_formatos -v 2>&1 | tail -12
```

Esperado: `OK` (7 pruebas). Si `test_cada_idea_de_ejemplo_marca_su_familia` falla, **no** baje el umbral:
mire qué cuenta el puntador con una REPL y corrija `_PISTAS`.

- [ ] **Paso 6 — Prueba real de coherencia con el resto del motor**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -c "
from tpi_videos.formatos import cargar_formatos
from tpi_videos.temas import existe_tema
from tpi_videos.guion import Visual
tipos = set(Visual.model_fields['tipo'].metadata[0]['literal_arguments'])
for k, f in cargar_formatos().items():
    assert existe_tema(f.tema), (k, f.tema)
    assert set(f.dibujos) <= tipos, (k, set(f.dibujos) - tipos)
print('familias coherentes con temas y Visual')
"
```

Esperado: `familias coherentes con temas y Visual`. (Los temas `neon_reja`, `kraft_tiza`, `plano_azul` y
`rotulador` existen desde la promoción de `677f195`.)

- [ ] **Paso 7 — Suite completa, lint y commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add src/tpi_videos/formatos.py src/tpi_videos/plantillas/formatos.yaml pruebas/test_formatos.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'Formatos: las cuatro familias del canal, con su molde, su estilo y su puntador sin IA'
```

---

### Tarea A.2 · La etiqueta de la hoja deja de pintarse en blanco

**Archivos:** modificar `src/tpi_videos/componentes.py:579` · probar `pruebas/test_piel.py`

- [ ] **Paso 1 — Prueba que falla**

`pruebas/test_piel.py`:

```python
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:
    MANIM = False

from tpi_videos.componentes import marco_hoja
from tpi_videos.config import cargar_marca
from tpi_videos.temas import Tema, cargar_tema


@unittest.skipUnless(MANIM, "manim no esta instalado")
class HojaTest(unittest.TestCase):
    def _texto(self, tema):
        marco = marco_hoja(tema)
        return next(m for m in marco.family_members_with_points() if getattr(m, "text", "") == "Notas")

    def test_la_etiqueta_usa_el_color_tenue_del_tema(self):
        marca = cargar_marca()
        for ident in ("hoja_de_desarrollo", "kraft_claro"):
            tema = cargar_tema(ident, marca)
            self.assertEqual(str(self._texto(tema).color).upper(), tema.colores.tenue.upper(), ident)

    def test_la_etiqueta_no_es_blanca_ni_sobre_papel_claro(self):
        tema = cargar_tema("kraft_claro", cargar_marca())
        self.assertNotEqual(str(self._texto(tema).color).upper(), "#FFFFFF")
```

- [ ] **Paso 2 — Verificar que falla y por qué**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_piel -v 2>&1 | tail -8
```

Esperado: `AssertionError: '#FFFFFF' != ...` (en manim 0.22 el color se lee con `str(mobject.color)`; no
existe `.get_hex_l()` ni `MColor`).

- [ ] **Paso 3 — Arreglo de una línea**

En `componentes.py`, dentro de `marco_hoja`, la rama de `h.etiqueta`:

```python
    if h.etiqueta.strip():
        etiqueta = Text(
            h.etiqueta.strip(), font="Montserrat", weight=MEDIUM, font_size=34, color=tema.colores.tenue
        )
```

(cambia solo `color="#FFFFFF"`; el alto y la posición quedan igual para no mover el resto del marco).

- [ ] **Paso 4 — Prueba verde + un cuadro mirado**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_piel -v 2>&1 | tail -4
```

Luego abrir con `Read` un fotograma real de `kraft_claro` (el que ya está en `salida/_vistas/kraft_claro/`,
o generar uno con `./tpi crear guiones/ejemplos/moldes_virales.yaml --borrador --voz silencio
--sincronizar estimado --sin-subtitulos --salida /tmp/tallerA2`) y **confirmar con los ojos** que «Notas» se
lee sobre el papel claro.

- [ ] **Paso 5 — Commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
git add src/tpi_videos/componentes.py pruebas/test_piel.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'La etiqueta de la hoja usa el tenue del tema: en papel claro era invisible'
```

---

### Tarea A.3 · El borde del subtítulo deja de ser negro fijo

**Archivos:** `src/tpi_videos/config.py` (`EstiloSubtitulos`), `src/tpi_videos/subtitulos.py:229`,
`src/tpi_videos/plantillas/temas/*.yaml` (los claros), probar en `pruebas/test_piel.py`.

**Por qué:** con `kraft_claro`/`cuaderno_*` el texto es oscuro sobre crema y el borde negro lo embarra.

- [ ] **Paso 1 — Prueba que falla** (agregar a `pruebas/test_piel.py`)

```python
class BordeSubtituloTest(unittest.TestCase):
    def _linea_estilo(self, tema) -> str:
        from tpi_videos.subtitulos import Palabra, escribir_ass

        estilo = tema.subtitulos.model_copy(update={"color": "#2B2B2B", "color_borde": "#FBF7EC"})
        palabra = Palabra(texto="Hola", inicio=0.0, fin=0.5)
        ruta = Path("/tmp/borde_prueba.ass")
        escribir_ass([[palabra]], ruta, estilo)
        return next(l for l in ruta.read_text(encoding="utf-8").splitlines() if l.startswith("Style: CapCut"))

    def test_el_borde_del_subtitulo_usa_el_color_del_tema(self):
        from tpi_videos.config import cargar_marca
        from tpi_videos.temas import cargar_tema

        linea = self._linea_estilo(cargar_tema("kraft_claro", cargar_marca()))
        campos = [c.strip() for c in linea.split(",")]
        self.assertEqual(campos[6], "&H00ECF7FB", campos[6])  # &HAABBGGRR de #FBF7EC

    def test_sin_color_borde_sigue_saliendo_negro(self):
        from tpi_videos.config import EstiloSubtitulos
        from unittest import mock

        tema = mock.Mock(subtitulos=EstiloSubtitulos())
        linea = self._linea_estilo(tema)
        self.assertEqual([c.strip() for c in linea.split(",")][6], "&H00000000")
```

- [ ] **Paso 2 — Verificar que falla**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_piel.BordeSubtituloTest -v 2>&1 | tail -6
```

Esperado: `ValidationError` / `TypeError` en `color_borde` (el campo aún no existe).

- [ ] **Paso 3 — Campo nuevo con default que no cambia nada**

En `config.py`, clase `EstiloSubtitulos`, justo debajo de `color_activo`:

```python
    color_borde: str = "#000000"  # el contorno; en temas claros va el color del papel
```

y en el validador de hex, agregarlo:

```python
    _hex = field_validator("color", "color_activo", "color_borde")(classmethod(lambda cls, v: _validar_hex(v)))
```

- [ ] **Paso 4 — Usarlo en el ASS**

En `subtitulos.py:229`, la línea `Style: CapCut` ya tiene un `&H00000000` literal; reemplazar **solo** ese
literal por la llamada existente (no inventar un formato nuevo):

```python
        f"Style: CapCut,{estilo.fuente},{estilo.tamano},{blanco},{blanco},{_color_ass(estilo.color_borde)},"
        f"&H78000000,0,0,0,0,"
```

- [ ] **Paso 5 — Los temas claros ponen su papel como borde**

Son los temas con `marco: hoja` o fondo claro. Aplicar por lista leída, no por suposición:

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && grep -l 'fondo: "#F' src/tpi_videos/plantillas/temas/*.yaml
```

En cada archivo que salga, dentro del bloque `subtitulos:` agregar `color_borde: "<el mismo color de
colores.fondo>"`. Si un tema no tiene bloque `subtitulos:`, crearlo con solo esa clave.

- [ ] **Paso 6 — Suite, revisar, mirar, commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
./tpi revisar guiones/ejemplos/moldes_virales.yaml && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add -u src/tpi_videos pruebas/test_piel.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'El borde del subtítulo es un color del tema: sobre crema el negro embarraba'
```

---

### Tarea A.4 · Las ocho familias de letras llegan al panel

**Archivos:** `src/tpi_videos/tipografia.py:38-39`.

- [ ] **Paso 1 — Prueba** (agregar a `pruebas/test_piel.py`)

```python
class LetrasTest(unittest.TestCase):
    def test_el_panel_ofrece_todas_las_letras_del_motor(self):
        from tpi_videos.tipografia import FAMILIAS, PARA_TEXTO, PARA_TITULOS

        self.assertEqual(set(PARA_TITULOS), set(FAMILIAS))
        self.assertEqual(set(PARA_TEXTO), set(FAMILIAS))
        for extra in ("Bangers", "Luckiest Guy", "Cinzel"):
            self.assertIn(extra, PARA_TITULOS)
```

- [ ] **Paso 2 — Verificar que falla**: `AssertionError: Items in the first set are not in the second` para
  Bangers/Luckiest Guy/Cinzel.
- [ ] **Paso 3 — Cambio**: en `tipografia.py`, reemplazar las dos tuplas literales por

```python
# Opciones que ofrece el panel para cada uso: todo lo que el motor trae embebido.
PARA_TITULOS = tuple(FAMILIAS)
PARA_TEXTO = tuple(FAMILIAS)
```

`PARA_SUBTITULOS` **no** se toca: son nombres como los busca libass (familia + estilo en una sola cadena), y
`Bangers`/`Luckiest Guy` ya están ahí.

- [ ] **Paso 4 — Comprobar que ningún tema viejo pide una letra inexistente**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -c "
from tpi_videos.config import cargar_marca
from tpi_videos.temas import listar_temas, _leer
from tpi_videos.temas import TEMAS_DIR
marca = cargar_marca()
for ident, _, _ in listar_temas():
    t = _leer(TEMAS_DIR / f'{ident}.yaml')
    print(ident, t.tipografia.titulos.familia, '/', t.tipografia.texto.familia)
" | sort
```

Esperado: 19 líneas, todas con familias que están en `FAMILIAS`. Si alguna sale con error, **no** la cambie a
una parecida: repórtela (sería un tema roto en la promoción).

- [ ] **Paso 5 — Verde, lint, commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && \
git add src/tpi_videos/tipografia.py pruebas/test_piel.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'Ocho familias de letras en el selector: Bangers, Luckiest Guy y Cinzel estaban fuera'
```

---

## Hito B — Editor: los 24 dibujos, su miniatura y el LaTeX en vivo

### Tarea B.1 · La tabla `VISUALES` (un solo catálogo, escrito una vez)

**Archivos:** modificar `src/tpi_videos/visuales.py` · crear `pruebas/test_visuales.py`

**Qué existe hoy y por qué está mal:**

- `visuales.py:15` `TIPOS_VISUAL` es una tupla vieja de **4** entradas que **no importa nadie** → se borra.
- `panel/editor.py:44-55` tiene `_TIPOS_VISUAL` (3 tipos) y `_VISUAL_CAMPOS` escritos a mano.
- `_campos_del_tipo` (`guion.py:288-505`) es un `model_validator`: dice qué **falta**, no qué campos tiene
  cada tipo. No se puede derivar de ahí, así que la tabla se escribe a mano **una vez** y una prueba la
  obliga a permanecer completa.

**Producción (nombres exactos para B.2 y B.3):**

```python
visuales.CAMPOS: dict[str, CampoVisual]
visuales.VISUALES: dict[str, TipoVisual]
visuales.opciones_select() -> dict[str, str]
visuales.TipoVisual  # clave, nombre, materia, icono, campos, marcas, ejemplo
visuales.CampoVisual  # clave, etiqueta, forma, ayuda, opciones
```

- [ ] **Paso 1 — Prueba que falla**

`pruebas/test_visuales.py`:

```python
import unittest

from tpi_videos.guion import Visual
from tpi_videos.visuales import CAMPOS, SEGUNDOS_VISUAL, VISUALES, TipoVisual, opciones_select


def tipos_del_modelo() -> set[str]:
    return set(Visual.model_fields["tipo"].metadata[0]["literal_arguments"])


class TablaTest(unittest.TestCase):
    def test_la_tabla_cubre_todos_los_tipos_del_modelo(self):
        self.assertEqual(set(VISUALES), tipos_del_modelo())
        self.assertGreaterEqual(len(VISUALES), 24)

    def test_todo_campo_mencionado_existe_en_el_modelo(self):
        campos = set(Visual.model_fields)
        for tipo in VISUALES.values():
            for clave in tipo.campos:
                self.assertIn(clave, campos, f"{tipo.clave} usa {clave}, que Visual no tiene")

    def test_ningun_tipo_queda_sin_campos_ni_sin_segundos_estimados(self):
        for clave, tipo in VISUALES.items():
            self.assertTrue(tipo.nombre and tipo.icono and tipo.materia, clave)
            self.assertTrue(tipo.ejemplo, f"{clave} sin ejemplo para la miniatura")
            self.assertIn(clave, SEGUNDOS_VISUAL, f"{clave} no suma duración")

    def test_el_ejemplo_de_cada_tipo_valida_con_Visual(self):
        for clave, tipo in VISUALES.items():
            Visual.model_validate({"tipo": clave, **tipo.ejemplo})  # no debe lanzar ValidationError

    def test_las_marcas_prometidas_son_las_del_motor(self):
        from tpi_videos import visuales as v

        esperadas = {
            "poligono_regular": v.MARCAS_POLIGONO,
            "proyectil": v.MARCAS_PROYECTIL,
            "circulo_trig": v.MARCAS_CIRCULO,
            "solido": v.MARCAS_SOLIDO,
            "venn": v.MARCAS_VENN,
            "probabilidad": v.MARCAS_PROBABILIDAD,
            "onda": v.MARCAS_ONDA,
            "pendulo": v.MARCAS_PENDULO,
            "resorte": v.MARCAS_RESORTE,
            "polea": v.MARCAS_POLEA,
            "tanque": v.MARCAS_TANQUE,
            "viga": v.MARCAS_VIGA,
            "cercha": v.MARCAS_CERCHA,
            "bloques": v.MARCAS_BLOQUES,
            "engranaje": v.MARCAS_ENGRANAJE,
            "mohr": v.MARCAS_MOHR,
        }
        for clave, marcas in esperadas.items():
            self.assertEqual(VISUALES[clave].marcas, tuple(marcas), clave)

    def test_la_lista_del_select_trae_a_todos_con_su_materia(self):
        opciones = opciones_select()
        self.assertEqual(set(opciones), {"", *tipos_del_modelo()})
        self.assertEqual(opciones[""], "Sin dibujo")
        self.assertTrue(opciones["poligono_regular"].startswith("Matemática · "))
        self.assertTrue(opciones["mohr"].startswith("Ingeniería · "))

    def test_todo_dibujo_que_promete_una_familia_existe_en_la_tabla(self):
        """El spec (§9) lo pide, y en A.1 no se podía probar: la tabla nacía acá.
        Si una tarjeta ofrece un dibujo que el motor no sabe hacer, el video se cae en el paso 3."""
        from tpi_videos.formatos import cargar_formatos

        for clave, familia in cargar_formatos().items():
            for dibujo in familia.dibujos:
                self.assertIn(dibujo, VISUALES, f"la familia {clave} promete {dibujo}")


class Tipo3dReservadoTest(unittest.TestCase):
    def test_solido_3d_aun_no_esta_en_el_modelo_pero_si_en_el_plan(self):
        # El hito D lo agrega. Acá solo se deja constancia de que la tabla se diseña para crecer.
        self.assertNotIn("solido_3d", VISUALES)
```

- [ ] **Paso 2 — Verificar que falla**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_visuales -v 2>&1 | tail -6
```

Esperado: `ImportError: cannot import name 'VISUALES'`.

- [ ] **Paso 3 — Escribir la tabla en `visuales.py`**

Borrar la línea 15 (`TIPOS_VISUAL = (...)`) y agregar debajo de `ARREGLOS = ("serie", "paralelo")`:

```python
# --------------------------------------------------------------------------------------
# El catálogo: qué campos y qué marcas tiene cada dibujo. El panel lo lee para armar el
# formulario, así que agregar un tipo al modelo sin agregarlo acá rompe una prueba.
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CampoVisual:
    clave: str
    etiqueta: str
    forma: str = "texto"  # texto | numero | numeros | lista | opcion | booleano
    ayuda: str = ""
    opciones: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class TipoVisual:
    clave: str
    nombre: str
    materia: str  # matematica | fisica | ingenieria
    icono: str
    campos: tuple[str, ...]
    marcas: tuple[str, ...] = ()
    ejemplo: dict[str, Any] = field(default_factory=dict)


_MATERIAS = {"matematica": "Matemática", "fisica": "Física", "ingenieria": "Ingeniería"}

CAMPOS: dict[str, CampoVisual] = {
    c.clave: c
    for c in [
        CampoVisual("funcion", "La función, en texto plano", "texto", "-4.9t^2 + 20   ·   12/U   ·   sin(x)"),
        CampoVisual("variable", "La variable", "texto", "t"),
        CampoVisual("eje_x", "Eje horizontal", "texto", "tiempo (s)"),
        CampoVisual("eje_y", "Eje vertical", "texto", "altura (m)"),
        CampoVisual("rango", "Rango del eje horizontal", "numeros", "0 a 2,5"),
        CampoVisual("marcar", "Puntos con su valor escrito", "numeros", "0; 2,45"),
        CampoVisual(
            "cuerpo", "El cuerpo", "opcion", "", (("bloque", "Bloque (una caja)"), ("bola", "Bola"))
        ),
        CampoVisual("vectores", "Flechas del cuerpo", "lista"),
        CampoVisual("angulo", "Ángulo en grados", "numero", "30"),
        CampoVisual("descomponer", "Partir el peso en P sen θ y P cos θ", "booleano"),
        CampoVisual("fuente", "La fuente", "texto", "12 V"),
        CampoVisual(
            "arreglo", "Arreglo", "opcion", "", (("serie", "En serie"), ("paralelo", "En paralelo"))
        ),
        CampoVisual("resistencias", "Resistencias, de 2 a 4", "lista", "4 Ω, 6 Ω"),
        CampoVisual("lados", "Lados del polígono (de 3 a 8)", "numero", "6"),
        CampoVisual("lado", "Medida de un lado o arista", "texto", "12 cm"),
        CampoVisual("anotar", "Qué anotar en el dibujo", "lista"),
        CampoVisual("velocidad", "Velocidad de lanzamiento", "texto", "20 m/s"),
        CampoVisual(
            "figura",
            "El sólido",
            "opcion",
            "",
            (("cubo", "Cubo"), ("cilindro", "Cilindro"), ("cono", "Cono"), ("esfera", "Esfera")),
        ),
        CampoVisual("radio", "Radio", "texto", "3 cm"),
        CampoVisual("altura", "Altura", "texto", "5 cm"),
        CampoVisual("solo_a", "Cuántos sólo en A", "numero", "25"),
        CampoVisual("solo_b", "Cuántos sólo en B", "numero", "13"),
        CampoVisual("ambos", "Cuántos en los dos", "numero", "12"),
        CampoVisual("fuera", "Cuántos en ninguno", "numero", "5"),
        CampoVisual("extremo_a", "Extremo izquierdo (o el origen del rayo)", "numero", "2"),
        CampoVisual("extremo_b", "Extremo derecho (vacío = rayo)", "numero", "7"),
        CampoVisual("incluye_a", "Incluye el extremo izquierdo", "booleano"),
        CampoVisual("incluye_b", "Incluye el extremo derecho", "booleano"),
        CampoVisual("derecha", "El rayo apunta a la derecha", "booleano"),
        CampoVisual("favorables", "Casos favorables", "numero", "3"),
        CampoVisual("totales", "Casos totales", "numero", "8"),
        CampoVisual("categorias", "Categorías con su valor", "lista", "Fútbol 12, Básquetbol 8"),
        CampoVisual("amplitud", "Amplitud", "texto", "0,5 m"),
        CampoVisual("longitud_onda", "Longitud de onda (λ)", "texto", "2 m"),
        CampoVisual("periodo", "Periodo en segundos", "numero", "0,4"),
        CampoVisual("n1", "Índice del medio de origen", "numero", "1,0"),
        CampoVisual("n2", "Índice del medio al que pasa", "numero", "1,33"),
        CampoVisual("angulo_incidence", "Ángulo de incidencia (desde la normal)", "numero", "30"),
        CampoVisual("longitud", "Longitud", "texto", "1 m"),
        CampoVisual("constante", "Constante del resorte", "texto", "200 N/m"),
        CampoVisual("extension", "Extensión", "texto", "10 cm"),
        CampoVisual("masa_a", "Masa A", "texto", "3 kg"),
        CampoVisual("masa_b", "Masa B", "texto", "2 kg"),
        CampoVisual("capacidad", "Capacidad del tanque", "texto", "120 L"),
        CampoVisual("entrada", "Lo que entra por la llave", "texto", "8 L/min"),
        CampoVisual("salida", "Lo que pierde por la fisura", "texto", "2 L/min"),
        CampoVisual("carga", "La carga", "texto", "200 N"),
        CampoVisual("repartida", "La carga va repartida en todo el tramo", "booleano"),
        CampoVisual("base", "Base", "texto", "6 m"),
        CampoVisual("adelante", "Ganancia del bloque directo", "texto", "10"),
        CampoVisual("retro", "Ganancia de la realimentación", "texto", "0.2"),
        CampoVisual("negativa", "La realimentación es negativa", "booleano"),
        CampoVisual("dientes_a", "Dientes de la conductora", "texto", "20"),
        CampoVisual("dientes_b", "Dientes de la conducida", "texto", "60"),
        CampoVisual("rpm", "Vueltas del eje de entrada", "texto", "1200 rpm"),
        CampoVisual("sigma_x", "Esfuerzo normal en X", "texto", "80 MPa"),
        CampoVisual("sigma_y", "Esfuerzo normal en Y", "texto", "20 MPa"),
        CampoVisual("cortante", "Esfuerzo cortante", "texto", "30 MPa"),
    ]
}

VISUALES: dict[str, TipoVisual] = {
    t.clave: t
    for t in [
        TipoVisual("grafico_funcion", "Gráfico de la función", "matematica", "📈",
                   ("funcion", "variable", "eje_x", "eje_y", "rango", "marcar"),
                   ejemplo={"funcion": "-x^2 + 4x", "eje_x": "x", "eje_y": "y"}),
        TipoVisual("poligono_regular", "Polígono regular", "matematica", "⬡",
                   ("lados", "lado", "anotar"), MARCAS_POLIGONO,
                   ejemplo={"lados": 6, "lado": "12 cm", "anotar": ["apotema", "angulo_interior"]}),
        TipoVisual("circulo_trig", "Círculo trigonométrico", "matematica", "◯",
                   ("angulo", "anotar"), MARCAS_CIRCULO,
                   ejemplo={"angulo": 30, "anotar": ["seno", "coseno"]}),
        TipoVisual("solido", "Sólido (lámina)", "matematica", "🧊",
                   ("figura", "lado", "radio", "altura", "anotar"), MARCAS_SOLIDO,
                   ejemplo={"figura": "cilindro", "radio": "3 cm", "altura": "5 cm", "anotar": ["volumen"]}),
        TipoVisual("venn", "Diagrama de Venn", "matematica", "◌◌",
                   ("solo_a", "solo_b", "ambos", "fuera", "anotar"), MARCAS_VENN,
                   ejemplo={"solo_a": 25, "solo_b": 13, "ambos": 12}),
        TipoVisual("recta", "Recta numérica", "matematica", "📏",
                   ("extremo_a", "extremo_b", "incluye_a", "incluye_b", "derecha"), (),
                   ejemplo={"extremo_a": 2, "extremo_b": 7}),
        TipoVisual("probabilidad", "Urna de probabilidad", "matematica", "🎲",
                   ("favorables", "totales", "anotar"), MARCAS_PROBABILIDAD,
                   ejemplo={"favorables": 3, "totales": 8, "anotar": ["probabilidad"]}),
        TipoVisual("torta", "Torta de porcentajes", "matematica", "🥧", ("categorias",), (),
                   ejemplo={"categorias": ["Fútbol 12", "Básquetbol 8", "Natación 4"]}),
        TipoVisual("barras", "Barras de datos", "matematica", "📊", ("categorias",), (),
                   ejemplo={"categorias": ["2023 40", "2024 55", "2025 70"]}),
        TipoVisual("diagrama_fuerzas", "Diagrama de fuerzas", "fisica", "➡️",
                   ("cuerpo", "vectores", "angulo", "descomponer"), (),
                   ejemplo={"cuerpo": "bloque", "vectores": ["P", "N"], "angulo": 30, "descomponer": True}),
        TipoVisual("proyectil", "Tiro parabólico", "fisica", "🎯",
                   ("velocidad", "angulo", "anotar"), MARCAS_PROYECTIL,
                   ejemplo={"velocidad": "20 m/s", "angulo": 30, "anotar": ["alcance"]}),
        TipoVisual("circuito", "Circuito", "fisica", "🔌",
                   ("fuente", "arreglo", "resistencias"), (),
                   ejemplo={"fuente": "12 V", "arreglo": "serie", "resistencias": ["4 Ω", "6 Ω"]}),
        TipoVisual("onda", "Onda anotada", "fisica", "〰️",
                   ("amplitud", "longitud_onda", "periodo", "anotar"), MARCAS_ONDA,
                   ejemplo={"amplitud": "0,5 m", "longitud_onda": "2 m", "periodo": 0.4,
                            "anotar": ["velocidad"]}),
        TipoVisual("energia", "Barras de energía", "fisica", "🔋", ("categorias",), (),
                   ejemplo={"categorias": ["Cinética 60", "Térmica 40"]}),
        TipoVisual("optica", "Refracción de la luz", "fisica", "🔦",
                   ("n1", "n2", "angulo_incidence"), (),
                   ejemplo={"n1": 1.0, "n2": 1.33, "angulo_incidence": 30}),
        TipoVisual("pendulo", "Péndulo", "fisica", "🕰️", ("longitud", "angulo", "anotar"), MARCAS_PENDULO,
                   ejemplo={"longitud": "1 m", "angulo": 20, "anotar": ["periodo"]}),
        TipoVisual("resorte", "Resorte", "fisica", "🌀", ("constante", "extension", "anotar"),
                   MARCAS_RESORTE, ejemplo={"constante": "200 N/m", "extension": "10 cm",
                                            "anotar": ["fuerza"]}),
        TipoVisual("polea", "Polea con dos masas", "fisica", "🪝", ("masa_a", "masa_b", "anotar"),
                   MARCAS_POLEA, ejemplo={"masa_a": "3 kg", "masa_b": "2 kg",
                                          "anotar": ["aceleracion", "tension"]}),
        TipoVisual("tanque", "Tanque con llave y fisura", "ingenieria", "🛢️",
                   ("capacidad", "entrada", "salida", "anotar"), MARCAS_TANQUE,
                   ejemplo={"capacidad": "120 L", "entrada": "8 L/min", "salida": "2 L/min",
                            "anotar": ["llenado", "vaciado"]}),
        TipoVisual("viga", "Viga apoyada", "ingenieria", "🏗️",
                   ("longitud", "carga", "repartida", "anotar"), MARCAS_VIGA,
                   ejemplo={"longitud": "4 m", "carga": "200 N", "anotar": ["reacciones"]}),
        TipoVisual("cercha", "Cercha", "ingenieria", "🔺",
                   ("base", "altura", "carga", "anotar"), MARCAS_CERCHA,
                   ejemplo={"base": "6 m", "altura": "2 m", "carga": "500 N", "anotar": ["esfuerzo"]}),
        TipoVisual("bloques", "Lazo de control", "ingenieria", "📦",
                   ("adelante", "retro", "negativa", "anotar"), MARCAS_BLOQUES,
                   ejemplo={"adelante": "10", "retro": "0.2", "anotar": ["lazo_cerrado"]}),
        TipoVisual("engranaje", "Pareja de engranajes", "ingenieria", "⚙️",
                   ("dientes_a", "dientes_b", "rpm", "anotar"), MARCAS_ENGRANAJE,
                   ejemplo={"dientes_a": "20", "dientes_b": "60", "rpm": "1200 rpm",
                            "anotar": ["velocidad", "relacion"]}),
        TipoVisual("mohr", "Círculo de Mohr", "ingenieria", "📐",
                   ("sigma_x", "sigma_y", "cortante", "anotar"), MARCAS_MOHR,
                   ejemplo={"sigma_x": "80 MPa", "sigma_y": "20 MPa", "cortante": "30 MPa",
                            "anotar": ["principales"]}),
    ]
}


def opciones_select() -> dict[str, str]:
    """La lista del selector: 'Matemática · Polígono regular'. ui.select no acepta optgroup, así que
    la materia va escrita en la etiqueta y el orden agrupa."""
    salida = {"": "Sin dibujo"}
    for materia in ("matematica", "fisica", "ingenieria"):
        for tipo in VISUALES.values():
            if tipo.materia == materia:
                salida[tipo.clave] = f"{_MATERIAS[materia]} · {tipo.nombre}"
    return salida
```

`visuales.py` ya importa `Any`, `dataclass` y `field` (líneas 12-13): **no** agregar import.

- [ ] **Paso 4 — Verde**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_visuales -v 2>&1 | tail -12
```

Esperado: `OK` (8 pruebas). Si `test_el_ejemplo_de_cada_tipo_valida_con_Visual` falla, el ejemplo está
pidiendo un campo que el validador exige distinto (ej. `tanque` con `vaciado` necesita `salida`): **arreglar
el ejemplo**, no el validador.

- [ ] **Paso 5 — Suite, lint, commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add src/tpi_videos/visuales.py pruebas/test_visuales.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'VISUALES: un catálogo con los 24 dibujos, sus campos y un ejemplo que valida'
```

---

### Tarea B.2 · El editor arma el formulario desde la tabla

**Archivos:** modificar `src/tpi_videos/panel/editor.py` (líneas 39-56 y 220-286) · crear
`pruebas/test_editor_visual.py`

**Contrato:** el editor deja de saber qué dibujos existen. `_TIPOS_VISUAL`, `_VISUAL_CAMPOS` y las tres ramas
`elif` de `_visual()` se van; queda un generador sobre `VISUALES`/`CAMPOS`.

- [ ] **Paso 1 — Prueba que falla**

`pruebas/test_editor_visual.py` (solo lógica del formulario, sin widget):

```python
import copy
import unittest

from tpi_videos.guion import Visual
from tpi_videos.panel.editor import PASO_VACIO, _visual_al_formulario, _visual_al_guardar
from tpi_videos.visuales import VISUALES


class IdaYVueltaTest(unittest.TestCase):
    def test_cada_tipo_sobrevive_a_guardar_y_recargar_sin_perder_datos(self):
        for clave, tipo in VISUALES.items():
            crudo = {"tipo": clave, **copy.deepcopy(tipo.ejemplo)}
            visual = Visual.model_validate(crudo).model_dump(exclude_none=True)
            guardado = _visual_al_guardar(_visual_al_formulario(visual))
            self.assertEqual(guardado["tipo"], clave)
            for campo in tipo.campos:
                if campo in crudo:
                    self.assertIn(campo, guardado, f"{clave} perdió {campo}")
            self.assertEqual(Visual.model_validate(guardado), Visual.model_validate(crudo), clave)

    def test_una_campo_lleno_de_otro_tipo_no_se_guarda(self):
        guardado = _visual_al_guardar(_visual_al_formulario({"tipo": "torta", "categorias": ["A 1", "B 2"],
                                                             "funcion": "x", "angulo": 30}))
        self.assertNotIn("funcion", guardado)
        self.assertNotIn("angulo", guardado)

    def test_sin_tipo_no_hay_visual(self):
        self.assertIsNone(_visual_al_guardar(copy.deepcopy(PASO_VACIO["visual"])))

    def test_el_formulario_acepta_coma_chilena_y_la_devuelve_como_numero(self):
        formulario = _visual_al_formulario({"tipo": "recta", "extremo_a": 2.5, "extremo_b": 7.0})
        self.assertEqual(formulario["extremo_a"], "2,5")
        guardado = _visual_al_guardar(formulario)
        self.assertEqual(guardado["extremo_a"], 2.5)

    def test_la_lista_del_editor_es_el_catalogo_completo(self):
        from tpi_videos.panel.editor import tipos_visual_del_editor

        self.assertEqual(set(tipos_visual_del_editor()), {"", *VISUALES})
```

- [ ] **Paso 2 — Verificar que falla**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_editor_visual -v 2>&1 | tail -8
```

Esperado: `ImportError: cannot import name 'tipos_visual_del_editor'` y los fallos de ida y vuelta (hoy
`_VISUAL_CAMPOS` solo conoce 3 tipos, así que los demás se guardan vacíos).

- [ ] **Paso 3 — Reemplazar las constantes del formulario**

En `editor.py`, borrar `_VISUAL_VACIO`, `_TIPOS_VISUAL`, `_VISUAL_CAMPOS` y `_VISUAL_NUMERICOS` (líneas
39-56) y dejar esto en su lugar (el formulario ya no tiene datos propios: los tres salen del catálogo):

```python
from ..visuales import CAMPOS, VECTORES, VISUALES, opciones_select

_FORMA = {clave: campo.forma for clave, campo in CAMPOS.items()}


def tipos_visual_del_editor() -> dict[str, str]:
    """La lista del selector: las 24 entradas del catálogo, agrupadas por materia en la etiqueta."""
    return opciones_select()


def _campos_de(tipo: str) -> tuple[str, ...]:
    return VISUALES[tipo].campos if tipo in VISUALES else ()


def _visual_vacio() -> dict[str, Any]:
    """El formulario en blanco: el valor inicial es el default del modelo, no una cadena a mano."""
    modelo = Visual.model_validate({"tipo": "torta", "categorias": ["A 1"]})
    salida: dict[str, Any] = {"tipo": ""}
    for clave, campo in CAMPOS.items():
        si_no_tocado = getattr(modelo, clave)
        if campo.forma == "lista":
            salida[clave] = []
        elif campo.forma == "booleano":
            salida[clave] = bool(si_no_tocado)
        elif campo.forma in ("numero", "numeros"):
            salida[clave] = ""
        else:
            salida[clave] = "" if si_no_tocado is None else str(si_no_tocado)
    return salida
```

y `PASO_VACIO["visual"] = _visual_vacio()` (la línea 106). El import de `Visual` ya existe en la línea 18
(`from ..guion import ... Guion, ...`) — agregar `Visual` a esa lista.

Por qué el default sale del modelo y no de una tabla: `cuerpo` es `"bloque"`, `arreglo` `"serie"`,
`incluye_a` `True` y `negativa` `True` en `guion.py`; copiarlos a mano al panel es exactamente el error que
esta tarea está borrando.

- [ ] **Paso 4 — `_visual_al_formulario` / `_visual_al_guardar` genéricos**

Reemplazar las dos funciones (líneas 68-95) por:

```python
def _visual_al_formulario(v: dict[str, Any]) -> dict[str, Any]:
    """El dict del guion al formulario: los números salen con coma chilena, las listas quedan listas."""
    salida = {**_visual_vacio(), **copy.deepcopy(v)}
    for clave in _campos_de(str(salida.get("tipo") or "")):
        forma = _FORMA.get(clave, "texto")
        valor = salida.get(clave)
        if forma == "numeros":
            numeros = list(valor or [])
            salida[clave] = (
                " a ".join(_texto_numero(n) for n in numeros)
                if clave == "rango" and len(numeros) == 2
                else "; ".join(_texto_numero(n) for n in numeros)
            )
        elif forma == "numero":
            salida[clave] = _texto_numero(valor) if valor not in (None, "") else ""
        elif forma == "lista":
            salida[clave] = [str(x) for x in (valor or [])]
    return salida


def _visual_al_guardar(v: dict[str, Any]) -> dict[str, Any] | None:
    """El formulario otra vez en formato guion: solo los campos del tipo elegido."""
    tipo = str(v.get("tipo") or "").strip()
    if tipo not in VISUALES:
        return None
    salida: dict[str, Any] = {"tipo": tipo}
    for clave in _campos_de(tipo):
        forma = _FORMA.get(clave, "texto")
        valor = v.get(clave)
        if forma == "numeros":
            if (numeros := _numeros(str(valor or ""))):
                salida[clave] = numeros
        elif forma == "numero":
            if (numeros := _numeros(str(valor or ""))):
                salida[clave] = numeros[0]
        elif forma == "booleano":
            salida[clave] = bool(valor)
        elif forma == "lista":
            if limpia := [str(x).strip() for x in (valor or []) if str(x).strip()]:
                salida[clave] = limpia
        elif str(valor or "").strip():
            salida[clave] = str(valor).strip()
    return salida
```

Dos cambios de comportamiento reales, que la prueba del paso 1 obliga:

- `angulo` (escalar) y `rango`/`marcar` (listas) se siguen tratando igual que antes, pero la clasificación
  sale de `_FORMA`, no de la tupla `_VISUAL_NUMERICOS` que se borra.
- `descomponer`, `repartida`, `negativa`, `incluye_a`, `incluye_b` y `derecha` **antes no se podían poner
  nunca desde el panel** (no estaban en `_VISUAL_CAMPOS`); ahora viajan, que es justo lo que él pidió.

- [ ] **Paso 5 — `_visual()` genera los campos**

Reemplazar el cuerpo del `expansion` (desde `ui.select(_TIPOS_VISUAL...)` hasta el `elif tipo == "circuito"`
incluido, líneas 228-281) por un solo lazo sin ramas por tipo. **Una columna por campo**: es más legible en
un panel de 1152 px y evita el estado que exigiría maquetar parejas.

```python
    def _visual(self, paso: dict) -> None:
        """Los campos del dibujo elegido: los decide el catálogo, no una copia en el editor."""
        v = paso.setdefault("visual", _visual_vacio())
        with (
            ui.expansion("Dibujo en el pie de la hoja (opcional)", icon="draw", value=bool(v.get("tipo")))
            .classes("w-full")
            .props("dense")
        ):
            (
                ui.select(tipos_visual_del_editor(), label="Qué dibujar")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(v, "tipo")
                .on("update:model-value", lambda: self.seccion_pasos.refresh())
            )
            tipo = str(v.get("tipo") or "")
            if not tipo:
                return
            definicion = VISUALES[tipo]
            for clave in definicion.campos:
                campo = CAMPOS[clave]
                if clave == "vectores":
                    self._chips(v, clave, campo.etiqueta, {k: f"{k} — {n}" for k, n in VECTORES.items()})
                elif clave == "anotar":
                    self._chips(v, clave, campo.etiqueta, {m: m.replace("_", " ") for m in definicion.marcas})
                elif campo.forma == "opcion":
                    (
                        ui.select(dict(campo.opciones), label=campo.etiqueta)
                        .props("outlined dense")
                        .classes("w-full")
                        .bind_value(v, clave)
                    )
                elif campo.forma == "booleano":
                    ui.switch(campo.etiqueta).props("dense").bind_value(v, clave)
                elif campo.forma == "lista":
                    self._chips(v, clave, campo.etiqueta, None)
                else:
                    self._texto(v, clave, campo.etiqueta, campo.ayuda)
            ui.label(
                f"{definicion.nombre} se dibuja en el pie de la hoja mientras suena la voz de este paso. "
                "Con un dibujo en todo el video basta."
            ).classes("tpi-ayuda")
```

Verificar `_chips` (`editor.py:196-211`): su firma es `(d, clave, etiqueta, opciones=None)` y con
`opciones=None` usa los valores tal cual — sirve para `resistencias` y `categorias` (escribe y presiona
Enter, `new_value_mode="add-unique"`). `anotar` y `vectores` reciben su diccionario de opciones, así que el
usuario elige de una lista en vez de adivinar la clave: eso es la regla «todo se muestra con su valor».

- [ ] **Paso 6 — Verde y prueba de arranque real del panel**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_editor_visual pruebas.test_visuales -v 2>&1 | tail -14 && \
.venv/bin/python -c "
import sys; sys.argv=['x']
from tpi_videos.panel.paginas import crear
from tpi_videos.panel.editor import EditorGuion, PASO_VACIO
from tpi_videos.visuales import VISUALES
for k, t in VISUALES.items():
    v = dict(PASO_VACIO['visual'], tipo=k, **t.ejemplo)
    assert k in str(v), k
print('formulario arma los 24 tipos')
"
```

Esperado: `OK` y `formulario arma los 24 tipos`.

- [ ] **Paso 7 — Mirar la pantalla de verdad**

Arrancar el panel y revisar el acordeón «Dibujo» en 4 tipos al azar (uno de cada materia):

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && ./tpi panel
```

Con el navegador (o `browser-use`) abrir `http://127.0.0.1:8080/crear`, elegir «Ingeniería · Círculo de Mohr»
y confirmar que aparecen σx, σy, cortante y «Qué anotar». **Captura de pantalla en la conversación antes de
seguir**: él tiene que ver que su palanca existe.

- [ ] **Paso 8 — Suite, lint, commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add -u src/tpi_videos pruebas/test_editor_visual.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'El editor ofrece los 24 dibujos: el formulario se arma desde el catálogo'
```

---

### Tarea B.3 · Miniatura real del dibujo (0,2 s, sin video)

**Archivos:** crear `src/tpi_videos/panel/miniaturas.py` · crear `pruebas/test_miniaturas.py` · modificar
`src/tpi_videos/panel/editor.py` (mostrar la miniatura dentro del acordeón).

**Camino verificado en esta sesión** (0,2 s por cuadro, sin voz, sin IA, sin `TAREAS`):

```python
entorno.preparar(); entorno.registrar_fuentes()
tema = cargar_tema('hoja_de_desarrollo', cargar_marca())
dibujo = dibujos.dibujar_visual(visual, tema.colores, componentes.ANCHO_UTIL, dibujos.ALTO_DIBUJO,
                                tema.hoja.color)
cam = Camera(...); cam.capture_mobject(dibujo.mobs); cam.get_image().save(ruta)
```

Dos cosas que **no** funcionan y por qué:

- No existe una ruta `--save_last_frame` en este proyecto: manim se usa como biblioteca (`tempconfig` +
  `escena.render()`), y renderizar una escena cuesta segundos y un mp4.
- La cámara **no** puede heredar `frame_width=9, frame_height=16` del render: el dibujo queda minúsculo
  (así salió la primera prueba). Hay que encuadrar desde el tamaño real del `VGroup`, y `_encajar` no sirve
  porque solo achica.

- [ ] **Paso 1 — Prueba que falla**

`pruebas/test_miniaturas.py`:

```python
import unittest
from pathlib import Path

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:
    MANIM = False

from tpi_videos.panel.miniaturas import dibujar_miniatura, marco_para, ruta_miniatura
from tpi_videos.visuales import VISUALES


class EncuadreTest(unittest.TestCase):
    def test_el_marco_9a16_contiene_un_dibujo_ancho(self):
        ancho, alto = marco_para(6.0, 2.0)
        self.assertAlmostEqual(alto / ancho, 16 / 9, places=5)
        self.assertGreaterEqual(ancho, 6.0)
        self.assertGreaterEqual(alto, 2.0)

    def test_el_marco_9a16_contiene_un_dibujo_alto(self):
        ancho, alto = marco_para(1.0, 5.0)
        self.assertGreaterEqual(alto, 5.0)
        self.assertAlmostEqual(alto / ancho, 16 / 9, places=5)

    def test_dibujo_degenerado_no_rompe_el_marco(self):
        ancho, alto = marco_para(0.0, 0.0)
        self.assertGreater(ancho, 0)
        self.assertGreater(alto, 0)


@unittest.skipUnless(MANIM, "manim no esta instalado")
class DibujarTest(unittest.TestCase):
    def _llenado(self, ruta: Path) -> float:
        """Cuánto del alto del cuadro ocupa la tinta (el defecto que hay que evitar)."""
        from PIL import Image

        im = Image.open(ruta).convert("L")
        fondo = im.getpixel((2, 2))
        filas = [y for y in range(im.height) if any(abs(p - fondo) > 24 for p in
                   [im.getpixel((x, y)) for x in range(0, im.width, 3)])]
        return (filas[-1] - filas[0]) / im.height if len(filas) > 3 else 0.0

    def test_tipos_de_ejemplo_producen_un_png_usable(self):
        for clave in ("engranaje", "poligono_regular", "viga", "torta", "mohr", "solido"):
            ruta = dibujar_miniatura({"tipo": clave, **VISUALES[clave].ejemplo})
            self.assertTrue(ruta.exists(), clave)
            self.assertGreater(self._llenado(ruta), 0.30, f"{clave} llega muy chico: {ruta}")

    def test_la_huella_repite_archivo_si_no_cambia_nada(self):
        v = {"tipo": "barras", "categorias": ["A 3", "B 5"]}
        primera = dibujar_miniatura(v)
        self.assertEqual(primera, ruta_miniatura(v))
        self.assertEqual(primera.stat().st_mtime, dibujar_miniatura(v).stat().st_mtime)

    def test_un_tipo_inventado_avisa_en_vez_de_devolver_nada(self):
        with self.assertRaises(Exception) as sube:
            dibujar_miniatura({"tipo": "dibujo_imposible"})
        self.assertIn("dibujo_imposible", str(sube.exception))
```

- [ ] **Paso 2 — Verificar que falla**: `ModuleNotFoundError: No module named
  'tpi_videos.panel.miniaturas'`.

- [ ] **Paso 3 — Escribir `panel/miniaturas.py`**

```python
"""El dibujo de un paso, visto antes de crear el video: un fotograma, sin voz y sin IA.

Costo medido: ~0,2 s por cuadro (menos si LaTeX ya tiene su cache). No pasa por ``TAREAS`` porque la cola
es de un trabajo a la vez y una miniatura no puede pelearse con un video en marcha.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import dibujos as _d
from .. import entorno as _entorno
from ..config import cargar_marca
from ..errores import ErrorMotor
from ..guion import Visual
from ..temas import cargar_tema

RAZON = 16 / 9  # alto / ancho de un cuadro vertical
HOLGURA = 1.35  # aire alrededor del dibujo para que no toque el borde
LADO = 320  # px del alto del PNG: se muestra a 78-160 px, sobra


def _huella(visual: dict, tema: str) -> str:
    texto = json.dumps({"visual": visual, "tema": tema}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def ruta_miniatura(visual: dict, tema: str = "hoja_de_desarrollo") -> Path:
    tipo = str(visual.get("tipo") or "sin_tipo").replace("/", "_")
    return _carpeta() / f"{tipo}_{_huella(visual, tema)}.png"


def _carpeta() -> Path:
    from ..entorno import raiz_proyecto

    carpeta = raiz_proyecto() / "salida" / "_miniaturas"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def marco_para(ancho: float, alto: float) -> tuple[float, float]:
    """El marco 9:16 mínimo que contiene un dibujo de ``ancho``×``alto`` (con su holgura)."""
    ancho = max(ancho, 0.5)
    alto = max(alto, 0.5)
    alto_marco = max(alto, ancho * RAZON) * HOLGURA
    return alto_marco / RAZON, alto_marco


def dibujar_miniatura(
    visual: dict, tema: str = "hoja_de_desarrollo", forzar: bool = False
) -> Path:
    """Un PNG con el dibujo centrado y encuadrado. Lanza ErrorMotor si el tipo o los campos no valen."""
    destino = ruta_miniatura(visual, tema)
    if destino.exists() and not forzar:
        return destino
    tipo = str(visual.get("tipo") or "")
    if not tipo:
        raise ErrorMotor("No hay dibujo que mostrar: elige uno en «Qué dibujar».")
    try:
        modelo = Visual.model_validate(visual)
    except Exception as e:  # pydantic: el texto del error ya es útil en español
        raise ErrorMotor(f"El dibujo «{tipo}» aún no está completo: {e}") from e

    from manim import Camera, VGroup, tempconfig

    _entorno.preparar()
    _entorno.registrar_fuentes()
    estilo = cargar_tema(tema, cargar_marca())
    dibujo = _d.dibujar_visual(modelo, estilo.colores, _ANCHO_UTIL(), _d.ALTO_DIBUJO, estilo.hoja.color)
    grupo: VGroup = dibujo.mobs
    ancho, alto = marco_para(grupo.width, grupo.height)
    with tempconfig(
        {
            "pixel_width": round(LADO / RAZON),
            "pixel_height": LADO,
            "frame_width": ancho,
            "frame_height": alto,
            "background_color": estilo.colores.fondo,
            "verbosity": "ERROR",
            "disable_caching": True,
        }
    ):
        camara = Camera()
        camara.capture_mobject(grupo)
        destino.parent.mkdir(parents=True, exist_ok=True)
        camara.get_image().save(destino)
    return destino


def _ANCHO_UTIL() -> float:
    from .. import componentes as c

    return c.ANCHO_UTIL
```

**Tres trampas verificadas que el código de arriba ya esquiva:** `Dibujo` no es un Mobject (no tiene
`get_family`); hay que pasar `dibujo.mobs`. `capture_mobject()` devuelve `None`, así que se encadena
`camara.get_image().save(...)`. Y `ManimColor` no tiene `.get_hex_l()`.

- [ ] **Paso 4 — Verde**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_miniaturas -v 2>&1 | tail -14
```

Esperado: `OK` (6 pruebas). El umbral `0.30` de `_llenado` es **la prueba del encuadre**: si un tipo sale muy
chico, no se baja el umbral, se revisa por qué `marco_para` no lo contuvo (dibujos que se arman con
`move_to` fuera del origen se salen del marco: medir con `group.width/height` después de `.copy()` y, si
hace falta, `grupo.move_to(ORIGIN)` antes de capturar).

- [ ] **Paso 5 — Medir el costo real y mirarlo**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -c "
import time
from tpi_videos.panel.miniaturas import dibujar_miniatura
from tpi_videos.visuales import VISUALES
for k in ('engranaje','mohr','tanque','cercha','optica'):
    t = time.time(); p = dibujar_miniatura({'tipo': k, **VISUALES[k].ejemplo}, forzar=True)
    print(f'{k:16} {time.time()-t:5.2f}s  {p}')
"
```

Esperado: cada tipo en menos de ~2 s (los que usan LaTeX tardan más la primera vez). **Abrir 3 de esos PNG
con `Read` y mirarlos** antes de continuar.

- [ ] **Paso 6 — Mostrarla en el editor**

En `editor.py::_visual`, dentro del `if tipo:` final, agregar la miniatura con su estado:

```python
            try:
                png = miniaturas.dibujar_miniatura(_visual_al_guardar(v) or {"tipo": tipo})
                ui.image(url_medio(png)).classes("w-full max-w-[260px] rounded-lg border border-[#DCDCD7]")
            except ErrorMotor as e:
                ui.label(f"⏳ Todavía no puedo dibujarlo: {e}").classes("tpi-ayuda")
```

`url_medio()` **no** sirve para `salida/_miniaturas` salvo que la ruta media exista: revisar que
`app.py:60` monta `raiz / "salida"` en `/medios/salida` — sí lo hace, y `_miniaturas` está adentro, así que
`url_medio` ya la resuelve. No hace falta una ruta nueva.

Importar arriba: `from . import miniaturas` y `from ..errores import ErrorMotor`.

- [ ] **Paso 7 — Panel abierto, mirar, commit**

Abrir `/crear`, desplegar «Dibujo» en 3 tipos y **ver el dibujo en la pantalla** (si sale «Todavía no puedo
dibujarlo: …», el mensaje ya es útil: dice qué falta; si sale un cuadro gris, es un defecto y se arregla
acá, no en el hito C).

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add src/tpi_videos/panel/miniaturas.py pruebas/test_miniaturas.py src/tpi_videos/panel/editor.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'Miniatura real del dibujo: un fotograma en 0,2 s, encuadrado y cacheado por huella'
```

---

### Tarea B.4 · El LaTeX se redibuja mientras se escribe (y gana el último)

**Archivos:** `src/tpi_videos/panel/editor.py:288-315` (`_formula`).

**Hoy:** `campo.on("blur", dibujar)` y `campo.on("keydown.enter", dibujar)` → nada cambia al tocar. Es la
falla 4 del diagnóstico.

**Qué se usa para el freno y qué no:** el retardo lo da Quasar con `input-debounce=400` sobre el propio campo
(el evento `update:model-value` ya llega frenado). **No** se escribe un freno en Python: uno propio tendría
que reimplementar un temporizador por campo y es exactamente la clase de sistema nuevo que él rechaza. Lo que
sí hace falta en Python es descartar el resultado de una fórmula que quedó vieja mientras se dibujaba (el
render de LaTeX puede tardar más que lo que el autor tarda en seguir escribiendo).

- [ ] **Paso 1 — Prueba que falla** (agregar a `pruebas/test_editor_visual.py`)

```python
class FormulaEnVivoTest(unittest.TestCase):
    def test_gana_la_ultima_peticion(self):
        from tpi_videos.panel.editor import _ultima_version

        versiones = _ultima_version()
        vieja, media, nueva = versiones.nueva(), versiones.nueva(), versiones.nueva()
        self.assertFalse(versiones.al_dia(vieja))
        self.assertFalse(versiones.al_dia(media))
        self.assertTrue(versiones.al_dia(nueva))

    def test_el_campo_de LaTeX_llega_frenado_mientras_se_escribe(self):
        import inspect

        from tpi_videos.panel.editor import EditorGuion

        fuente = inspect.getsource(EditorGuion._formula)
        self.assertIn("input-debounce=400", fuente)
        self.assertIn('"update:model-value"', fuente)
        self.assertNotIn('"blur"', fuente)  # el blur era la única puerta: sin foco, sin dibujo
```

- [ ] **Paso 2 — Verificar que falla**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_editor_visual -v 2>&1 | tail -8
```

Esperado: `ImportError: cannot import name '_ultima_version'` y el aserto de `input-debounce`.

- [ ] **Paso 3 — Implementar el guardador de versión**

En `editor.py`, sobre `_formula`:

```python
class _ultima_version:
    """Descarta el resultado de una fórmula que quedó vieja mientras LaTeX la dibujaba.

    El retardo lo pone Quasar (`input-debounce=400`); acá solo importa que una compilación lenta no tape a la
    fórmula que el autor escribió después.
    """

    def __init__(self) -> None:
        self._turno = 0

    def nueva(self) -> int:
        self._turno += 1
        return self._turno

    def al_dia(self, turno: int) -> bool:
        return turno == self._turno
```

Import nuevo arriba: `import asyncio` (si aún no está).

- [ ] **Paso 4 — Cablear `_formula`**

Reemplazar el final de `_formula` (desde `async def dibujar()` hasta `if d.get(clave):` incluido, líneas
302-315) por:

```python
            versiones = _ultima_version()

            async def dibujar() -> None:
                turno = versiones.nueva()
                svg, error = await formulas.dibujar(d.get(clave) or "", self.negrita)
                if not versiones.al_dia(turno):
                    return  # llegó otra escritura mientras se dibujaba: ésa se pinta sola
                imagen.set_visibility(svg is not None)
                if svg is not None:
                    ancho, alto = formulas.tamano_en_pantalla(svg)
                    imagen.style(f"height:{alto}px; width:{ancho}px; max-width:100%; object-fit:contain")
                    imagen.props["src"] = url_medio(svg)
                    imagen.update()
                aviso.text = f"⚠️ {error}" if error else ""

            campo.props("outlined dense input-debounce=400")
            campo.on("update:model-value", lambda: asyncio.create_task(dibujar()))
            if d.get(clave):
                ui.timer(0.1, lambda: asyncio.create_task(dibujar()), once=True)
```

Si `campo.props("outlined dense …")` pisa el `props("outlined dense")` de la línea 292, **dejar uno solo**: el
`props` de la declaración del campo pasa a llevar las tres palabras y se borra el de abajo.

- [ ] **Paso 5 — Verde y probarlo en la pantalla**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_editor_visual -v 2>&1 | tail -10 && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3
```

Con el panel abierto, escribir `\frac{a+b}{c}` **tecleando sin sacar el foco** y verificar que el dibujo sigue
al texto con ~0,4 s de retraso; después escribir `\frac{a}{b}` rápido y confirmar que no aparece el cuadro de
la fórmula anterior (eso es «gana el último»). Captura en la conversación.

- [ ] **Paso 6 — Commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add -u src/tpi_videos pruebas/test_editor_visual.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'La fórmula se dibuja mientras se escribe y una compilación vieja no la tapa'
```

---

## Hito C — Piel y muro: cuatro pantallas con el detalle al costado

### Tarea C.1 · Los tokens `PIEL` y el `DESIGN.md`

**Archivos:** `src/tpi_videos/panel/comun.py`, `src/tpi_videos/panel/paginas/fabrica.py`, crear
`DESIGN.md`.

**Medido, no supuesto:** `AZUL`/`ROJO`/`VERDE`/`GRIS` solo se usan en `comun.py` y `paginas/fabrica.py`. El
refactor es de dos archivos, no de cinco páginas.

- [ ] **Paso 1 — Prueba que falla** (agregar a `pruebas/test_piel.py`)

```python
class PielTest(unittest.TestCase):
    def test_los_tokens_de_la_piel_existen_y_son_hex(self):
        from tpi_videos.panel.comun import PIEL

        for clave in ("muro", "tarjeta", "borde_muro", "texto_muro", "tenue_muro", "hoja", "tinta",
                      "marca", "error", "exito", "gris", "costado_px"):
            self.assertIn(clave, PIEL, clave)
        for clave, valor in PIEL.items():
            if clave.endswith("_px"):
                self.assertRegex(valor, r"^\d+$", clave)
            else:
                self.assertRegex(valor, r"^#[0-9A-Fa-f]{6}$", clave)

    def test_no_quedan_hexadecimales_sueltos_en_el_css_del_panel(self):
        from pathlib import Path
        import re

        fuente = Path("src/tpi_videos/panel/comun.py").read_text(encoding="utf-8")
        self.assertNotIn("AZUL = ", fuente)
        sueltos = re.findall(r'background:\s*#[0-9A-Fa-f]{6}', fuente)
        self.assertEqual(sueltos, [], f"colores escritos a mano: {sueltos}")
```

- [ ] **Paso 2 — Verificar que falla**: `ImportError: cannot import name 'PIEL'`.

- [ ] **Paso 3 — Definir los tokens**

En `comun.py`, reemplazar las cuatro constantes (líneas 16-19) por:

```python
# La piel del panel, en un solo lugar. Las páginas leen de acá; no reciben colores nuevos.
# MODO Operate (impeccable): la expresión vive en el muro y en la hoja, no en los controles.
PIEL = {
    "muro": "#080A0D",  # la pantalla del muro de portadas
    "tarjeta": "#11161C",
    "borde_muro": "#223041",
    "texto_muro": "#EAF2FF",
    "tenue_muro": "#8A97A8",
    "hoja": "#FBF7EC",  # el papel crema donde se escribe
    "tinta": "#1B2430",
    "marca": "#1C3D74",
    "error": "#D32F2F",
    "exito": "#2E7D32",
    "gris": "#6B6B6B",  # el gris que sí se lee sobre blanco (4,5:1)
    "costado_px": "392",  # el ancho del panel de detalle aprobado en el mockup
}
```

**Sin alias de compatibilidad:** `AZUL`, `ROJO`, `VERDE` y `GRIS` se **borran**; cada uso se reemplaza por
`PIEL["marca"]`, `PIEL["error"]`, `PIEL["exito"]` y `PIEL["gris"]`. Dejar los cuatro nombres «por si acaso»
es justo lo que este hito está quitando.

- [ ] **Paso 4 — CSS del muro y del costado**

Dentro de `CSS` (que ya es un f-string), agregar:

```css
.tpi-muro {{ background: {PIEL['muro']}; color: {PIEL['texto_muro']}; }}
.tpi-tarjeta {{ background: {PIEL['tarjeta']}; border: 1px solid {PIEL['borde_muro']}; border-radius: 12px; }}
.tpi-tarjetaactiva {{ border-color: {PIEL['texto_muro']}; box-shadow: 0 0 0 2px {PIEL['texto_muro']}; }}
.tpi-tenue {{ color: {PIEL['tenue_muro']}; }}
.tpi-columnas {{ display: grid; grid-template-columns: minmax(0, 1fr) {PIEL['costado_px']}px;
  gap: 16px; align-items: start; }}
@media (max-width: 900px) {{ .tpi-columnas {{ grid-template-columns: minmax(0, 1fr); }} }}
.tpi-costado {{ position: sticky; top: 12px; }}
```

Y los `background:#F3F3F0` / `#262626` / `#FFFFFF` / `#DCDCD7` que ya están en `body` y `.tpi-hoja` pasan a
leer de `PIEL` (`tinta`, `hoja`) o a una clave nueva si hacen falta (`papel_panel`, `borde_hoja`). La prueba
del paso 1 exige que no quede ningún `background:#…` literal.

- [ ] **Paso 5 — Las dos páginas leen de `PIEL`**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
grep -rn 'AZUL\|ROJO\|VERDE\|GRIS' src/tpi_videos/panel --include='*.py'
```

Reemplazar cada coincidencia (en `comun.py`: `ui.colors(...)` y `marco()`; en `fabrica.py`: sus chips y
bordes). Al final, el `grep` no debe devolver nada en `.py` del panel.

- [ ] **Paso 6 — `DESIGN.md` en la raíz**

`DESIGN.md` con: la tabla de tokens (clave, valor, para qué), la rejilla del muro y el costado
(`minmax(0,1fr)` + `392px`, `position: sticky`, breakpoint 900 px), las tipografías embebidas que usa el panel
(`Comic Neue`, `Montserrat`, `Bangers`) y **la regla que manda**, textual: «todo lo que decide la IA se muestra
con su valor y un «cambiar»; ningún botón primario se deshabilita por no haber tocado una sugerencia». Sin
inventario de componentes ni teoría: solo lo que otro agente necesita para no romper la piel.

- [ ] **Paso 7 — Verde, panel abierto y visto, commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_piel -v 2>&1 | tail -8 && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add -u src/tpi_videos/panel DESIGN.md pruebas/test_piel.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'PIEL: los colores del panel viven en un solo lugar y el muro tiene su rejilla'
```

Abrir `http://127.0.0.1:8080/` y confirmar que **ninguna página cambió de aspecto** — esta tarea es mecánica;
si algo se ve distinto, está mal.

---

### Tarea C.2 · El muro de las cuatro familias, con el detalle al costado

**Archivos:** crear `src/tpi_videos/panel/formatos_ui.py` · crear `pruebas/test_formatos_ui.py` · modificar
`src/tpi_videos/panel/paginas/crear.py`.

**Layout aprobado** (mockup del 27-10-2026, después de su «al costado»): muro de 4 tarjetas a la izquierda y
`<aside>` de 392 px pegajoso a la derecha, con la miniatura 9:16 de 78 px en la testera del costado.

- [ ] **Paso 1 — Prueba de la lógica, separada del widget**

`pruebas/test_formatos_ui.py`:

```python
import unittest

from tpi_videos.panel.formatos_ui import elegir, texto_del_pie


class SugerenciaTest(unittest.TestCase):
    def test_una_idea_nueva_sugiere_su_familia_sin_bloquear_nada(self):
        from tpi_videos.panel.formatos_ui import sugerido

        self.assertEqual(sugerido("32 por 11 sin lápiz: un atajo de dos segundos"), "hacks")
        self.assertIsNone(sugerido("hola"))

    def test_lo_que_el_autor_toca_gana_a_lo_que_sugiere_la_maquina(self):
        e = elegir(autor="hacks", sugerida="trampas")
        self.assertEqual(e.activo, "hacks")
        self.assertTrue(e.la_puso_el_autor)

    def test_sin_toque_propio_el_activo_es_la_sugerencia(self):
        e = elegir(autor=None, sugerida="datos")
        self.assertEqual(e.activo, "datos")
        self.assertFalse(e.la_puso_el_autor)

    def test_una_clave_que_no_existe_no_rompe_la_tarjeta(self):
        self.assertEqual(elegir(autor="familia_inventada", sugerida=None).activo, "datos")


class PieTest(unittest.TestCase):
    def test_el_cta_se_muestra_como_pie_nunca_como_voz(self):
        self.assertIn("va en el pie", texto_del_pie("hacks"))
```

- [ ] **Paso 2 — Verificar que falla**: `ModuleNotFoundError: No module named
  'tpi_videos.panel.formatos_ui'`.

- [ ] **Paso 3 — Escribir `panel/formatos_ui.py`**

```python
"""El muro de familias y su detalle al costado.

La lógica (qué familia está activa y quién la puso) va separada del widget: las pantallas de NiceGUI no
tienen pruebas en este repo y ésta es la pantalla que él va a usar todos los días.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from nicegui import ui

from ..formatos import FORMATO_POR_DEFECTO, Formato, cargar_formatos, formato, puntuar_idea
from . import miniaturas
from .comun import PIEL, url_medio


@dataclass(frozen=True)
class Eleccion:
    activo: str
    la_puso_el_autor: bool


def sugerido(texto: str) -> str | None:
    """La familia que delata la idea escrita; None si la frase todavía no dice nada."""
    return puntuar_idea(texto)


def elegir(autor: str | None, sugerida: str | None = None) -> Eleccion:
    """Lo que el autor tocó gana a la sugerencia. Nada de esto bloquea el paso siguiente."""
    familias = cargar_formatos()
    if autor in familias:
        return Eleccion(autor, True)
    if sugerida in familias:
        return Eleccion(sugerida, False)
    return Eleccion(FORMATO_POR_DEFECTO, False)


def texto_del_pie(clave: str) -> str:
    return f"Para el pie del post (no se narra en el video): «{formato(clave).cta}»"


def muro_y_costado(
    activa: str | None, idea: str, al_elegir: Callable[[str], Any], al_cambiar_pieza: Callable[[str, str], Any]
) -> None:
    """Cuatro tarjetas al ancho y, al costado, la familia activa con sus piezas y su «cambiar»."""
    clave = elegir(activa, sugerido(idea)).activo
    familias = cargar_formatos()
    with ui.row().classes("tpi-columnas w-full items-start"):
        with ui.column().classes("gap-3 w-full"):
            with ui.element("div").classes("grid grid-cols-4 gap-3 w-full"):
                for f in familias.values():
                    _tarjeta(f, f.clave == clave, al_elegir)
        with ui.column().classes("tpi-costado gap-3 w-full"):
            _costado(familias[clave], al_cambiar_pieza)


def _tarjeta(f: Formato, activa: bool, al_elegir: Callable[[str], Any]) -> None:
    con = "tpi-tarjetaactiva" if activa else ""
    with (
        ui.card().classes(f"{con} w-full p-0 overflow-hidden gap-0")
        .on("click", lambda _e, clave=f.clave: al_elegir(clave))
    ):
        with ui.element("div").classes("w-full aspect-[9/16] relative"):
            _portada(f)
            ui.label(f.nombre).classes(
                "absolute left-2 top-2 text-[11px] font-bold uppercase tracking-wide"
            ).style(f"background:{f.color}; color:#0B0B0C; padding:2px 6px; border-radius:6px")


def _portada(f: Formato) -> None:
    """La viñeta del dibujo típico de la familia, sobre el fondo del tema que sugiere."""
    try:
        png = miniaturas.dibujar_miniatura({"tipo": f.dibujos[0]}, tema=f.tema)
        ui.image(url_medio(png)).classes("w-full h-full").props("fit=cover")
    except Exception as e:  # una portada que falla no puede tapar la familia elegida
        with ui.element("div").classes("w-full h-full flex items-center justify-center p-3"):
            ui.label(f.nombre).classes("text-sm text-center").style(f"color:{PIEL['texto_muro']}")
            ui.tooltip(str(e))


def _costado(f: Formato, al_cambiar_pieza: Callable[[str, str], Any]) -> None:
    with ui.card().classes("tpi-tarjeta w-full p-4 gap-3"):
        with ui.row().classes("items-start gap-3 no-wrap w-full"):
            try:
                png = miniaturas.dibujar_miniatura({"tipo": f.dibujos[0]}, tema=f.tema)
                ui.image(url_medio(png)).classes("w-[78px] shrink-0 rounded-md")
            except Exception:
                ui.element("div").classes("w-[78px] h-[139px] shrink-0 rounded-md bg-[#2A2A2C]")
            with ui.column().classes("gap-1 min-w-0"):
                ui.label(f.nombre).classes("tpi-titulo text-lg leading-tight")
                ui.label(f.que_es).classes("text-sm")
        for pieza, valor in (
            ("Molde", " o ".join(f.moldes)),
            ("Estilo", f.tema),
            ("Dibujos", ", ".join(f.dibujos)),
        ):
            with ui.row().classes("items-center justify-between gap-2 w-full"):
                ui.label(f"{pieza}: {valor}").classes("text-sm")
                ui.button("cambiar", on_click=lambda p=pieza: al_cambiar_pieza(f.clave, p)).props(
                    "flat dense size=sm"
                )
        ui.label(texto_del_pie(f.clave)).classes("tpi-tenue text-xs")
```

Import que falta en `typing`: `Callable` va en `from collections.abc import Callable` (no en `typing`), y
`Any` en `typing`. Corregir la línea de imports al escribirlo.

- [ ] **Paso 4 — Verde la lógica**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_formatos_ui -v 2>&1 | tail -10
```

- [ ] **Paso 5 — Montarlo en la pantalla Idea**

En `crear.py::seccion_ejercicio`, la pestaña «Ideas» (`_panel_ideas`, líneas 112-142) termina con
`muro_y_costado(...)`: la idea escrita arriba, el muro abajo, el costado al lado. Atributos nuevos en
`__init__`:

```python
        self.eleccion: dict[str, Any] = {"clave": None, "molde": None, "tema": None, "dibujo": None}
```

`al_elegir(clave)` escribe `self.eleccion["clave"] = clave` y refresca la columna. `al_cambiar_pieza(clave,
pieza)` abre un `ui.dialog` con un `ui.select` de las opciones reales de esa pieza — `MOLDES` para Molde,
`listar_temas()` para Estilo, `opciones_select()` para Dibujos — y guarda el cambio en
`self.eleccion[pieza.lower()]`. Cambiar una pieza **no** deshace la familia: sigue activa, con la pieza
distinta a la vista (su regla: «todo elegible, nada obligatorio»).

- [ ] **Paso 6 — Verlo con los ojos**

Panel abierto → `/crear` → escribir «32 por 11 sin lápiz» → confirmar: la tarjeta **Hacks** aparece marcada,
el detalle está **al costado** y no debajo, cada pieza tiene su «cambiar», y tocar otra tarjeta no deshabilita
ningún botón. Captura en la conversación antes del commit.

- [ ] **Paso 7 — Suite, lint, commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add src/tpi_videos/panel/formatos_ui.py pruebas/test_formatos_ui.py src/tpi_videos/panel/paginas/crear.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'El muro de las cuatro familias con su detalle al costado, como quedó aprobado en el mockup'
```

---

### Tarea C.3 · Cuatro pantallas sin candados

**Archivos:** `src/tpi_videos/panel/paginas/crear.py`, `src/tpi_videos/panel/editor.py`.

- [ ] **Paso 1 — Prueba de que nada bloquea** (agregar a `pruebas/test_formatos_ui.py`)

```python
class CaminoTest(unittest.TestCase):
    def test_se_puede_llegar_al_video_sin_tocar_ninguna_sugerencia(self):
        from tpi_videos.panel.paginas.crear import puede_continuar

        self.assertEqual(puede_continuar({"idea": "una idea"}), (True, ""))

    def test_sin_idea_no_hay_paso_siguiente_y_lo_dice(self):
        from tpi_videos.panel.paginas.crear import puede_continuar

        continuable, motivo = puede_continuar({"idea": "   "})
        self.assertFalse(continuable)
        self.assertIn("idea", motivo.lower())
```

- [ ] **Paso 2 — Verificar que falla**: `ImportError: cannot import name 'puede_continuar'`.

- [ ] **Paso 3 — El paso del camino como dato, no como estado escondido**

En `crear.py`, arriba de `PaginaCrear`:

```python
PASOS = ("idea", "formato", "hoja", "video")
_NOMBRES = {"idea": "Idea", "formato": "Formato", "hoja": "La hoja", "video": "Video"}


def puede_continuar(estado: dict) -> tuple[bool, str]:
    """Ninguna sugerencia sin tocar impide avanzar: solo hace falta la idea escrita."""
    if not (estado.get("idea") or "").strip():
        return False, "Escribe la idea (o sube una foto) para seguir."
    return True, ""
```

- [ ] **Paso 4 — Redibujar la página como camino**

Hoy `PaginaCrear` apila `titulo_seccion("1", …)`, `("2", …)`, `("3", …)` y la sección 1 nunca se retira (falla
2 del diagnóstico). Cambio: una barra arriba con los cuatro nombres (`_NOMBRES`), el activo en `tinta` y los
demás en `tpi-tenue`, todos clicables; el cuerpo muestra **una** pantalla en `self._capa = ui.column()`, con
`self.paso = "idea"`. Al elegir familia, `self.paso = "hoja"` y el editor abre con `molde` y `tema` puestos
desde `self.eleccion` (el guion nuevo se arma con `VACIO | {"molde": …, "tema": …}`).

- [ ] **Paso 5 — La hoja con las tres cosas a la vez**

En `editor.py`, la tarjeta de cada paso muestra **a la vez** su nota, su `tex` con el dibujo en vivo (B.4) y
su voz. No hay stepper «paso 2 de 3» (decisión textual: «mejor las 3 a la vez»). Cada bloque con su
«cambiar». El botón «Crear el video» nunca se deshabilita por no haber tocado una sugerencia; solo cuando el
guion no valida, y entonces el motivo ya lo dice `explicar_errores`.

- [ ] **Paso 6 — Un origen visible en cada texto de la IA**

Donde un bloque viene de la IA (`_escribir_con_ia`, `_buscar_ideas`, `fabrica`), agregar
`ui.label("lo escribió la IA").classes("tpi-tenue")` en el título del bloque. Es la regla de su memoria
«todo elegible, nada obligatorio»: el valor queda a la vista y se puede cambiar.

- [ ] **Paso 7 — Video: el clip de 5 s y «otra vez con este estilo»**

En `seccion_video` (líneas 696-722), debajo del reproductor: el primary sigue siendo el crear normal, y una
acción nueva «Solo el gancho (≈5 s)» que llama a `render.crear_clip_gancho(guion, ...)` por el mismo camino
de `TAREAS.lanzar` que usan los lotes en `crear.py` (el laboratorio de ganchos ya lo hace; **reusar esa
ruta**, no escribir un render paralelo). En las familias con `gancho_corto: true` va marcada como sugerida.
«Otra vez con este estilo» reusa el rehacer con otro tema que ya existe en `videos.py`.

- [ ] **Paso 8 — Verde, recorrer el camino, commit**

Recorrer en el navegador con una idea propia **sin tocar ninguna sugerencia** hasta llegar a un video, y
también el camino inverso (elegir familia, cambiar el estilo, mantener la familia). Cuatro capturas en la
conversación.

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add -u src/tpi_videos/panel && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'Cuatro pantallas sin candados: la hoja muestra las cuentas a la vez y nada bloquea el paso'
```

---

### Tarea C.4 · Mis videos: muro con portada garantizada

**Archivos:** `src/tpi_videos/panel/biblioteca.py`, `src/tpi_videos/panel/paginas/videos.py`,
`src/tpi_videos/render.py`, probar en `pruebas/test_piel.py`.

**Hoy:** `biblioteca.miniatura()` (`:92-107`) devuelve `None` ante cualquier error y `videos.py:187` pinta un
cuadro gris `bg-[#2A2A2C]` en una pila de ~24 tarjetas. Falla 6 del diagnóstico.

- [ ] **Paso 1 — Prueba que falla**

```python
class PortadaTest(unittest.TestCase):
    def test_sin_cuadro_del_video_se_arma_una_portada_con_el_gancho(self):
        from PIL import Image

        from tpi_videos.panel.biblioteca import portada_de_reserva

        destino = Path("/tmp/portada_reserva.png")
        destino.unlink(missing_ok=True)
        ruta = portada_de_reserva(
            "¿Pitágoras era a + b = c?", "#0B1220", "#F8FAFC", destino
        )
        self.assertTrue(ruta.exists())
        im = Image.open(ruta)
        self.assertEqual(im.size[0] * 16, im.size[1] * 9)  # 9:16 de verdad
        gris = im.convert("L")
        self.assertTrue(len({p for p in gris.getdata() if p > 40}) > 1, "la portada no tiene tinta")

    def test_un_titulo_bajado_no_rompe_la_portada(self):
        from tpi_videos.panel.biblioteca import portada_de_reserva

        self.assertTrue(
            portada_de_reserva("", "#FFFFFF", "#000000", Path("/tmp/portada_vacia.png")).exists()
        )
```

- [ ] **Paso 2 — Verificar que falla**: `ImportError: cannot import name 'portada_de_reserva'`.

- [ ] **Paso 3 — Implementarla (PIL, sin render, sin IA)**

```python
def portada_de_reserva(titulo: str, color_fondo: str, color_texto: str, destino: Path) -> Path:
    """El cuadro que se muestra cuando extraer el fotograma falla: el gancho sobre el color del tema."""
    from PIL import Image, ImageDraw, ImageFont

    from ..tipografia import archivo

    ancho, alto = 540, 960
    imagen = Image.new("RGB", (ancho, alto), color_fondo)
    trazo = ImageDraw.Draw(imagen)
    fuente = ImageFont.truetype(str(archivo("Montserrat", "HEAVY")), 62)
    lineas: list[str] = []
    actual = ""
    for palabra in (titulo or "Video sin título").split():
        candidato = f"{actual} {palabra}".strip()
        if trazo.textlength(candidato, font=fuente) <= ancho - 96:
            actual = candidato
        else:
            lineas.append(actual)
            actual = palabra
    lineas.append(actual)
    lineas = lineas[:6]
    y = (alto - len(lineas) * 78) // 2
    for linea in lineas:
        x = (ancho - trazo.textlength(linea, font=fuente)) / 2
        trazo.text((x, y), linea, fill=color_texto, font=fuente)
        y += 78
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagen.save(destino, "PNG")
    return destino
```

- [ ] **Paso 4 — La clave del tema tiene que viajar en el tiempo**

`Video.tema` guarda el **nombre visible** (`linea.get("tema", …)`), que no sirve para cargar los colores.
Verificar primero qué guarda `Tema.nombre`:

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -c "
from tpi_videos.temas import listar_temas
for ident, t, propio in listar_temas()[:4]:
    print(repr(ident), '->', repr(t.nombre))
"
```

Confirmado que son distintos, agregar la clave en `render.py` (donde ya amplía `linea` con
`{"guion":…, "calidad":…, "intermedio":…}`):

```python
    linea |= {"guion": str(Path(ruta_guion).resolve()), "calidad": calidad, "intermedio": str(video_manim),
              "tema_clave": tema_usado}
```

con `tema_usado = tema or guion.tema or marca.tema` resuelto **antes** de `cargar_tema` (hoy se pierde:
`cargar_tema` devuelve el tema ya cargado). Y en `biblioteca.Video` agregar el campo
`tema_clave: str | None = None`, leyendo `linea.get("tema_clave")`.

- [ ] **Paso 5 — Usarla en `miniatura()`**

```python
    except (ErrorMotor, OSError, KeyError, IndexError, json.JSONDecodeError):
        from ..temas import cargar_tema

        marca = cargar_marca()
        try:
            estilo = cargar_tema(video.tema_clave, marca) if video.tema_clave else None
        except ErrorMotor:
            estilo = None
        fondo = estilo.colores.fondo if estilo else "#080A0D"
        texto = estilo.colores.texto if estilo else "#EAF2FF"
        return portada_de_reserva(video.titulo, fondo, texto, video.carpeta / "miniatura_fallback.png")
```

Y en `videos.py::_tarjeta`, el `ui.image("")` recibe siempre `url_medio(biblioteca.miniatura(video))` — el
`bg-[#2A2A2C]` queda solo como fondo del `<div>` mientras carga, no como resultado final.

- [ ] **Paso 6 — Buscador, filtro y grilla**

Sobre la lista en `videos.py`: `ui.input("Buscar por título o materia")` y `ui.select` con
`{"todo": "Todo", "borrador": "Borradores", "publicable": "Publicables"}`, filtrando `self._todos` (atributo
nuevo con la lista sin filtrar) y refrescando. La pila de tarjetas pasa a grilla:

```python
            ui.element("div").classes("grid gap-3 w-full").style(
                "grid-template-columns: repeat(auto-fill, minmax(190px, 1fr))"
            )
```

dentro de la cual `_tarjeta` usa `w-full` en vez de `w-[250px]`, y cada portada lleva arriba a la izquierda
la **etiqueta de la familia** (`formato_de_guion(guion).nombre` de la tarea A.1; si el guion va libre, la
etiqueta es el nombre del molde con `nombre_molde`).

- [ ] **Paso 7 — Comprobarlo con un video roto de propósito**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -c "
from pathlib import Path
import shutil
movidas = []
for p in sorted(Path('salida').glob('*/miniatura.jpg'))[:3]:
    destino = p.with_suffix('.jpg.aparcado'); shutil.move(p, destino); movidas.append(destino)
print('apartadas:', [str(m) for m in movidas])
"
```

Abrir `/videos` y **ver** que donde había un cuadro gris ahora hay una portada con el gancho. Devolver:

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -c "
from pathlib import Path
for p in sorted(Path('salida').glob('*.jpg.aparcado')):
    p.rename(p.with_suffix(''))
print('restauradas')
"
```

`salida/preview_cuaderno_hd/` (corrupta, detectada antes) es el caso real de prueba: ahí tiene que aparecer
la portada de reserva.

- [ ] **Paso 8 — Suite, lint, commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add -u src/tpi_videos pruebas/test_piel.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'Mis videos: buscador, filtro y portada de reserva; el cuadro gris desaparece'
```

---

### Tarea C.5 · La vista previa sale del guion del autor (y los fondos del paquete tienen URL)

**Archivos:** `src/tpi_videos/vista_previa.py`, `src/tpi_videos/panel/paginas/estilos.py`,
`src/tpi_videos/panel/app.py`, `src/tpi_videos/panel/comun.py`, probar en `pruebas/test_miniaturas.py`.

**Dos defectos:** la vista previa usa siempre `plantillas/vista_previa.yaml` (cuya `(a+b)²` no dice nada del
autor) y `carpeta_vistas(tema)`/`_huella(tema)` ignoran el guion, así que al cambiar de guion quedaría el
cache viejo. Y `app.py:59-61` monta `/medios/fondos` sobre `mis_ajustes/fondos`, que quedó vacío tras la
promoción: un estilo con textura del paquete no muestra su fondo en el panel (aunque `ruta_fondo()`
`temas.py:204` sí la encuentra para el render).

- [ ] **Paso 1 — Pruebas que fallan**

```python
class VistaPreviaConGuionTest(unittest.TestCase):
    def test_cambiar_el_guion_cambia_la_huella(self):
        from tpi_videos.vista_previa import carpeta_vistas, huella

        base = huella("neon_cian", None)
        otro = huella("neon_cian", Path("guiones/ejemplos/moldes_virales.yaml"))
        self.assertNotEqual(base, otro)
        self.assertEqual(carpeta_vistas("neon_cian", ""), Path("salida/_vistas/neon_cian").resolve().parent / "_vistas" / "neon_cian")
        self.assertIn(otro[:8], carpeta_vistas("neon_cian", otro[:8]).name)

    def test_la_url_de_un_fondo_del_paquete_no_es_vacia(self):
        from tpi_videos.entorno import PAQUETE
        from tpi_videos.panel.comun import url_medio

        fondos = sorted((PAQUETE / "assets" / "fondos").glob("*.png"))
        self.assertTrue(fondos, "el paquete no trae fondos")
        self.assertTrue(url_medio(fondos[0]), f"{fondos[0]} no tiene URL en el panel")
```

La primera aserción de `carpeta_vistas` es enredada: reemplazarla por
`self.assertTrue(str(carpeta_vistas("neon_cian", "")).endswith("neon_cian"))`.

- [ ] **Paso 2 — Verificar que fallan**: `ImportError: cannot import name 'huella'` (hoy `_huella`) y
  `AssertionError` en la URL.

- [ ] **Paso 3 — Huella y carpeta con el guion**

En `vista_previa.py`:

```python
def carpeta_vistas(tema: str, sufijo: str = "") -> Path:
    return raiz_proyecto() / "salida" / "_vistas" / f"{id_tema(tema)}{sufijo}"


def huella(tema: str, guion: Path | None = None) -> str:
    """Cambia si cambia el tema, la marca, el guion del autor o la versión del motor."""
    marca = cargar_marca()
    datos = {"tema": cargar_tema(tema, marca).model_dump(mode="json"), "marca": marca.model_dump(mode="json")}
    contenido = (guion or GUION).read_text(encoding="utf-8")
    texto = json.dumps(datos, sort_keys=True, ensure_ascii=False) + __version__ + contenido
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]
```

Las tres funciones que reciben `tema` (`en_cache`, `crear_vista_previa`) pasan a recibir
`guion: Path | None = None`, calculan `sufijo = f"__{huella(tema, guion)[:8]}"` **solo si `guion` no es
None**, y `crear_video(str(guion or GUION), …)`. `GUION` queda como default: sin guion abierto, la plantilla
de siempre. Actualizar todos los llamadores:

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && grep -rn 'vista_previa\.\|en_cache\|crear_vista_previa\|carpeta_vistas' src/tpi_videos/ --include='*.py'
```

- [ ] **Paso 4 — La ruta de los fondos del paquete**

En `app.py`, junto a las otras tres:

```python
    from ..temas import FONDOS_DIR

    app.add_media_files("/medios/fondos_paquete", FONDOS_DIR)
```

y en `comun.url_medio`, una pareja más en la tupla `for base, prefijo in (...)`:

```python
        (PAQUETE / "assets" / "fondos", "/medios/fondos_paquete"),
```

con `from ..entorno import PAQUETE, raiz_proyecto`.

- [ ] **Paso 5 — Estilos pide la miniatura con el guion abierto**

En `estilos.py`, donde se calculan las vistas de cada tema, pasar la ruta del guion abierto; el estado ya
existe en el panel (`guion_permitido` en `crear.py` y `EditorGuion` guardan la ruta). **Máximo 4 estilos
calculados por visita** (el riesgo del spec: 17 × 3 renders) y el resto al abrir ese estilo.

- [ ] **Paso 6 — Verde, mirar, commit**

Verificar que la miniatura de `neon_cian` muestra **una fórmula del guion propio** y no `(a+b)²`, y que
`kraft_tiza` muestra su papel.

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add -u src/tpi_videos pruebas && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'La vista previa de estilos sale del guion del autor y los fondos del paquete tienen su URL'
```

---

### Tarea C.6 · El editor de estilos deja elegir la nota al margen

**Archivos:** `src/tpi_videos/panel/paginas/estilos.py`.

**Corrección al spec:** `fondo.imagen`, `formulas_negrita`, `emojis` y la hoja **ya** están expuestos
(`:256`, `:266`, `:278`, `:323`). Falta `nota` y nada más.

- [ ] **Paso 1 — Prueba** (agregar a `pruebas/test_piel.py`)

```python
class NotaTest(unittest.TestCase):
    def test_el_editor_de_estilos_deja_elegir_la_nota(self):
        import inspect

        from tpi_videos.panel.paginas import estilos

        fuente = inspect.getsource(estilos)
        self.assertIn("nota", fuente)
        self.assertIn('"materia"', fuente)  # las tres opciones reales de Nota.color
```

- [ ] **Paso 2 — Verificar que falla** (hoy `nota` no aparece en `estilos.py`).
- [ ] **Paso 3 — La fila, con las opciones del modelo**

Junto a la fila de la hoja (`:323`), una tarjeta «Nota al margen» con: `ui.select` sobre las tres claves de
`Nota.color` (`temas.py:77`: `materia | titulos | acento`), `ui.select` sobre `Nota.rol`
(`texto | titulos`) y `ui.number("Tamaño", min=0.5, max=2.5, step=0.1)` para `Nota.escala`. Guardar con el
mismo camino que usan las otras filas del archivo (`guardar_tema(...)`); **no** escribir un guardado paralelo.

- [ ] **Paso 4 — Verde, mirar dos estilos, commit**

Cambiar la nota de `hoja_de_desarrollo` a `acento` y verificar en la vista previa que la nota se pinta de
acento.

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add -u src/tpi_videos/panel pruebas && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'Estilos deja elegir la nota al margen: color, letra y tamaño'
```

---

## Hito D — Ingeniería 3D

El área que él pidió («falta el área de ingeniería 3D»). Todo lo de este hito sale de **medir Manim 0.22 con
renders mirados uno por uno**, no de su documentación. Los cinco hechos que definen el diseño:

1. **No hay z-buffer.** `ThreeDCamera.capture_mobject()` pinta en el orden que le entregan las caras. Un cubo
   capturado en orden de familia sale **del revés** (parece una caja abierta). Hay que ordenar cada cara por la
   profundidad de su centroide proyectado: `cam.project_points(m.points)[:, 2].mean()`.
2. **`set_phi`/`set_theta` no sirven solos.** Solo mueven `ValueTracker`; `get_rotation_matrix()` devuelve la
   matriz guardada en `__init__`. Sin `cam.reset_rotation_matrix()` **las cuatro vistas salen idénticas** (nos pasó:
   frente/ala/piso dieron el mismo bbox). Es el error más caro del hito.
3. **`resolution=(n, 1)` en `Cylinder`/`Cone` no pinta nada.** Medido: tinta 0,000 con `(64,1)` y `(32,1)`
   contra 0,360 con `(48,2)` (quads degenerados). Se usa `(48, 2)` siempre.
4. **`should_apply_shading=False`** da el aspecto plano de lámina de libro; con sombreado aparecen franjas en el
   manto del cilindro. Y las superficies de Manim no llevan trazo útil: `set_stroke(color, 2)` dibuja una malla
   sobre cada quad. Por eso el **contorno se saca de los píxeles** ya renderizados (`_contorno`).
5. **El corte honesto.** El spec prometía `horizontal`/`vertical` para cualquier cuerpo. Con `painter's
   algorithm` la cara plana de un cilindro o cono partido no se ordena contra su propio manto (el centroide cae
   *dentro* de la silueta): el render salía con la cara de corte flotando adentro. **`corte` se reduce a
   `sin_corte` | `mitad` y solo en el cubo**, donde sí queda perfecto (`/tmp/w_cubo.png`: cara roja arriba,
   paredes azules). Ya está corregido en el spec §4.1 — contarlo al entregar.

Costo medido del render completo (con contorno y recorte): **0,21 s por cuadro**, 16/16 combinaciones sin tocar
el borde. El PNG sale **con el papel transparente** (verificado en `/tmp/p50_resultado.png`: el cilindro
compuesto sobre un rectángulo azul deja ver el azul por donde no hay cuerpo), así la hoja cuadriculada no se
tapa con un rectángulo de color.

**Contrato con lo que ya existe:** `dibujar_visual()` sigue devolviendo un `Dibujo` 2D; el 3D llega adentro como
`ImageMobject`. `escena.py` **no se toca**. La miniatura del muro y del editor sale gratis, porque
`dibujar_miniatura()` llama a `dibujar_visual()`.

### Tarea D.1 · `solido_3d` en el modelo, el catálogo, el revisor y la IA (sin una línea de Manim)

**Archivos:** modificar `src/tpi_videos/guion.py` (`:158` `Literal`, `:212` campos, `:337` validador,
`:574` acceso `solido()`, `:970` `_visual_yaml`), `src/tpi_videos/visuales.py` (`SEGUNDOS_VISUAL`, `CAMPOS`,
`VISUALES`), `src/tpi_videos/revision.py:120`, `src/tpi_videos/redactor.py` (`:68` `dibujo`, `:137-142` campos,
`:242` `anotar`, `:442` `_DIBUJOS`, `:503` `_visual`), `src/tpi_videos/dibujos.py:2192` (el final de
`dibujar_visual`) · modificar `pruebas/test_visuales.py:901` (la prueba que reserva el tipo) · crear
`pruebas/test_solido_3d_modelo.py`

**Carácter:** nada de esta tarea importa manim. Se puede probar entero sin renderer.

**Por qué va todo junto en un commit:** `test_la_tabla_cubre_todos_los_tipos_del_modelo` (B.1) exige
`set(VISUALES) == tipos_del_modelo()`. Agregar el tipo al `Literal` sin agregarlo a la tabla rompe la suite, y
agregarlo a la tabla sin el `Literal` también. El modelo, el catálogo, el formulario del editor (que B.2 arma
desde `CAMPOS`) y el aviso del revisor son **un solo cambio atómico**.

- [ ] **Paso 1 — Pruebas que fallan**

`pruebas/test_solido_3d_modelo.py`:

```python
import unittest

from tpi_videos.guion import Visual, a_yaml, cargar_guion
from tpi_videos.visuales import CAMPOS, SEGUNDOS_VISUAL, VISUALES


def _solido(**extra):
    base = {"tipo": "solido_3d", "figura": "cilindro", "radio": "3 cm", "altura": "5 cm"}
    return Visual.model_validate(base | extra)


class ModeloTest(unittest.TestCase):
    def test_el_tipo_esta_en_la_tabla_con_su_fila_completa(self):
        self.assertIn("solido_3d", VISUALES)
        tipo = VISUALES["solido_3d"]
        self.assertEqual(tipo.materia, "ingenieria")
        self.assertEqual(tipo.marcas, VISUALES["solido"].marcas)  # mismo anotar que el sólido plano
        self.assertIn("solido_3d", SEGUNDOS_VISUAL)
        for clave in ("vista", "corte"):
            self.assertIn(clave, CAMPOS)
            self.assertEqual(CAMPOS[clave].forma, "opcion")

    def test_reusa_la_matematica_del_solido_plano(self):
        plano = Visual.model_validate(
            {"tipo": "solido", "figura": "cilindro", "radio": "3 cm", "altura": "5 cm"}
        )
        self.assertEqual(_solido().solido(), plano.solido())

    def test_la_vista_por_defecto_es_la_axonometrica(self):
        self.assertEqual(_solido().vista, "axonometrica")
        with self.assertRaises(Exception):
            _solido(vista="de_arriba")

    def test_el_corte_a_la_mitad_solo_se_pide_en_el_cubo(self):
        _solido(figura="cubo", lado="4 cm", corte="mitad")  # no debe lanzar
        for figura in ("cilindro", "cono", "esfera"):
            with self.assertRaises(Exception) as sube:
                _solido(figura=figura, corte="mitad")
            self.assertIn("cubo", str(sube.exception).lower(), figura)

    def test_escribir_y_volver_a_leer_conserva_vista_y_corte(self):
        guion = _solido(figura="cubo", lado="4 cm", corte="mitad", anotar=["volumen"])
        bloque = "\n".join(a_yaml({"visual": guion.model_dump(exclude_none=True)}).splitlines())
        self.assertIn("vista: axonometrica", bloque)
        self.assertIn("corte: mitad", bloque)


class ElMotorAvisaTest(unittest.TestCase):
    def test_un_tipo_que_el_motor_no_sabe_dibujar_no_dibuja_un_circuito(self):
        """Hoy dibujar_visual() cae al final y dibuja un circuito para cualquier tipo desconocido.
        Con un catálogo que crece, eso es un dibujo equivocado en el video: tiene que gritar."""
        from tpi_videos.dibujos import dibujar_visual
        from tpi_videos.errores import ErrorMotor
        from tpi_videos.temas import cargar_tema
        from tpi_videos.config import cargar_marca

        col = cargar_tema("pizarra_nocturna", cargar_marca()).colores
        falso = Visual.model_validate({"tipo": "solido", "figura": "cubo", "lado": "4 cm"})
        object.__setattr__(falso, "tipo", "dibujo_inventado")
        with self.assertRaises(ErrorMotor):
            dibujar_visual(falso, col, 7.6, 3.3)
```

- [ ] **Paso 2 — Verificar que fallan**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_solido_3d_modelo -v 2>&1 | tail -8
```

Esperado: `error: ... 'solido_3d' is not valid for 'Visual.tipo'` en las que construyen el visual, y
`AssertionError: 'solido_3d' not found` en la de la tabla.

- [ ] **Paso 3 — El modelo: `guion.py`**

En el `Literal` de `Visual.tipo` (`:158`), una entrada nueva **debajo de `"solido"`** (el orden es el del
select del editor):

```python
        "solido",
        "solido_3d",
```

En el bloque `# solido` (`:212-215`), agregar las dos claves propias:

```python
    # solido_3d (además de figura / lado / radio / altura / anotar)
    vista: Literal["frente", "piso", "ala", "axonometrica"] = "axonometrica"
    corte: Literal["sin_corte", "mitad"] = "sin_corte"  # mitad solo en cubo: ver el validador
```

En el validador (`:337`), abrir la rama a los dos tipos y agregar la restricción del corte:

```python
        elif self.tipo in ("solido", "solido_3d"):
            if not self.figura:
                raise ValueError(
                    "un sólido necesita decir cuál es, ej. figura: 'cilindro' (cubo, cilindro, cono o esfera)"
                )
            analizar_solido(self.figura, self.lado, self.radio, self.altura)
            if self.tipo == "solido_3d" and self.corte == "mitad" and self.figura != "cubo":
                raise ValueError(
                    f"el corte a la mitad solo se dibuja bien en el cubo; en el {self.figura} la cara "
                    "de corte no se ordena con la superficie: usa corte: 'sin_corte'"
                )
            desconocidas = [m for m in self.anotar if m not in MARCAS_SOLIDO]
```

(el resto de la rama queda igual). En el acceso `solido()` (`:576`), aceptar los dos tipos:

```python
        if self.tipo not in ("solido", "solido_3d"):
```

En `_visual_yaml` (`:970`), mismo tratamiento y las dos claves nuevas:

```python
    elif tipo in ("solido", "solido_3d"):
        campos.append(("figura", v.get("figura") or ""))
        for clave in ("lado", "radio", "altura"):
            if v.get(clave):
                campos.append((clave, _simples(v[clave])))
        if tipo == "solido_3d":
            campos.append(("vista", v.get("vista") or "axonometrica"))
            if v.get("corte") not in (None, "", "sin_corte"):
                campos.append(("corte", v["corte"]))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
```

- [ ] **Paso 4 — El catálogo: `visuales.py`**

`SEGUNDOS_VISUAL` (`:18-43`), debajo de `"solido": 3.0`:

```python
    "solido_3d": 3.2,  # el relieve se mira un poco más que la lámina
```

`CAMPOS`, dos entradas nuevas (van junto a `figura`, que ya existe):

```python
        CampoVisual(
            "vista",
            "La vista",
            "opcion",
            "axonometrica es la que mejor se entiende en un video",
            (
                ("axonometrica", "Axonométrica (en relieve)"),
                ("frente", "De frente"),
                ("ala", "De lado"),
                ("piso", "Desde arriba"),
            ),
        ),
        CampoVisual(
            "corte",
            "El corte",
            "opcion",
            "mitad parte el cuerpo y pinta la cara de corte en rojo (solo cubo)",
            (("sin_corte", "Sin corte"), ("mitad", "Partido por la mitad")),
        ),
```

`VISUALES`, la fila nueva **justo debajo de la de `solido`**:

```python
        TipoVisual("solido_3d", "Sólido en 3D", "ingenieria", "🔷",
                   ("figura", "lado", "radio", "altura", "vista", "corte", "anotar"), MARCAS_SOLIDO,
                   ejemplo={"figura": "cilindro", "radio": "3 cm", "altura": "5 cm",
                            "vista": "axonometrica", "anotar": ["volumen"]}),
```

- [ ] **Paso 5 — El revisor y el motor**

`revision.py:120` — el mismo aviso de las 2 marcas sirve para los dos cuerpos:

```python
        if v.tipo in ("solido", "solido_3d"):
```

`dibujos.py:2192` — hoy el final de `dibujar_visual()` construye un circuito para **cualquier** tipo que no
reconoció. Con un catálogo que crece eso es un dibujo equivocado dentro de un video. Cambiar las dos últimas
líneas por su rama explícita y un grito:

```python
    if visual.tipo == "circuito":
        fuente, resistencias = analizar_circuito(visual.fuente, visual.resistencias)
        return circuito(fuente, resistencias, col, ancho, alto, visual.arreglo, papel)
    raise ErrorMotor(f"el motor todavía no sabe dibujar «{visual.tipo}»")
```

`ErrorMotor` ya está importado en `dibujos.py` (lo usa `grafico_funcion`); si no, `from .errores import
ErrorMotor`. **No** se agrega todavía la rama `solido_3d`: esa es la tarea D.2, y entre las dos el tipo grita en
vez de dibujar un circuito.

- [ ] **Paso 6 — Que la IA lo sepa pedir**

La IA no recibe un prompt con la lista de dibujos: **aprende de solo el esquema pydantic** de `PasoIA`. Los
cuatro cambios son el prompt.

```python
# redactor.py:68 — el Literal, debajo de "solido"
        "solido",
        "solido3d",
# redactor.py:97-100 — la descripción (mismo string, agregada al final)
'"engranaje", "mohr" o "solido3d" (máximo 1 en el guion)'
# redactor.py:442 — el mapa
    "solido": "solido",
    "solido3d": "solido_3d",
```

Dos campos nuevos en `PasoIA`, junto a `figura` (`:137-142`), y las descripciones de `figura`/`radio`/`altura`
ampliadas para que digan `"solido" o "solido3d"`:

```python
    vista: Literal["", "frente", "piso", "ala", "axonometrica"] = Field(
        default="", description='Con dibujo="solido3d": "axonometrica" (relieve), "frente", "ala" o "piso"'
    )
    corte: Literal["", "sin_corte", "mitad"] = Field(
        default="",
        description='Con dibujo="solido3d": "mitad" parte el cuerpo; solo vale con figura="cubo"',
    )
```

`_visual()` (`:503`) — la rama compartida:

```python
    elif tipo in ("solido", "solido_3d"):
        if p.figura:
            visual["figura"] = _texto(p.figura)
        for clave in ("lado", "radio", "altura"):
            valor = _texto(getattr(p, clave))
            if valor:
                visual[clave] = valor
        if tipo == "solido_3d":
            if p.vista:
                visual["vista"] = p.vista
            if p.corte:
                visual["corte"] = p.corte
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
```

y en la descripción de `anotar` (`:248`), `'con "solido" o "solido3d", de "volumen", "area"; '`.

- [ ] **Paso 7 — Voltear la prueba que reservaba el tipo**

En `pruebas/test_visuales.py`, la clase `Tipo3dReservadoTest` (`:901`) se escribió para que D.1 la cambiara.
Reemplazarla por:

```python
class Tipo3dTest(unittest.TestCase):
    def test_solido_3d_ya_esta_en_la_tabla_y_en_el_modelo(self):
        self.assertIn("solido_3d", VISUALES)
        self.assertIn("solido_3d", tipos_del_modelo())
```

- [ ] **Paso 8 — Verde, suite completa, commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_solido_3d_modelo pruebas.test_visuales -v 2>&1 | tail -10 && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add src/tpi_videos/guion.py src/tpi_videos/visuales.py src/tpi_videos/revision.py \
        src/tpi_videos/redactor.py src/tpi_videos/dibujos.py pruebas/test_solido_3d_modelo.py \
        pruebas/test_visuales.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'solido_3d entra al modelo, al catálogo y al esquema de la IA'
```

Esperado: `OK` en las dos clases y en la suite (292 + 7 nuevas). Si `test_el_ejemplo_de_cada_tipo_valida_con_
Visual` falla, el `ejemplo` de la fila pide algo que el validador no acepta: arreglar el ejemplo.

- [ ] **Paso 9 — Ver el formulario en el panel (sin render)**

`./tpi panel` → Crear → «Qué dibujar» → **Ingeniería · Sólido en 3D**. Tienen que aparecer los dos `select`
nuevos (La vista, El corte) armados desde `CAMPOS` sin tocar `editor.py` — esa es la prueba de que B.2 quedó
bien. Elegir `cilindro` + `corte: mitad`: el panel debe mostrar el aviso en español del validador, no
rechazarlo en silencio.

---

### Tarea D.2 · `dibujos_3d.py`: la receta medida, con sus cinco trampas

**Archivos:** crear `src/tpi_videos/dibujos_3d.py` · modificar `src/tpi_videos/dibujos.py:2156` (la rama) ·
crear `pruebas/test_solido_3d.py` · modificar `pruebas/test_miniaturas.py:1476` (agregar el tipo a la lista)

**Contrato:** `dibujar_solido_3d(visual, col, ancho, alto, papel) -> Dibujo`, con la misma firma que las otras
funciones de dibujo. Devuelve `Dibujo(mobs=VGroup(imagen, *parches, *rótulos), trazo=[], aparece=[imagen,
*rótulos])`. `trazo` vacío a propósito: un PNG no se traza, y `escena.py:429` ya salta el `Create` si no hay
nada.

- [ ] **Paso 1 — Prueba que falla**

`pruebas/test_solido_3d.py`:

```python
import unittest

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:
    MANIM = False

from tpi_videos.componentes import ANCHO_UTIL
from tpi_videos.config import cargar_marca
from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual
from tpi_videos.guion import Visual
from tpi_videos.temas import cargar_tema
from tpi_videos.visuales import SOLIDOS, VISUALES

COLORES = cargar_tema("hoja_de_desarrollo", cargar_marca()).colores
PAPEL = cargar_tema("hoja_de_desarrollo", cargar_marca()).hoja.color


def _visual(figura, vista, corte="sin_corte"):
    datos = dict(VISUALES["solido_3d"].ejemplo)
    datos.update({"tipo": "solido_3d", "figura": figura, "vista": vista, "corte": corte})
    if figura == "cubo":
        datos.pop("radio", None)
        datos.pop("altura", None)
        datos["lado"] = "4 cm"
    if figura == "esfera":
        datos.pop("altura", None)
    return Visual.model_validate(datos)


@unittest.skipUnless(MANIM, "manim no está instalado")
class LasDieciseisCombinacionesTest(unittest.TestCase):
    """El encuadre es el defecto que hay que evitar: un cuerpo que toca el borde del cuadro se ve
    cortado en el video y nadie se da cuenta mirando el log del render."""

    def _cuadro(self, visual):
        """El mismo camino de 2 líneas de la miniatura: dibujar_visual + Camera a 7,6 x 3,3."""
        from manim import Camera, tempconfig

        dibujo = dibujar_visual(visual, COLORES, ANCHO_UTIL, ALTO_DIBUJO, PAPEL)
        with tempconfig(
            {
                "pixel_width": 950,
                "pixel_height": 412,
                "frame_width": ANCHO_UTIL,
                "frame_height": ALTO_DIBUJO,
                "background_color": PAPEL,
                "verbosity": "ERROR",
                "disable_caching": True,
            }
        ):
            camara = Camera()
            camara.capture_mobject(dibujo.mobs)
            return camara.get_image()

    def test_ninguna_combinacion_toca_el_borde_y_todas_dejan_cuerpo(self):
        from PIL import Image
        import io

        for figura in SOLIDOS:
            for vista in ("frente", "ala", "piso", "axonometrica"):
                im = self._cuadro(_visual(figura, vista))
                img = im.convert("RGB")
                px = list(img.getdata())
                fondo = img.getpixel((2, 2))
                tintados = [
                    (x, y)
                    for y in range(img.height)
                    for x in range(0, img.width, 2)
                    if sum(abs(a - b) for a, b in zip(px[y * img.width + x], fondo)) > 60
                ]
                self.assertTrue(tintados, f"{figura}/{vista} salió en blanco")
                xs = [p[0] for p in tintados]
                ys = [p[1] for p in tintados]
                margen_x = min(min(xs), img.width - 1 - max(xs)) / img.width
                margen_y = min(min(ys), img.height - 1 - max(ys)) / img.height
                self.assertGreater(margen_x, 0.02, f"{figura}/{vista} toca el borde izquierdo/derecho")
                self.assertGreater(margen_y, 0.02, f"{figura}/{vista} toca el borde arriba/abajo")
                self.assertGreater(len(tintados) / (img.width * img.height / 2), 0.03, f"{figura}/{vista}")

    def test_el_corte_del_cubo_pinta_la_cara_en_acento(self):
        from PIL import Image

        im = self._cuadro(_visual("cubo", "axonometrica", corte="mitad")).convert("RGB")
        acento = tuple(int(str(COLORES.acento).lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
        encontrados = sum(
            1
            for y in range(0, im.height, 3)
            for x in range(0, im.width, 3)
            if sum(abs(a - b) for a, b in zip(im.getpixel((x, y)), acento)) < 40
        )
        self.assertGreater(encontrados, 200, "la cara del corte no se ve sombreada en el color de acento")
```

- [ ] **Paso 2 — Verificar que falla**: `solido_3d` lanza `ErrorMotor: el motor todavía no sabe dibujar`
  (el grito que puso D.1). Si en vez de eso pasa el test con un circuito, el grito no está: volver a D.1 paso 5.

- [ ] **Paso 3 — Escribir `src/tpi_videos/dibujos_3d.py`**

```python
"""Un sólido con relieve, renderizado fuera de línea a un PNG que la escena 2D usa como imagen.

Manim 0.22 no tiene z-buffer: pinta cara por cara en el orden que le entregan, y para ordenar usa el
centroide proyectado de cada cara. Cada rareza de abajo (pintar por profundidad, reset_rotation_matrix(),
resolution=(48, 2), el contorno sacado de los píxeles) existe por eso y fue medida cuadro por cuadro.
Costo: 0,21 s por cuerpo.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from manim import DEGREES, ORIGIN, Circle, Cone, Cylinder, ImageMobject, Prism, Sphere, ThreeDCamera, VGroup
from PIL import Image

from . import componentes as c
from . import dibujos as d
from .entorno import raiz_proyecto
from .errores import ErrorMotor

# (phi, theta) en grados: los cuatro puntos de vista del dibujo técnico.
VISTAS: dict[str, tuple[float, float]] = {
    "frente": (0.0, -90.0),
    "ala": (0.0, 0.0),
    "piso": (90.0, -90.0),
    "axonometrica": (35.0, -60.0),
}

PX = 950  # ancho del PNG; el alto sale de la razón ancho/alto del cuadro de dibujo
LARGO_MARCO = 3.2  # lado corto del marco 3D, en unidades de Manim
OBJETIVO = 0.80  # cuánto del lado corto ocupa el cuerpo
MARGEN_PX = 6  # aire que se deja al recortar, para no comerse el trazo


def _rgb(color: Any) -> tuple[int, int, int]:
    hexa = str(color).lstrip("#")
    return int(hexa[0:2], 16), int(hexa[2:4], 16), int(hexa[4:6], 16)


def _puntos(grupo: VGroup) -> np.ndarray:
    return np.vstack([m.points for m in grupo.get_family() if len(m.points)])


@dataclass
class Cuadro3D:
    """El PNG recortado y la cámara que lo generó, para poder anclar los rótulos sobre el cuerpo."""

    camara: ThreeDCamera
    ancho_px: int
    alto_px: int
    marco_ancho: float
    marco_alto: float
    recorte: tuple[int, int, int, int]  # x0, y0, ancho, alto dentro del PNG sin recortar
    centro: np.ndarray  # el centro 3D que se le restó al cuerpo
    factor: float  # la escala que se le aplicó para que entrara en el marco

    def pixeles(self, punto: Any) -> tuple[float, float]:
        """Un punto en las coordenadas 3D originales → (x, y) en píxeles del PNG recortado."""
        p = (np.asarray(punto, dtype=float) - self.centro) * self.factor
        pro = self.camara.project_point(p)
        x = (pro[0] / self.marco_ancho + 0.5) * self.ancho_px - self.recorte[0]
        y = (0.5 - pro[1] / self.marco_alto) * self.alto_px - self.recorte[1]
        return float(x), float(y)


def _piezas(figura: str, corte: str, r: float, h: float, a: float, col: Any):
    """(lo que va detrás del todo, lo que se ordena por profundidad, lo que va al frente).

    Las tapas del cilindro y la base del cono se dibujan a mano: con show_ends=True Manim las pinta
    en el orden de la familia y el cuerpo sale abierto como una taza.
    """
    linea = col.formulas
    if figura == "cubo":
        dims = [a, a, a / 2] if corte == "mitad" else [a, a, a]
        caja = Prism(dimensions=dims).set_fill(col.tenue, 1).set_stroke(linea, 3)
        if corte == "mitad":
            caja.submobjects[1].set_fill(col.acento, 1)  # la cara +Z: la que el corte deja expuesta
        return [], [m for m in caja.get_family() if len(m.points)], []
    if figura == "cilindro":
        manto = (
            Cylinder(radius=r, height=h, show_ends=False, resolution=(48, 2))
            .set_fill(col.tenue, 1)
            .set_stroke(linea, 0)
        )
        abajo = Circle(radius=r, num_components=48).set_fill(col.tenue, 1).set_stroke(linea, 3)
        abajo.move_to([0, 0, -h / 2])
        arriba = Circle(radius=r, num_components=48).set_fill(col.cuadricula, 1).set_stroke(linea, 3)
        arriba.move_to([0, 0, h / 2])
        return [abajo], [manto], [arriba]
    if figura == "cono":
        manto = (
            Cone(base_radius=r, height=h, show_base=False, resolution=(48, 2))
            .set_fill(col.tenue, 1)
            .set_stroke(linea, 0)
        )
        base = Circle(radius=r, num_components=48).set_fill(col.tenue, 1).set_stroke(linea, 3)
        base.move_to([0, 0, -h])  # el cono de Manim cuelga bajo el origen: su base no está en z=0
        return [base], [manto], []
    bola = Sphere(radius=r, resolution=(36, 24)).set_fill(col.tenue, 1).set_stroke(linea, 0)
    return [], [bola], []


def _contorno(cuerpo: np.ndarray, grosor: int = 3) -> np.ndarray:
    """El borde exterior de la máscara: la silueta que las superficies de Manim no traen.

    Trazar cada quad de la superficie dibuja una malla sobre el cuerpo, y sin trazo el cilindro y el
    cono no tienen lados. Los píxeles ya renderizados sí dicen dónde termina el cuerpo.
    """
    interior = cuerpo.copy()
    for dy in range(-grosor, grosor + 1):
        for dx in range(-grosor, grosor + 1):
            interior &= np.roll(cuerpo, (dy, dx), (0, 1))
    return cuerpo & ~interior


def _png_transparente(rgb: np.ndarray, papel, linea, con_contorno: bool):
    """Recorta el cuerpo a su caja con el papel transparente. Devuelve (RGBA, (x0, y0, w, h))."""
    if con_contorno:
        rgb = rgb.copy()
        cuerpo = np.abs(rgb.astype(int) - np.array(papel)).max(axis=2) > 10
        rgb[_contorno(cuerpo)] = linea
    cuerpo = np.abs(rgb.astype(int) - np.array(papel)).max(axis=2) > 10
    ys, xs = np.nonzero(cuerpo)
    if len(xs) == 0:
        raise ErrorMotor("el sólido 3D salió en blanco: revisa los colores del estilo.")
    x0 = max(int(xs.min()) - MARGEN_PX, 0)
    y0 = max(int(ys.min()) - MARGEN_PX, 0)
    x1 = min(int(xs.max()) + MARGEN_PX + 1, rgb.shape[1])
    y1 = min(int(ys.max()) + MARGEN_PX + 1, rgb.shape[0])
    recorte = rgb[y0:y1, x0:x1]
    alpha = (np.abs(recorte.astype(int) - np.array(papel)).max(axis=2) > 10) * 255
    return np.dstack([recorte, alpha.astype(np.uint8)]), (x0, y0, x1 - x0, y1 - y0)


def _medidas(visual: Any) -> tuple[float, float, float]:
    """(radio, altura, arista) del dibujo, con la proporción real que dijo el guion.

    Un cilindro r=1 h=4 se dibuja esbelto y uno r=3 h=5 pancigordo: el número en pantalla y la forma
    tienen que decir lo mismo. El cubo y la esfera no tienen proporción que respetar.
    """
    cuerpo = visual.solido()
    if cuerpo.figura == "cubo":
        return 1.0, 1.0, 2.6
    if cuerpo.figura == "esfera":
        return 1.5, 0.0, 0.0
    r = 3.0 * float(cuerpo.radio) / float(cuerpo.altura) if cuerpo.radio and cuerpo.altura else 1.15
    return min(max(r, 0.35), 1.9), 3.0, 0.0


def _ruta_cache(figura, vista, corte, r, h, a, col, papel) -> Path:
    huella = hashlib.sha1(
        json.dumps(
            [figura, vista, corte, round(r, 3), round(h, 3), a, col.tenue, col.cuadricula, col.acento,
             col.formulas, papel],
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:16]
    carpeta = raiz_proyecto() / "salida" / "_3d"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / f"{figura}_{vista}_{corte}_{huella}.png"


def _render(visual: Any, col: Any, ancho: float, alto: float, papel: str) -> tuple[Path, Cuadro3D]:
    figura, vista, corte = visual.figura, visual.corte, visual.vista
    r, h, a = _medidas(visual)
    destino = _ruta_cache(figura, vista, corte, r, h, a, col, papel)
    phi, theta = VISTAS[visual.vista]
    if ancho >= alto:
        marco_alto, marco_ancho = LARGO_MARCO, LARGO_MARCO * ancho / alto
    else:
        marco_ancho, marco_alto = LARGO_MARCO, LARGO_MARCO * alto / ancho
    alto_px = int(round(PX * alto / ancho))
    # La cámara y el encuadre se arman siempre, haya o no PNG en cache: los rótulos se anclan
    # proyectando sobre esta misma cámara, y construirlos cuesta milisegundos contra capturar.
    camara = _camara(phi, theta, marco_ancho, marco_alto, alto_px, papel)
    detras, cuerpo, encima = _piezas(figura, corte, r, h, a, col)
    grupo = VGroup(*detras, *cuerpo, *encima)
    centro, factor = _encuadrar(camara, grupo, marco_ancho, marco_alto)
    lado = destino.with_suffix(".json")
    if destino.exists() and lado.exists():
        recorte = tuple(json.loads(lado.read_text(encoding="utf-8"))["recorte"])
        return destino, Cuadro3D(camara, PX, alto_px, marco_ancho, marco_alto, recorte, centro, factor)

    def profundidad(m):
        return float(camara.project_points(m.points)[:, 2].mean())

    for m in VGroup(*detras).get_family():
        camara.capture_mobject(m)
    for m in sorted([x for x in VGroup(*cuerpo).get_family() if len(x.points)], key=profundidad):
        camara.capture_mobject(m)
    for m in VGroup(*encima).get_family():
        camara.capture_mobject(m)
    imagen = camara.get_image()  # PIL: si se pasa a np.asarray() se pierde .save y .convert
    rgba, recorte = _png_transparente(
        np.array(imagen.convert("RGB")), _rgb(papel), _rgb(col.formulas), con_contorno=figura != "cubo"
    )
    Image.fromarray(rgba, "RGBA").save(destino)
    # El recorte va al lado del PNG: sin él, la segunda vez que se pide el mismo cuerpo los rótulos
    # se anclarían como si el PNG no estuviera recortado y saldrían corridos.
    lado.write_text(json.dumps({"recorte": list(recorte)}), encoding="utf-8")
    return destino, Cuadro3D(camara, PX, alto_px, marco_ancho, marco_alto, recorte, centro, factor)


def _camara(phi, theta, marco_ancho, marco_alto, alto_px, papel) -> ThreeDCamera:
    camara = ThreeDCamera(
        pixel_width=PX,
        pixel_height=alto_px,
        frame_width=marco_ancho,
        frame_height=marco_alto,
        background_color=papel,
        should_apply_shading=False,  # con sombreado el manto sale a franjas
    )
    camara.set_phi(phi * DEGREES)
    camara.set_theta(theta * DEGREES)
    camara.set_gamma(0.0)
    # set_phi/set_theta solo mueven trackers: sin esto la rotación queda la de la cámara recién creada
    # y las cuatro vistas salen idénticas.
    camara.reset_rotation_matrix()
    return camara


def _encuadrar(camara, grupo, marco_ancho, marco_alto) -> tuple[np.ndarray, float]:
    """Centra el cuerpo en su propia caja 3D y lo escala hasta OBJETIVO del lado corto."""
    pts = _puntos(grupo)
    centro = (pts.max(axis=0) + pts.min(axis=0)) / 2
    grupo.shift(-centro)
    factor = 1.0
    for _ in range(6):
        pro = camara.project_points(_puntos(grupo))  # todos los puntos: muestrear de a 7 se salta esquinas
        excede = (
            max(
                (pro[:, 0].max() - pro[:, 0].min()) / marco_ancho,
                (pro[:, 1].max() - pro[:, 1].min()) / marco_alto,
            )
            / OBJETIVO
        )
        if excede <= 1.0:
            break
        grupo.scale(1.0 / excede)
        factor /= excede
    return centro, factor


def dibujar_solido_3d(visual: Any, col: Any, ancho: float, alto: float, papel: str = "#FFFFFF") -> d.Dibujo:
    """El cuerpo en relieve como imagen, con su medida y su V y A escritos al lado."""
    ruta, cuadro = _render(visual, col, ancho, alto, papel)
    imagen = ImageMobject(str(ruta))
    imagen.scale(OBJETIVO * min(alto / imagen.height, ancho / imagen.width))
    imagen.move_to(ORIGIN)

    s = imagen.width / cuadro.recorte[2]  # unidades de escena por píxel del PNG

    def ancla(punto_3d, dx: float = 0.0, dy: float = 0.0) -> np.ndarray:
        x, y = cuadro.pixeles(punto_3d)
        return np.array([(x - cuadro.recorte[2] / 2) * s + dx, (cuadro.recorte[3] / 2 - y) * s + dy, 0.0])

    cuerpo = visual.solido()
    r, h, a = _medidas(visual)
    unidad = cuerpo.unidad or ""
    parches, rótulos = VGroup(), VGroup()

    def etiqueta(texto: str, donde: np.ndarray, tam: int = 20) -> None:
        rotulo = c.texto(texto, tam, c.SEMIBOLD, col.texto).move_to(donde)
        fondo, rotulo = d._parche(rotulo, papel, 0.16)  # el mismo cartón que usa la lámina 2D
        parches.add(fondo)
        rótulos.add(rotulo)

    def mide(clave: str, valor: float, punto, dx: float, dy: float) -> None:
        etiqueta(f"{clave} = {d._numero_latex(valor)} {unidad}".strip(), ancla(punto, dx, dy))

    if cuerpo.figura == "cubo":
        mide("a", cuerpo.lado or a, [0, -a / 2, -a / 2], 0.0, -0.42)
    elif cuerpo.figura == "cilindro":
        mide("r", cuerpo.radio or 0.0, [r / 2, 0, h / 2], 0.0, 0.34)
        mide("h", cuerpo.altura or 0.0, [-r, 0, 0], -0.85, 0.0)
    elif cuerpo.figura == "cono":
        mide("r", cuerpo.radio or 0.0, [r / 2, 0, -h], 0.0, -0.34)
        mide("h", cuerpo.altura or 0.0, [0, 0, -h / 2], -0.95, 0.0)
    else:
        mide("r", cuerpo.radio or 0.0, [r / 2, 0, 0], 0.0, 0.30)

    # El volumen y el área al costado, donde siempre hay hueco: el cuerpo mide ~2,6 de 7,6 de ancho.
    pie = 0
    for marca in visual.anotar[:2]:
        valor = cuerpo.volumen if marca == "volumen" else cuerpo.area
        sufijo = "³" if marca == "volumen" else "²"
        etiqueta(
            f"{'V' if marca == 'volumen' else 'A'} = {d._numero_latex(valor)} {unidad}{sufijo}".strip(),
            np.array([ancho * 0.30, 0.42 - pie * 0.62, 0.0]),
            22,
        )
        pie += 1

    todo = VGroup(imagen, parches, rótulos)
    return d.Dibujo(mobs=todo, trazo=[], aparece=[imagen, *rótulos])
```

**Lo que hay que saber de este código antes de escribirlo** (cada uno costó un render mirado):

- `Prism(dimensions=[x, y, z])` con **z la vertical**; `Cube` no tiene `edge_length`. La cara de arriba es
  `submobjects[1]` (el orden de las 6 caras es −Z, +Z, −X, +X, +Y, −Y: medido imprimiendo los centros).
- `Circle(radius=r, num_components=48)`: con los 4 por defecto la elipse proyectada es un polígono y se nota
  el quiebre contra la silueta. `arc_resolution` **no** es argumento en 0.22.
- `camara.project_point()` devuelve (x, y, profundidad) en unidades del marco; el mapeo a píxel es el de
  `Cuadro3D.pixeles`, verificado midiendo que el punto caía sobre el relleno del cuerpo.
- El recorte con alpha es lo que hace que la hoja cuadriculada se vea **a través** del dibujo. Sin recortar,
  `ImageMobject` mide 7,6×3,3 con aire transparente adentro y la miniatura sale diminuta: `marco_para()` de
  B.3 encuadra por la caja del grupo, no por la tinta.

- [ ] **Paso 4 — La rama en `dibujos.py`**

En `dibujar_visual()`, debajo de la rama de `solido` (`:2156`):

```python
    if visual.tipo == "solido_3d":
        from .dibujos_3d import dibujar_solido_3d  # adentro: manim 3D no debe pesar en los dibujos 2D

        return dibujar_solido_3d(visual, col, ancho, alto, papel)
```

- [ ] **Paso 5 — Verde**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_solido_3d -v 2>&1 | tail -8
```

Esperado: `OK` (2 pruebas, ~7 s las 16 combinaciones). **Si una combinación toca el borde, no se baja el
umbral 0,02**: se mira el PNG (`salida/_3d/*.png`) y se revisa `_encuadrar` (el `::7` de muestreo y el
`reset_rotation_matrix()` son los dos sospechosos históricos).

- [ ] **Paso 6 — Mirar los 8 cuadros, no solo que pasen**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python - <<'PY'
from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual
from tpi_videos.componentes import ANCHO_UTIL
from tpi_videos.config import cargar_marca
from tpi_videos.guion import Visual
from tpi_videos.temas import cargar_tema
from tpi_videos.visuales import SOLIDOS
from manim import Camera, tempconfig
import time
col = cargar_tema("hoja_de_desarrollo", cargar_marca()).colores
papel = cargar_tema("hoja_de_desarrollo", cargar_marca()).hoja.color
t0 = time.time()
for figura in SOLIDOS:
    for vista in ("axonometrica", "frente"):
        v = Visual.model_validate({"tipo": "solido_3d", "figura": figura, "radio": "3 cm",
                                   "altura": "5 cm", "lado": "4 cm", "vista": vista,
                                   "anotar": ["volumen"]})
        dd = dibujar_visual(v, col, ANCHO_UTIL, ALTO_DIBUJO, papel)
        with tempconfig({"pixel_width": 950, "pixel_height": 412, "frame_width": ANCHO_UTIL,
                         "frame_height": ALTO_DIBUJO, "background_color": papel,
                         "verbosity": "ERROR", "disable_caching": True}):
            cam = Camera(); cam.capture_mobject(dd.mobs); cam.get_image().save(f"/tmp/D_{figura}_{vista}.png")
print(f"8 cuadros en {time.time() - t0:.1f} s -> /tmp/D_*.png")
PY
```

**Abrir los 8 PNG con Read y mirarlos.** La lista de verificación, en español para el usuario:

- ¿El cilindro tiene su tapa de arriba más clara y el arco de abajo cerrado (no una taza abierta)?
- ¿El cono se lee como cono? **Defecto conocido y aceptado:** donde el flanco toca la elipse de la base queda
  un pequeño quiebre (la tangente real de un cono en perspectiva no cae sobre un vértice del borde). Se ve
  como un hombro, no como un error. Si se ve como un globo, está mal la proporción.
- ¿La esfera es un círculo con su trazo, sin malla?
- ¿El cubo partido tiene la cara de arriba en el rojo de acento y las paredes grises?
- ¿Las cuatro vistas dan **distintas**? (Si dos son idénticas, se perdió el `reset_rotation_matrix()`.)
- ¿`r`, `h` o `a` están escritas y coinciden con el guion? ¿`V` y `A` también?

- [ ] **Paso 7 — La miniatura también (agregar el tipo a la prueba de B.3)**

En `pruebas/test_miniaturas.py:1476`, la tupla de tipos pasa a
`("engranaje", "poligono_regular", "viga", "torta", "mohr", "solido", "solido_3d")`. Verde con el umbral
`0.30` **sin tocarlo**: si el 3D llega chico, el culpable es el recorte del paso 3 (punto 4 de la lista).

- [ ] **Paso 8 — Suite, lint, commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3 && \
uvx ruff@0.12 check src pruebas && uvx ruff@0.12 format src pruebas && \
git add src/tpi_videos/dibujos_3d.py src/tpi_videos/dibujos.py pruebas/test_solido_3d.py \
        pruebas/test_miniaturas.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'dibujos_3d: cubo, cilindro, cono y esfera en cuatro vistas, renderizados a PNG'
```

---

### Tarea D.3 · End-to-end: el guion, el video, la familia 1 y la cuota de IA en cero

**Archivos:** crear `guiones/el_cubo_partido.yaml` · modificar `plantillas/formatos.yaml` (la familia `trampas`)
· nada de `src/`

**Carácter:** el paso que él espera. Un video con un sólido en 3D que se vea en el cuadro, y la confirmación de
que nada de esto gastó una llamada.

- [ ] **Paso 1 — El guion, escrito a mano**

`guiones/el_cubo_partido.yaml` — un guion corto (4 pasos, voz de ≤18 palabras cada una) con **dos** dibujos 3D
para probar las dos vistas y el corte. Los números de la pantalla salen del texto: `lado: "4 cm"` → la arista
se escribe `a = 4 cm`, y `V`/`A` los calcula `analizar_solido()`, así que no hay forma de contradecirse.

```yaml
titulo: "El cubo partido"
materia: ingenieria
curso: "Estática · resistencia de materiales"
duracion_apuntada: 30
gancho:
  texto: "Cortar un cubo por la mitad cambia una de sus cuentas, pero no como piensas."
  estilo: curiosidad
datos:
  - tex: "a = 4\\ \\text{cm}"
    voz: "La arista mide cuatro centímetros."
pasos:
  - tex: "V = a^3 = 64\\ \\text{cm}^3"
    voz: "El volumen de un cubo es la arista al cubo: sesenta y cuatro centímetros cúbicos."
    visual:
      tipo: solido_3d
      figura: cubo
      lado: "4 cm"
      vista: axonometrica
      anotar: [volumen]
  - tex: "A = 6a^2 = 96\\ \\text{cm}^2"
    voz: "El área son seis caras. Cada cara dieciséis, noventa y seis en total."
    visual:
      tipo: solido_3d
      figura: cubo
      lado: "4 cm"
      vista: frente
  - tex: "A' = 5a^2 + 2a^2 = 112\\ \\text{cm}^2"
    voz: "Partido por la mitad aparecen dos caras nuevas: el área sube a ciento doce."
    visual:
      tipo: solido_3d
      figura: cubo
      lado: "4 cm"
      corte: mitad
      vista: axonometrica
      anotar: [area]
  - tex: "V' = a^3 / 2 = 32\\ \\text{cm}^3"
    voz: "Y el volumen, en cambio, se parte justo por la mitad: treinta y dos."
    visual:
      tipo: solidos_3d_placeholder
```

**El último paso está mal a propósito** (`solidos_3d_placeholder`): sirve para comprobar que `./tpi revisar`
avisa del tipo inexistente en vez de callarse. En cuanto se vea el aviso, cambiarlo a:

```yaml
    visual:
      tipo: solido_3d
      figura: cilindro
      radio: "3 cm"
      altura: "5 cm"
      vista: ala
      anotar: [volumen]
```

- [ ] **Paso 2 — Revisar sin gastar nada**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && ./tpi revisar guiones/el_cubo_partido.yaml
```

Primero: un aviso sobre `solidos_3d_placeholder` (el error de a propósito). Después de arreglarlo: salida limpia
o con sugerencias, **y ninguna línea que mencione un proveedor de IA** — `revisar` con `--sin-ia` no hace
llamadas, y este paso no tiene clave configurada a propósito.

- [ ] **Paso 3 — El render rápido y los cuadros**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
./tpi crear guiones/el_cubo_partido.yaml --borrador --voz silencio --sincronizar estimado \
  --sin-subtitulos --salida /tmp/taller3d
```

Con los 4 dibujos 3D en cache, el render no debería pasar de ~2 minutos. Cuando termine la notificación (nada de
sondeo), extraer **un cuadro por paso**, sobre el minuto 0:8, 0:16, 0:24 y 0:32, y abrirlos con Read:

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -c "from tpi_videos.videos import extraer_cuadro; \
[extraer_cuadro('/tmp/taller3d/El_cubo_partido.mp4', f'/tmp/d3d_{s}.png', s) for s in (8, 16, 24, 32)]"
```

Mirar: el cuerpo con relieve sobre la hoja cuadriculada **sin rectángulo de color tapando la grilla** (eso
prueba el alpha), la medida escrita coincidiendo con el guion, la cara del corte en rojo, y que la vista
`frente` del paso 2 se vea distinta de la `axonometrica` del paso 1.

- [ ] **Paso 4 — La familia 1 pasa a ofrecer el 3D**

En `plantillas/formatos.yaml`, la familia `trampas`: `dibujos: [poligono_regular, venn, probabilidad, solido]`
→ `dibujos: [poligono_regular, venn, probabilidad, solido_3d]`. El `solido` plano sigue existiendo en el
catálogo (es más barato y sirve para pizarra); lo que cambia es **lo que la tarjeta sugiere**.

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
.venv/bin/python -m unittest pruebas.test_formatos -v 2>&1 | tail -6
```

Esperado: `OK`. Si alguna prueba de `test_formatos.py` comparaba la lista literal de dibujos de `trampas`,
actualizar **la prueba** a `solido_3d` (es un cambio de contenido decidido por el autor, no una regresión).

- [ ] **Paso 5 — El panel, con clics**

`./tpi panel`:
1. **Crear** → una idea de la familia «Desafíos y trampas» → la tarjeta muestra 🔷 Sólido en 3D entre sus
   dibujos sugeridos.
2. **Editor** → «Qué dibujar» → Ingeniería · Sólido en 3D → la **miniatura real** aparece en el costado
   (prueba de que el PNG 3D pasa por `dibujar_miniatura` sin cambios).
3. Cambiar la vista a `piso`: la miniatura se redibuja y cambia.
4. Poner `cilindro` + `corte: mitad`: el panel muestra el aviso en español, **sin bloquear** el guardado de lo
   demás.

- [ ] **Paso 6 — Commit**

```bash
cd /Users/documentos/Downloads/tuprofeindustrial-videos && \
git add guiones/el_cubo_partido.yaml plantillas/formatos.yaml pruebas/test_formatos.py && \
git -c user.name='paillamilm-blip' -c user.email='paillamil.m@gmail.com' commit -m \
'El cubo partido: primer video con sólido 3D y la familia de trampas lo sugiere'
```

(tercer archivo solo si hubo que actualizar la prueba). **Sin push**: los ~16 commits se empujan cuando él lo
diga.

- [ ] **Paso 7 — Contarle, con sus palabras, lo que se ganó y lo que se recortó**

El informe al usuario tiene que decir las tres cosas, sin esconder la tercera:
- ya elige el sólido en 3D, con sus cuatro vistas y su corte, y se ve en el video y en la miniatura;
- el corte a la mitad **solo funciona en el cubo** y por qué (Manim pinta en orden, no con z-buffer);
- nada de esto tocó la cuota de Gemini: 0 llamadas.

---

## Revisión de este plan contra el spec

Se releyó `2026-10-27-panel-hoja-y-muro-design.md` párrafo por párrafo y se buscó la tarea que lo ejecuta:

| Spec | Dónde se ejecuta |
|---|---|
| §1 las 4 familias, con nombre, comentario y estilo sugerido | A.1 (catálogo + puntador) y C.2 (el muro con el detalle al costado) |
| §2 panel sin candados, todo elegible | C.3 |
| §3 los 24 dibujos con su miniatura real | B.1 (tabla), B.2 (formulario), B.3 (PNG) |
| §4 LaTeX en vivo | B.4 |
| §4.1 el área de ingeniería 3D | D.1 modelo · D.2 dibujo · D.3 video |
| §5 vista previa con SU guion | C.5 |
| §6 los 17 temas dentro del paquete + la ruta `/medios/fondos_paquete` | C.5 (la falla de la promoción se arregla ahí) |
| §7 los tres arreglos gratis del motor | A.2 (`hoja.etiqueta`), A.3 (`subtitulos.color_borde`), A.4 (las 8 letras) |
| §8 mis videos: muro con portada garantizada | C.4 |
| §9 pruebas | A.1 `test_formatos` + `test_puntuar`, B.1 `test_visuales`, B.3 `test_miniaturas`, D.2 `test_solido_3d` |

**Dos huecos que esta revisión encontró y ya están tapados en el texto:**
1. §9 pide que cada familia puntee a dibujos que **existan** en la tabla. En A.1 eso era inalcanzable (la tabla
   `VISUALES` nace en B.1), así que la prueba vive al final de B.1:
   `test_todo_dibujo_que_promete_una_familia_existe_en_la_tabla`.
2. Ninguna tarea podía comprobarse tal como estaba escrita: `uvx ruff@0.12 check src pruebas` **ya falla en el
   árbol limpio** con 10 hallazgos previos a la fase 12, y como cada commit del plan va encadenado con `&&`, el
   primero habría abortado. De ahí la Tarea 0.0. Dos de esos hallazgos (B023 en `lote.py:266` y `crear.py:236`)
   no son ruido: son enlaces tardíos que agarran la tarjeta equivocada.

**Coherencia de nombres revisada** entre tareas: `formatos.cargar_formatos()`, `formato_de_guion()`,
`formatos.puntuar()`, `VISUALES`, `dibujar_miniatura()`, `dibujar_solido_3d()`, `CampoVisual`, `TipoVisual`,
`solido_3d` / `vista` / `corte` — los mismos nombres en el modelo, el catálogo, el editor, el revisor, el
esquema de la IA y las pruebas. La búsqueda de placeholders (`TBD`, `TODO`, «más tarde», «igual que la tarea N»)
no dio nada.

**Lo que este plan NO hace** (para que nadie lo invente sobre la marcha):
- el zoom y la pantalla partida (quedan en pausa; son otra fase);
- subir nada a GitHub: ni push ni merge sin el OK de él;
- cambiar las voces, el kit de publicación ni la cuota;
- añadir figuras 3D nuevas (prisma, torso de revolución) — D deja la puerta abierta en `_piezas()` y nada más.

---

## Cómo ejecutar este plan

Dos caminos:

1. **Subagente por tarea** (recomendado): un subagente limpio ejecuta una tarea, se revisa contra el spec y
   contra las pruebas, y se aprueba antes de pasar a la vecina. Itera rápido y no contamina el contexto.
2. **En línea, por lotes:** se ejecutan las tareas de un hito en esta sesión, con punto de control al final del
   hito.

En ambos casos el orden es **0 → A → B → C → D** y el criterio de «esta tarea está lista» es siempre el mismo:
pruebas verdes + ruff verde + `./tpi revisar` conforme + un render corto **cuyos cuadros fueron mirados**.




