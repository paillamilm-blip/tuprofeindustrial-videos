"""El generador pide volumen: un sólido geométrico sale como cuerpo 3D, no como línea plana.

La IA puede pedir «solido» (el contorno plano de siempre) o «solido3d»; el motor promociona el
primero al segundo para que toda figura geométrica tenga relieve, luz y caras, no solo alambre.
"""

import unittest

from tpi_videos.redactor import PasoIA, _visual


def _paso(**campos):
    return PasoIA(nota="N", tex="x = 1", voz="Una voz.", **campos)


class VolumenPorDefectoTest(unittest.TestCase):
    def test_un_solido_pedido_como_plano_se_promueve_a_cuerpo_3d(self):
        visual = _visual(_paso(dibujo="solido", figura="cilindro", radio="3 cm", altura="5 cm"))
        self.assertEqual(visual["tipo"], "solido_3d")

    def test_el_solido_3d_explicito_sigue_siendo_3d(self):
        visual = _visual(_paso(dibujo="solido3d", figura="cubo", lado="4 cm"))
        self.assertEqual(visual["tipo"], "solido_3d")

    def test_la_promocion_conserva_la_figura_y_sus_medidas(self):
        visual = _visual(_paso(dibujo="solido", figura="cono", radio="2 cm", altura="6 cm"))
        self.assertEqual(visual["figura"], "cono")
        self.assertEqual(visual["radio"], "2 cm")
        self.assertEqual(visual["altura"], "6 cm")


if __name__ == "__main__":
    unittest.main()