# Auditoría de prioridades (puntos 2, 5, 6, 7 y 8) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar lo que quedó abierto de la tabla de 8 prioridades del dueño. Son cinco frentes: la etiqueta del enunciado que se pierde al guardar (resto del punto 2), una sola regla de voz y de tiempos (punto 5), los estilos agrupados en el catálogo (punto 6), la limpieza de `_promovidos` (punto 7) y la poda de `_vistas` y de los trozos de Manim (punto 8). Nada se reconstruye y los videos de los ejemplos siguen idénticos.

**Architecture:** Hay cambios chicos y aislados, cada uno con su prueba `unittest`. Las reglas puras salen a funciones sin Manim (`voz_elegida.py`, `acomodo.py`, `revision.tiempo_de_escritura`) y la escena solo las aplica. Los grupos de estilos son una tabla de presentación en `temas.py`: no deciden ningún estilo. La poda amplía `mantenimiento.podar_temporales`, que ya tiene modo de prueba y confirmación.

**Tech Stack:** Python 3.12 (también corre en ≥3.11), Manim CE + manim-voiceover, Pydantic v2, PyYAML, NiceGUI, Rich. Pruebas con `unittest` (**NO** pytest).

**Spec:** `docs/superpowers/specs/2026-11-11-auditoria-prioridades-design.md` (léelo antes de empezar).

## Global Constraints

- **Dónde se trabaja:** en el Mac del dueño, en `~/Downloads/tuprofeindustrial-videos`, con su `.venv` (`./scripts/instalar_mac.sh` ya lo deja listo). En un sandbox sin PyPI **no** se pueden correr las pruebas: no declarar nada como listo sin correrlas.
- **Runner:** `.venv/bin/python -m unittest discover -s pruebas -t . -v`. Una sola: `.venv/bin/python -m unittest pruebas.test_<nombre> -v`. NO usar pytest.
- **TDD estricto:** escribir la prueba, verla FALLAR por la razón esperada, implementar lo mínimo y verla pasar.
- **Rama:** `fix/auditoria-prioridades` creada desde `main` actualizado. Nunca hacer push a `main`. Al final, abrir una PR a `main`.
- **Commits:** uno por tarea, con el formato de la historia (`fix: …`, `feat: …`, `docs: …`, en español y en minúscula).
- **Reglas del repo** (`.kiro/steering/reglas-del-repo.md`), las que más pesan aquí:
  - No crear ni modificar YAML de `plantillas/temas/`.
  - No tocar `sugerir_tema` ni `resolver_tema`.
  - No agregar selectores de estilo: el estilo se elige solo en la ficha de QC.
  - Todo campo nuevo es opcional.
  - Los textos al usuario van en español de Chile, claros.
  - No tocar `mis_ajustes/`.
  - Nunca subir videos ni audios.
- **No romper el estilo original:** con `--tema pizarra_nocturna --voz silencio --borrador` y `PYTHONHASHSEED=0`, los ejemplos de `guiones/ejemplos/` deben salir idénticos cuadro a cuadro a los de `main` (Task 0 guarda la referencia y Task 9 compara).
- **No usar la palabra «familia»** para los grupos de estilos: ya significa formatos (`formatos.py`) y tipografías (`tipografia.py`).
- **Nunca borrar algo que no se pueda regenerar.** En `salida/` se conservan siempre `<video>.mp4`, `<video>_borrador.mp4`, `.srt`, `.ass`, `linea_de_tiempo.json`, `publicacion.json`, `miniatura.jpg`, `portada.png` y `manim/videos/*/animacion.mp4`.

## File Structure

- Modify `src/tpi_videos/guion.py`: `a_yaml` → `bloque()` escribe `etiqueta` (Task 1).
- Create `src/tpi_videos/voz_elegida.py`: `VozElegida` y `elegir_voz` (Task 2).
- Modify `src/tpi_videos/render.py`: `crear_video` y `crear_clip_gancho` usan `elegir_voz`; el clip pasa `tono` (Task 2).
- Modify `src/tpi_videos/ganchos.py`: `guion_de_vista_previa` deja de copiar `voz or texto` (Task 2).
- Modify `src/tpi_videos/revision.py`: `tiempo_de_escritura` (Task 3).
- Create `src/tpi_videos/acomodo.py`: `SEPARACION_PILA` y `lineas_que_salen` (Task 4).
- Modify `src/tpi_videos/escena.py`: usa `tiempo_de_escritura` (Task 3) y `lineas_que_salen` (Task 4).
- Modify `src/tpi_videos/temas.py`: `GRUPOS_DE_ESTILO`, `GRUPO_PROPIOS`, `grupo_de_estilo`, `catalogo_agrupado` (Task 5).
- Modify `src/tpi_videos/cli.py` (`cmd_temas`, `cmd_podar` y su parser, docstring), `src/tpi_videos/panel/paginas/tablero.py` (`_dialogo_estilo`) y `src/tpi_videos/panel/paginas/estilos.py` (lista) (Tasks 6 y 7).
- Modify `src/tpi_videos/mantenimiento.py`: `_podar_vistas`, `_podar_trozos_manim` y quitar carpetas vacías (Task 7).
- Create pruebas: `pruebas/test_voz_elegida.py`, `pruebas/test_acomodo.py`, `pruebas/test_grupos_de_estilo.py`.
- Extend pruebas: `pruebas/test_ganchos.py`, `pruebas/test_mantenimiento.py`, `pruebas/test_render_gancho.py`, `pruebas/test_ritmo.py`.
- Docs: `README.md`, `docs/PLAN.md`, `docs/ANALISIS_TECNICO.md` (+ su HTML generado) (Task 9).

---

### Task 0: Preparación y referencia cuadro a cuadro

**Files:** ninguno (solo comandos)

- [ ] **Step 1: Rama limpia desde `main`**

```bash
cd ~/Downloads/tuprofeindustrial-videos && git checkout main && git pull origin main
git checkout -b fix/auditoria-prioridades
```

- [ ] **Step 2: Suite en verde antes de tocar nada**

Run: `.venv/bin/python -m unittest discover -s pruebas -t . -v 2>&1 | tail -5`
Expected: `OK` (o solo `skipped`). Si algo falla **antes** de cambiar código, anotarlo y avisar al dueño: no es culpa de este plan.

- [ ] **Step 3: Guardar los cuadros de referencia de `main`**

Run:
```bash
mkdir -p /tmp/ref_main
for g in guiones/ejemplos/*.yaml; do
  n=$(basename "$g" .yaml)
  PYTHONHASHSEED=0 ./tpi crear "$g" --tema pizarra_nocturna --voz silencio --borrador --salida /tmp/ref_main/$n
done
```
Expected: un `*_borrador.mp4` por ejemplo dentro de `/tmp/ref_main/<n>/`. Si `./tpi crear` no acepta `--salida`, revisar `./tpi crear --help` y usar la opción equivalente. No cambiar la CLI para esto.

---

### Task 1: La etiqueta del enunciado se conserva al guardar (resto del punto 2)

**Files:**
- Modify: `src/tpi_videos/guion.py` (función interna `bloque` dentro de `a_yaml`, ~línea 1720)
- Test: `pruebas/test_ganchos.py` (clase `GuardadoGuionTest`)

- [ ] **Step 1: Write the failing test** (agregarlo dentro de `GuardadoGuionTest`)

```python
    def test_el_yaml_conserva_la_etiqueta_del_enunciado(self):
        for etiqueta in ("LA RESPUESTA", "PROBLEMA"):
            with self.subTest(etiqueta=etiqueta):
                datos = guion_datos()
                datos["enunciado"]["etiqueta"] = etiqueta
                original = Guion.model_validate(datos)
                texto = a_yaml(original.model_dump())
                reabierto = Guion.model_validate(yaml.safe_load(texto))
                self.assertEqual(reabierto.enunciado.etiqueta, etiqueta)
                # la de fábrica no se escribe: el YAML queda igual que antes para los guiones de siempre
                self.assertEqual("etiqueta:" in texto, etiqueta != "PROBLEMA")

    def test_elegir_gancho_no_cambia_la_etiqueta(self):
        datos = guion_datos()
        datos["enunciado"]["etiqueta"] = "LA RESPUESTA"
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "guion.yaml"
            ruta.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
            elegir_gancho(ruta, 2)
            reabierto = Guion.model_validate(yaml.safe_load(ruta.read_text(encoding="utf-8")))
            self.assertEqual(reabierto.enunciado.etiqueta, "LA RESPUESTA")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_ganchos -v`
Expected: FAIL en el subtest `LA RESPUESTA`, con `'PROBLEMA' != 'LA RESPUESTA'`.

- [ ] **Step 3: Write minimal implementation** (en `bloque`, justo después de la línea que escribe `texto`)

```python
    def bloque(nombre: str, b: dict[str, Any]) -> None:
        lineas.extend(["", f"{nombre}:", f"  texto: {_dobles(b['texto'])}"])
        if b.get("etiqueta") not in (None, "", "PROBLEMA"):  # solo el enunciado la tiene
            lineas.append(f"  etiqueta: {_dobles(b['etiqueta'])}")
        if b.get("voz"):
            ...  # (el resto queda igual)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest pruebas.test_ganchos -v`
Expected: PASS (todas, incluidas las de `GuardadoGuionTest` que ya existían).

- [ ] **Step 5: Comprobar con los dos guiones reales**

Run:
```bash
.venv/bin/python - <<'EOF'
import yaml
from pathlib import Path
from tpi_videos.guion import Guion, a_yaml, cabecera_de
for n in ("f_3_mas_1_no_es_10", "tu_gps_te_miente"):
    r = Path(f"guiones/{n}.yaml"); g = Guion.model_validate(yaml.safe_load(r.read_text()))
    otra = Guion.model_validate(yaml.safe_load(a_yaml(g.model_dump(), cabecera_de(r))))
    print(n, otra.enunciado.etiqueta, otra.model_dump() == g.model_dump())
EOF
```
Expected: `LA RESPUESTA True` en las dos líneas. **No** reescribir los archivos.

- [ ] **Step 6: Commit**

```bash
git add src/tpi_videos/guion.py pruebas/test_ganchos.py
git commit -m "fix: conservar la etiqueta del enunciado al guardar"
```

---

### Task 2: Una sola regla de voz para el video y el gancho (punto 5a)

**Files:**
- Create: `src/tpi_videos/voz_elegida.py`
- Modify: `src/tpi_videos/render.py` (`crear_video` ~línea 196; `crear_clip_gancho` ~líneas 355–375)
- Modify: `src/tpi_videos/ganchos.py` (`guion_de_vista_previa`, ~línea 82)
- Test: `pruebas/test_voz_elegida.py` (nuevo), `pruebas/test_render_gancho.py`

- [ ] **Step 1: Write the failing test** (`pruebas/test_voz_elegida.py`)

```python
import unittest

from tpi_videos.config import Voz
from tpi_videos.voz_elegida import elegir_voz

MARCA = Voz(proveedor="edge", nombre="es-CL-LorenzoNeural", velocidad="+5%", tono="+2Hz")


class ElegirVozTest(unittest.TestCase):
    def test_sin_nada_manda_la_marca(self):
        v = elegir_voz(MARCA)
        self.assertEqual((v.proveedor, v.voz, v.velocidad, v.tono), ("edge", "es-CL-LorenzoNeural", "+5%", "+2Hz"))

    def test_el_guion_le_gana_a_la_marca(self):
        v = elegir_voz(MARCA, guion_voz="es-CL-CatalinaNeural", guion_velocidad="+10%")
        self.assertEqual((v.voz, v.velocidad), ("es-CL-CatalinaNeural", "+10%"))

    def test_la_terminal_le_gana_a_todo(self):
        v = elegir_voz(MARCA, guion_voz="es-CL-CatalinaNeural", guion_velocidad="+10%",
                       proveedor="gtts", voz="es-MX-JorgeNeural", velocidad="+0%", tono="-3Hz")
        self.assertEqual((v.proveedor, v.voz, v.velocidad, v.tono), ("gtts", "es-MX-JorgeNeural", "+0%", "-3Hz"))

    def test_silencio_en_proveedor_o_voz_silencia_los_dos(self):
        for args in ({"proveedor": "silencio"}, {"voz": "silencio"}):
            with self.subTest(args=args):
                v = elegir_voz(MARCA, guion_voz="es-CL-CatalinaNeural", **args)
                self.assertEqual((v.proveedor, v.voz), ("silencio", "silencio"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_voz_elegida -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'tpi_videos.voz_elegida'`.

- [ ] **Step 3: Write minimal implementation** (`src/tpi_videos/voz_elegida.py`)

```python
"""Una sola regla para elegir la voz: la usan el video final y el clip del gancho.

Orden: lo que se pide en la Terminal > lo que dice el guion > lo de marca.yaml. Si el proveedor o la
voz dicen «silencio», los dos quedan en silencio (así nunca se pide la voz «silencio» a edge-tts).
El piso de lectura NO es parte de esta regla: el clip del gancho lo deja en 0 a propósito.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Voz


@dataclass(frozen=True)
class VozElegida:
    proveedor: str
    voz: str
    velocidad: str
    tono: str


def elegir_voz(
    marca: Voz,
    *,
    guion_voz: str | None = None,
    guion_velocidad: str | None = None,
    proveedor: str | None = None,
    voz: str | None = None,
    velocidad: str | None = None,
    tono: str | None = None,
) -> VozElegida:
    velocidad_final = velocidad or guion_velocidad or marca.velocidad
    tono_final = tono or marca.tono
    if proveedor == "silencio" or voz == "silencio":
        return VozElegida("silencio", "silencio", velocidad_final, tono_final)
    return VozElegida(
        proveedor or marca.proveedor, voz or guion_voz or marca.nombre, velocidad_final, tono_final
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest pruebas.test_voz_elegida -v`
Expected: PASS (4 pruebas).

- [ ] **Step 5: Write the failing test of the gancho clip** (agregar en `pruebas/test_render_gancho.py`)

```python
import tempfile
from pathlib import Path
from unittest import mock

from tpi_videos.config import Marca


class VozDelClipTest(unittest.TestCase):
    def test_el_clip_del_gancho_usa_el_tono_de_la_marca(self):
        from tpi_videos import render
        from tpi_videos.ganchos import guion_de_vista_previa, idea_desde_guion
        from tpi_videos.guion import Guion
        from pruebas.test_ganchos import guion_datos

        guion = Guion.model_validate(guion_datos())
        corto = guion_de_vista_previa(idea_desde_guion(guion), idea_desde_guion(guion).ganchos[0])
        marca = Marca.model_validate({"voz": {"tono": "+3Hz"}})
        with tempfile.TemporaryDirectory() as tmp:
            crudo = Path(tmp) / "crudo.mp4"
            crudo.write_bytes(b"x")
            with mock.patch.object(render, "cargar_marca", return_value=marca), \
                 mock.patch.object(render, "verificar_requisitos"), \
                 mock.patch.object(render, "renderizar_manim", return_value=(crudo, {})) as rm:
                render.crear_clip_gancho(corto, salida=Path(tmp) / "g" / "gancho.mp4")
        self.assertEqual(rm.call_args.kwargs.get("tono"), "+3Hz")
        self.assertEqual(rm.call_args.kwargs.get("piso"), 0.0)  # el piso del gancho sigue en 0
```

Si `Marca.model_validate({"voz": {"tono": "+3Hz"}})` exige más campos, construir la marca como lo hacen las pruebas de `pruebas/test_voz_tono.py`. Si `idea_desde_guion(...).ganchos[0]` no es la forma de obtener una variante, copiar cómo lo hace la prueba que ya existe para `guion_de_vista_previa` en `pruebas/test_ganchos.py`.

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_render_gancho -v`
Expected: FAIL con `None != '+3Hz'` (hoy el clip no pasa `tono`).

- [ ] **Step 7: Usar `elegir_voz` en los dos caminos**

En `render.py`, agregar `from .voz_elegida import elegir_voz` a los imports. Luego, en `crear_video`, reemplazar las 4 líneas `proveedor = … / voz = … / velocidad = … / tono = …` por:

```python
    elegida = elegir_voz(
        marca.voz, guion_voz=guion.voz, guion_velocidad=guion.velocidad,
        proveedor=proveedor, voz=voz, velocidad=velocidad, tono=tono,
    )  # fmt: skip
    proveedor, voz, velocidad, tono = elegida.proveedor, elegida.voz, elegida.velocidad, elegida.tono
```

En `crear_clip_gancho`, reemplazar el bloque `if proveedor == "silencio" … velocidad = velocidad or marca.voz.velocidad` por:

```python
    elegida = elegir_voz(
        marca.voz, guion_voz=guion.voz, guion_velocidad=guion.velocidad,
        proveedor=proveedor, voz=voz, velocidad=velocidad,
    )  # fmt: skip
```

y la llamada a `renderizar_manim` por:

```python
    crudo, _ = renderizar_manim(
        guion, marca, estilo, calidad, elegida.proveedor, elegida.voz, elegida.velocidad, destino.parent,
        progreso=por_bloque if progreso else None, solo_gancho=True, tono=elegida.tono,
        piso=0.0,  # el laboratorio compara ganchos seguidos: el silencio del piso ahí estorba
    )  # fmt: skip
```

En `ganchos.guion_de_vista_previa`, cambiar `"voz": variante.voz or variante.texto,` por `"voz": variante.voz or None,`. Así la escena usa `Gancho.voz_final`, la misma regla que el video final.

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest pruebas.test_render_gancho pruebas.test_voz_elegida pruebas.test_ganchos pruebas.test_voz_tono pruebas.test_cli_ganchos -v`
Expected: PASS. Si una prueba vieja comparaba `gancho.voz == texto`, cambiarla para comparar `gancho.voz_final`: es la misma regla, y hay que anotarlo en la PR.

- [ ] **Step 9: Commit**

```bash
git add src/tpi_videos/voz_elegida.py src/tpi_videos/render.py src/tpi_videos/ganchos.py pruebas/test_voz_elegida.py pruebas/test_render_gancho.py
git commit -m "fix: una sola regla de voz para el video y el gancho"
```

---

### Task 3: Un solo tiempo de escritura de la fórmula (punto 5b)

**Files:**
- Modify: `src/tpi_videos/revision.py` (junto a `FRACCION_DE_ESCRITURA`, ~línea 33; y `_quieto_estimado`, ~línea 403)
- Modify: `src/tpi_videos/escena.py` (import de la línea 79; `self.play(*aparecer, …)` ~línea 1498)
- Test: `pruebas/test_ritmo.py` (ya cubre `_quieto_estimado`/`espera_de_lectura`; agregar ahí la clase nueva)

- [ ] **Step 1: Write the failing test** (agregar en `pruebas/test_ritmo.py`; sumar `tiempo_de_escritura` al import de `tpi_videos.revision`)

```python
class TiempoDeEscrituraTest(unittest.TestCase):
    def test_es_el_45_por_ciento_entre_0_8_y_1_6(self):
        self.assertAlmostEqual(tiempo_de_escritura(1.0), 0.8)   # 0,45 → se sube al mínimo
        self.assertAlmostEqual(tiempo_de_escritura(2.0), 0.9)
        self.assertAlmostEqual(tiempo_de_escritura(10.0), 1.6)  # 4,5 → se baja al máximo

    def test_es_lo_que_estima_la_revision(self):
        from tpi_videos.revision import SALIDA_DE_LA_LINEA, _quieto_estimado
        for s in (0.5, 2.0, 3.3, 9.0):
            with self.subTest(segundos=s):
                self.assertAlmostEqual(_quieto_estimado(s), max(0.0, s - tiempo_de_escritura(s) - SALIDA_DE_LA_LINEA))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_ritmo -v`
Expected: FAIL con `ImportError: cannot import name 'tiempo_de_escritura'`.

- [ ] **Step 3: Write minimal implementation**

En `revision.py`, debajo de `SALIDA_DE_LA_LINEA`:

```python
def tiempo_de_escritura(segundos_de_voz: float) -> float:
    """Cuánto tarda la escena en escribir la fórmula de un bloque: la misma regla para escena y revisión."""
    return min(ESCRITURA_MAX, max(ESCRITURA_MIN, segundos_de_voz * FRACCION_DE_ESCRITURA))
```

En `_quieto_estimado`, cambiar la línea `escritura = min(ESCRITURA_MAX, …)` por `escritura = tiempo_de_escritura(segundos_de_voz)`.

En `escena.py`, cambiar el import de la línea 79 por `from .revision import PISO_LECTURA, espera_de_lectura, tiempo_de_escritura`, y la línea ~1498 por:

```python
                self.play(*aparecer, run_time=tiempo_de_escritura(tr.duration))
```

(`np.clip` y `min/max` dan el mismo número, así que los cuadros no cambian.) Actualizar el comentario de `revision.py` que dice «escena.py escribe la fórmula durante ~45 %…» para que diga que ambos usan `tiempo_de_escritura`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest pruebas.test_ritmo -v && .venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3`
Expected: PASS y la suite completa en `OK`.

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/revision.py src/tpi_videos/escena.py pruebas/test_ritmo.py
git commit -m "fix: un solo tiempo de escritura para escena y revisión"
```

---

### Task 4: El acomodo de la pila sale de la escena (punto 5c)

**Files:**
- Create: `src/tpi_videos/acomodo.py` (sin Manim)
- Modify: `src/tpi_videos/escena.py` (`_pasos`, bloque `while True` ~líneas 1415–1428)
- Test: `pruebas/test_acomodo.py`

- [ ] **Step 1: Write the failing test** (`pruebas/test_acomodo.py`)

```python
import unittest

from tpi_videos.acomodo import SEPARACION_PILA, lineas_que_salen


class LineasQueSalenTest(unittest.TestCase):
    def test_si_cabe_no_sale_ninguna(self):
        self.assertEqual(lineas_que_salen([0.5, 0.5], 1.0, 5.0), 0)

    def test_salen_las_mas_viejas_hasta_que_cabe(self):
        # 3 líneas de 1,0 + nueva de 1,0 + 3 separaciones de 0,34 = 5,02 > 4 → sale 1 (3,68 ≤ 4)
        self.assertEqual(lineas_que_salen([1.0, 1.0, 1.0], 1.0, 4.0), 1)

    def test_la_nueva_nunca_sale_aunque_no_quepa(self):
        self.assertEqual(lineas_que_salen([1.0, 1.0], 9.0, 4.0), 2)

    def test_sin_pila_no_sale_nada(self):
        self.assertEqual(lineas_que_salen([], 9.0, 4.0), 0)

    def test_el_borde_justo_cabe(self):
        self.assertEqual(lineas_que_salen([1.0], 1.0, 2.0 + SEPARACION_PILA), 0)

    def test_la_separacion_es_la_de_la_escena(self):
        self.assertEqual(SEPARACION_PILA, 0.34)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_acomodo -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'tpi_videos.acomodo'`.

- [ ] **Step 3: Write minimal implementation** (`src/tpi_videos/acomodo.py`)

```python
"""Dónde cabe cada línea de la pizarra, en números: sin Manim, para poder probarlo solo.

La escena mide las alturas y aplica el resultado; acá solo se decide.
"""

from __future__ import annotations

SEPARACION_PILA = 0.34  # el aire entre líneas de la columna de pasos (el `buff` del arrange)


def lineas_que_salen(
    alturas: list[float], alto_nueva: float, alto_zona: float, separacion: float = SEPARACION_PILA
) -> int:
    """Cuántas líneas viejas (desde la más antigua) salen para que la columna con la nueva quepa.

    La columna mide la suma de sus alturas más una separación entre cada par. La nueva nunca sale:
    si ni sola cabe, salen todas las viejas y la escena la achica.
    """
    salen = 0
    while salen < len(alturas):
        quedan = alturas[salen:]
        if sum(quedan) + alto_nueva + separacion * len(quedan) <= alto_zona:
            break
        salen += 1
    return salen
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest pruebas.test_acomodo -v`
Expected: PASS (6 pruebas).

- [ ] **Step 5: Usar la función en la escena**

En `escena.py`, agregar `from .acomodo import SEPARACION_PILA, lineas_que_salen` y reemplazar el bucle:

```python
                    alto_zona = tope - fondo
                    while True:
                        destinos = []
                        for linea in pila:
                            ...
                        columna = VGroup(*destinos, nueva).arrange(DOWN, buff=0.34)
                        if columna.height <= alto_zona or not pila:
                            break
                        salen.append(pila.pop(0))
```

por:

```python
                    alto_zona = tope - fondo
                    copias = []
                    for linea in pila:
                        copia = VGroup(*[m.copy() for m in linea.mobs])
                        if id(linea.eq) not in en_historial:
                            copia.scale(c.ESCALA_HISTORIAL)
                        copias.append(copia.set_fill(opacity=0.35))
                    n_salen = lineas_que_salen([x.height for x in copias], nueva.height, alto_zona)
                    for _ in range(n_salen):
                        salen.append(pila.pop(0))
                    destinos = copias[n_salen:]
                    columna = VGroup(*destinos, nueva).arrange(DOWN, buff=SEPARACION_PILA)
```

Las líneas siguientes (`if columna.height > alto_zona: …` y `columna.move_to(…)`) quedan igual. `destinos[pos]` sigue alineado con `pila` porque las dos pierden las mismas primeras `n_salen`.

- [ ] **Step 6: Run tests + render de control**

Run: `.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3`
Expected: `OK`.
Luego renderizar **un** ejemplo con muchos pasos y compararlo con su referencia de Task 0 (el método de comparación está en Task 9, Step 2). Debe dar idéntico. Si no da idéntico, revertir este paso y avisar: la altura de `arrange` difiere de la suma y hay que medir `columna.height` directamente.

- [ ] **Step 7: Commit**

```bash
git add src/tpi_videos/acomodo.py src/tpi_videos/escena.py pruebas/test_acomodo.py
git commit -m "refactor: sacar de la escena el acomodo de la pila de pasos"
```

---

### Task 5: Grupos de estilos en `temas.py` (punto 6, datos)

**Files:**
- Modify: `src/tpi_videos/temas.py` (después de `TEMA_DE_ERROR`, ~línea 76; y después de `listar_temas`, ~línea 340)
- Test: `pruebas/test_grupos_de_estilo.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from tpi_videos import temas
from tpi_videos.temas import GRUPO_PROPIOS, GRUPOS_DE_ESTILO, catalogo_agrupado, grupo_de_estilo


class GruposDeEstiloTest(unittest.TestCase):
    def test_cada_estilo_incluido_esta_en_un_solo_grupo(self):
        incluidos = {r.stem for r in temas.TEMAS_DIR.glob("*.yaml")}
        agrupados = [c for claves in GRUPOS_DE_ESTILO.values() for c in claves]
        self.assertEqual(len(agrupados), len(set(agrupados)), "un estilo repetido en dos grupos")
        self.assertEqual(set(agrupados), incluidos)

    def test_consola_neon_se_mantiene(self):
        self.assertEqual(grupo_de_estilo("consola_neon"), "Neón")

    def test_los_propios_van_a_su_grupo(self):
        self.assertEqual(grupo_de_estilo("mi_tema", propio=True), GRUPO_PROPIOS)
        self.assertEqual(grupo_de_estilo("desconocido"), GRUPO_PROPIOS)

    def test_el_catalogo_agrupado_tiene_los_mismos_estilos_que_la_lista(self):
        planos = [c for _, items in catalogo_agrupado() for c, _, _ in items]
        self.assertEqual(sorted(planos), sorted(c for c, _, _ in temas.listar_temas()))
        nombres = [g for g, _ in catalogo_agrupado()]
        self.assertEqual(nombres[: len(GRUPOS_DE_ESTILO)], list(GRUPOS_DE_ESTILO)[: len(nombres)])

    def test_no_usa_la_palabra_familia(self):
        self.assertFalse(any("familia" in g.lower() for g in GRUPOS_DE_ESTILO))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest pruebas.test_grupos_de_estilo -v`
Expected: FAIL con `ImportError: cannot import name 'GRUPO_PROPIOS'`.

- [ ] **Step 3: Write minimal implementation** (en `temas.py`)

```python
# Cómo se MUESTRA el catálogo (QC, página Estilos y ./tpi temas). No elige ningún estilo: eso es
# sugerir_tema. Son 20 estilos sobre dos marcos (pizarra y hoja); los grupos juntan las variantes.
GRUPOS_DE_ESTILO: dict[str, tuple[str, ...]] = {
    "Hoja y cuaderno": ("hoja_de_desarrollo", "cuaderno_con_sello", "cuaderno_tinta_roja", "rotulador", "rotulador_fucsia"),
    "Pizarra y tiza": ("pizarra_nocturna", "tiza_verde", "tiza_azul"),
    "Neón": ("neon_cian", "neon_reja", "neon_uva", "consola_neon"),
    "Planos técnicos": ("plano_azul", "plano_noche"),
    "Cómic y viñeta": ("comic_azul", "comic_semitono", "vineta_cine", "vineta_dorada"),
    "Kraft": ("kraft_claro", "kraft_tiza"),
}
GRUPO_PROPIOS = "Tus estilos"
_GRUPO_DE = {clave: grupo for grupo, claves in GRUPOS_DE_ESTILO.items() for clave in claves}


def grupo_de_estilo(clave: str, propio: bool = False) -> str:
    """El grupo con que se muestra un estilo; los tuyos (y los que no están en la tabla) van aparte."""
    return GRUPO_PROPIOS if propio else _GRUPO_DE.get(clave, GRUPO_PROPIOS)
```

y, debajo de `listar_temas`:

```python
def catalogo_agrupado() -> list[tuple[str, list[tuple[str, Tema, bool]]]]:
    """Los mismos estilos de listar_temas(), en el orden de GRUPOS_DE_ESTILO y con los tuyos al final."""
    por_grupo: dict[str, list[tuple[str, Tema, bool]]] = {g: [] for g in [*GRUPOS_DE_ESTILO, GRUPO_PROPIOS]}
    for item in listar_temas():
        por_grupo[grupo_de_estilo(item[0], item[2])].append(item)
    orden = {c: i for claves in GRUPOS_DE_ESTILO.values() for i, c in enumerate(claves)}
    return [
        (g, sorted(items, key=lambda it: orden.get(it[0], 99)))
        for g, items in por_grupo.items()
        if items
    ]
```

**Antes del commit**, mostrarle la tabla al dueño (por ejemplo con la vista previa de los estilos de cada grupo). `vineta_cine` se llama «Pizarra de cine»: confirmar con él si va en «Cómic y viñeta» o en «Pizarra y tiza». Si mueve algo, se cambia solo esta tabla.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest pruebas.test_grupos_de_estilo pruebas.test_estilo_sugerido pruebas.test_tema_por_categoria pruebas.test_escena_gramatica -v`
Expected: PASS. Las pruebas de sugerencia no cambian, porque `sugerir_tema` no se tocó.

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/temas.py pruebas/test_grupos_de_estilo.py
git commit -m "feat: agrupar los estilos del catálogo por parecido"
```

---

### Task 6: Mostrar los grupos en QC, Estilos y `./tpi temas` (punto 6, vistas)

**Files:**
- Modify: `src/tpi_videos/panel/paginas/tablero.py` (`_dialogo_estilo`, ~líneas 853–910)
- Modify: `src/tpi_videos/panel/paginas/estilos.py` (bucle `for identificador, tema, propio in listar_temas():`, ~línea 190)
- Modify: `src/tpi_videos/cli.py` (`cmd_temas`, ~líneas 1164–1186)

No se agrega ningún selector: solo cambia el orden y aparecen títulos de grupo.

- [ ] **Step 1: `./tpi temas` con columna de grupo**

En `cmd_temas`, importar `catalogo_agrupado`, agregar la columna `"Grupo"` como primera de la `Table` y recorrer así:

```python
    for grupo, items in catalogo_agrupado():
        for identificador, tema, propio in items:
            marca = " ⭐" if identificador == actual else ""
            origen = " (tuyo)" if propio else ""
            estilo = "bold green" if identificador == actual else ""
            tabla.add_row(grupo, f"{identificador}{marca}", f"{tema.nombre}{origen}", tema.descripcion, style=estilo)
        tabla.add_section()
```

Run: `./tpi temas`
Expected: 6 grupos separados por líneas, con los 20 estilos. El ⭐ queda en `hoja_de_desarrollo` (o en el de `marca.yaml`).

- [ ] **Step 2: Diálogo de estilo de QC**

En `_dialogo_estilo`, mantener **arriba y solo** la ficha sugerida (la regla «sugerido primero» no cambia). Debajo, un título por grupo con su grilla. Mover el cuerpo actual de cada ficha a una función local `ficha(clave)` y luego:

```python
            def grilla(claves: list[str]) -> None:
                with (
                    ui.element("div").classes("w-full grid gap-3")
                    .style("grid-template-columns: repeat(auto-fill, minmax(250px, 1fr))")
                ):
                    for clave in claves:
                        if clave in temas:
                            ficha(clave)

            grilla([sugerido])
            for grupo, items in catalogo_agrupado():
                claves = [c for c, _, _ in items if c != sugerido]
                if claves:
                    ui.label(grupo).classes("tpi-sobrio text-xs uppercase tracking-wide pt-2")
                    grilla(claves)
```

`elegir(clave)` → `qc.cambiar_estilo(...)` queda igual.

- [ ] **Step 3: Página Estilos**

Cambiar `for identificador, tema, propio in listar_temas():` por:

```python
        for grupo, items in catalogo_agrupado():
            ui.label(grupo).classes("tpi-titulo text-base pt-4")
            for identificador, tema, propio in items:
                ...  # el cuerpo de la tarjeta queda igual
```

- [ ] **Step 4: Verificar con el panel**

Run: `./tpi panel`. En el navegador, abrir una ficha de QC → «Estilo» y la página Estilos. Tomar captura de las dos (la regla del repo pide Playwright y capturas; si no hay Playwright, sirven capturas a mano). Revisar que el sugerido sigue arriba, que elegir un estilo sigue escribiendo `tema:` en el guion y que no se repite ninguna ficha.
Run: `.venv/bin/python -m unittest discover -s pruebas -t . 2>&1 | tail -3` → `OK`.

- [ ] **Step 5: Commit**

```bash
git add src/tpi_videos/cli.py src/tpi_videos/panel/paginas/tablero.py src/tpi_videos/panel/paginas/estilos.py
git commit -m "feat: mostrar los estilos agrupados en QC, Estilos y tpi temas"
```

---

### Task 7: `./tpi podar` también limpia `_vistas` y los trozos de Manim (punto 8)

**Files:**
- Modify: `src/tpi_videos/mantenimiento.py`
- Modify: `src/tpi_videos/cli.py` (`cmd_podar` ~línea 1245; parser `podar` ~línea 1653; docstring ~línea 20)
- Test: `pruebas/test_mantenimiento.py` (nueva clase `PodaDeVistasYTrozosTest`)

- [ ] **Step 1: Write the failing tests** (al final de `pruebas/test_mantenimiento.py`, antes de `if __name__`)

```python
class PodaDeVistasYTrozosTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.vista = self.raiz / "salida" / "_vistas" / "neon_cian"
        (self.vista / "vista_previa" / "manim").mkdir(parents=True)
        self.guardados = [self.vista / n for n in ("1_gancho.png", "2_paso.png", "3_resultado.png", "huella.txt")]
        self.borrador = self.vista / "vista_previa" / "vista_previa_borrador.mp4"
        self.trozo = self.vista / "vista_previa" / "manim" / "a.mp4"
        for r in (*self.guardados, self.borrador, self.trozo):
            r.write_bytes(b"x")
            _viejo(r)
        video = self.raiz / "salida" / "mi_video"
        self.trozos = video / "manim" / "videos" / "1920p30" / "partial_movie_files" / "VideoEjercicio"
        self.trozos.mkdir(parents=True)
        self.parcial = self.trozos / "001.mp4"
        self.animacion = video / "manim" / "videos" / "1920p30" / "animacion.mp4"
        self.finales = [video / n for n in ("mi_video.mp4", "mi_video_borrador.mp4", "mi_video.srt",
                                            "subtitulos.ass", "linea_de_tiempo.json", "miniatura.jpg")]
        for r in (self.parcial, self.animacion, *self.finales):
            r.write_bytes(b"x")
            _viejo(r)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_borra_el_video_de_la_vista_y_conserva_sus_cuadros(self) -> None:
        poda = podar_temporales(raiz=self.raiz)
        self.assertIn(self.borrador, poda.archivos)
        self.assertIn(self.trozo, poda.archivos)
        self.assertFalse((self.vista / "vista_previa").exists(), "la carpeta vacía también se va")
        for r in self.guardados:
            self.assertTrue(r.exists(), r.name)

    def test_borra_los_trozos_de_manim_y_nunca_los_videos(self) -> None:
        podar_temporales(raiz=self.raiz)
        self.assertFalse(self.parcial.exists())
        self.assertTrue(self.animacion.exists(), "animacion.mp4 es el intermedio de la miniatura")
        for r in self.finales:
            self.assertTrue(r.exists(), r.name)

    def test_lo_reciente_no_se_toca(self) -> None:
        _nuevo(self.borrador)
        _nuevo(self.parcial)
        poda = podar_temporales(raiz=self.raiz)
        self.assertNotIn(self.borrador, poda.archivos)
        self.assertNotIn(self.trozo, poda.archivos, "si algo de la carpeta es nuevo, la carpeta se queda")
        self.assertTrue(self.parcial.exists())

    def test_en_prueba_no_borra_nada(self) -> None:
        poda = podar_temporales(raiz=self.raiz, aplicar=False)
        self.assertIn(self.borrador, poda.archivos)
        self.assertTrue(self.borrador.exists())

    def test_no_sigue_enlaces(self) -> None:
        afuera = self.raiz / "afuera"
        afuera.mkdir()
        (afuera / "importante.mp4").write_bytes(b"x")
        _viejo(afuera / "importante.mp4")
        (self.vista / "enlace").symlink_to(afuera, target_is_directory=True)
        podar_temporales(raiz=self.raiz)
        self.assertTrue((afuera / "importante.mp4").exists())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m unittest pruebas.test_mantenimiento -v`
Expected: las nuevas FALLAN (`borrador not found in []`, `parcial` sigue existiendo) y las viejas PASAN.

- [ ] **Step 3: Write minimal implementation** (en `mantenimiento.py`)

```python
def _archivos_de(carpeta: Path) -> list[Path]:
    """Todos los archivos de una carpeta, sin entrar por enlaces simbólicos."""
    salida: list[Path] = []
    for ruta in carpeta.iterdir():
        if ruta.is_symlink():
            continue
        if ruta.is_dir():
            salida += _archivos_de(ruta)
        elif ruta.is_file():
            salida.append(ruta)
    return salida


def _carpeta_vieja(carpeta: Path, limite: float) -> list[Path]:
    """Los archivos de la carpeta si TODOS son viejos; si uno es reciente, la carpeta se queda entera."""
    if not carpeta.is_dir() or carpeta.is_symlink():
        return []
    archivos = _archivos_de(carpeta)
    if not archivos or any(r.stat().st_mtime >= limite for r in archivos):
        return []
    return archivos


def _podar_vistas(carpeta: Path, limite: float) -> list[Path]:
    """En cada `_vistas/<estilo>/` se va el video borrador (sus subcarpetas); quedan los 3 PNG y huella.txt."""
    if not carpeta.is_dir():
        return []
    candidatos: list[Path] = []
    for estilo in sorted(carpeta.iterdir()):
        if estilo.is_symlink() or not estilo.is_dir():
            continue
        for sub in sorted(estilo.iterdir()):
            if sub.is_dir() and not sub.is_symlink():
                candidatos += _carpeta_vieja(sub, limite)
    return candidatos


def _podar_trozos_manim(raiz: Path, limite: float) -> list[Path]:
    """Los trozos que Manim ya unió en animacion.mp4; animacion.mp4 se queda (es el intermedio)."""
    candidatos: list[Path] = []
    for carpeta in sorted(raiz.glob("salida/*/manim/videos/*/partial_movie_files")):
        candidatos += _carpeta_vieja(carpeta, limite)
    return candidatos


def _quitar_vacias(carpetas: set[Path], tope: Path) -> None:
    """Sube desde cada carpeta borrando las que quedaron vacías, sin pasar de `tope`."""
    for carpeta in sorted(carpetas, key=lambda c: len(c.parts), reverse=True):
        actual = carpeta
        while actual != tope and tope in actual.parents:
            try:
                actual.rmdir()  # solo funciona si está vacía
            except OSError:
                break
            actual = actual.parent
```

En `podar_temporales`, después de `candidatos += _podar_voz(base, limite)`:

```python
    candidatos += _podar_vistas(base / "salida" / "_vistas", limite)
    candidatos += _podar_trozos_manim(base, limite)
```

y, antes del `return Poda(archivos=borrados, bytes=liberados)` final:

```python
    _quitar_vacias({r.parent for r in borrados}, base / "salida")
```

Actualizar el docstring del módulo y el de `podar_temporales` para nombrar también `_vistas` y los trozos de Manim, y para listar lo que nunca se toca.

**Ojo:** la carpeta `_vistas/<estilo>/` queda (tiene los PNG), pero `_quitar_vacias` nunca borra `salida/` ni nada que no esté vacío.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest pruebas.test_mantenimiento -v`
Expected: PASS (las viejas y las 5 nuevas).

- [ ] **Step 5: Textos de la CLI**

En `cli.py`:
- **Docstring (~línea 20):** `./tpi podar                          borra cachés viejas (dibujos 3D, voces, vistas previas y trozos de Manim)`.
- **`help` del parser `podar`:** el mismo texto entre paréntesis.
- **`cmd_podar`:** reemplazar `"   Son dibujos 3D y audios de voz que se pueden volver a generar."` por:

```python
    consola.print("   Son dibujos 3D, audios de voz, videos de las vistas previas y trozos de Manim:")
    consola.print("   todo se vuelve a generar solo. Tus videos, subtítulos y miniaturas no se tocan.")
```

- [ ] **Step 6: Probar en el Mac, sin borrar**

Run: `./tpi podar` y responder **N** (enter).
Expected: un número de archivos y MB. Contra la tabla del dueño, debería acercarse a la mayor parte de 1,1 GB de `_vistas` más los trozos. Anotar la cifra para `docs/ANALISIS_TECNICO.md`. **Solo si el dueño lo autoriza**, correr `./tpi podar --si` y verificar en el panel:
- que **Videos** sigue mostrando todos los videos con su miniatura;
- que **Estilos** sigue mostrando las vistas previas sin volver a calcularlas.

- [ ] **Step 7: Commit**

```bash
git add src/tpi_videos/mantenimiento.py src/tpi_videos/cli.py pruebas/test_mantenimiento.py
git commit -m "feat: podar también vistas previas y trozos de manim"
```

---

### Task 8: `_promovidos` (punto 7) — paso manual, sin código

**Files:** ninguno. **No escribir código ni borrar nada por tu cuenta.**

En el repo no hay ningún código que cree o lea `_promovidos`: ni `listar_temas` (no es recursivo) ni la biblioteca (salta carpetas que empiezan con `_`) lo cargan. La carpeta está solo en el Mac del dueño.

- [ ] **Step 1: Ubicarla y confirmar que son copias idénticas** (darle al dueño este bloque para copiar y pegar)

```bash
cd ~/Downloads/tuprofeindustrial-videos
find . -path ./.git -prune -o -type d -name '_promovidos' -print
# por cada carpeta encontrada (reemplaza RUTA):
find RUTA -type f -exec shasum {} + | sort | awk '{print $1}' | uniq -c | sort -rn | head
du -sh RUTA
```

Expected: la ruta (probablemente dentro de `mis_ajustes/`) y cuántas copias tiene cada huella. Si son «8 copias idénticas», se ve un mismo hash repetido.

- [ ] **Step 2: Que el dueño la mande a la Papelera desde Finder**

```bash
open -R "RUTA"
```

El dueño la arrastra a la Papelera, así se puede recuperar. No usar `rm`. Después correr `./tpi temas` y confirmar que siguen saliendo los mismos estilos.

- [ ] **Step 3: Anotar en la PR** la ruta, el tamaño y que se borró a mano (o que el dueño prefirió dejarla).

---

### Task 9: Verificación final, documentación y PR

**Files:**
- Modify: `README.md` (sección de `./tpi podar` y `./tpi temas`), `docs/PLAN.md` (línea ~50 de la poda; mención de los grupos), `docs/ANALISIS_TECNICO.md` (cifras medidas en Task 7, Step 6)
- Generate: `docs/ANALISIS_TECNICO.html`

- [ ] **Step 1: Suite completa**

Run: `.venv/bin/python -m unittest discover -s pruebas -t . -v 2>&1 | tail -5`
Expected: `OK`. Anotar el número de pruebas, que debe ser mayor que el de Task 0.

- [ ] **Step 2: Cuadro a cuadro contra `main`**

```bash
mkdir -p /tmp/rama
for g in guiones/ejemplos/*.yaml; do
  n=$(basename "$g" .yaml)
  PYTHONHASHSEED=0 ./tpi crear "$g" --tema pizarra_nocturna --voz silencio --borrador --salida /tmp/rama/$n
  a=$(ls /tmp/ref_main/$n/*/*_borrador.mp4 2>/dev/null || ls /tmp/ref_main/$n/*_borrador.mp4)
  b=$(ls /tmp/rama/$n/*/*_borrador.mp4 2>/dev/null || ls /tmp/rama/$n/*_borrador.mp4)
  ffmpeg -loglevel error -i "$a" -i "$b" -lavfi "[0:v][1:v]psnr" -f null - 2>&1 | tail -1
done
```

Expected: `average:inf` (idénticos) en todos. Si alguno no es `inf`, extraer cuadros con `ffmpeg -ss <t> -i … -frames:v 1` y **mirarlos a tamaño completo**. No declarar listo si hay diferencias. Este paso no cubre el cambio de voz de Task 2, porque se compara con `--voz silencio`.

- [ ] **Step 3: El clip del gancho con voz**

Run: `./tpi ganchos guiones/<uno_con_variantes>.yaml` (ver `./tpi ganchos --help`) y escuchar un clip: debe sonar con el mismo tono que el video final. Anotarlo en la PR.

- [ ] **Step 4: Docs**

- **`README.md`:** qué borra ahora `./tpi podar` y qué nunca toca, y que `./tpi temas` muestra grupos.
- **`docs/PLAN.md`:** la poda ampliada y los grupos de estilos (solo presentación).
- **`docs/ANALISIS_TECNICO.md`:** los MB medidos en Task 7, Step 6 (cifras medidas, no estimadas).

Run: `python3 scripts/doc_a_html.py docs/ANALISIS_TECNICO.md docs/ANALISIS_TECNICO.html`

- [ ] **Step 5: Commit, push y PR**

```bash
git add README.md docs/PLAN.md docs/ANALISIS_TECNICO.md docs/ANALISIS_TECNICO.html
git commit -m "docs: poda ampliada, grupos de estilos y regla de voz"
git push -u origin fix/auditoria-prioridades
```

PR a `main` con:
- **Qué cambió**, por punto (2, 5a, 5b, 5c, 6, 7, 8).
- **Cambios de comportamiento intencionales:** el clip del gancho usa el tono de la marca; `--voz silencio` silencia también el proveedor; `./tpi podar` borra más cosas.
- **Lo que quedó sin probar en un Mac**, si algo.
- **Para probar en el Mac:**
  `cd ~/Downloads/tuprofeindustrial-videos && git checkout main && git pull origin main`
  luego `./tpi temas`, `./tpi podar` (responder N) y `./tpi panel` → QC → Estilo.
