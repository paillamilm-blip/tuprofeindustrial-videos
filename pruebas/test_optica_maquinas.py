"""Óptica y máquinas simples: refracción, péndulo, resorte y polea."""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import (
    analizar_optica,
    analizar_pendulo,
    analizar_polea,
    analizar_resorte,
)

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import Text

    from tpi_videos.dibujos import ALTO_DIBUJO, optica, pendulo, polea, resorte

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)


class OpticaTest(unittest.TestCase):
    def test_el_raye_se_refracta_hacia_la_normal(self):
        figura = analizar_optica(1.0, 1.33, 30)
        self.assertAlmostEqual(figura.refraccion, 22.08, places=1)

    def test_de_vidrio_al_aire_a_60_no_sale_raye(self):
        figura = analizar_optica(1.5, 1.0, 60)
        self.assertIsNone(figura.refraccion)
        self.assertAlmostEqual(figura.critico, 41.8, places=1)

    def test_la_incidencia_pasa_rasando_no_vale(self):
        with self.assertRaises(ValueError) as error:
            analizar_optica(1.0, 1.33, 95)
        self.assertIn("90", str(error.exception))

    def test_un_indice_negativo_se_rechaza(self):
        with self.assertRaises(ValueError) as error:
            analizar_optica(0, 1.33, 30)
        self.assertIn("positiv", str(error.exception))


class MaquinasTest(unittest.TestCase):
    def test_el_pendulo_saca_su_periodo(self):
        figura = analizar_pendulo("1 m", 20)
        self.assertAlmostEqual(figura.periodo, 2.006, places=2)

    def test_el_pendulo_no_confunde_centimetros_con_metros(self):
        figura = analizar_pendulo("80 cm", 24)
        self.assertAlmostEqual(figura.periodo, 1.795, places=3)
        self.assertEqual((figura.longitud, figura.unidad), (80.0, "cm"))

    def test_el_pendulo_rechaza_angulo_plano(self):
        with self.assertRaises(ValueError) as error:
            analizar_pendulo("1 m", 0)
        self.assertIn("90", str(error.exception))

    def test_la_longitud_del_pendulo_necesita_numero(self):
        with self.assertRaises(ValueError) as error:
            analizar_pendulo("largo", 20)
        self.assertIn("número", str(error.exception))

    def test_el_resorte_convierte_centimetros_a_metros(self):
        figura = analizar_resorte("200 N/m", "10 cm")
        self.assertAlmostEqual(figura.fuerza, 20.0, places=6)

    def test_la_polea_saca_aceleracion_y_tension(self):
        figura = analizar_polea("3 kg", "2 kg")
        self.assertAlmostEqual(figura.aceleracion, 1.96, places=2)
        self.assertAlmostEqual(figura.tension, 23.52, places=2)

    def test_masas_iguales_no_mueven_la_polea(self):
        with self.assertRaises(ValueError) as error:
            analizar_polea("2 kg", "2 kg")
        self.assertIn("iguales", str(error.exception))


class GuionOpticaMaquinasTest(unittest.TestCase):
    def test_la_optica_pide_sus_tres_datos(self):
        visual = Visual(tipo="optica", n1=1.0, n2=1.33, angulo_incidence=30)
        self.assertAlmostEqual(visual.optica().refraccion, 22.08, places=1)

    def test_el_pendulo_reusa_el_angulo(self):
        visual = Visual(tipo="pendulo", longitud="1 m", angulo=20, anotar=["periodo"])
        self.assertAlmostEqual(visual.pendulo().periodo, 2.006, places=2)

    def test_el_resorte_pide_constante_y_extension(self):
        visual = Visual(tipo="resorte", constante="200 N/m", extension="10 cm")
        self.assertAlmostEqual(visual.resorte().fuerza, 20.0, places=6)

    def test_sin_segunda_masa_no_hay_polea(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="polea", masa_a="3 kg")
        self.assertIn("masa_b", str(error.exception))

    def test_el_yaml_guarda_el_pendulo(self):
        texto = "\n".join(_visual_yaml({"tipo": "pendulo", "longitud": "1 m", "angulo": 20}))
        self.assertIn("tipo: pendulo", texto)
        self.assertIn("longitud", texto)

    def test_la_ia_puede_pedir_la_polea(self):
        paso = PasoIA(
            nota="Suelta las masas",
            tex=r"a = 1{,}96\ \text{m/s}^2",
            voz="Mira la polea.",
            dibujo="polea",
            masa_a="3 kg",
            masa_b="2 kg",
        )
        visual = Visual(**_visual(paso))
        self.assertEqual(visual.tipo, "polea")


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoOpticaMaquinasTest(unittest.TestCase):
    def _textos(self, dib) -> str:
        return " | ".join(m.original_text for m in dib.mobs.get_family() if isinstance(m, Text))

    def test_la_optica_escribe_los_dos_angulos(self):
        dib = optica(analizar_optica(1.0, 1.33, 30), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        textos = self._textos(dib)
        self.assertIn("30°", textos)
        self.assertIn("22", textos)

    def test_el_pendulo_anota_su_periodo(self):
        dib = pendulo(analizar_pendulo("1 m", 20), ["periodo"], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        self.assertIn("2,0", self._textos(dib))

    def test_el_resorte_escribe_su_fuerza(self):
        dib = resorte(
            analizar_resorte("200 N/m", "10 cm"), ["fuerza"], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
        )
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertTrue(dib.trazo)
        self.assertIn("20 N", self._textos(dib))

    def test_la_polea_escribe_su_aceleracion(self):
        dib = polea(analizar_polea("3 kg", "2 kg"), ["aceleracion"], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        self.assertIn("1,96", self._textos(dib))


if __name__ == "__main__":
    unittest.main()
