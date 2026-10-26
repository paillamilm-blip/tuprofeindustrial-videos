"""El tiro parabólico: la matemática, el guion y la figura con sus flechas de velocidad."""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import analizar_proyectil

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    import numpy as np
    from manim import Arrow, Text

    from tpi_videos.dibujos import ALTO_DIBUJO, proyectil

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)


class MatematicaProyectilTest(unittest.TestCase):
    """Con 20 m/s a 30° el vuelo dura 2,04 s y llega a 35,3 m: números de libro."""

    def _figura(self, velocidad="20 m/s", angulo=30):
        return analizar_proyectil(velocidad, angulo)

    def test_el_vuelo_dura_lo_que_dice_el_libro(self):
        self.assertAlmostEqual(self._figura().tiempo, 2.04, places=2)

    def test_el_alcance_y_la_altura_salen_de_las_componentes(self):
        figura = self._figura()
        self.assertAlmostEqual(figura.alcance, 35.3, places=1)
        self.assertAlmostEqual(figura.altura, 5.10, places=2)

    def test_a_45_grados_el_alcance_es_el_maximo(self):
        recto = self._figura(angulo=45).alcance
        self.assertGreater(recto, self._figura(angulo=30).alcance)
        self.assertGreater(recto, self._figura(angulo=60).alcance)

    def test_la_unidad_se_conserva_para_los_rotulos(self):
        self.assertEqual(self._figura("12,5 km/h").unidad, "km")

    def test_sin_numero_el_error_viene_en_espanol(self):
        with self.assertRaises(ValueError) as error:
            self._figura("rápido")
        self.assertIn("velocidad", str(error.exception))

    def test_angulo_fuera_de_rango_se_rechaza(self):
        with self.assertRaises(ValueError) as error:
            self._figura("20 m/s", 95)
        self.assertIn("90", str(error.exception))


class GuionProyectilTest(unittest.TestCase):
    def test_pide_un_proyectil_con_su_velocidad(self):
        visual = Visual(tipo="proyectil", velocidad="20 m/s", angulo=30)
        self.assertAlmostEqual(visual.proyectil().alcance, 35.3, places=1)

    def test_sin_velocidad_el_error_habla_del_dibujo(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="proyectil", angulo=30)
        self.assertIn("velocidad", str(error.exception))

    def test_marcas_desconocidas_se_rechazan(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="proyectil", velocidad="20 m/s", angulo=30, anotar=["energia"])
        self.assertIn("energia", str(error.exception))

    def test_el_yaml_guarda_el_proyectil(self):
        texto = "\n".join(
            _visual_yaml({"tipo": "proyectil", "velocidad": "20 m/s", "angulo": 30, "anotar": ["alcance"]})
        )
        self.assertIn("tipo: proyectil", texto)
        self.assertIn("velocidad: '20 m/s'", texto)
        self.assertIn("anotar: ['alcance']", texto)

    def test_la_ia_puede_pedir_el_proyectil(self):
        paso = PasoIA(
            nota="Miro el vuelo",
            tex=r"x = v_0 \cos\theta\, t",
            voz="Mira el vuelo de la bola.",
            dibujo="proyectil",
            velocidad="20 m/s",
            angulo=30,
            anotar=["alcance", "altura_maxima"],
        )
        visual = Visual(**_visual(paso))
        self.assertEqual(visual.tipo, "proyectil")
        self.assertEqual(visual.anotar, ["alcance", "altura_maxima"])


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoProyectilTest(unittest.TestCase):
    """La parábola apoyada en el suelo, con la flecha del lanzamiento y las marcas del guion."""

    def _dibujar(self, anotar=(), velocidad="20 m/s", angulo=30):
        return proyectil(
            analizar_proyectil(velocidad, angulo), list(anotar), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
        )

    def _textos(self, dib) -> list[str]:
        return [m.original_text for m in dib.mobs.get_family() if isinstance(m, Text)]

    def test_entra_en_la_franja_del_pie(self):
        dib = self._dibujar(anotar=["alcance", "altura_maxima", "componentes"])
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)

    def test_la_parabola_toca_el_suelo_en_la_salida_y_en_la_caída(self):
        curva = self._dibujar().trazo[1]
        puntos = np.array(curva.get_anchors())
        suelo = self._dibujar().trazo[0]
        ys = np.array(suelo.get_anchors())[:, 1]
        self.assertAlmostEqual(float(puntos[:, 1].min()), float(ys.mean()), places=4)
        arriba = puntos[:, 1].max() - puntos[:, 1].min()
        ancho = puntos[:, 0].max() - puntos[:, 0].min()
        figura = analizar_proyectil("20 m/s", 30)
        self.assertAlmostEqual(ancho / arriba, figura.alcance / figura.altura, places=1)

    def test_las_marcas_escriben_sus_numeros_con_coma_chilena(self):
        textos = " | ".join(self._textos(self._dibujar(anotar=["alcance", "altura_maxima"])))
        self.assertIn("35,3", textos)
        self.assertIn("5,1", textos)

    def test_las_componentes_son_una_flecha_horizontal_y_una_vertical(self):
        flechas = [m for m in self._dibujar(anotar=["componentes"]).mobs.get_family() if isinstance(m, Arrow)]
        direcciones = []
        for flecha in flechas:
            d = flecha.get_end() - flecha.get_start()
            direcciones.append(d / np.linalg.norm(d))
        horizontal = [d for d in direcciones if abs(float(d[1])) < 1e-6]
        vertical = [d for d in direcciones if abs(float(d[0])) < 1e-6]
        self.assertGreaterEqual(len(horizontal), 1, "falta la vx")
        self.assertGreaterEqual(len(vertical), 1, "falta la vy")


if __name__ == "__main__":
    unittest.main()
