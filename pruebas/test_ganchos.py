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

    def test_el_visual_del_gancho_llega_al_clip(self):
        datos = guion_datos()
        datos["gancho"]["visual"] = {"tipo": "vector_3d", "componentes": [3, 4, 12], "unidad": "cm"}
        idea = idea_desde_guion(Guion.model_validate(datos))

        self.assertEqual(idea.ganchos[0].visual.tipo, "vector_3d")
        g = guion_de_vista_previa(idea, idea.ganchos[0])
        self.assertIsNotNone(g.gancho.visual)
        self.assertEqual(g.gancho.visual.tipo, "vector_3d")
        self.assertEqual(list(g.gancho.visual.componentes), [3, 4, 12])

    def test_cada_variante_conserva_su_propio_visual(self):
        datos = guion_datos()
        datos["gancho_variantes"][0]["visual"] = {
            "tipo": "circuito",
            "fuente": "9 V",
            "resistencias": ["4 Ω", "6 Ω"],
        }
        idea = idea_desde_guion(Guion.model_validate(datos))

        self.assertIsNone(idea.ganchos[0].visual)
        self.assertEqual(idea.ganchos[1].visual.tipo, "circuito")
        g = guion_de_vista_previa(idea, idea.ganchos[1])
        self.assertEqual(g.gancho.visual.tipo, "circuito")

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
