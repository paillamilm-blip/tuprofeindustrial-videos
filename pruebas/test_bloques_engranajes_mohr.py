"""Las tres láminas del taller: el lazo de control, la pareja de engranajes y el círculo de Mohr."""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import (
    MARCAS_BLOQUES,
    MARCAS_ENGRANAJE,
    MARCAS_MOHR,
    SEGUNDOS_VISUAL,
    analizar_bloques,
    analizar_engranajes,
    analizar_mohr,
)

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import Text

    from tpi_videos.dibujos import ALTO_DIBUJO, bloques, engranaje, mohr

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)


class BloquesTest(unittest.TestCase):
    def test_la_realimentacion_negativa_baja_la_ganancia(self):
        figura = analizar_bloques("10", "0.2")
        self.assertAlmostEqual(figura.adelante, 10.0, places=6)
        self.assertAlmostEqual(figura.retro, 0.2, places=6)
        self.assertAlmostEqual(figura.lazo_cerrado, 10.0 / 3.0, places=6)
        self.assertTrue(figura.negativa)

    def test_la_realimentacion_positiva_puede_volverse_locura(self):
        with self.assertRaises(ValueError) as error:
            analizar_bloques("10", "0.1", negativa=False)
        self.assertIn("inestable", str(error.exception))

    def test_un_bloque_necesita_numero(self):
        with self.assertRaises(ValueError) as error:
            analizar_bloques("alta", "0.2")
        self.assertIn("número", str(error.exception))


class EngranajeTest(unittest.TestCase):
    def test_el_grande_gira_mas_lento(self):
        figura = analizar_engranajes("20", "60", "1200 rpm")
        self.assertAlmostEqual(figura.relacion, 3.0, places=6)
        self.assertAlmostEqual(figura.salida, 400.0, places=6)
        self.assertEqual((figura.z1, figura.z2), (20, 60))
        self.assertEqual(figura.unidad, "rpm")

    def test_la_vuelta_sale_al_reves(self):
        figura = analizar_engranajes("20", "60", "1200 rpm")
        self.assertTrue(figura.invertida)

    def test_un_engranaje_no_es_una_rueda_sola(self):
        with self.assertRaises(ValueError) as error:
            analizar_engranajes("20", "20", "1200 rpm")
        self.assertIn("dientes", str(error.exception))

    def test_los_dientes_se_cuentan(self):
        with self.assertRaises(ValueError) as error:
            analizar_engranajes("muchos", "60", "1200 rpm")
        self.assertIn("número", str(error.exception))


class MohrTest(unittest.TestCase):
    def test_el_circulo_saca_los_principales(self):
        figura = analizar_mohr("80 MPa", "20 MPa", "30 MPa")
        self.assertAlmostEqual(figura.centro, 50.0, places=6)
        self.assertAlmostEqual(figura.radio, 42.426406871192854, places=6)
        self.assertAlmostEqual(figura.principal_1, 92.42640687119285, places=6)
        self.assertAlmostEqual(figura.principal_2, 7.573593128807146, places=6)
        self.assertAlmostEqual(figura.max_cortante, 42.426406871192854, places=6)
        self.assertAlmostEqual(figura.angulo, 22.5, places=6)
        self.assertEqual(figura.unidad, "MPa")

    def test_sin_cortante_el_circulo_se_aplasta_en_los_ejes(self):
        figura = analizar_mohr("80 MPa", "20 MPa", "0 MPa")
        self.assertAlmostEqual(figura.radio, 30.0, places=6)
        self.assertAlmostEqual(figura.angulo, 0.0, places=6)

    def test_un_esfuerzo_necesita_su_unidad(self):
        with self.assertRaises(ValueError) as error:
            analizar_mohr("ochenta", "20 MPa", "30 MPa")
        self.assertIn("número", str(error.exception))


class MarcasYTiempoTest(unittest.TestCase):
    def test_los_tres_dibujos_tienen_su_tiempo(self):
        for tipo in ("bloques", "engranaje", "mohr"):
            self.assertGreaterEqual(SEGUNDOS_VISUAL[tipo], 2.5, tipo)

    def test_las_marcas_no_se_pisan(self):
        self.assertEqual(MARCAS_BLOQUES, ("lazo_cerrado",))
        self.assertEqual(MARCAS_ENGRANAJE, ("velocidad", "relacion"))
        self.assertEqual(MARCAS_MOHR, ("principales", "cortante"))


class GuionBloquesEngranajeMohrTest(unittest.TestCase):
    def test_el_lazo_se_cierra_solo(self):
        visual = Visual(tipo="bloques", adelante="10", retro="0.2", anotar=["lazo_cerrado"])
        self.assertAlmostEqual(visual.bloques().lazo_cerrado, 10.0 / 3.0, places=6)

    def test_el_bloque_pide_su_ganancia(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="bloques", retro="0.2")
        self.assertIn("adelante", str(error.exception))

    def test_la_pareja_de_engranajes_saca_su_velocidad(self):
        visual = Visual(
            tipo="engranaje", dientes_a="20", dientes_b="60", rpm="1200 rpm", anotar=["velocidad"]
        )
        self.assertAlmostEqual(visual.engranaje().salida, 400.0, places=6)

    def test_el_mohr_rechaza_anotar_de_otro_dibujo(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="mohr", sigma_x="80 MPa", sigma_y="20 MPa", cortante="30 MPa", anotar=["radio"])
        self.assertIn("principales", str(error.exception))

    def test_la_realimentacion_positiva_se_guarda_en_el_yaml(self):
        datos = {"tipo": "bloques", "adelante": "10", "retro": "0.2", "negativa": False}
        texto = "\n".join(_visual_yaml(datos))
        self.assertIn("tipo: bloques", texto)
        self.assertIn("adelante: '10'", texto)
        self.assertIn("negativa: false", texto)

    def test_la_ia_puede_pedir_la_pareja_de_engranajes(self):
        paso = PasoIA(
            nota="La vuelta se reduce",
            tex=r"n_2 = n_1 \frac{z_1}{z_2} = 400\ \text{rpm}",
            voz="Mira los engranajes.",
            dibujo="engranaje",
            dientes_a="20",
            dientes_b="60",
            rpm="1200 rpm",
            anotar=["velocidad"],
        )
        visual = Visual(**_visual(paso))
        self.assertEqual(visual.tipo, "engranaje")
        self.assertEqual(visual.dientes_b, "60")


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoBloquesEngranajeMohrTest(unittest.TestCase):
    def _textos(self, dib) -> str:
        return " | ".join(m.original_text for m in dib.mobs.get_family() if isinstance(m, Text))

    def test_el_lazo_escribe_su_ganancia(self):
        dib = bloques(analizar_bloques("10", "0.2"), ["lazo_cerrado"], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        self.assertTrue(dib.trazo)
        textos = self._textos(dib)
        self.assertIn("G = 10", textos)
        self.assertIn("3,33", textos)

    def test_la_pareja_escribe_su_velocidad(self):
        dib = engranaje(
            analizar_engranajes("20", "60", "1200 rpm"), ["velocidad"], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
        )
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        textos = self._textos(dib)
        self.assertIn("z₁ = 20", textos)
        self.assertIn("400 rpm", textos)

    def test_el_mohr_escribe_sus_principales(self):
        dib = mohr(
            analizar_mohr("80 MPa", "20 MPa", "30 MPa"),
            ["principales"],
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
        )
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        self.assertIn("92,43", self._textos(dib))


if __name__ == "__main__":
    unittest.main()
