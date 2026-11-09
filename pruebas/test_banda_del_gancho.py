"""La banda del dibujo: hasta el filo real del subtítulo y sin tope de catálogo.

Medido cuadro a cuadro (el-vector-en-el-espacio, 2026-11-02): el subtítulo quemado vive anclado
al 78% del alto y su peor techo (dos líneas) queda a 0,25 del cuadro por debajo de ese ancla. La
reserva vieja (0,34) le regalaba al vacío más de una unidad por dibujo. Y el tope ALTO_DIBUJO
recortaba la banda aunque hubiera hueco: el dibujo entraba chico en un cuadro lleno de aire.
"""

import unittest

from tpi_videos.dibujos import ALTO_DIBUJO
from tpi_videos.escena import (
    AIRE_DIBUJO,
    BANDA_SUBTITULO,
    Paisaje,
    escala_base,
    franja_del_dibujo,
)

ALTO_CUADRO = 14.222
HOJA = Paisaje(5.8, 0.1, 7.0, 3.95)
FONDO_HOJA = -3.55  # el fondo del papel de verdad, no la reserva de la zona
TOPE_PASOS = 3.95
PISO_DEL_GANCHO = 1.9  # dónde termina la pregunta de cuatro líneas, clavada arriba
ESCALA = escala_base("suave")


def filo_del_subtitulo(paisaje=HOJA, escala=ESCALA):
    return paisaje.centro_y - (0.5 - BANDA_SUBTITULO) * ALTO_CUADRO * escala


class BandaDelDibujoTest(unittest.TestCase):
    def test_la_reserva_mide_lo_que_ocupa_el_subtitulo(self):
        """0,34 era un susto: el subtítulo real (peor caso, dos líneas) no pasa de 0,26."""
        self.assertAlmostEqual(BANDA_SUBTITULO, 0.28, places=6)

    def test_el_dibujo_baja_hasta_el_filo_del_subtitulo(self):
        """Con el fondo real del papel, el piso lo marca el subtítulo, no la reserva de la zona."""
        _, centro, alto = franja_del_dibujo(
            HOJA, ALTO_CUADRO, ESCALA, FONDO_HOJA, TOPE_PASOS, borde_papel=FONDO_HOJA
        )
        filo = filo_del_subtitulo()
        self.assertAlmostEqual(centro - alto / 2, filo, places=6)

    def test_sin_tope_de_catalogo_la_banda_se_la_come_entera(self):
        """Gancho con techo propio: si sobra hueco entre la pregunta y el subtítulo, es del dibujo."""
        _, _, alto = franja_del_dibujo(
            HOJA, ALTO_CUADRO, ESCALA, FONDO_HOJA, PISO_DEL_GANCHO,
            techo=PISO_DEL_GANCHO, borde_papel=FONDO_HOJA,
        )
        self.assertGreater(alto, ALTO_DIBUJO)
        self.assertAlmostEqual(alto, PISO_DEL_GANCHO - AIRE_DIBUJO - filo_del_subtitulo(), places=6)

    def test_el_borde_del_papel_frena_el_piso_cuando_es_alto(self):
        """Pizarra corta: si el papel termina arriba, el dibujo no se cuelga fuera de él."""
        papel_chico = -1.0
        _, centro, alto = franja_del_dibujo(
            HOJA, ALTO_CUADRO, ESCALA, FONDO_HOJA, TOPE_PASOS, borde_papel=papel_chico
        )
        self.assertAlmostEqual(centro - alto / 2, papel_chico, places=6)

    def test_sin_borde_papel_manda_la_reserva_de_siempre(self):
        """La firma vieja no cambia de comportamiento: el que no pase borde sigue donde estaba."""
        _, centro, alto = franja_del_dibujo(HOJA, ALTO_CUADRO, ESCALA, FONDO_HOJA, TOPE_PASOS)
        piso_esperado = max(FONDO_HOJA, filo_del_subtitulo())
        self.assertAlmostEqual(centro - alto / 2, piso_esperado, places=6)

    def test_el_dibujo_cuelga_del_techo_no_flota_en_la_banda(self):
        """Con techo puesto, el techo de la banda es la pregunta menos el aire de siempre."""
        _, centro, alto = franja_del_dibujo(
            HOJA, ALTO_CUADRO, ESCALA, FONDO_HOJA, PISO_DEL_GANCHO,
            techo=PISO_DEL_GANCHO, borde_papel=FONDO_HOJA,
        )
        self.assertAlmostEqual(centro + alto / 2, PISO_DEL_GANCHO - AIRE_DIBUJO, places=6)


class LaBandaNoSeDaVueltaTest(unittest.TestCase):
    def test_si_el_techo_queda_bajo_el_piso_el_alto_es_cero(self):
        """Una pregunta larguísima con dibujo puede invertir la banda: el alto no puede ser negativo
        (la escena se salta el dibujo), porque una escala negativa deforma la imagen."""
        from types import SimpleNamespace

        from tpi_videos.escena import VideoEjercicio

        trampa = object.__new__(VideoEjercicio)
        trampa.paisaje = HOJA
        trampa.alto_cuadro = ALTO_CUADRO
        trampa.modo_camara = "suave"
        paso = SimpleNamespace(visual=object())
        _, _, invertida = trampa._franja_del_dibujo(paso, -3.0, techo=-3.0)
        self.assertEqual(invertida, 0.0)
        _, _, normal = trampa._franja_del_dibujo(paso, PISO_DEL_GANCHO, techo=PISO_DEL_GANCHO)
        self.assertGreater(normal, 0.0)


if __name__ == "__main__":
    unittest.main()
