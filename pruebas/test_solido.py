"""Los sólidos de siempre (cubo, cilindro, cono, esfera) con su volumen y su área calculados y dibujados."""

import math
import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import analizar_solido

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import Text

    from tpi_videos.dibujos import ALTO_DIBUJO, solido

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)


class MatematicaSolidoTest(unittest.TestCase):
    """Las fórmulas del cuaderno: π r² h, un tercio de eso en el cono, y la esfera completa."""

    def test_el_cilindro(self):
        figura = analizar_solido("cilindro", radio="3 cm", altura="5 cm")
        self.assertAlmostEqual(figura.volumen, math.pi * 9 * 5, places=2)
        self.assertAlmostEqual(figura.area, 2 * math.pi * 3 * 8, places=2)
        self.assertEqual(figura.unidad, "cm")

    def test_el_cono_usa_la_generatriz(self):
        figura = analizar_solido("cono", radio="3 cm", altura="4 cm")
        self.assertAlmostEqual(figura.volumen, math.pi * 9 * 4 / 3, places=2)
        self.assertAlmostEqual(figura.area, math.pi * 3 * (3 + 5), places=2)

    def test_la_esfera(self):
        figura = analizar_solido("esfera", radio="3 cm")
        self.assertAlmostEqual(figura.volumen, 4 * math.pi * 27 / 3, places=2)
        self.assertAlmostEqual(figura.area, 4 * math.pi * 9, places=2)

    def test_el_cubo(self):
        figura = analizar_solido("cubo", lado="4 cm")
        self.assertAlmostEqual(figura.volumen, 64, places=6)
        self.assertAlmostEqual(figura.area, 96, places=6)

    def test_marcas_nuevas_nota(self):
        cono = analizar_solido("cono", radio="3 cm", altura="4 cm")
        rot, val, suf = cono.nota("altura")
        self.assertEqual((rot, val, suf), ("h", 4.0, ""))
        rot, val, suf = cono.nota("radio")
        self.assertEqual((rot, val, suf), ("r", 3.0, ""))
        rot, val, suf = cono.nota("generatriz")
        self.assertEqual((rot, val, suf), ("g", 5.0, ""))
        rot, val, suf = cono.nota("area_base")
        self.assertEqual(rot, "A base")
        self.assertAlmostEqual(val, math.pi * 9, places=2)

    def test_el_area_basal_de_cada_solido(self):
        casos = (
            ("cilindro", {"radio": "1,2 m", "altura": "2,5 m"}, math.pi * 1.2**2),
            ("cono", {"radio": "3 cm", "altura": "4 cm"}, math.pi * 9),
            ("cubo", {"lado": "4 cm"}, 16.0),
            ("esfera", {"radio": "3 cm"}, math.pi * 9),
        )
        for figura, medidas, esperada in casos:
            with self.subTest(figura=figura):
                self.assertAlmostEqual(analizar_solido(figura, **medidas).area_base, esperada, places=6)

    def test_de_piso_se_anota_el_area_basal_no_la_total(self):
        estanque = analizar_solido("cilindro", radio="1,2 m", altura="2,5 m")
        rotulo, valor, sufijo = estanque.nota("area", "piso")
        self.assertEqual(rotulo, "A base")
        self.assertAlmostEqual(valor, math.pi * 1.2**2, places=6)
        self.assertEqual(sufijo, "²")
        # mirando el cuerpo entero el área sigue siendo la de toda la superficie
        rotulo, valor, _ = estanque.nota("area", "axonometrica")
        self.assertEqual(rotulo, "A")
        self.assertAlmostEqual(valor, 2 * math.pi * 1.2 * (1.2 + 2.5), places=6)
        rotulo, valor, sufijo = estanque.nota("volumen", "piso")
        self.assertEqual((rotulo, sufijo), ("V", "³"))
        self.assertAlmostEqual(valor, math.pi * 1.2**2 * 2.5, places=6)

    def test_la_lata_y_el_cubo_partido_siguen_con_su_area_total(self):
        lata = analizar_solido("cilindro", radio="3 cm", altura="5 cm")
        self.assertAlmostEqual(lata.nota("area", "axonometrica")[1], 2 * math.pi * 3 * 8, places=2)
        cubo = analizar_solido("cubo", lado="4 cm")
        self.assertAlmostEqual(cubo.nota("area", "frente")[1], 96, places=6)

    def test_el_cilindro_convierte_todas_las_medidas_a_la_primera_unidad(self):
        casos = (
            ("1 m", "100 cm", "m", 1.0, 1.0, math.pi, 4 * math.pi),
            ("100 cm", "1 m", "cm", 100.0, 100.0, 1000000 * math.pi, 40000 * math.pi),
            ("10 dm", "1000 mm", "dm", 10.0, 10.0, 1000 * math.pi, 400 * math.pi),
        )
        for radio, altura, unidad, r, h, volumen, area in casos:
            with self.subTest(radio=radio, altura=altura):
                figura = analizar_solido("cilindro", radio=radio, altura=altura)
                self.assertEqual(figura.unidad, unidad)
                self.assertAlmostEqual(figura.radio, r)
                self.assertAlmostEqual(figura.altura, h)
                self.assertAlmostEqual(figura.volumen, volumen)
                self.assertAlmostEqual(figura.area, area)

    def test_el_cono_convierte_la_altura_antes_de_calcular_la_generatriz(self):
        figura = analizar_solido("cono", radio="3 cm", altura="0,04 m")
        self.assertEqual(figura.unidad, "cm")
        self.assertAlmostEqual(figura.altura, 4.0)
        self.assertAlmostEqual(figura.volumen, 12 * math.pi)
        self.assertAlmostEqual(figura.area, 24 * math.pi)

    def test_una_unidad_que_no_es_longitud_se_rechaza(self):
        for radio in ("3 pulgadas", "3 mph", "3 m/s", "3 m²"):
            with self.subTest(radio=radio):
                with self.assertRaises(ValueError) as error:
                    analizar_solido("esfera", radio=radio)
                self.assertIn("unidad", str(error.exception))

    def test_al_cilindro_le_falta_la_altura(self):
        with self.assertRaises(ValueError) as error:
            analizar_solido("cilindro", radio="3 cm")
        self.assertIn("altura", str(error.exception))

    def test_una_medida_sin_numero_se_rechaza(self):
        with self.assertRaises(ValueError) as error:
            analizar_solido("esfera", radio="grande")
        self.assertIn("número", str(error.exception))

    def test_un_solido_que_el_motor_no_conoce(self):
        with self.assertRaises(ValueError) as error:
            analizar_solido("piramide", radio="3 cm")
        self.assertIn("piramide", str(error.exception))


class GuionSolidoTest(unittest.TestCase):
    def test_pide_el_solido_con_sus_medidas(self):
        visual = Visual(tipo="solido", figura="cilindro", radio="3 cm", altura="5 cm", anotar=["volumen"])
        self.assertAlmostEqual(visual.solido().volumen, math.pi * 45, places=2)

    def test_los_solidos_planos_y_3d_normalizan_las_medidas_del_guion(self):
        for tipo in ("solido", "solido_3d"):
            with self.subTest(tipo=tipo):
                visual = Visual(tipo=tipo, figura="cilindro", radio="1 m", altura="100 cm")
                figura = visual.solido()
                self.assertEqual(figura.unidad, "m")
                self.assertAlmostEqual(figura.altura, 1.0)
                self.assertAlmostEqual(figura.volumen, math.pi)

    def test_sin_radio_el_error_habla_del_solido(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="solido", figura="esfera", altura="5 cm")
        self.assertIn("radio", str(error.exception))

    def test_marca_desconocida_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="solido", figura="cubo", lado="4 cm", anotar=["arista"])
        self.assertIn("arista", str(error.exception))

    def test_el_yaml_guarda_el_solido(self):
        texto = "\n".join(
            _visual_yaml({"tipo": "solido", "figura": "cono", "radio": "3 cm", "altura": "4 cm"})
        )
        self.assertIn("tipo: solido", texto)
        self.assertIn("figura: cono", texto)
        self.assertIn("radio: '3 cm'", texto)

    def test_la_ia_puede_pedir_el_solido_y_sale_con_volumen(self):
        paso = PasoIA(
            nota="Calculo el volumen",
            tex=r"V = \pi r^2 h",
            voz="Mira el cilindro y su volumen.",
            dibujo="solido",
            figura="cilindro",
            radio="3 cm",
            altura="5 cm",
            anotar=["volumen", "area"],
        )
        visual = Visual(**_visual(paso))
        # El generador promociona el sólido plano al cuerpo 3D: relieve y caras, no alambre.
        self.assertEqual(visual.tipo, "solido_3d")
        self.assertEqual(visual.anotar, ["volumen", "area"])

    def test_marcas_geometricas_validan(self):
        visual = Visual(tipo="solido_3d", figura="cono", radio="3 cm", altura="4 cm", anotar=["altura", "radio"])
        self.assertEqual(visual.anotar, ["altura", "radio"])
        visual_g = Visual(tipo="solido_3d", figura="cono", radio="3 cm", altura="4 cm", anotar=["generatriz"])
        self.assertEqual(visual_g.anotar, ["generatriz"])


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoSolidoTest(unittest.TestCase):
    """El dibujo es la lámina del libro: el cuerpo en perspectiva chica y sus medidas al lado."""

    def _dibujar(self, figura="cilindro", anotar=("volumen", "area"), **medidas):
        por_defecto = {"cubo": {"lado": "4 cm"}, "esfera": {"radio": "3 cm"}}.get(
            figura, {"radio": "3 cm", "altura": "5 cm" if figura != "cono" else "4 cm"}
        )
        por_defecto.update(medidas)
        return solido(
            analizar_solido(figura, **por_defecto), list(anotar), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
        )

    def _textos(self, dib) -> str:
        return " | ".join(m.original_text for m in dib.mobs.get_family() if isinstance(m, Text))

    def test_los_cuatro_entran_en_la_franja(self):
        for figura in ("cubo", "cilindro", "cono", "esfera"):
            dib = self._dibujar(figura)
            self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6, figura)
            self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6, figura)

    def test_el_cilindro_escribe_sus_numeros_con_coma_chilena(self):
        textos = self._textos(self._dibujar("cilindro"))
        self.assertIn("141,37", textos)
        self.assertIn("150,8", textos)
        self.assertIn("cm³", textos)

    def test_el_cubo_escribe_numeros_enteros(self):
        textos = self._textos(self._dibujar("cubo"))
        self.assertIn("64", textos)
        self.assertIn("96", textos)

    def test_cono_3d_destaca_altura_y_radio(self):
        from tpi_videos.dibujos_3d import dibujar_solido_3d
        visual = Visual(tipo="solido_3d", figura="cono", radio="3 cm", altura="4 cm", anotar=["altura"])
        dib = dibujar_solido_3d(visual, ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertIsNotNone(dib)
        self.assertTrue(len(dib.mobs) > 0)


if __name__ == "__main__":
    unittest.main()
