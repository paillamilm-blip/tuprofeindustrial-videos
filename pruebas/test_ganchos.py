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
