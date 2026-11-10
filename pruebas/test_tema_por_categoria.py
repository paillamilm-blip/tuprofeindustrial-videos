"""El estilo de un video sale de su categoría cuando nadie eligió uno, y solo con estilos que existen."""

import unittest
from types import SimpleNamespace

from tpi_videos.config import cargar_marca
from tpi_videos.entorno import PLANTILLAS_DIR
from tpi_videos.guion import Guion
from tpi_videos.temas import TEMA_POR_CATEGORIA, cargar_tema, resolver_tema


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
    def test_el_mapa_es_el_pedido_y_usa_estilos_que_ya_existen(self):
        self.assertEqual(
            TEMA_POR_CATEGORIA,
            {"matematicas": "pizarra_nocturna", "fisica": "neon_cian", "ingenieria": "plano_noche"},
        )
        marca = cargar_marca()
        for tema in TEMA_POR_CATEGORIA.values():
            self.assertTrue((PLANTILLAS_DIR / "temas" / f"{tema}.yaml").is_file(), tema)
            cargar_tema(tema, marca)  # y se lee sin error

    def test_la_categoria_sale_de_la_materia(self):
        self.assertEqual(_guion("matematica").categoria, "matematicas")
        self.assertEqual(_guion("Matemáticas").categoria, "matematicas")
        self.assertEqual(_guion("fisica").categoria, "fisica")
        self.assertEqual(_guion("ingenieria").categoria, "ingenieria")


class CascadaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.marca = SimpleNamespace(tema="hoja_de_desarrollo")

    def test_1_lo_elegido_a_mano_manda(self):
        self.assertEqual(resolver_tema("kraft_claro", _guion("fisica"), self.marca), "kraft_claro")
        g = _guion("fisica", tema="comic_azul")
        self.assertEqual(resolver_tema(None, g, self.marca), "comic_azul")
        self.assertEqual(resolver_tema("kraft_claro", g, self.marca), "kraft_claro")

    def test_2_sin_eleccion_va_el_de_la_categoria(self):
        self.assertEqual(resolver_tema(None, _guion("matematica"), self.marca), "pizarra_nocturna")
        self.assertEqual(resolver_tema("", _guion("fisica"), self.marca), "neon_cian")
        self.assertEqual(resolver_tema(None, _guion("ingenieria"), self.marca), "plano_noche")

    def test_3_sin_guion_queda_el_de_la_marca(self):
        self.assertEqual(resolver_tema(None, None, self.marca), "hoja_de_desarrollo")
        self.assertEqual(
            resolver_tema(None, SimpleNamespace(tema=None, categoria="otra"), self.marca),
            "hoja_de_desarrollo",
        )


if __name__ == "__main__":
    unittest.main()
