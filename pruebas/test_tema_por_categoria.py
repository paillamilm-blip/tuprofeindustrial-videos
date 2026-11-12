"""La categoría sale de la materia; el estilo ya no: lo decide la forma del contenido (temas.py)."""

import unittest
from types import SimpleNamespace

import yaml
from pydantic import ValidationError

from tpi_videos.guion import Guion, a_yaml
from tpi_videos.temas import TEMA_DE_PASOS, resolver_tema


def _guion(materia: str = "fisica", **extra) -> Guion:
    return Guion.model_validate(
        {
            "titulo": "T",
            "materia": materia,
            "gancho": {"texto": "¿Sí?"},
            "enunciado": {"texto": "E"},
            "pasos": [{"voz": "Una voz.", "tex": "x = 1"}],
            "resultado": {"tex": "x = 1", "voz": "Listo."},
            **extra,
        }
    )


class MapaTest(unittest.TestCase):
    def test_la_categoria_sale_de_la_materia(self):
        self.assertEqual(_guion("matematica").categoria, "matematicas")
        self.assertEqual(_guion("Matemáticas").categoria, "matematicas")
        self.assertEqual(_guion("fisica").categoria, "fisica")
        self.assertEqual(_guion("ingenieria").categoria, "ingenieria")

    def test_categoria_escrita_en_el_yaml_es_opcional_y_debe_calzar(self):
        self.assertEqual(_guion("ingenieria", categoria="ingenieria").categoria, "ingenieria")
        self.assertEqual(_guion("matematica", categoria="Matemáticas").categoria, "matematicas")
        with self.assertRaisesRegex(ValidationError, "no calza"):
            _guion("fisica", categoria="ingenieria")
        with self.assertRaisesRegex(ValidationError, "no existe"):
            _guion("fisica", categoria="quimica")
        # no queda guardada aparte: cambiar la materia cambia la categoría (editor, model_copy)
        self.assertNotIn("categoria", _guion("fisica", categoria="fisica").model_dump())

    def test_a_yaml_escribe_la_categoria_y_se_vuelve_a_leer(self):
        g = _guion("ingenieria")
        texto = a_yaml(g.model_dump(exclude_none=True))
        self.assertEqual(yaml.safe_load(texto)["categoria"], "ingenieria")
        self.assertEqual(Guion.model_validate(yaml.safe_load(texto)).categoria, "ingenieria")


class CascadaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.marca = SimpleNamespace(tema="consola_pasos")

    def test_1_lo_elegido_a_mano_manda(self):
        self.assertEqual(resolver_tema("kraft_claro", _guion("fisica"), self.marca), "kraft_claro")
        g = _guion("fisica", tema="comic_azul")
        self.assertEqual(resolver_tema(None, g, self.marca), "comic_azul")
        self.assertEqual(resolver_tema("kraft_claro", g, self.marca), "kraft_claro")

    def test_2_sin_eleccion_la_materia_no_cambia_el_estilo(self):
        for materia in ("matematica", "fisica", "ingenieria"):
            self.assertEqual(resolver_tema(None, _guion(materia), self.marca), TEMA_DE_PASOS, materia)
        self.assertEqual(resolver_tema("", _guion("fisica"), self.marca), TEMA_DE_PASOS)

    def test_3_sin_guion_queda_el_de_la_marca(self):
        self.assertEqual(resolver_tema(None, None, SimpleNamespace(tema="kraft_claro")), "kraft_claro")
        self.assertEqual(resolver_tema(None, None, self.marca), "consola_pasos")


if __name__ == "__main__":
    unittest.main()
