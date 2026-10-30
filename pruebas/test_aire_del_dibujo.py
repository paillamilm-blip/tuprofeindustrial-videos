"""El aire del dibujo: que el subtítulo quemado no le pase por encima en el plano de reposo.

Todo es geometría, medida con el cuadro vertical del motor (14,222 x 8) y los dos marcos: la hoja
cuadriculada —más alta que el cuadro, así que la cámara no tiene a dónde bajar— y la pizarra.
"""

import unittest

from tpi_videos.dibujos import ALTO_DIBUJO
from tpi_videos.escena import AIRE_DIBUJO, BANDA_SUBTITULO, Paisaje, escala_base, franja_del_dibujo

ALTO_CUADRO, ANCHO_CUADRO = 14.222, 8.0
HOJA = Paisaje(5.8, 0.1, 7.0, 3.95)
PIZARRA = Paisaje(7.9, 0.0, 7.6, 4.5)
FONDO_HOJA, FONDO_PIZARRA = -3.55, -2.4  # el filo de abajo de cada marco
TOPE = 3.95  # de ahí para abajo baja la pizarra de pasos
ESCALA = escala_base("suave")


def en_pantalla(y: float, centro: float, escala: float) -> float:
    """Dónde cae esa altura de la pizarra en el cuadro: 0 arriba, 1 abajo."""
    return 0.5 + (centro - y) / (ALTO_CUADRO * escala)


class FranjaDelDibujoTest(unittest.TestCase):
    def dibujo(self, paisaje, fondo_papel):
        """El bulto del dibujo en el plano de reposo: centro, alto y dónde está la cámara."""
        _, centro, alto = franja_del_dibujo(paisaje, ALTO_CUADRO, ESCALA, fondo_papel, TOPE)
        return centro, alto, paisaje.centro_y

    def test_en_la_hoja_el_borde_del_dibujo_no_le_baja_al_subtitulo(self):
        """A 24,0 s del video de la apotema la palabra amarilla cruzaba sus dos últimas aristas."""
        centro, alto, camara = self.dibujo(HOJA, FONDO_HOJA)
        self.assertLessEqual(
            en_pantalla(centro - alto / 2, camara, ESCALA), 1.0 - BANDA_SUBTITULO + 1e-6
        )

    def test_achicar_el_dibujo_no_le_sube_el_techo_a_los_pasos(self):
        """La reserva de la cadena es la de siempre: el aire se lo quita el dibujo, no la letra."""
        fondo, centro, alto = franja_del_dibujo(HOJA, ALTO_CUADRO, ESCALA, FONDO_HOJA, TOPE)
        self.assertAlmostEqual(fondo, FONDO_HOJA + ALTO_DIBUJO + AIRE_DIBUJO, places=6)
        self.assertLess(alto, ALTO_DIBUJO)
        self.assertLessEqual(centro + alto / 2, fondo - AIRE_DIBUJO + 1e-6)

    def test_en_la_pizarra_tambien_clara_y_apenas_un_poco_mas_chica(self):
        centro, alto, camara = self.dibujo(PIZARRA, FONDO_PIZARRA)
        self.assertLessEqual(
            en_pantalla(centro - alto / 2, camara, ESCALA), 1.0 - BANDA_SUBTITULO + 1e-6
        )
        self.assertGreater(alto, ALTO_DIBUJO - 0.3)

    def test_un_papel_que_no_toca_la_banda_no_se_levanta_por_esta_regla(self):
        """Sin aprieto, el dibujo se queda apoyado en el filo de abajo del papel, con su alto entero."""
        papel_bajo = Paisaje(7.9, -1.0, 7.6, 4.5)
        _, centro, alto = franja_del_dibujo(papel_bajo, ALTO_CUADRO, ESCALA, FONDO_PIZARRA, TOPE)
        self.assertAlmostEqual(alto, ALTO_DIBUJO, places=6)
        self.assertAlmostEqual(centro, FONDO_PIZARRA + ALTO_DIBUJO / 2, places=6)

    def test_si_la_pizarra_de_pasos_baja_el_dibujo_se_corre_antes_de_encimarla(self):
        _, centro, alto = franja_del_dibujo(HOJA, ALTO_CUADRO, ESCALA, FONDO_HOJA, -0.5)
        self.assertLessEqual(centro + alto / 2, -0.5 - AIRE_DIBUJO + 1e-6)


if __name__ == "__main__":
    unittest.main()
