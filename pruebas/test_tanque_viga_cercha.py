"""Ingeniería en la hoja: el tanque que se llena y pierde, la viga apoyada y la cercha triangular."""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import (
    MARCAS_CERCHA,
    MARCAS_TANQUE,
    MARCAS_VIGA,
    SEGUNDOS_VISUAL,
    analizar_cercha,
    analizar_tanque,
    analizar_viga,
)

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import Text

    from tpi_videos.dibujos import ALTO_DIBUJO, cercha, tanque, viga

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)


class TanqueTest(unittest.TestCase):
    def test_con_fuga_se_llena_mas_lento(self):
        figura = analizar_tanque("120 L", "8 L/min", "2 L/min")
        self.assertAlmostEqual(figura.neto, 6.0, places=6)
        self.assertAlmostEqual(figura.llenado, 20.0, places=6)
        self.assertAlmostEqual(figura.vaciado, 60.0, places=6)
        self.assertEqual((figura.capacidad, figura.unidad), (120.0, "L"))
        self.assertEqual(figura.unidad_tiempo, "min")

    def test_sin_fuga_no_hay_vaciado(self):
        figura = analizar_tanque("120 L", "8 L/min")
        self.assertAlmostEqual(figura.llenado, 15.0, places=6)
        self.assertIsNone(figura.vaciado)

    def test_si_sale_mas_de_lo_que_entra_nunca_se_llena(self):
        with self.assertRaises(ValueError) as error:
            analizar_tanque("120 L", "3 L/min", "5 L/min")
        self.assertIn("llena", str(error.exception))

    def test_el_caudal_se_escribe_por_unidad_de_tiempo(self):
        with self.assertRaises(ValueError) as error:
            analizar_tanque("120 L", "8 L")
        self.assertIn("L/min", str(error.exception))

    def test_la_capacidad_necesita_numero(self):
        with self.assertRaises(ValueError) as error:
            analizar_tanque("grande", "8 L/min")
        self.assertIn("número", str(error.exception))


class VigaTest(unittest.TestCase):
    def test_la_carga_al_centro_se_reparte_entre_los_dos_apoyos(self):
        figura = analizar_viga("4 m", "200 N")
        self.assertAlmostEqual(figura.reaccion, 100.0, places=6)
        self.assertAlmostEqual(figura.momento, 200.0, places=6)
        self.assertFalse(figura.repartida)

    def test_la_carga_repartida_pesa_toda_la_luz(self):
        figura = analizar_viga("4 m", "50 N/m", repartida=True)
        self.assertTrue(figura.repartida)
        self.assertAlmostEqual(figura.reaccion, 100.0, places=6)
        self.assertAlmostEqual(figura.momento, 100.0, places=6)

    def test_una_viga_sin_carga_no_carga_nada(self):
        with self.assertRaises(ValueError) as error:
            analizar_viga("4 m", "0 N")
        self.assertIn("positiv", str(error.exception))


class CerchaTest(unittest.TestCase):
    def test_el_triangulo_3_4_5_da_su_esfuerzo(self):
        figura = analizar_cercha("6 m", "4 m", "300 N")
        self.assertAlmostEqual(figura.angulo, 53.13, places=2)
        self.assertAlmostEqual(figura.esfuerzo, 187.5, places=6)
        self.assertAlmostEqual(figura.reaccion, 150.0, places=6)

    def test_mas_alta_la_cercha_menos_esfuerzo(self):
        baja = analizar_cercha("6 m", "2 m", "300 N")
        alta = analizar_cercha("6 m", "5 m", "300 N")
        self.assertGreater(baja.esfuerzo, alta.esfuerzo)

    def test_la_cercha_necesita_su_carga(self):
        with self.assertRaises(ValueError) as error:
            analizar_cercha("6 m", "4 m", "")
        self.assertIn("número", str(error.exception))


class MarcasYTiempoTest(unittest.TestCase):
    def test_los_tres_dibujos_tienen_su_tiempo(self):
        for tipo in ("tanque", "viga", "cercha"):
            self.assertGreaterEqual(SEGUNDOS_VISUAL[tipo], 2.5, tipo)

    def test_las_marcas_no_se_pisan(self):
        self.assertEqual(MARCAS_TANQUE, ("llenado", "vaciado"))
        self.assertEqual(MARCAS_VIGA, ("reacciones", "momento"))
        self.assertEqual(MARCAS_CERCHA, ("esfuerzo", "angulo"))


class GuionTanqueVigaCerchaTest(unittest.TestCase):
    def test_el_tanque_saca_su_llenado(self):
        visual = Visual(
            tipo="tanque",
            capacidad="120 L",
            entrada="8 L/min",
            salida="2 L/min",
            anotar=["llenado"],
        )
        self.assertAlmostEqual(visual.tanque().llenado, 20.0, places=6)

    def test_el_tanque_pide_su_entrada(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="tanque", capacidad="120 L")
        self.assertIn("entrada", str(error.exception))

    def test_la_viga_reusa_la_longitud_del_pendulo(self):
        visual = Visual(tipo="viga", longitud="4 m", carga="200 N", anotar=["momento"])
        self.assertAlmostEqual(visual.viga().momento, 200.0, places=6)

    def test_la_cercha_reusa_la_altura_del_solido(self):
        visual = Visual(tipo="cercha", base="6 m", altura="4 m", carga="300 N")
        self.assertAlmostEqual(visual.cercha().esfuerzo, 187.5, places=6)

    def test_la_viga_repartida_se_guarda_en_el_yaml(self):
        texto = "\n".join(
            _visual_yaml({"tipo": "viga", "longitud": "4 m", "carga": "50 N/m", "repartida": True})
        )
        self.assertIn("tipo: viga", texto)
        self.assertIn("repartida: true", texto)

    def test_la_ia_puede_pedir_la_cercha(self):
        paso = PasoIA(
            nota="Cada palo aguarta la mitad",
            tex=r"F = \frac{P}{2\sen\theta} = 187{,}5\ \text{N}",
            voz="Mira la cercha.",
            dibujo="cercha",
            base="6 m",
            altura="4 m",
            carga="300 N",
        )
        visual = Visual(**_visual(paso))
        self.assertEqual(visual.tipo, "cercha")
        self.assertEqual(visual.carga, "300 N")


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoTanqueVigaCerchaTest(unittest.TestCase):
    def _textos(self, dib) -> str:
        return " | ".join(m.original_text for m in dib.mobs.get_family() if isinstance(m, Text))

    def test_el_tanque_escribe_su_tiempo(self):
        dib = tanque(
            analizar_tanque("120 L", "8 L/min", "2 L/min"),
            ["llenado"],
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
        )
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        textos = self._textos(dib)
        self.assertIn("120 L", textos)
        self.assertIn("20 min", textos)

    def test_la_viga_escribe_apoyos_y_momento(self):
        dib = viga(
            analizar_viga("4 m", "200 N"), ["reacciones", "momento"], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
        )
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertTrue(dib.trazo)
        textos = self._textos(dib)
        self.assertIn("100 N", textos)
        self.assertIn("200", textos)

    def test_la_cercha_escribe_su_esfuerzo(self):
        dib = cercha(
            analizar_cercha("6 m", "4 m", "300 N"), ["esfuerzo"], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
        )
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        self.assertIn("187,5", self._textos(dib))


if __name__ == "__main__":
    unittest.main()
