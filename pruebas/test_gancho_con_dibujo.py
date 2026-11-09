"""El gancho con su propio dibujo: la flecha en pantalla mientras se dice la promesa.

Lo pidió después de ver el video del vector: catorce segundos hablando de «este vector» sin mostrar
ningún vector. El dibujo ya vive en los pasos; acá se le abre la misma puerta al gancho.
"""

import unittest

import yaml

from tpi_videos.guion import Guion, a_yaml
from tpi_videos.revision import revisar
from tpi_videos.visuales import SEGUNDOS_VISUAL

DIBUJO = {"tipo": "vector_3d", "componentes": [3, 4, 12], "unidad": "cm", "anotar": ["ejes"]}


def base(**extra):
    datos = {
        "titulo": "El vector en el espacio",
        "materia": "matematica",
        "nivel": "3° medio",
        "gancho": {
            "texto": "3 + 4 + 12 = 19: ese no es el largo del vector",
            "voz": "Tres más cuatro más doce son diecinueve.",
        },
        "enunciado": {
            "texto": "Un vector avanza 3 cm, 4 cm y 12 cm. ¿Cuánto mide de punta a punta?",
            "voz": "Avanza tres, cuatro y doce.",
        },
        "pasos": [{"voz": "Cada número va por su eje.", "tex": r"\vec v = (3,\ 4,\ 12)", "nota": "Ejes"}],
        "resultado": {"tex": "v = 13", "voz": "Trece."},
    }
    datos.update(extra)
    return datos


def con_dibujo() -> dict:
    datos = base()
    datos["gancho"]["visual"] = dict(DIBUJO)
    return datos


class GanchoConDibujoTest(unittest.TestCase):
    def test_el_gancho_acepta_su_dibujo(self):
        guion = Guion.model_validate(con_dibujo())
        self.assertEqual(guion.gancho.visual.tipo, "vector_3d")
        self.assertEqual(list(guion.gancho.visual.componentes), [3, 4, 12])

    def test_sin_pedirlo_el_gancho_sigue_sin_dibujo(self):
        self.assertIsNone(Guion.model_validate(base()).gancho.visual)

    def test_el_dibujo_del_gancho_cuenta_en_la_promesa_de_duracion(self):
        """Un dibujo se mira un rato: si no entra en la promesa, el video se pasa de largo."""
        sin = revisar(Guion.model_validate(base()), "Sígueme.").segundos
        con = revisar(Guion.model_validate(con_dibujo()), "Sígueme.").segundos
        self.assertAlmostEqual(con - sin, SEGUNDOS_VISUAL["vector_3d"], places=4)

    def test_el_yaml_escrito_conserva_el_dibujo_del_gancho(self):
        """El redactor y el lote reescriben el yaml: si pierden el visual, el video sale distinto."""
        reescrito = yaml.safe_load(a_yaml(con_dibujo()))
        self.assertEqual(reescrito["gancho"]["visual"], DIBUJO)


if __name__ == "__main__":
    unittest.main()
