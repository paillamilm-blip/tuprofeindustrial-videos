"""El círculo trigonométrico: sen, cos y tan como segmentos que se ven, no como números sueltos."""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import analizar_angulo

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    import numpy as np
    from manim import Circle, Text

    from tpi_videos.dibujos import ALTO_DIBUJO, circulo_trig

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)


class MatematicaAnguloTest(unittest.TestCase):
    """A 30° el seno vale medio y el coseno 0,87: los números del triángulo de siempre."""

    def test_los_valores_del_primer_cuadrante(self):
        figura = analizar_angulo(30)
        self.assertAlmostEqual(figura.seno, 0.5, places=3)
        self.assertAlmostEqual(figura.coseno, 0.866, places=3)
        self.assertAlmostEqual(figura.tangente, 0.577, places=3)
        self.assertEqual(figura.cuadrante, 1)

    def test_el_tercer_cuadrante_da_seno_y_coseno_negativos(self):
        figura = analizar_angulo(210)
        self.assertAlmostEqual(figura.seno, -0.5, places=3)
        self.assertLess(figura.coseno, 0)
        self.assertEqual(figura.cuadrante, 3)

    def test_a_90_grados_la_tangente_no_existe(self):
        self.assertIsNone(analizar_angulo(90).tangente)

    def test_una_vuelta_completa_vuelve_al_punto(self):
        self.assertAlmostEqual(analizar_angulo(390).seno, analizar_angulo(30).seno, places=6)


class GuionCirculoTest(unittest.TestCase):
    def test_pide_el_circulo_con_su_angulo(self):
        visual = Visual(tipo="circulo_trig", angulo=30, anotar=["seno", "coseno"])
        self.assertAlmostEqual(visual.angulo_trig().seno, 0.5, places=3)

    def test_sin_angulo_el_error_habla_del_dibujo(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="circulo_trig", anotar=["seno"])
        self.assertIn("angulo", str(error.exception))

    def test_angulo_fuera_de_la_vuelta_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="circulo_trig", angulo=400)
        self.assertIn("360", str(error.exception))

    def test_pedir_tangente_en_90_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="circulo_trig", angulo=90, anotar=["tangente"])
        self.assertIn("tangente", str(error.exception))

    def test_marcas_desconocidas_se_rechazan(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="circulo_trig", angulo=30, anotar=["secante"])
        self.assertIn("secante", str(error.exception))

    def test_el_yaml_guarda_el_circulo(self):
        texto = "\n".join(_visual_yaml({"tipo": "circulo_trig", "angulo": 30, "anotar": ["seno"]}))
        self.assertIn("tipo: circulo_trig", texto)
        self.assertIn("angulo: 30", texto)

    def test_la_ia_puede_pedir_el_circulo(self):
        paso = PasoIA(
            nota="Miro el ángulo",
            tex=r"\sin 30° = 0{,}5",
            voz="Mira el ángulo en el círculo.",
            dibujo="circulo",
            angulo=30,
            anotar=["seno", "tangente"],
        )
        visual = Visual(**_visual(paso))
        self.assertEqual(visual.tipo, "circulo_trig")
        self.assertEqual(visual.anotar, ["seno", "tangente"])


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoCirculoTest(unittest.TestCase):
    """El seno es el alto del punto, el coseno su avance y la tangente la raya del borde."""

    def _dibujar(self, anotar=("seno", "coseno", "tangente"), angulo=30):
        return circulo_trig(analizar_angulo(angulo), list(anotar), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)

    def _textos(self, dib) -> list[str]:
        return [m.original_text for m in dib.mobs.get_family() if isinstance(m, Text)]

    def test_entra_en_la_franja_del_pie(self):
        dib = self._dibujar()
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)

    def test_el_seno_y_el_coseno_miden_lo_que_dice_el_angulo(self):
        """Los dos segmentos contra el radio del círculo: sen y cos de verdad, no adornos."""
        dib = self._dibujar(anotar=["seno", "coseno"])
        circ = next(m for m in dib.mobs.get_family() if isinstance(m, Circle))
        radio = circ.width / 2
        lineas = [
            m
            for m in dib.trazo
            if hasattr(m, "get_start") and hasattr(m, "get_end") and not isinstance(m, Circle)
        ]
        verticales, horizontales = [], []
        for linea in lineas:
            d = linea.get_end() - linea.get_start()
            largo = float(np.linalg.norm(d))
            if largo < 1e-6:
                continue
            if abs(float(d[0])) < 1e-6:
                verticales.append(largo)
            elif abs(float(d[1])) < 1e-6:
                horizontales.append(largo)
        figura = analizar_angulo(30)
        self.assertTrue(
            any(abs(v / radio - abs(figura.seno)) < 0.02 for v in verticales), "falta el segmento del seno"
        )
        self.assertTrue(
            any(abs(h / radio - abs(figura.coseno)) < 0.02 for h in horizontales),
            "falta el segmento del coseno",
        )

    def test_las_marcas_escriben_sus_numeros_con_coma_chilena(self):
        textos = " | ".join(self._textos(self._dibujar(anotar=["seno", "coseno"])))
        self.assertIn("0,5", textos)
        self.assertIn("0,87", textos)


if __name__ == "__main__":
    unittest.main()
