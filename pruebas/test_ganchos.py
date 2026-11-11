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


class GuardadoGuionTest(unittest.TestCase):
    def test_el_yaml_conserva_la_camara_elegida(self):
        for camara in ("quieta", "fuerte", "suave"):
            with self.subTest(camara=camara):
                datos = guion_datos()
                datos["camara"] = camara
                original = Guion.model_validate(datos)
                reabierto = Guion.model_validate(yaml.safe_load(a_yaml(original.model_dump())))
                self.assertEqual(reabierto.camara, camara)

    def test_el_yaml_conserva_los_mapas_con_y_sin_color(self):
        for color in (None, "#22AA66"):
            with self.subTest(color=color):
                datos = guion_datos()
                mapa = [
                    {"termino": "c", "concepto": 'Hipotenusa "c"', "color": color},
                    {"termino": r"\sqrt{3^2 + 4^2}", "concepto": "Raíz de '3 y 4'"},
                ]
                datos["pasos"][1]["mapa"] = mapa
                original = Guion.model_validate(datos)
                reabierto = Guion.model_validate(yaml.safe_load(a_yaml(original.model_dump())))
                self.assertEqual(reabierto.pasos[1].mapa, original.pasos[1].mapa)
                self.assertEqual(reabierto.pasos[0].mapa, [])

    def test_el_yaml_conserva_conceptos_con_saltos_y_controles(self):
        conceptos = (
            "Hipotenusa\ndel triángulo",
            "Hipotenusa\rdel triángulo",
            "Hipotenusa\x00c",
            "Hipotenusa\x85del triángulo",
            "Hipotenusa\u2028del triángulo",
            ('Hipotenusa "c" del triángulo ' * 20) + "\nArista",
        )
        for concepto in conceptos:
            with self.subTest(concepto=concepto):
                datos = guion_datos()
                datos["pasos"][1]["mapa"] = [{"termino": "c", "concepto": concepto}]
                original = Guion.model_validate(datos)
                try:
                    reabierto = Guion.model_validate(yaml.safe_load(a_yaml(original.model_dump())))
                except yaml.YAMLError as error:
                    self.fail(f"El escritor generó YAML ilegible: {error}")
                self.assertEqual(reabierto.pasos[1].mapa[0].concepto, concepto)

    def test_el_yaml_conserva_terminos_multilinea(self):
        for salto in ("\n", "\r", "\x85", "\u2028"):
            with self.subTest(salto=salto):
                termino = "\\sqrt{3^2 +" + salto + "4^2}"
                datos = guion_datos()
                datos["pasos"][1]["mapa"] = [{"termino": termino, "concepto": "Hipotenusa"}]
                original = Guion.model_validate(datos)
                reabierto = Guion.model_validate(yaml.safe_load(a_yaml(original.model_dump())))
                self.assertEqual(reabierto.pasos[1].mapa[0].termino, termino)

    def test_el_yaml_conserva_el_dibujo_de_cada_variante(self):
        datos = guion_datos()
        datos["gancho_variantes"][0]["visual"] = {
            "tipo": "circuito", "fuente": "9 V", "resistencias": ["4 Ω", "6 Ω"]
        }
        datos["gancho_variantes"][1]["visual"] = {
            "tipo": "vector_3d", "componentes": [3, 4, 12], "unidad": "cm"
        }
        original = Guion.model_validate(datos)
        reabierto = Guion.model_validate(yaml.safe_load(a_yaml(original.model_dump())))
        self.assertEqual(reabierto.gancho_variantes, original.gancho_variantes)
        self.assertIsNone(reabierto.gancho.visual)


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

    def test_elegir_gancho_conserva_las_decisiones_del_guion(self):
        datos = guion_datos()
        datos["camara"] = "quieta"
        datos["pasos"][1]["mapa"] = [
            {"termino": "c", "concepto": "Hipotenusa", "color": "#22AA66"}
        ]
        datos["gancho"]["visual"] = {
            "tipo": "vector_3d", "componentes": [3, 4, 12], "unidad": "cm"
        }
        datos["gancho_variantes"][0]["visual"] = {
            "tipo": "circuito", "fuente": "9 V", "resistencias": ["4 Ω", "6 Ω"]
        }
        original = Guion.model_validate(datos)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "guion.yaml"
            ruta.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
            for _ in range(2):
                elegir_gancho(ruta, 2)
                reabierto = Guion.model_validate(yaml.safe_load(ruta.read_text(encoding="utf-8")))
                esperado = original.model_copy(update={
                    "gancho": original.gancho_variantes[0],
                    "gancho_variantes": [original.gancho, original.gancho_variantes[1]],
                })
                self.assertEqual(reabierto.model_dump(), esperado.model_dump())
                original = esperado


if __name__ == "__main__":
    unittest.main()
