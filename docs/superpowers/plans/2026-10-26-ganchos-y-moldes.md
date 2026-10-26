# Ganchos y moldes virales — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que cada idea traiga 3–5 ganchos y un molde narrativo probado, y que la persona pueda ver clips reales antes de gastar el video completo.

**Architecture:** Un catálogo de moldes sin dependencias (`moldes.py`) alimenta el prompt, la validación del guion y las etiquetas del panel. `ideas.py` produce y limpia los ganchos; `redactor.py` fija el gancho elegido y guarda las alternativas en el YAML. `ganchos.py` reutiliza `VideoEjercicio` con `solo_gancho=True` para renderizar clips de 4–6 s; el comando `tpi ganchos` y el panel muestran esos clips. Todo campo nuevo es opcional: los guiones v0.8 y el estilo `pizarra_nocturna` no cambian.

**Tech Stack:** Python 3.12+ (probado aquí con 3.14), Pydantic v2, Manim + manim-voiceover, NiceGUI, PyAV, PyYAML. Sin dependencias nuevas. Pruebas con `unittest` estándar.

**Spec:** `docs/superpowers/specs/2026-10-26-ganchos-y-moldes-virales-design.md`

## Global Constraints

- Solo Python. Nada de Node/React.
- El panel solo sirve `guiones/`, `salida/`, `mis_ajustes/stickers` y `mis_ajustes/fondos`; **nunca** `.env`.
- La clave de Gemini vive solo en `.env` o `GEMINI_API_KEY`; no imprimirla, registrarla ni pedirla.
- Nunca subir videos ni audios (`salida/` está en `.gitignore`).
- Entrega en rama nueva + PR a `main`; nunca push directo a `main`.
- `pizarra_nocturna` con `--voz silencio --borrador` debe salir idéntica cuadro a cuadro a `main` (`PYTHONHASHSEED=0`).
- Versión del paquete: **0.9.0**.
- `ruff` line-length 110. Si `ruff` no está instalado, usar `python -m compileall` y declararlo.

**Entorno de esta sesión (Windows):** no hay Manim, NiceGUI ni LaTeX instalados. Se pueden ejecutar las pruebas puras (`moldes`, `ideas`, `guion`, `redactor`, `ganchos` sin render). Los renders, el panel y la voz real se verifican en el Mac/CI y se declaran como no probados aquí.

---

### Task 1: Catálogo de moldes

**Files:**
- Create: `src/tpi_videos/moldes.py`
- Test: `pruebas/test_moldes.py`, `pruebas/__init__.py`

**Interfaces:**
- Produces: `MOLDE_POR_DEFECTO: str`, `Molde`, `MOLDES: dict[str, Molde]`, `normalizar_molde(valor: str | None) -> str`, `opciones_de_moldes() -> str`, `moldes_para_ia() -> str`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/__init__.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
```

```python
# pruebas/test_moldes.py
import unittest

from tpi_videos.moldes import (
    MOLDE_POR_DEFECTO,
    MOLDES,
    moldes_para_ia,
    normalizar_molde,
    opciones_de_moldes,
)


class MoldesTest(unittest.TestCase):
    def test_normaliza_tildes_mayusculas_y_guiones(self):
        self.assertEqual(normalizar_molde("3 Errores"), "tres_errores")
        self.assertEqual(normalizar_molde("tres-errores"), "tres_errores")
        self.assertEqual(normalizar_molde("MITO vs REALIDAD"), "mito_realidad")
        self.assertEqual(normalizar_molde("Nadie te enseñó esto"), "nadie_te_enseno")
        self.assertEqual(normalizar_molde("POV"), "pov")
        self.assertEqual(normalizar_molde("reto"), "reto")

    def test_desconocido_no_se_inventa(self):
        self.assertEqual(normalizar_molde("bailar"), "")
        self.assertEqual(normalizar_molde(None), "")
        self.assertEqual(normalizar_molde(""), "")

    def test_catalogo_y_texto_para_la_ia(self):
        self.assertEqual(set(MOLDES), {"mito_realidad", "tres_errores", "pov", "reto", "nadie_te_enseno"})
        self.assertEqual(MOLDE_POR_DEFECTO, "libre")
        tabla = moldes_para_ia()
        for clave in MOLDES:
            self.assertIn(clave, tabla)
        for clave in MOLDES:
            self.assertIn(clave, opciones_de_moldes())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest pruebas.test_moldes -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tpi_videos.moldes'`

- [ ] **Step 3: Write the implementation**

```python
"""Catálogo de moldes virales: formatos que ya funcionan en TikTok, Reels y Shorts.

Solo metadatos y normalización. No importa ``guion.py`` para que ``guion.py`` pueda leerlo sin ciclo.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

MOLDE_POR_DEFECTO = "libre"


@dataclass(frozen=True)
class Molde:
    clave: str
    nombre: str
    estructura: str  # los beats que pide el prompt
    regla: str  # un_error | tres_errores | reto | verificacion | ""
    pista: str  # la instrucción objetiva que recibe el guionista
    ejemplo: str  # una frase para que el modelo entienda el tono


MOLDES: dict[str, Molde] = {
    "mito_realidad": Molde(
        clave="mito_realidad",
        nombre="Mito vs realidad",
        estructura="Afirmación incorrecta → por qué falla → forma correcta → resultado",
        regla="un_error",
        pista=(
            "El primer paso es el error que casi todos creen correcto (error: true) y el paso "
            "siguiente muestra la forma correcta. No es el último paso."
        ),
        ejemplo="«¿Pitágoras era a + b = c?» → el error → la forma correcta.",
    ),
    "tres_errores": Molde(
        clave="tres_errores",
        nombre="3 errores",
        estructura="Tres equivocaciones típicas seguidas → la forma correcta → resultado",
        regla="tres_errores",
        pista=(
            "Tres pasos seguidos con error: true, cada uno con su fórmula equivocada, y después "
            "al menos un paso correcto. Nunca un error como último paso."
        ),
        ejemplo="«Los 3 errores que arruinan tu cálculo de porcentajes».",
    ),
    "pov": Molde(
        clave="pov",
        nombre="POV",
        estructura="«Estás en…» en segunda persona → resuelve con lo que tienes → resultado",
        regla="",
        pista=(
            "Cuenta la situación en segunda persona («Estás en el taller y…»), con un problema "
            "concreto, y resuélvelo con los datos que tienes. El gancho también va en segunda persona."
        ),
        ejemplo="«POV: tienes que calcular la caída antes de que suene el timbre».",
    ),
    "reto": Molde(
        clave="reto",
        nombre="Reto",
        estructura="Ejercicio resuelto → un desafío parecido para comentar",
        regla="reto",
        pista="El guion termina con el bloque «reto:»: un ejercicio parecido para responder en comentarios.",
        ejemplo="«Resuelve este y déjame tu respuesta en los comentarios».",
    ),
    "nadie_te_enseno": Molde(
        clave="nadie_te_enseno",
        nombre="Nadie te enseñó esto",
        estructura="Dato que contradice la intuición → se demuestra resolviendo → conclusión",
        regla="verificacion",
        pista=(
            "El guion incluye el bloque «verificacion:» con la comprobación o interpretación que "
            "demuestra el dato. El gancho presenta el dato que contradice la intuición."
        ),
        ejemplo="«Nadie te enseñó que una TV de 55\" mide 55 pulgadas en diagonal».",
    ),
}

_OTRAS_PALABRAS = {
    "mito_realidad": ("mitorealidad", "mito", "mitos", "mitovsrealidad", "mitoyrealidad"),
    "tres_errores": ("treserrores", "3errores", "3error", "errores"),
    "pov": ("pov", "puntodevista"),
    "reto": ("reto", "desafio", "challenge"),
    "nadie_te_enseno": ("nadieteenseno", "nadieloenseno", "nadiemeenseno", "nadie"),
}


def normalizar_molde(valor: str | None) -> str:
    """La clave del molde, venga con tildes, mayúsculas, guiones o espacios."""
    limpio = "".join(
        c
        for c in unicodedata.normalize("NFKD", (valor or "").casefold())
        if not unicodedata.combining(c) and c.isalnum()
    )
    for clave, otras in _OTRAS_PALABRAS.items():
        if limpio == clave.replace("_", "") or limpio in otras:
            return clave
    return ""


def opciones_de_moldes() -> str:
    return ", ".join(MOLDES)


def moldes_para_ia() -> str:
    """La tabla que entra a la plantilla del productor de ideas."""
    lineas = ["| clave | nombre | estructura | ejemplo |", "|---|---|---|---|"]
    for molde in MOLDES.values():
        lineas.append(f"| `{molde.clave}` | {molde.nombre} | {molde.estructura} | {molde.ejemplo} |")
    return "\n".join(lineas)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest pruebas.test_moldes -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/moldes.py pruebas/__init__.py pruebas/test_moldes.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: catálogo de moldes virales"
```

---

### Task 2: Guion con molde y variantes

**Files:**
- Modify: `src/tpi_videos/guion.py` (imports; `Guion`; `problemas_de_molde`; `a_yaml`)
- Modify: `src/tpi_videos/revision.py` (add mold warnings to `revisar`)
- Test: `pruebas/test_guion_moldes.py`

**Interfaces:**
- Consumes: `MOLDES`, `normalizar_molde`, `opciones_de_moldes`.
- Produces: `Guion.molde: str | None`, `Guion.gancho_variantes: list[Gancho]`, `problemas_de_molde(guion: Guion) -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_guion_moldes.py
import unittest

import yaml

from tpi_videos.guion import Guion, a_yaml, problemas_de_molde


def base(**extra):
    datos = {
        "titulo": "Mito de Pitágoras",
        "materia": "matematica",
        "nivel": "1° medio",
        "gancho": {"texto": "¿Pitágoras era a + b = c?", "voz": "¿Pitágoras era a más b igual a c?"},
        "enunciado": {"texto": "Calcula la hipotenusa de 3 y 4.", "voz": "Calcula la hipotenusa."},
        "pasos": [
            {"voz": "Casi todos suman.", "tex": "c = 3 + 4", "error": True, "nota": "Error típico"},
            {"voz": "En realidad es raíz.", "tex": "c = \\sqrt{3^2 + 4^2}", "nota": "Correcto"},
        ],
        "resultado": {"tex": "c = 5", "voz": "Cinco."},
    }
    datos.update(extra)
    return datos


class GuionMoldesTest(unittest.TestCase):
    def test_molde_se_normaliza(self):
        g = Guion.model_validate(base(molde="Mito vs realidad"))
        self.assertEqual(g.molde, "mito_realidad")

    def test_molde_desconocido_avisa_las_opciones(self):
        with self.assertRaises(Exception) as ctx:
            Guion.model_validate(base(molde="bailar"))
        self.assertIn("mito_realidad", str(ctx.exception))

    def test_regla_de_un_error(self):
        g = Guion.model_validate(base(molde="mito_realidad"))
        self.assertEqual(problemas_de_molde(g), [])
        sin_error = base(molde="mito_realidad")
        sin_error["pasos"][0].pop("error")
        self.assertTrue(problemas_de_molde(Guion.model_validate(sin_error)))

    def test_regla_de_tres_errores(self):
        datos = base(molde="tres_errores")
        datos["pasos"] = [
            {"voz": "Uno.", "tex": "1+1=3", "error": True},
            {"voz": "Dos.", "tex": "2+2=5", "error": True},
            {"voz": "Tres.", "tex": "3+3=7", "error": True},
            {"voz": "Bien.", "tex": "3+3=6"},
        ]
        self.assertEqual(problemas_de_molde(Guion.model_validate(datos)), [])

    def test_regla_de_reto_y_verificacion(self):
        self.assertTrue(problemas_de_molde(Guion.model_validate(base(molde="reto"))))
        con_reto = base(molde="reto", reto={"texto": "Intenta con 6 y 8.", "voz": "Intenta con seis y ocho."})
        self.assertEqual(problemas_de_molde(Guion.model_validate(con_reto)), [])
        self.assertTrue(problemas_de_molde(Guion.model_validate(base(molde="nadie_te_enseno"))))

    def test_variantes_y_vuelta_a_yaml(self):
        datos = base(
            molde="mito_realidad",
            gancho_variantes=[
                {"texto": "El error que casi todos cometen", "voz": "El error que casi todos cometen."},
                {"texto": "3 y 4 no dan 7", "tex": "3 + 4 \\neq 7"},
            ],
        )
        texto = a_yaml(datos)
        self.assertIn("molde: mito_realidad", texto)
        self.assertIn("gancho_variantes:", texto)
        g = Guion.model_validate(yaml.safe_load(texto))
        self.assertEqual(g.molde, "mito_realidad")
        self.assertEqual(len(g.gancho_variantes), 2)
        self.assertEqual(g.gancho_variantes[1].tex, "3 + 4 \\neq 7")

    def test_sin_campos_nuevos_el_yaml_no_cambia(self):
        texto = a_yaml(base())
        self.assertNotIn("molde:", texto)
        self.assertNotIn("gancho_variantes:", texto)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest pruebas.test_guion_moldes -v`
Expected: FAIL (`molde` is an extra field / `problemas_de_molde` missing).

- [ ] **Step 3: Implement**

In `guion.py`:

1. Add import:
```python
from .moldes import MOLDES, normalizar_molde, opciones_de_moldes
```

2. In `Guion`, after `velocidad`:
```python
    molde: str | None = None
```

3. After the `gancho` field:
```python
    gancho_variantes: list[Gancho] = []
```

4. Add the validator after `_normalizar_materia`:
```python
    @field_validator("molde", mode="before")
    @classmethod
    def _normalizar_molde(cls, valor: Any) -> Any:
        if valor in (None, ""):
            return None
        clave = normalizar_molde(str(valor))
        if not clave:
            raise ValueError(
                f"«{valor}» no es un molde conocido; usa {opciones_de_moldes()} o quita el campo"
            )
        return clave
```

5. Add the rule checker before `problemas_de_molde`:
```python
def _hay_correcto_despues(pasos: list[Paso], desde: int) -> bool:
    return any(not p.error for p in pasos[desde + 1 :])


def problemas_de_molde(guion: Guion) -> list[str]:
    """Las reglas objetivas del molde: avisos corregibles, nunca un bloqueo del render."""
    if not guion.molde:
        return []
    molde = MOLDES.get(guion.molde)
    if molde is None:
        return [f"«{guion.molde}» no es un molde conocido; usa {opciones_de_moldes()}."]
    errores = [i for i, p in enumerate(guion.pasos) if p.error]
    if molde.regla == "un_error":
        if not errores:
            return [f"«{molde.nombre}» necesita al menos un paso con «error: true»."]
        if not _hay_correcto_despues(guion.pasos, errores[0]):
            return [f"«{molde.nombre}» necesita un paso correcto después del error."]
    elif molde.regla == "tres_errores":
        if len(errores) != 3:
            return [
                f"«{molde.nombre}» necesita exactamente 3 pasos con «error: true» y este guion tiene "
                f"{len(errores)}."
            ]
        if not _hay_correcto_despues(guion.pasos, errores[-1]):
            return [f"«{molde.nombre}» necesita un paso correcto después de los 3 errores."]
    elif molde.regla == "reto" and guion.reto is None:
        return [f"«{molde.nombre}» necesita el bloque «reto:» al final."]
    elif molde.regla == "verificacion" and guion.verificacion is None:
        return [f"«{molde.nombre}» necesita el bloque «verificacion:»."]
    return []
```

6. In `a_yaml`, replace the `for clave in ("nivel", "tema", "voz", "velocidad")` block with:
```python
    if guion.get("nivel"):
        lineas.append(f"nivel: {_dobles(guion['nivel'])}")
    if guion.get("molde"):
        lineas.append(f"molde: {guion['molde']}")
    for clave in ("tema", "voz", "velocidad"):
        if guion.get(clave):
            lineas.append(f"{clave}: {_dobles(guion[clave])}")
```

7. Immediately after `bloque("gancho", guion["gancho"])`, add:
```python
    if guion.get("gancho_variantes"):
        lineas += ["", "gancho_variantes:"]
        for v in guion["gancho_variantes"]:
            lineas.append(f"  - texto: {_dobles(v['texto'])}")
            for clave in ("voz", "emoji"):
                if v.get(clave):
                    lineas.append(f"    {clave}: {_dobles(v[clave])}")
            if v.get("tex"):
                lineas.append(f"    tex: {_simples(v['tex'])}")
            if v.get("destacar"):
                lineas.append(f"    destacar: [{', '.join(_dobles(d) for d in v['destacar'])}]")
```

8. In `revision.py`, before `return Revision(...)`:
```python
    from .guion import problemas_de_molde

    for problema in problemas_de_molde(guion):
        avisos.append(Aviso("advertencia", "molde", problema))
```
This makes `problemas_de_formato()` include the mold warnings automatically (it reads `rev.avisos`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest pruebas.test_guion_moldes -v`
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/guion.py src/tpi_videos/revision.py pruebas/test_guion_moldes.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: molde y variantes opcionales en el guion"
```

---

### Task 3: Ideas con 3–5 ganchos y moldes distintos

**Files:**
- Modify: `src/tpi_videos/ideas.py`
- Test: `pruebas/test_ideas.py`

**Interfaces:**
- Consumes: `normalizar_molde`, `MOLDES`, `Gancho` (para validar tex).
- Produces: `ESTILOS_GANCHO`, `GanchoIdea`, `Idea.molde`, `Idea.ganchos`; `producir(..., molde=, gancho_variante=, gancho_variantes=)`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_ideas.py
import unittest

from tpi_videos.ideas import GanchoIdea, Idea, _limpiar, _texto


def idea(titulo, molde, textos, estilos=None, **extra):
    estilos = estilos or ["dolor", "curiosidad", "dato"]
    return Idea(
        angulo="error_tipico",
        titulo=titulo,
        gancho=textos[0],
        enunciado=f"Resuelve el ejercicio de {titulo} con números concretos y unidades.",
        materia="matematica",
        nivel="1° medio",
        porque="Porque frena el scroll.",
        segundos=45,
        molde=molde,
        ganchos=[
            GanchoIdea(texto=t, estilo=e, emoji="")
            for t, e in zip(textos, estilos, strict=False)
        ],
        **extra,
    )


class IdeasTest(unittest.TestCase):
    def test_conserva_tres_ideas_con_moldes_distintos(self):
        ideas = [
            idea("A", "mito_realidad", ["a", "b", "c"]),
            idea("B", "reto", ["d", "e", "f"]),
            idea("C", "pov", ["g", "h", "i"]),
        ]
        limpias = _limpiar(ideas, None, None)
        self.assertEqual(len(limpias), 3)
        self.assertEqual({i.molde for i in limpias}, {"mito_realidad", "reto", "pov"})
        self.assertEqual(limpias[0].gancho, "a")

    def test_descarta_gancho_de_once_palabras(self):
        largo = "uno dos tres cuatro cinco seis siete ocho nueve diez once"
        ideas = [idea("A", "mito_realidad", [largo, "b", "c", "d"]),
                 idea("B", "reto", ["e", "f", "g"]),
                 idea("C", "pov", ["h", "i", "j"])]  # fmt: skip
        limpias = _limpiar(ideas, None, None)
        self.assertEqual(len(limpias), 2)  # la de 4 válidos queda con 3; la de 3 queda igual
        self.assertNotIn(largo, [g.texto for g in limpias[0].ganchos])

    def test_descarta_idea_con_menos_de_tres_ganchos(self):
        ideas = [idea("A", "mito_realidad", ["a", "b"]), idea("B", "reto", ["d", "e", "f"])]
        limpias = _limpiar(ideas, None, None)
        self.assertEqual([i.titulo for i in limpias], ["B"])

    def test_descarta_emoji_dentro_del_texto(self):
        ideas = [idea("A", "mito_realidad", ["a 🔥", "b", "c"]),
                 idea("B", "reto", ["d", "e", "f"])]  # fmt: skip
        limpias = _limpiar(ideas, None, None)
        self.assertEqual(limpias[0].ganchos[0].texto, "b")

    def test_exige_dos_estilos_distintos(self):
        ideas = [idea("A", "mito_realidad", ["a", "b", "c"], ["dolor", "dolor", "dolor"]),
                 idea("B", "reto", ["d", "e", "f"])]  # fmt: skip
        self.assertEqual([i.titulo for i in _limpiar(ideas, None, None)], ["B"])

    def test_no_repite_molde(self):
        ideas = [idea("A", "reto", ["a", "b", "c"]), idea("B", "reto", ["d", "e", "f"])]
        self.assertEqual([i.titulo for i in _limpiar(ideas, None, None)], ["A"])

    def test_idea_guardada_sin_ganchos_sintetiza_uno(self):
        vieja = Idea(
            angulo="reto", titulo="Vieja", gancho="¿Cuánto pesa?", enunciado="Un ejercicio con números.",
            materia="fisica", nivel="2° medio", porque="Porque sí.", segundos=40,
        )  # fmt: skip
        self.assertEqual(len(vieja.ganchos), 1)
        self.assertEqual(vieja.ganchos[0].texto, "¿Cuánto pesa?")

    def test_texto_limpia_espacios(self):
        self.assertEqual(_texto("  hola   mundo  "), "hola mundo")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest pruebas.test_ideas -v`
Expected: FAIL (`GanchoIdea` missing).

- [ ] **Step 3: Implement**

In `ideas.py`:

1. Imports:
```python
from pydantic import BaseModel, Field, ValidationError, model_validator

from .guion import Gancho, Guion, sin_tildes
from .moldes import MOLDES, normalizar_molde
```

2. Add after `DIFICULTAD_PISTA`:
```python
ESTILOS_GANCHO = ("dolor", "curiosidad", "error", "reto", "dato")
_EQUIVALENCIAS_ESTILO = {"desafio": "reto", "miedo": "dolor", "sorpresa": "dato"}


class GanchoIdea(BaseModel):
    """Una variante del primer segundo. El modelo es tolerante; la limpieza fuerte vive en _limpiar."""

    texto: str = ""
    estilo: str = ""
    emoji: str = ""
    tex: str = ""  # fórmula corta bajo el gancho
    voz: str = ""  # si falta, se usa texto


def _estilo(valor: str) -> str:
    limpio = "".join(c for c in sin_tildes(valor or "").casefold() if c.isalnum())
    limpio = _EQUIVALENCIAS_ESTILO.get(limpio, limpio)
    return limpio if limpio in ESTILOS_GANCHO else ""
```

3. In `Idea`, add:
```python
    molde: str = Field(default="", description="Molde narrativo (ver moldes.py); las 3 ideas usan DISTINTOS")
    ganchos: list[GanchoIdea] = Field(default_factory=list, description="De 3 a 5 variantes del gancho")
```
Change `gancho: str = Field(default="", description=...)` so an old/new payload without it can synthesize.

Add validators after the fields:
```python
    @field_validator("molde", mode="before")
    @classmethod
    def _molde(cls, valor: Any) -> str:
        return normalizar_molde(str(valor)) if valor else ""

    @model_validator(mode="after")
    def _gancho_y_ganchos(self) -> "Idea":
        if not self.ganchos and self.gancho.strip():
            self.ganchos = [GanchoIdea(texto=self.gancho.strip(), estilo="curiosidad")]
        if not self.gancho.strip() and self.ganchos:
            self.gancho = self.ganchos[0].texto
        return self
```

4. Add the cleaner before `_idea`:
```python
def _gancho_limpio(g: GanchoIdea) -> GanchoIdea | None:
    texto = " ".join((g.texto or "").split())
    if not texto or len(texto.split()) > 10 or quitar_emojis(texto) != texto:
        return None
    voz = " ".join((g.voz or "").split())
    if quitar_emojis(voz) != voz:
        return None
    estilo = _estilo(g.estilo)
    if not estilo:
        return None
    try:
        valido = Gancho(texto=texto, voz=voz or None, tex=(g.tex or None))
    except ValidationError:
        return None
    return GanchoIdea(
        texto=texto,
        estilo=estilo,
        emoji=normalizar_para_ia(g.emoji) or "",
        tex=valido.tex or "",
        voz=valido.voz or "",
    )
```

5. In `_idea`, add `ganchos` and `molde` to the update:
```python
    limpios = [g for g in (_gancho_limpio(x) for x in idea.ganchos) if g is not None]
    unicos: list[GanchoIdea] = []
    vistos: set[str] = set()
    for g in limpios:
        clave = sin_tildes(g.texto).casefold()
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(g)
    return idea.model_copy(
        update={
            ...,
            "gancho": _texto(idea.gancho) or (unicos[0].texto if unicos else ""),
            "ganchos": unicos,
            "molde": normalizar_molde(idea.molde),
        }
    )
```
(Keep the existing fields.)

6. In `_limpiar`, add before the enunciado check:
```python
        if len(nueva.ganchos) < 3:
            continue
        if len({g.estilo for g in nueva.ganchos}) < 2:
            continue
        if not nueva.molde or nueva.molde in moldes_vistos:
            continue
```
Initialize `moldes_vistos: set[str] = set()` and `moldes_vistos.add(nueva.molde)` when accepted.

7. In `proponer_ideas`, feed the catalog:
```python
    sistema = (
        (PLANTILLAS_DIR / "ia" / "ideas.md")
        .read_text(encoding="utf-8")
        .replace("{{EMOJIS}}", lista_para_ia())
        .replace("{{MOLDES}}", moldes_para_ia())
    )
```
Import `moldes_para_ia`.

8. Extend `producir` signature after `dificultad`:
```python
    molde: str | None = None,
    gancho_variante: dict[str, Any] | None = None,
    gancho_variantes: list[dict[str, Any]] | None = None,
```
Before building `pistas`:
```python
    if gancho_variante and str(gancho_variante.get("texto") or "").strip():
        gancho = str(gancho_variante["texto"]).strip()
```
Pass to `redactar`:
```python
        molde=molde,
        gancho_variante=gancho_variante,
        gancho_variantes=gancho_variantes,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest pruebas.test_ideas -v`
Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/ideas.py pruebas/test_ideas.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: 3 a 5 ganchos y molde por idea"
```

---

### Task 4: Prompts de ideas y guionista

**Files:**
- Modify: `src/tpi_videos/plantillas/ia/ideas.md`
- Modify: `src/tpi_videos/plantillas/ia/sistema.md`

**Interfaces:**
- Consumes: `{{MOLDES}}` (lo reemplaza `proponer_ideas`).
- Produces: respuestas de Gemini con `molde`, `ganchos[]`, y guiones que respetan las pistas MOLDE / GANCHO ELEGIDO.

- [ ] **Step 1: Edit `ideas.md`**

Replace section 3 title and add the mold section before it:

```markdown
## 3. El molde narrativo (la estructura del video)
- Cada idea usa un MOLDE distinto del catálogo. Las 3 ideas de una respuesta no repiten molde.
- Si el tema no da para un molde, no lo fuerces: elige otro del catálogo. "reto" siempre está disponible.
- El molde decide los beats; el enunciado y el gancho se escriben para ese molde.

{{MOLDES}}

## 4. Los ganchos (3 a 5 por idea)
- Cada idea trae de 3 a 5 ganchos distintos, no cinco formas de la misma pregunta.
- Campos de cada gancho: texto, estilo, emoji y, si aporta, tex y voz.
- Estilos: "dolor" (lo que le cuesta al estudiante), "curiosidad" (brecha de información),
  "error" (la equivocación que casi todos cometen), "reto" (desafío con respuesta para comentar)
  y "dato" (un número que contradice la intuición).
- Al menos 2 estilos distintos por idea. Ningún par de ganchos dice lo mismo con otras palabras.
- texto: máximo 10 palabras, con el número clave en cifras. Nunca revela ni insinúa la respuesta.
- Nada de "Hola", "En este video" ni "Hoy veremos".
- El campo "gancho" de la idea es el RECOMENDADO: copia el texto del primero de la lista.
- tex: opcional, una fórmula corta de LaTeX sin $; si no aporta, vacío.
- voz: opcional, el mismo gancho dicho en palabras (sin cifras ni símbolos); si falta, se usa texto.
```

Renumber the following sections (the old 4, 5, 6 become 5, 6, 7) and change the old "el gancho y el título" to keep only the title:
```markdown
## 5. El título
- titulo: máximo 45 caracteres, que se entienda el tema.
```

Also add to `porque` (now section 7): "nombra el imán del molde y del gancho recomendado".

- [ ] **Step 2: Edit `sistema.md`**

After section 2 (before section 3) add:

```markdown
### El molde narrativo (pista MOLDE)
- Si la petición trae una pista MOLDE, respeta sus beats y su regla al pie de la letra.
- "mito_realidad": un paso con error = true y un paso correcto después.
- "tres_errores": exactamente tres pasos con error = true, seguidos de la forma correcta.
- "pov": cuenta la situación en segunda persona y resuélvela con los datos del enunciado.
- "reto": incluye el bloque reto.
- "nadie_te_enseno": incluye el bloque verificacion.
- Si el molde pide más errores de los que el ejercicio permite con honestidad, no inventes: resuelve bien y deja el aviso para que el profesor lo revise.

### El gancho elegido (pista GANCHO ELEGIDO)
- El texto, el emoji y la fórmula del gancho llegan fijos: úsalos tal cual en gancho_texto, gancho_emoji y gancho_tex.
- Solo puedes ajustar gancho_voz para que suene natural al decirlo.
- No generes gancho_variantes: las variantes las escribe el motor.
```

Also change the "Error típico" paragraph: keep "Máximo uno" for free guiones, but note that a MOLDE pista can ask for three.

- [ ] **Step 3: Verify the templates are complete**

Run: `python -c "from pathlib import Path; print('{{MOLDES}}' in Path('src/tpi_videos/plantillas/ia/ideas.md').read_text(encoding='utf-8'))"`
Expected: `True`

- [ ] **Step 4: Commit**

```bash
git add src/tpi_videos/plantillas/ia/ideas.md src/tpi_videos/plantillas/ia/sistema.md
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: prompts de moldes y ganchos"
```

---

### Task 5: Redactor fija el gancho elegido y guarda alternativas

**Files:**
- Modify: `src/tpi_videos/redactor.py`
- Test: `pruebas/test_redactor_variantes.py`

**Interfaces:**
- Consumes: `Gancho`, `normalizar_molde`, `MOLDES`.
- Produces: `redactar(..., molde=None, gancho_variante=None, gancho_variantes=None)`; helpers `_variante_limpia`, `_aplicar_eleccion`.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_redactor_variantes.py
import unittest

from tpi_videos.redactor import _aplicar_eleccion


def datos_base():
    return {
        "gancho": {"texto": "Del modelo", "voz": "Del modelo.", "emoji": "🤔", "tex": "x = 1"},
    }


class RedactorVariantesTest(unittest.TestCase):
    def test_sobrescribe_texto_tex_y_emoji(self):
        elegido = {"texto": "El elegido", "tex": "x = 2", "emoji": "🔥", "voz": "El elegido."}
        datos = _aplicar_eleccion(datos_base(), "reto", elegido, [elegido])
        self.assertEqual(datos["gancho"]["texto"], "El elegido")
        self.assertEqual(datos["gancho"]["tex"], "x = 2")
        self.assertEqual(datos["gancho"]["emoji"], "🔥")
        self.assertEqual(datos["gancho"]["voz"], "El elegido.")
        self.assertEqual(datos["molde"], "reto")

    def test_sin_voz_en_la_variante_respeta_la_del_modelo(self):
        elegido = {"texto": "El elegido"}
        datos = _aplicar_eleccion(datos_base(), None, elegido, [elegido])
        self.assertEqual(datos["gancho"]["voz"], "Del modelo.")

    def test_alternativas_sin_duplicar_el_elegido(self):
        elegido = {"texto": "El elegido"}
        otras = [elegido, {"texto": "Otra"}, {"texto": "EL ELEGIDO"}]
        datos = _aplicar_eleccion(datos_base(), None, elegido, otras)
        self.assertEqual([v["texto"] for v in datos["gancho_variantes"]], ["Otra"])

    def test_maximo_cinco_alternativas(self):
        elegido = {"texto": "El elegido"}
        otras = [elegido] + [{"texto": f"Otra {n}"} for n in range(1, 9)]
        datos = _aplicar_eleccion(datos_base(), None, elegido, otras)
        self.assertEqual(len(datos["gancho_variantes"]), 5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest pruebas.test_redactor_variantes -v`
Expected: FAIL (`_aplicar_eleccion` missing).

- [ ] **Step 3: Implement**

1. Imports:
```python
from .guion import Gancho, Guion, sin_tildes
from .moldes import MOLDES, normalizar_molde, opciones_de_moldes
```
(Merge with the existing guion import.)

2. Add helpers after `a_guion`:
```python
def _variante_limpia(v: dict[str, Any]) -> dict[str, Any] | None:
    try:
        g = Gancho.model_validate(v)
    except ValidationError:
        return None
    limpio: dict[str, Any] = {"texto": g.texto}
    if g.voz:
        limpio["voz"] = g.voz
    if g.tex:
        limpio["tex"] = g.tex
    if g.emoji:
        limpio["emoji"] = g.emoji
    if g.destacar:
        limpio["destacar"] = g.destacar
    return limpio


def _aplicar_eleccion(
    datos: dict[str, Any],
    molde: str | None,
    gancho_variante: dict[str, Any] | None,
    gancho_variantes: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """El gancho elegido manda sobre lo que escribió el modelo; las alternativas quedan sin repetirlo."""
    if molde:
        datos["molde"] = molde
    elegido = _variante_limpia(gancho_variante) if gancho_variante else None
    if elegido:
        gancho = datos.setdefault("gancho", {})
        gancho["texto"] = elegido["texto"]
        for clave in ("voz", "tex", "emoji", "destacar"):
            if elegido.get(clave):
                gancho[clave] = elegido[clave]
            elif clave in gancho:
                gancho.pop(clave)
    texto_elegido = (elegido or datos.get("gancho") or {}).get("texto", "").strip()
    clave_elegida = sin_tildes(texto_elegido).casefold()
    alternativas: list[dict[str, Any]] = []
    for v in gancho_variantes or []:
        limpio = _variante_limpia(v)
        if limpio and sin_tildes(limpio["texto"]).casefold() != clave_elegida:
            alternativas.append(limpio)
    datos["gancho_variantes"] = alternativas[:5]
    return datos
```

3. Extend `redactar` signature after `segundos_prometidos`:
```python
    molde: str | None = None,
    gancho_variante: dict[str, Any] | None = None,
    gancho_variantes: list[dict[str, Any]] | None = None,
```

4. At the start of `redactar`, normalize the mold:
```python
    clave_molde = normalizar_molde(molde) if molde else ""
    if molde and not clave_molde:
        raise ErrorMotor(
            f"El molde «{molde}» no existe.",
            ayuda=f"Opciones: {opciones_de_moldes()}.",
        )
    molde = clave_molde or None
```

5. After the `segundos_prometidos` block, add mold/variant pistas:
```python
    pistas = list(pistas or [])
    if molde:
        m = MOLDES[molde]
        pistas.append(
            f"MOLDE «{m.nombre}»: {m.estructura}. {m.pista}"
        )
    if gancho_variante:
        texto = str(gancho_variante.get("texto") or "").strip()
        if texto:
            emoji = str(gancho_variante.get("emoji") or "").strip()
            tex = str(gancho_variante.get("tex") or "").strip()
            pistas.append(
                "GANCHO ELEGIDO: usa tal cual el texto «"
                f"{texto}»"
                + (f", el emoji {emoji}" if emoji else "")
                + (f" y la fórmula {tex}" if tex else "")
                + ". Solo ajusta gancho_voz para que suene natural."
            )
```
Careful: existing code reassigns `pistas = [*(pistas or []), duración...]`. Place this after that assignment or adjust. Use `pistas = list(pistas or [])` after the duration block, then append. And `_contenido_base(entrada, materia, nivel, pistas)` gets it.

6. In the correction loop, replace:
```python
        datos = a_guion(respuesta)
```
with:
```python
        datos = _aplicar_eleccion(a_guion(respuesta), molde, gancho_variante, gancho_variantes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest pruebas.test_redactor_variantes -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/redactor.py pruebas/test_redactor_variantes.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: el redactor respeta el gancho elegido"
```

---

### Task 6: Lote reparte moldes y variantes

**Files:**
- Modify: `src/tpi_videos/lote.py`
- Test: `pruebas/test_ideas.py` (add one assertion) or `pruebas/test_lote.py`

**Interfaces:**
- Consumes: `Idea.ganchos`, `Idea.molde`, `producir(..., molde=, gancho_variante=, gancho_variantes=)`.
- Produces: `ItemLote.como_dict()` with `"molde"`; each item keeps its idea with ganchos.

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_lote.py
import unittest

from tpi_videos.ideas import GanchoIdea, Idea
from tpi_videos.lote import ItemLote


class LoteTest(unittest.TestCase):
    def test_payload_incluye_molde_y_ganchos(self):
        idea = Idea(
            angulo="reto",
            titulo="Reto de Ohm",
            gancho="¿Cuánto vale la corriente?",
            enunciado="Un circuito de 12 V y 4 ohm.",
            materia="fisica",
            nivel="2° medio",
            porque="Porque reta.",
            segundos=45,
            molde="reto",
            ganchos=[
                GanchoIdea(texto="¿Cuánto vale la corriente?", estilo="curiosidad"),
                GanchoIdea(texto="No es 3 amperes", estilo="error"),
                GanchoIdea(texto="Resuélvelo en 5 segundos", estilo="reto"),
            ],
        )
        datos = ItemLote(idea=idea, ok=False, error="x").como_dict()
        self.assertEqual(datos["molde"], "reto")
        self.assertEqual(len(datos["idea"]["ganchos"]), 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest pruebas.test_lote -v`
Expected: FAIL (`KeyError: 'molde'`).

- [ ] **Step 3: Implement**

1. In `ItemLote.como_dict`, add:
```python
            "molde": self.idea.molde,
```
next to `"dificultad"`.

2. In `_una_idea`, change the `producir(...)` call:
```python
                gancho=idea.gancho,
                molde=idea.molde or None,
                gancho_variante=idea.ganchos[0].model_dump() if idea.ganchos else None,
                gancho_variantes=[g.model_dump() for g in idea.ganchos] or None,
```
Keep `titulo`, `segundos`, `dificultad`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest pruebas.test_lote -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/lote.py pruebas/test_lote.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: el lote reparte moldes y conserva los ganchos"
```

---

### Task 7: Escena y render de un clip de gancho

**Files:**
- Modify: `src/tpi_videos/escena.py`
- Modify: `src/tpi_videos/render.py`

**Interfaces:**
- Produces: `OpcionesEscena.solo_gancho: bool`; `renderizar_manim(..., solo_gancho: bool = False)`; `crear_clip_gancho(guion, calidad="borrador", proveedor=None, voz=None, velocidad=None, salida=None, progreso=None) -> Path`.

- [ ] **Step 1: Write the failing test (pure, no Manim)**

```python
# pruebas/test_render_gancho.py
import inspect
import unittest

from tpi_videos import escena, render


class FirmaTest(unittest.TestCase):
    def test_opciones_tiene_solo_gancho(self):
        campos = {f.name for f in __import__("dataclasses").fields(escena.OpcionesEscena)}
        self.assertIn("solo_gancho", campos)

    def test_crear_clip_gancho_existe(self):
        self.assertTrue(callable(render.crear_clip_gancho))
        params = inspect.signature(render.crear_clip_gancho).parameters
        self.assertIn("salida", params)
        self.assertIn("voz", params)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest pruebas.test_render_gancho -v`
Expected: FAIL (no `solo_gancho` / no `crear_clip_gancho`). Note: importing `render` does not import Manim at module level, so this test runs in this environment.

- [ ] **Step 3: Implement**

1. `escena.py` — add to `OpcionesEscena`:
```python
    solo_gancho: bool = False
```

2. `escena.py` — in `construct()`, after `self.add(self.fondo)`:
```python
        if self.op.solo_gancho:
            self._gancho()
            # Sin voz el bloque dura ~1 s: se espera para que el clip no dure medio segundo.
            self.wait(3.2 if self.op.proveedor == "silencio" or self.op.voz == "silencio" else 0.4)
            self._guardar_linea_de_tiempo()
            return
```

3. `render.py` — add the parameter and pass it:
```python
def renderizar_manim(
    guion, marca, tema, calidad, proveedor, voz, velocidad, carpeta,
    progreso=None, solo_gancho: bool = False,
) -> tuple[Path, dict]:
```
```python
            opciones=OpcionesEscena(
                proveedor, voz, velocidad, linea, progreso=progreso, solo_gancho=solo_gancho
            ),
```

4. `render.py` — add at the end (after `crear_video`):
```python
def crear_clip_gancho(
    guion: Guion,
    calidad: str = "borrador",
    proveedor: str | None = None,
    voz: str | None = None,
    velocidad: str | None = None,
    salida: Path | None = None,
    progreso: Progreso | None = None,
) -> Path:
    """Renderiza solo cabecera + gancho (sin subtítulos ni recodificación). Devuelve el mp4."""
    import shutil

    from .temas import cargar_tema

    marca = cargar_marca()
    estilo = cargar_tema(guion.tema, marca)
    verificar_requisitos(subtitulos=False)
    if proveedor == "silencio" or voz == "silencio":
        proveedor, voz = "silencio", "silencio"
    else:
        proveedor = proveedor or marca.voz.proveedor
        voz = voz or marca.voz.nombre
    velocidad = velocidad or marca.voz.velocidad
    destino = salida or entorno.raiz_proyecto() / "salida" / "ganchos" / slug(guion.titulo) / "gancho.mp4"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if calidad not in CALIDADES:
        raise ErrorMotor(f"Calidad «{calidad}» no existe.", ayuda=f"Opciones: {', '.join(CALIDADES)}")

    def por_bloque(actual: int, total: int, seccion: str) -> None:
        if progreso:
            progreso("animacion", 0.1 + 0.85 * actual / max(total, 1), "gancho")

    crudo, _ = renderizar_manim(
        guion, marca, estilo, calidad, proveedor, voz, velocidad, destino.parent,
        progreso=por_bloque if progreso else None, solo_gancho=True,
    )
    shutil.copyfile(crudo, destino)
    if progreso:
        progreso("animacion", 1.0, "clip listo")
    return destino
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest pruebas.test_render_gancho -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/escena.py src/tpi_videos/render.py pruebas/test_render_gancho.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: render de un clip de gancho"
```

---

### Task 8: Laboratorio de ganchos

**Files:**
- Create: `src/tpi_videos/ganchos.py`
- Test: `pruebas/test_ganchos.py`

**Interfaces:**
- Consumes: `Idea`, `GanchoIdea`, `Guion`, `a_yaml`, `cabecera_de`, `cargar_guion`, `crear_clip_gancho`, `duracion`.
- Produces:
  - `idea_desde_guion(guion: Guion) -> Idea`
  - `guion_de_vista_previa(idea: Idea, variante: GanchoIdea) -> Guion`
  - `renderizar_ganchos(idea, *, calidad="borrador", proveedor=None, voz=None, velocidad=None, sin_voz=False, progreso=None) -> dict`
  - `elegir_gancho(ruta: str | Path, numero: int) -> Path`

- [ ] **Step 1: Write the failing test**

```python
# pruebas/test_ganchos.py
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from tpi_videos.ganchos import elegir_gancho, guion_de_vista_previa, idea_desde_guion
from tpi_videos.guion import Guion, a_yaml


def guion_datos():
    return {
        "titulo": "Mito de Pitágoras",
        "materia": "matematica",
        "nivel": "1° medio",
        "molde": "mito_realidad",
        "gancho": {"texto": "¿Pitágoras era a + b = c?", "voz": "¿Pitágoras era a más b igual a c?"},
        "gancho_variantes": [
            {"texto": "El error que casi todos cometen", "voz": "El error que casi todos cometen."},
            {"texto": "3 y 4 no dan 7", "tex": "3 + 4 \\neq 7"},
        ],
        "enunciado": {"texto": "Calcula la hipotenusa de 3 y 4.", "voz": "Calcula la hipotenusa."},
        "pasos": [
            {"voz": "Casi todos suman.", "tex": "c = 3 + 4", "error": True},
            {"voz": "En realidad es raíz.", "tex": "c = \\sqrt{3^2 + 4^2}"},
        ],
        "resultado": {"tex": "c = 5", "voz": "Cinco."},
    }


class GanchosTest(unittest.TestCase):
    def test_vista_previa_es_un_guion_valido(self):
        idea = idea_desde_guion(Guion.model_validate(guion_datos()))
        g = guion_de_vista_previa(idea, idea.ganchos[0])
        self.assertEqual(g.gancho.texto, idea.ganchos[0].texto)
        self.assertEqual(g.titulo, idea.titulo)

    def test_elegir_intercambia_sin_duplicar(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "guion.yaml"
            ruta.write_text(a_yaml(guion_datos()), encoding="utf-8")
            elegir_gancho(ruta, 2)
            g = Guion.model_validate(yaml.safe_load(ruta.read_text(encoding="utf-8")))
            self.assertEqual(g.gancho.texto, "El error que casi todos cometen")
            textos = [v.texto for v in g.gancho_variantes]
            self.assertIn("¿Pitágoras era a + b = c?", textos)
            self.assertNotIn("El error que casi todos cometen", textos)
            self.assertEqual(len(textos), len(set(textos)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest pruebas.test_ganchos -v`
Expected: FAIL (`No module named 'tpi_videos.ganchos'`).

- [ ] **Step 3: Implement**

```python
"""Laboratorio de ganchos: clips cortos para elegir el primer segundo antes del video completo.

Reutiliza la escena normal con ``solo_gancho=True``: la hoja, la cabecera, la letra y la voz son las
del video real. No hay pipeline nuevo ni se guardan audios en Git (todo vive en ``salida/``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .entorno import raiz_proyecto
from .errores import ErrorMotor
from .guion import Gancho, Guion, a_yaml, cabecera_de, cargar_guion, sin_tildes
from .ideas import GanchoIdea, Idea

Progreso = Callable[[str, float, str], None]


def _huella(idea: Idea) -> str:
    base = f"{idea.titulo}|{idea.enunciado}|{[g.texto for g in idea.ganchos]}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def _carpeta(idea: Idea) -> Path:
    """salida/ganchos/<slug>/; si otra idea ya usa ese nombre, agrega -2, -3."""
    from .render import slug

    base = raiz_proyecto() / "salida" / "ganchos" / slug(idea.titulo)
    for n in range(1, 100):
        carpeta = base if n == 1 else base.parent / f"{base.name}-{n}"
        marca = carpeta / "clips.json"
        if not marca.exists():
            return carpeta
        try:
            datos = json.loads(marca.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return carpeta
        if datos.get("huella") == _huella(idea):
            return carpeta
    raise ErrorMotor("Hay demasiadas carpetas de ganchos con el mismo título.", ayuda="Borra salida/ganchos/.")


def idea_desde_guion(guion: Guion) -> Idea:
    """El guion ya escrito, con la misma forma que una idea para reutilizar el laboratorio."""
    ganchos = [
        GanchoIdea(
            texto=g.texto,
            estilo="curiosidad" if n == 0 else "dato",
            emoji=g.emoji or "",
            tex=g.tex or "",
            voz=g.voz or "",
        )
        for n, g in enumerate([guion.gancho, *guion.gancho_variantes])
    ]
    return Idea(
        angulo="paso_a_paso",
        titulo=guion.titulo,
        gancho=guion.gancho.texto,
        enunciado=guion.enunciado.texto,
        materia=guion.materia,
        nivel=guion.nivel or "",
        porque="",
        segundos=45,
        molde=guion.molde or "",
        ganchos=ganchos,
    )


def guion_de_vista_previa(idea: Idea, variante: GanchoIdea) -> Guion:
    """Un guion mínimo válido: la escena corta solo dibuja la cabecera y este gancho."""
    datos = {
        "titulo": idea.titulo,
        "materia": idea.materia,
        "nivel": idea.nivel or None,
        "molde": idea.molde or None,
        "gancho": {
            "texto": variante.texto,
            "voz": variante.voz or variante.texto,
            "emoji": variante.emoji or None,
            "tex": variante.tex or None,
        },
        "enunciado": {"texto": idea.enunciado or idea.titulo, "voz": idea.enunciado or idea.titulo},
        "pasos": [{"voz": "Vista previa del gancho.", "nota": "Vista previa"}],
        "resultado": {"tex": "x", "voz": "Vista previa."},
    }
    return Guion.model_validate(datos)


def _manifiesto(idea: Idea, clips: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "titulo": idea.titulo,
        "molde": idea.molde,
        "huella": _huella(idea),
        "clips": clips,
    }


def renderizar_ganchos(
    idea: Idea,
    *,
    calidad: str = "borrador",
    proveedor: str | None = None,
    voz: str | None = None,
    velocidad: str | None = None,
    sin_voz: bool = False,
    progreso: Progreso | None = None,
) -> dict[str, Any]:
    """Un clip por variante, de a uno. El manifiesto se escribe tras cada clip (cancelar no lo pierde)."""
    from .postproduccion import duracion
    from .render import crear_clip_gancho

    variantes = idea.ganchos or [GanchoIdea(texto=idea.gancho, estilo="curiosidad")]
    carpeta = _carpeta(idea)
    carpeta.mkdir(parents=True, exist_ok=True)
    clips: list[dict[str, Any]] = []
    for numero, variante in enumerate(variantes, 1):
        if progreso:
            progreso("animacion", (numero - 1) / len(variantes), f"Gancho {numero} de {len(variantes)}")
        archivo = carpeta / f"gancho-{numero}.mp4"
        crear_clip_gancho(
            guion_de_vista_previa(idea, variante),
            calidad=calidad,
            proveedor="silencio" if sin_voz else proveedor,
            voz="silencio" if sin_voz else voz,
            velocidad=velocidad,
            salida=archivo,
            progreso=progreso,
        )
        clips.append(
            {
                "numero": numero,
                "texto": variante.texto,
                "estilo": variante.estilo,
                "emoji": variante.emoji,
                "tex": variante.tex,
                "voz": variante.voz,
                "archivo": str(archivo),
                "segundos": round(duracion(archivo), 1),
            }
        )
        (carpeta / "clips.json").write_text(
            json.dumps(_manifiesto(idea, clips), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return _manifiesto(idea, clips)


def elegir_gancho(ruta: str | Path, numero: int) -> Path:
    """Pone la variante N como gancho y guarda la anterior (y las demás) en gancho_variantes."""
    ruta = Path(ruta)
    guion = cargar_guion(ruta)
    lista = [guion.gancho, *guion.gancho_variantes]
    if not 1 <= numero <= len(lista):
        raise ErrorMotor(
            f"No hay un gancho {numero} en {ruta.name}: hay {len(lista)}.",
            ayuda="Mira la lista con: ./tpi ganchos " + ruta.name,
        )
    elegido = lista[numero - 1]
    otras = [g for i, g in enumerate(lista, 1) if i != numero]
    vistos = {sin_tildes(elegido.texto).casefold()}
    alternativas = []
    for g in otras:
        clave = sin_tildes(g.texto).casefold()
        if clave not in vistos:
            vistos.add(clave)
            alternativas.append(g.model_dump(exclude_none=True))
    datos = guion.model_dump()
    datos["gancho"] = elegido.model_dump(exclude_none=True)
    datos["gancho_variantes"] = alternativas[:5]
    ruta.write_text(a_yaml(datos, cabecera_de(ruta)), encoding="utf-8")
    cargar_guion(ruta)  # comprueba que lo escrito se lee igual
    return ruta
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest pruebas.test_ganchos -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/ganchos.py pruebas/test_ganchos.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: laboratorio de ganchos"
```

---

### Task 9: Terminal — `tpi ganchos` y flags nuevos

**Files:**
- Modify: `src/tpi_videos/cli.py`

**Interfaces:**
- Consumes: `ganchos.renderizar_ganchos`, `ganchos.elegir_gancho`, `ganchos.idea_desde_guion`, `MOLDES`, `normalizar_molde`.
- Produces: `cmd_ganchos(args)`; `--ganchos` en `ideas`; `--molde`, `--gancho-json`, `--ganchos-json` en `producir`.

- [ ] **Step 1: Add `cmd_ganchos` after `cmd_ideas`**

```python
def _json_de(valor: str | None) -> Any:
    if not valor:
        return None
    try:
        return json.loads(valor)
    except json.JSONDecodeError as e:
        raise ErrorMotor("No entendí el JSON que llegó del panel.", ayuda=f"JSON inválido: {e}") from e


def _mostrar_ganchos(manifiesto: dict, ruta_guion: Path | None) -> None:
    clips = manifiesto["clips"]
    consola.print(f"\n[bold]🎣 Ganchos de «{manifiesto['titulo']}»[/] · {len(clips)} clip(s)\n")
    for clip in clips:
        consola.print(
            f" [bold cyan]{clip['numero']}[/]  [bold]{clip['texto']}[/]  [dim]({clip['estilo']})[/]"
        )
        consola.print(
            f"    [dim]{clip['segundos']} s · {_ruta_amigable(Path(clip['archivo']))}[/]"
        )
    if ruta_guion:
        consola.print(
            f"\n   Para dejar uno fijo: [bold]./tpi ganchos {ruta_guion.name} --elegir N[/]"
            f"\n   Para ver el video con ese gancho: [bold]./tpi crear {ruta_guion.name} --borrador[/]"
        )


def cmd_ganchos(args: argparse.Namespace) -> int:
    """Renderiza los clips de las variantes o cambia el gancho de un guion sin renderizar."""
    from .ganchos import elegir_gancho, idea_desde_guion, renderizar_ganchos
    from .ideas import Idea

    json_activo = _modo_json(args)
    if args.elegir is not None:
        if not args.guion:
            raise ErrorMotor("Para --elegir necesito el guion.", ayuda="Ej. ./tpi ganchos guiones/x.yaml --elegir 2")
        ruta = elegir_gancho(args.guion, args.elegir)
        if json_activo:
            _emitir(etapa="resultado", avance=1.0, guion=ruta, elegido=args.elegir)
        else:
            consola.print(f"[green]✅ Gancho {args.elegir} guardado en {_ruta_amigable(ruta)}.[/]")
            consola.print("   El video se recrea con: ./tpi crear " + _ruta_amigable(ruta) + " --borrador")
        return 0

    if args.idea_json:
        idea = Idea.model_validate(_json_de(args.idea_json)["idea"] if "idea" in _json_de(args.idea_json) else _json_de(args.idea_json))
        ruta_guion = None
    elif args.guion:
        from .guion import cargar_guion

        ruta_guion = Path(args.guion)
        idea = idea_desde_guion(cargar_guion(ruta_guion))
    else:
        raise ErrorMotor(
            "Dime qué ganchos probar.",
            ayuda="Ej. ./tpi ganchos guiones/x.yaml --sin-voz   (o usa «Probar ganchos» en el panel)",
        )

    def avisar(mensaje: str) -> None:
        if json_activo:
            _emitir(etapa="animacion", avance=0.0, detalle=mensaje)
        else:
            consola.print(f"[dim]→ {mensaje}[/dim]")

    if not json_activo:
        consola.print(f"\n[bold]🎣 Probando {len(idea.ganchos)} gancho(s)[/] en 540×960, sin subtítulos.\n")
    manifiesto = renderizar_ganchos(
        idea,
        calidad="borrador",
        sin_voz=args.sin_voz,
        progreso=_progreso_json if json_activo else None,
    )
    if json_activo:
        _emitir(etapa="resultado", avance=1.0, titulo=manifiesto["titulo"], clips=manifiesto["clips"])
    _mostrar_ganchos(manifiesto, ruta_guion)
    return 0
```

- [ ] **Step 2: Wire `ideas --ganchos`**

Add the flag to the `ideas` parser:
```python
    s.add_argument("--ganchos", action="store_true", help="lista las 3–5 variantes de gancho de cada idea")
```
In `_mostrar_ideas(ideas, tema, mostrar_ganchos=False)`, after the recommended hook:
```python
        if mostrar_ganchos:
            for g in idea.ganchos:
                consola.print(f"      [dim]· {g.estilo}: «{g.texto}»[/]")
```
and pass `args.ganchos` from `cmd_ideas`.

In `cmd_ideas`, when choosing an idea, pass the chosen variant:
```python
        variante = elegida.ganchos[0].model_dump() if elegida.ganchos else None
        return _producir(
            ...,
            molde=elegida.molde or None,
            gancho_variante=variante,
            gancho_variantes=[g.model_dump() for g in elegida.ganchos] or None,
        )
```

- [ ] **Step 3: Wire `producir` flags**

Parser:
```python
    s.add_argument("--molde", choices=list(MOLDES), help="molde narrativo del guion (ver ./tpi ideas)")
    s.add_argument("--gancho-json", help=argparse.SUPPRESS)  # la variante elegida, desde el panel
    s.add_argument("--ganchos-json", help=argparse.SUPPRESS)  # todas las variantes, desde el panel
```
Import `MOLDES` at the top of the parser function:
```python
    from .moldes import MOLDES
```
In `_producir`, add parameters `molde=None, gancho_variante=None, gancho_variantes=None`, resolve from args:
```python
    molde = molde if molde is not None else getattr(args, "molde", None)
    variante = gancho_variante if gancho_variante is not None else _json_de(getattr(args, "gancho_json", None))
    variantes = gancho_variantes if gancho_variantes is not None else _json_de(getattr(args, "ganchos_json", None))
```
Pass to `producir(...)`:
```python
        molde=molde,
        gancho_variante=variante,
        gancho_variantes=variantes,
```
Include `molde` and the chosen hook in the JSON result:
```python
            molde=resultado.guion.molde,
            gancho=resultado.guion.gancho.texto,
```

- [ ] **Step 4: Register the parser**

```python
    s = sub.add_parser(
        "ganchos",
        help="prueba clips cortos de cada gancho y elige el mejor antes del video completo",
    )
    s.add_argument("guion", nargs="?", help="el .yaml del guion (opcional si usas --idea-json)")
    s.add_argument("--idea-json", help=argparse.SUPPRESS)  # la idea completa, desde el panel
    s.add_argument("--elegir", type=int, help="deja ese gancho en el guion sin renderizar")
    s.add_argument("--sin-voz", action="store_true", help="clips sin voz (más rápidos)")
    s.add_argument("--progreso-json", action="store_true", help=argparse.SUPPRESS)
    s.set_defaults(func=cmd_ganchos)
```

- [ ] **Step 5: Verify the parser and help**

Run: `python -m tpi_videos ganchos --help` (con `PYTHONPATH=src`)
Expected: shows `guion`, `--elegir`, `--sin-voz`.

- [ ] **Step 6: Commit**

```bash
git add src/tpi_videos/cli.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: comando ganchos y flags de molde"
```

---

### Task 10: Panel — tarjeta con molde, ganchos y clips

**Files:**
- Modify: `src/tpi_videos/panel/paginas/crear.py`
- Modify: `src/tpi_videos/panel/paginas/fabrica.py`

**Interfaces:**
- Consumes: `MOLDES`, `nombre_molde` (nuevo helper en `moldes.py`), `TAREAS`, `url_medio`.
- Produces: botón «Probar ganchos», fila de clips y «Usar este»; chip de molde en Fábrica.

- [ ] **Step 1: Add `nombre_molde` to `moldes.py`**

```python
def nombre_molde(valor: str | None) -> str:
    clave = normalizar_molde(valor)
    return MOLDES[clave].nombre if clave else "Libre"
```

- [ ] **Step 2: Edit the idea card in `crear.py`**

At the top:
```python
from ...moldes import MOLDES, nombre_molde
```

Inside `_mostrar_tarjetas`, after the `ui.row` with the title/angle add:
```python
                    molde = str(idea.get("molde") or "")
                    if molde:
                        ui.chip(nombre_molde(molde), icon="movie_filter").props("dense outline size=sm")
```
Replace the recommended hook label with:
```python
                    elegido_label = ui.label(f"«{idea.get('gancho', '')}»").classes("text-base")
                    ganchos = list(idea.get("ganchos") or [])
                    if ganchos:
                        with ui.expansion(f"Ver los {len(ganchos)} ganchos", icon="bolt").classes("w-full"):
                            for g in ganchos:
                                ui.label(f"{g.get('estilo', '')}: «{g.get('texto', '')}»").classes(
                                    "tpi-ayuda"
                                )
```
In the buttons row, before «Hacer este video»:
```python
                        if ganchos:
                            ui.button(
                                "Probar ganchos",
                                icon="videocam",
                                on_click=lambda i=idea: self._probar_ganchos(i, elegido_label),
                            ).props("outline")
```

- [ ] **Step 3: Add `_probar_ganchos`**

```python
    async def _probar_ganchos(self, idea: dict, etiqueta) -> None:
        if TAREAS.ocupado():
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
            return
        if not idea.get("ganchos"):
            ui.notify("Esta idea no trae variantes: busca otras 3.", type="warning")
            return
        self.zona_idea_video.clear()
        with self.zona_idea_video:
            with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
                ui.label(f"🎣 Probando los ganchos de «{idea.get('titulo', '')}»").classes(
                    "text-lg font-bold"
                )
                barra = ui.linear_progress(value=0, show_value=False).classes("w-full")
                estado = ui.label("Preparando los clips…").classes("tpi-ayuda")
                boton_cancelar = ui.button("Cancelar", icon="stop", on_click=TAREAS.cancelar).props(
                    "flat color=negative"
                )
                fila = ui.row().classes("w-full gap-4 items-start flex-wrap")

        def avance(t: Tarea) -> None:
            barra.value = t.avance
            estado.text = t.texto_etapa

        tarea = await TAREAS.ejecutar("Ganchos", [
            "ganchos", "--idea-json", json.dumps(idea, ensure_ascii=False)
        ], al_cambiar=avance)  # fmt: skip
        boton_cancelar.set_visibility(False)
        if not tarea.ok:
            if tarea.cancelada:
                ui.notify("Cancelado: los clips que alcanzaron a salir quedan en salida/ganchos/.", type="info")
                return
            self._error(tarea)
            return
        estado.text = "Elige el que más frena el scroll."
        clips = list(tarea.resultado.get("clips") or [])
        if not clips:
            ui.notify("No se generó ningún clip.", type="warning")
            return

        def usar(clip: dict) -> None:
            idea["gancho"] = clip["texto"]
            idea["gancho_elegido"] = clip
            etiqueta.text = f"«{clip['texto']}»"
            ui.notify("Ese gancho viaja al video cuando toques «Hacer este video».", type="positive")

        with fila:
            for clip in clips:
                archivo = Path(str(clip.get("archivo", "")))
                with ui.column().classes("items-center gap-2 w-44"):
                    ui.video(url_medio(archivo)).classes("w-full aspect-[9/16] rounded-lg bg-black").props(
                        'preload="metadata"'
                    )
                    ui.label(f"{clip.get('numero')}. «{clip.get('texto', '')}»").classes(
                        "text-sm font-bold text-center"
                    )
                    ui.label(f"{clip.get('estilo', '')} · {clip.get('segundos', 0)} s").classes("tpi-ayuda")
                    ui.button("Usar este", icon="check", on_click=lambda c=clip: usar(c)).props(
                        "outline dense"
                    )
```

- [ ] **Step 4: Make `_hacer_video` send the chosen variant**

Replace the `--gancho` block with:
```python
        variante = idea.get("gancho_elegido")
        if variante:
            args += ["--gancho-json", json.dumps(variante, ensure_ascii=False)]
        elif idea.get("gancho"):
            args += ["--gancho", str(idea["gancho"])]
        if idea.get("ganchos"):
            args += ["--ganchos-json", json.dumps(idea["ganchos"], ensure_ascii=False)]
        if idea.get("molde"):
            args += ["--molde", str(idea["molde"])]
```

- [ ] **Step 5: Show the mold in the batch and in Fábrica**

In `crear.py` `_mostrar_lote`, after the duration label:
```python
                        if item.get("molde"):
                            ui.label(nombre_molde(str(item["molde"]))).classes("tpi-ayuda")
```
In `fabrica.py`, import:
```python
from ...moldes import nombre_molde
```
In `_fila_resultado`, add the mold to `etiqueta`:
```python
                nombre_molde(str(item.get("molde"))) if item.get("molde") else "",
```

- [ ] **Step 6: Verify imports (sin NiceGUI instalado no se puede abrir el panel)**

Run: `python -m compileall -q src/tpi_videos/panel`
Expected: no output (compiles).

- [ ] **Step 7: Commit**

```bash
git add src/tpi_videos/moldes.py src/tpi_videos/panel/paginas/crear.py src/tpi_videos/panel/paginas/fabrica.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "feat: probar ganchos desde el panel"
```

---

### Task 11: Ejemplo, CI y documentación

**Files:**
- Create: `guiones/ejemplos/moldes_virales.yaml`
- Modify: `.github/workflows/render.yml`
- Modify: `README.md`, `docs/GUIA_GUIONES.md`, `docs/PLAN.md`
- Modify: `pyproject.toml`, `src/tpi_videos/__init__.py`

**Interfaces:**
- Produces: un guion real con `molde` y `gancho_variantes` que CI renderiza; documentación de los campos opcionales.

- [ ] **Step 1: Create the example**

```yaml
# Ejemplo de la fase 0.9: un molde narrativo (mito vs realidad) y ganchos alternativos.
titulo: "¿Pitágoras era a + b = c?"
materia: matematica
nivel: "1° medio"
molde: mito_realidad

gancho:
  texto: "¿Pitágoras era a + b = c?"
  voz: "¿Pitágoras era a más b igual a c?"
  emoji: "🤔"
  tex: "a + b = c"

gancho_variantes:
  - texto: "El error que casi todos cometen"
    voz: "El error que casi todos cometen."
    emoji: "⚠️"
  - texto: "3 y 4 no dan 7"
    voz: "Tres y cuatro no dan siete."
    tex: "3 + 4 \neq 7"
  - texto: "La hipotenusa no se suma"
    voz: "La hipotenusa no se suma."
    emoji: "📐"

enunciado:
  texto: "Calcula la hipotenusa de un triángulo rectángulo cuyos catetos miden 3 m y 4 m."
  voz: "Calcula la hipotenusa de un triángulo rectángulo cuyos catetos miden tres y cuatro metros."
  destacar: ["3 m", "4 m"]

datos:
  - tex: "a = 3\\ \\text{m}"
    voz: "Un cateto mide tres metros."
  - tex: "b = 4\\ \\text{m}"
    voz: "El otro cateto mide cuatro metros."
  - tex: "c = ?"
    voz: "Y buscamos la hipotenusa."

pasos:
  - nota: "Error típico"
    tex: "c = 3 + 4"
    voz: "Casi todos suman los catetos y dicen que la hipotenusa mide siete."
    error: true
  - nota: "Pitágoras"
    tex: "c = \\sqrt{a^2 + b^2}"
    voz: "Pero Pitágoras dice que la hipotenusa es la raíz de la suma de los cuadrados."
  - nota: "Reemplazamos"
    tex: "c = \\sqrt{3^2 + 4^2}"
    voz: "Reemplazamos los catetos: tres al cuadrado más cuatro al cuadrado."
  - nota: "Calculamos"
    tex: "c = \\sqrt{25} = 5\\ \\text{m}"
    voz: "Nueve más dieciséis es veinticinco, y su raíz es cinco."

resultado:
  tex: "c = 5\\ \\text{m}"
  voz: "La hipotenusa mide cinco metros."
  emoji: "✅"

verificacion:
  texto: "5 m es mayor que cada cateto y menor que su suma: tiene sentido."
  voz: "Cinco es mayor que cada cateto y menor que su suma: tiene sentido."

reto:
  texto: "¿Y si los catetos miden 6 m y 8 m?"
  voz: "¿Y si los catetos miden seis y ocho metros? Déjalo en los comentarios."
  emoji: "💬"

cierre:
  texto: "Sígueme para más ejercicios resueltos"
  voz: "Sígueme para más ejercicios resueltos. ¡Nos vemos en el próximo!"
```

- [ ] **Step 2: Add CI steps**

In `.github/workflows/render.yml`, after the existing render step, add a clip render:
```yaml
      - name: Clip de gancho
        run: |
          ./tpi ganchos guiones/ejemplos/moldes_virales.yaml --sin-voz
          CLIP=$(find salida/ganchos -name 'gancho-1.mp4' | head -1)
          ffprobe -v error -select_streams v:0 -show_entries stream=width,height \
            -show_entries format=duration -of json "$CLIP" > clip.json
          python - <<'PY'
          import json
          datos = json.load(open("clip.json"))
          w = datos["streams"][0]["width"]
          h = datos["streams"][0]["height"]
          d = float(datos["format"]["duration"])
          assert (w, h) == (540, 960), (w, h)
          assert 3 <= d <= 6, d
          PY
```
(Use the same shell/python setup as the existing workflow. If the workflow renders only one example, also add the new example to the render matrix/step.)

- [ ] **Step 3: Docs**

- `README.md`: in the ideas section, explain the mold and «Probar ganchos»; add `./tpi ganchos guiones/x.yaml` to the command table.
- `docs/GUIA_GUIONES.md`: add optional fields:
```markdown
## moldes y ganchos alternativos (opcional)

`molde:` elige una estructura probada: `mito_realidad`, `tres_errores`, `pov`, `reto` o
`nadie_te_enseno`. `gancho_variantes:` guarda los ganchos que no se usaron, para probarlos con
`./tpi ganchos guion.yaml`. Sin estos campos el guion funciona igual que antes.
```
- `docs/PLAN.md`: mark **v0.9 · Ganchos y moldes** as done and move v1.0 to next.
- `pyproject.toml`: `version = "0.9.0"`.
- `src/tpi_videos/__init__.py`: `__version__ = "0.9.0"`.

- [ ] **Step 4: Verify the example loads**

Run: `PYTHONPATH=src python -c "from tpi_videos.guion import cargar_guion, problemas_de_molde; g = cargar_guion('guiones/ejemplos/moldes_virales.yaml'); print(g.molde, len(g.gancho_variantes), problemas_de_molde(g))"`
Expected: `mito_realidad 3 []`

- [ ] **Step 5: Commit**

```bash
git add guiones/ejemplos/moldes_virales.yaml .github/workflows/render.yml README.md docs/GUIA_GUIONES.md docs/PLAN.md pyproject.toml src/tpi_videos/__init__.py
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "docs: ejemplo y versión 0.9.0"
```

---

### Task 12: Verificación final

**Files:** none (solo comprobaciones).

- [ ] **Step 1: Run all pure tests**

```bash
python -m unittest discover -s pruebas -t . -v
```
Expected: all PASS.

- [ ] **Step 2: Compile every module**

```bash
python -m compileall -q src
```
Expected: no output.

- [ ] **Step 3: Import every module that does not need Manim/NiceGUI**

```bash
PYTHONPATH=src python -c "
import tpi_videos.moldes, tpi_videos.guion, tpi_videos.ideas, tpi_videos.redactor
import tpi_videos.lote, tpi_videos.ganchos, tpi_videos.revision, tpi_videos.cli
print('imports ok')
"
```
Expected: `imports ok`.

- [ ] **Step 4: Check `a_yaml` compatibility**

```bash
PYTHONPATH=src python -c "
from tpi_videos.guion import cargar_guion
for ruta in ['guiones/ejemplos/fisica_caida_libre.yaml', 'guiones/ejemplos/moldes_virales.yaml']:
    g = cargar_guion(ruta)
    print(ruta, g.molde, len(g.gancho_variantes))
"
```
Expected: old example loads with `None 0`; new one with `mito_realidad 3`.

- [ ] **Step 5: Declare what was not verified**

In the final report and PR: no Manim/NiceGUI/LaTeX on Windows, so no real render, no panel browser test, no voice; the style regression and CI render must be confirmed on the Mac. Include exact commands for the user.

- [ ] **Step 6: Final commit (if any fix was needed)**

```bash
git add -A
git -c user.name="Matias" -c user.email="paillamil.m@gmail.com" commit -m "test: verificación de la fase 0.9"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| 1 · catálogo de moldes | 1 |
| 2.1 `GanchoIdea` | 3 |
| 2.2 `Idea` ampliada y dos entradas | 3, 6 |
| 2.3 `Guion`, `problemas_de_molde`, `a_yaml` | 2 |
| 3.1 `ideas.md` | 4 |
| 3.2 `sistema.md` | 4 |
| 3.3 `redactar()` | 5 |
| 3.4 `producir()` y lote | 3, 6 |
| 4.1 guion de vista previa | 8 |
| 4.2 escena, render, clips, colisiones | 7, 8 |
| 4.3 `tpi ganchos` y `--elegir` | 8, 9 |
| 5.1 Crear → Ideas | 10 |
| 5.2 Fábrica | 10 |
| 5.3 Terminal | 9 |
| 6 compatibilidad | 2, 7, 12 |
| 7 riesgos | 1–12 |
| 8 pruebas | 1–12 |
| 9 documentación y versión | 11 |
| 10 fuera de alcance | — (no se implementa) |

**Placeholder scan:** no TBD/TODO; all code steps contain code; test steps name the command and expected result.

**Type consistency:** `GanchoIdea` fields are `texto, estilo, emoji, tex, voz` in Task 3, 5, 7, 8, 10. `guion_variantes` is `list[Gancho]` in Task 2 and serialized as dicts with `texto/voz/tex/emoji/destacar` in Tasks 5 and 8. `crear_clip_gancho` takes a `Guion` in Tasks 7 and 8. `renderizar_ganchos` returns `{titulo, molde, huella, clips}` in Tasks 8 and 9; the panel reads `tarea.resultado["clips"]` in Task 10, which `Tarea._aplicar` stores from the `resultado` event.

## Execution Handoff

El usuario ya pidió «sigue con la implementación»; se ejecuta **inline** con `superpowers:executing-plans`, verificando después de cada tarea. El commit queda en `feat/ganchos-y-moldes`; **no se hace push ni PR** hasta que el usuario lo pida.
