import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual
from tpi_videos.redactor import PasoIA, _visual


class RedactorPoligonoTest(unittest.TestCase):
    """Que la IA pueda pedir la figura con campos planos y el motor la entienda."""

    def _paso(self, **cambios):
        datos = {
            "nota": "Miro la figura",
            "tex": r"a = \frac{P}{n}",
            "voz": "Mira la figura y su medida.",
            "dibujo": "poligono",
            "lados": 5,
            "lado": "12 cm",
            **cambios,
        }
        return PasoIA(**datos)

    def test_la_ia_pide_un_poligono_y_el_motor_lo_entiende(self):
        visual = Visual(**_visual(self._paso(anotar=["apotema"])))
        self.assertEqual(visual.tipo, "poligono_regular")
        self.assertEqual(visual.lados, 5)
        self.assertAlmostEqual(visual.poligono().apotema, 8.26, places=2)

    def test_sin_medida_el_error_vuelve_a_la_ia_en_espanol(self):
        with self.assertRaises(ValidationError) as error:
            Visual(**_visual(self._paso(lado="")))
        self.assertIn("lado", str(error.exception))

    def test_el_poligono_no_se_lleva_los_campos_del_grafico(self):
        visual = _visual(self._paso(funcion="-x^2 + 4x", fuente="12 V"))
        self.assertNotIn("funcion", visual)
        self.assertNotIn("fuente", visual)


if __name__ == "__main__":
    unittest.main()
