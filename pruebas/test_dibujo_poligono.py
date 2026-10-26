import unittest

from tpi_videos.temas import ColoresTema

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    import numpy as np
    from manim import Text

    from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual, poligono_regular
    from tpi_videos.guion import Visual
    from tpi_videos.visuales import analizar_poligono

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoPoligonoTest(unittest.TestCase):
    """La figura que se ve en el pie de la pizarra: contorno, medida y lo que el guion pida anotar."""

    def _dibujar(self, lados=5, lado="12 cm", anotar=(), ancho=ANCHO_HOJA, alto=ALTO_DIBUJO):
        return poligono_regular(analizar_poligono(lados, lado), list(anotar), ColoresTema(), ancho, alto)

    def _textos(self, dib) -> list[str]:
        return [m.original_text for m in dib.mobs.get_family() if isinstance(m, Text)]

    def _esquinas(self, m) -> int:
        return len({tuple(np.round(p, 5)) for p in m.get_anchors()})

    # ----------------------------------------------------------------------------------

    def test_entra_en_la_franja_del_pie(self):
        for lados in (3, 4, 5, 6, 8):
            dib = self._dibujar(lados, anotar=["apotema", "radio", "angulo_central"])
            self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6, f"con {lados} lados se sale de ancho")
            self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6, f"con {lados} lados se sale de alto")

    def test_el_primer_trazo_es_la_figura_cerrada(self):
        dib = self._dibujar(5)
        contorno = dib.trazo[0]
        self.assertEqual(self._esquinas(contorno), 5)
        self.assertTrue(contorno.is_closed(), "la figura va cerrada de una sola vez")

    def test_sin_anotar_nada_solo_se_traza_el_contorno(self):
        self.assertEqual(len(self._dibujar(6, anotar=[]).trazo), 1)

    def test_siempre_queda_escrita_la_medida_del_lado(self):
        self.assertIn("12 cm", self._textos(self._dibujar(5)))

    def test_anotar_la_apotema_escribe_su_numero_con_coma_chilena(self):
        textos = " | ".join(self._textos(self._dibujar(5, anotar=["apotema"])))
        self.assertIn("a ≈ 8,26 cm", textos)

    def test_la_linea_de_la_apotema_mide_lo_que_dice_la_matematica(self):
        """De centro al punto medio de la base, ni un dedo más largo: se comprueba contra el radio."""
        dib = self._dibujar(5, anotar=["apotema"])
        figura = analizar_poligono(5, "12 cm")
        anch = np.array(dib.trazo[0].get_anchors())
        centro = anch.mean(axis=0)
        escala = np.linalg.norm(anch[0] - centro) / figura.radio
        auxiliar = dib.trazo[1]
        largo = np.linalg.norm(auxiliar.get_end() - auxiliar.get_start()) / escala
        self.assertAlmostEqual(largo, figura.apotema, places=2)
        # y de verdad va del centro de la figura al medio de la base
        self.assertAlmostEqual(float(np.linalg.norm(auxiliar.get_start() - centro)), 0.0, places=5)

    def test_la_apotema_deja_escrita_la_escuadra_en_su_pie(self):
        """Sin la escuadra, la raya a plomo parece un alto cualquiera y no una apotema."""
        dib = self._dibujar(3, anotar=["apotema"])
        con_escuadra = len(dib.trazo)
        self.assertEqual(con_escuadra, 3, "contorno + apotema + escuadra")
        escuadra = dib.trazo[-1]
        self.assertFalse(escuadra.is_closed(), "la escuadra son dos rayitas, no un cuadrito relleno")
        anch = np.array(escuadra.get_anchors())
        base = float(np.array(dib.trazo[0].get_anchors())[:, 1].min())
        self.assertAlmostEqual(anch[:, 0].max() - anch[:, 0].min(), anch[:, 1].max() - anch[:, 1].min())
        self.assertAlmostEqual(float(anch[:, 0].min()), 0.0, places=5, msg="arranca en la apotema")
        self.assertAlmostEqual(float(anch[:, 1].min()), base, places=5, msg="apoyada sobre el lado")
        self.assertEqual(len(self._dibujar(3, anotar=["radio"]).trazo), 2, "sin apotema no hay escuadra")

    def test_el_centro_queda_marcado_cuando_el_radio_y_la_apotema_se_pisan(self):
        """En un triángulo el radio a la punta y la apotema caen en la misma raya: el punto hace el corte."""
        con_medidas = self._dibujar(3, anotar=["apotema", "radio"])
        solo_lado = self._dibujar(3, anotar=[])
        self.assertEqual(len(con_medidas.aparece) - len(solo_lado.aparece), 3, "centro + 2 rótulos")
        distancias = [
            float(np.linalg.norm(np.array(d.get_anchors()).mean(axis=0))) for d in con_medidas.aparece[:4]
        ]
        self.assertLess(min(distancias), 1e-6, "ningún punto cae encima del centro de la figura")
        self.assertEqual(len(solo_lado.aparece), 4, "los tres vértices y la medida del lado")

    def test_anotar_el_angulo_interior_lo_escribe_en_grados(self):
        self.assertIn("108°", " | ".join(self._textos(self._dibujar(5, anotar=["angulo_interior"]))))

    def test_anotar_el_angulo_central_lo_escribe_en_grados(self):
        self.assertIn("72°", " | ".join(self._textos(self._dibujar(5, anotar=["angulo_central"]))))

    def test_dibujar_visual_reconoce_el_poligono_del_guion(self):
        visual = Visual(tipo="poligono_regular", lados=6, lado="4 cm", anotar=["apotema"])
        dib = dibujar_visual(visual, ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO, "#FFFFFF")
        self.assertEqual(self._esquinas(dib.trazo[0]), 6)
        self.assertIn("4 cm", self._textos(dib))


if __name__ == "__main__":
    unittest.main()
