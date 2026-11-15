"""Capas por rol: el texto y las fórmulas siempre por encima de las cajas que los contienen.

En las capturas del estanque y la cañería los chips («área basal», «radio interior») quedaban
tapados por el borde de la tarjeta del dibujo: texto y caja empataban en z_index=0 y decidía el
orden de agregado. Acá se exige el desempate por rol: CAPA_TEXTO sobre CAPA_CAJA.
"""

import unittest

from tpi_videos import componentes as c


class CapasPorRolTest(unittest.TestCase):
    def test_el_texto_nace_por_encima_de_las_cajas(self):
        self.assertEqual(c.texto("hola", 30).z_index, c.CAPA_TEXTO)
        self.assertGreater(c.CAPA_TEXTO, c.CAPA_CAJA)

    def test_el_parrafo_y_la_ecuacion_tambien(self):
        self.assertEqual(c.parrafo("una linea", 30).z_index, c.CAPA_TEXTO)
        self.assertEqual(c.ecuacion(r"V = \pi R^2 H", 30).z_index, c.CAPA_TEXTO)

    def test_el_rotulo_del_chip_gana_a_su_propia_caja(self):
        chip = c.chip("área basal", "#F2A93B")
        caja, etiqueta = chip[0], chip[1]
        self.assertEqual(etiqueta.z_index, c.CAPA_TEXTO)
        self.assertLess(caja.z_index, etiqueta.z_index)

    def test_la_tarjeta_deja_su_contenido_arriba_y_su_caja_abajo(self):
        contenido = c.texto("dato", 30)
        tarjeta = c.tarjeta(contenido, 6.0, "#101820", "#2A3644")
        self.assertEqual(tarjeta[1].z_index, c.CAPA_TEXTO)
        self.assertLessEqual(tarjeta[0].z_index, c.CAPA_CAJA)


class ZonaSeguraTest(unittest.TestCase):
    """El contenido se agrupa y escala en el centro de la banda usable: nunca la invade."""

    def _bulto(self, alto, ancho):
        from manim import Rectangle, VGroup

        return VGroup(Rectangle(width=ancho, height=alto), c.texto("rótulo", 30))

    def test_un_dibujo_demasiado_alto_se_achica_y_centra_en_la_banda(self):
        mob = self._bulto(alto=10, ancho=6)
        c.ajustar_a_zona(mob, alto=4, ancho=7, centro_y=1.0)
        self.assertLessEqual(mob.height, 4 + 1e-6)
        self.assertLessEqual(mob.width, 7 + 1e-6)
        self.assertAlmostEqual(mob.get_center()[1], 1.0, places=6)
        self.assertGreaterEqual(mob.get_bottom()[1], 1.0 - 2 - 1e-6)
        self.assertLessEqual(mob.get_top()[1], 1.0 + 2 + 1e-6)

    def test_un_dibujo_que_ya_cabe_no_se_agranda(self):
        mob = self._bulto(alto=2, ancho=3)
        c.ajustar_a_zona(mob, alto=4, ancho=7, centro_y=0.5)
        self.assertAlmostEqual(mob.height, 2, places=6)
        self.assertAlmostEqual(mob.get_center()[1], 0.5, places=6)

    def test_lo_ancho_tambien_se_recorta(self):
        mob = self._bulto(alto=2, ancho=12)
        c.ajustar_a_zona(mob, alto=4, ancho=7, centro_y=0.0)
        self.assertLessEqual(mob.width, 7 + 1e-6)


class AnclaDeLaIntroTest(unittest.TestCase):
    """El enunciado se ancla en el objeto del ejercicio: su primer dibujo, o el de la promesa."""

    def _paso(self, visual):
        from types import SimpleNamespace

        return SimpleNamespace(visual=visual)

    def test_toma_el_primer_dibujo_del_desarrollo(self):
        from tpi_videos.escena import ancla_del_enunciado

        objeto, otro = object(), object()
        pasos = [self._paso(None), self._paso(objeto), self._paso(otro)]
        gancho = self._paso("promesa")
        self.assertIs(ancla_del_enunciado(pasos, gancho), objeto)

    def test_sin_dibujo_en_pasos_cae_al_de_la_promesa(self):
        from tpi_videos.escena import ancla_del_enunciado

        gancho = self._paso("promesa")
        self.assertEqual(ancla_del_enunciado([self._paso(None)], gancho), "promesa")

    def test_sin_ningun_dibujo_no_inventa_un_ancla(self):
        from tpi_videos.escena import ancla_del_enunciado

        self.assertIsNone(ancla_del_enunciado([self._paso(None)], self._paso(None)))


class RepartoDeLaIntroTest(unittest.TestCase):
    """Con ancla, el texto va arriba y el dibujo abajo, los dos dentro de la zona segura."""

    SUP, INF, AIRE = 4.75, -2.4, 0.28

    def _reparto(self, con_ancla):
        return c.reparto_de_intro(
            y_superior=self.SUP, y_inferior=self.INF, con_ancla=con_ancla, aire=self.AIRE
        )

    def test_el_ancla_se_apoya_en_el_filo_de_abajo_de_la_zona(self):
        _, ancla = self._reparto(True)
        centro, alto = ancla
        self.assertAlmostEqual(centro - alto / 2, self.INF, places=6)
        self.assertGreater(alto, 0)

    def test_el_texto_queda_arriba_del_ancla_con_aire(self):
        texto, ancla = self._reparto(True)
        centro_t, alto_t = texto
        centro_a, alto_a = ancla
        self.assertLessEqual(centro_t + alto_t / 2, self.SUP + 1e-6)
        self.assertGreaterEqual(centro_t - alto_t / 2, centro_a + alto_a / 2 + self.AIRE - 1e-6)

    def test_sin_ancla_el_texto_usa_toda_la_zona(self):
        texto, ancla = self._reparto(False)
        centro, alto = texto
        self.assertIsNone(ancla)
        self.assertAlmostEqual(centro, (self.SUP + self.INF) / 2, places=6)
        self.assertAlmostEqual(alto, self.SUP - self.INF, places=6)


if __name__ == "__main__":
    unittest.main()