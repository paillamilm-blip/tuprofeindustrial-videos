"""La rampa ya existía; lo nuevo es partir el peso en sus dos componentes, como en el cuaderno."""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.temas import ColoresTema

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    import numpy as np
    from manim import Arrow

    from tpi_videos.dibujos import ALTO_DIBUJO, diagrama_fuerzas

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)


class GuionRampaTest(unittest.TestCase):
    """Descomponer el peso sólo tiene sentido con plano inclinado y con la flecha P en el dibujo."""

    def test_descomponer_sin_plano_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="diagrama_fuerzas", vectores=["P", "N"], descomponer=True)
        self.assertIn("angulo", str(error.exception))

    def test_descomponer_sin_peso_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="diagrama_fuerzas", vectores=["N"], angulo=30, descomponer=True)
        self.assertIn("P", str(error.exception))

    def test_descomponer_con_plano_y_peso_pasa(self):
        visual = Visual(tipo="diagrama_fuerzas", vectores=["P", "N"], angulo=30, descomponer=True)
        self.assertTrue(visual.descomponer)

    def test_el_yaml_guarda_el_descomponer(self):
        texto = "\n".join(
            _visual_yaml(
                {"tipo": "diagrama_fuerzas", "vectores": ["P", "N"], "angulo": 30, "descomponer": True}
            )
        )
        self.assertIn("descomponer: true", texto)

    def test_la_ia_puede_pedir_las_componentes(self):
        paso = PasoIA(
            nota="Parto el peso",
            tex=r"P_{\parallel} = P\sin\theta",
            voz="Parto el peso en dos.",
            dibujo="fuerzas",
            vectores=["P", "N"],
            angulo=30,
            descomponer=True,
        )
        visual = Visual(**_visual(paso))
        self.assertTrue(visual.descomponer)
        self.assertEqual(visual.angulo, 30)


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoRampaTest(unittest.TestCase):
    """Dos flechas punteadas que salen del cuerpo: una a lo largo del plano y otra a lo ancho."""

    def _dibujar(self, angulo=30.0, vectores=("P", "N"), descomponer=True):
        return diagrama_fuerzas(
            list(vectores),
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
            angulo=angulo,
            descomponer=descomponer,
        )

    def _flechas(self, dib):
        return [m for m in dib.mobs.get_family() if isinstance(m, Arrow)]

    @staticmethod
    def _direccion(flecha):
        d = flecha.get_end() - flecha.get_start()
        return d / np.linalg.norm(d)

    def _planos(self, angulo_grados):
        ang = np.radians(angulo_grados)
        plano = np.array([np.cos(ang), -np.sin(ang), 0.0])
        return plano, np.array([-plano[1], plano[0], 0.0])

    def test_sin_descomponer_el_dibujo_queda_como_siempre(self):
        self.assertEqual(len(self._flechas(self._dibujar(descomponer=False))), 2)

    def test_las_componentes_apuntan_a_lo_largo_y_a_lo_ancho_del_plano(self):
        plano, normal = self._planos(30)
        direcciones = [self._direccion(f) for f in self._flechas(self._dibujar())]
        self.assertEqual(len(direcciones), 4, "P, N y las dos componentes")
        for esperada in (plano, -normal):
            iguales = [d for d in direcciones if float(np.dot(d, esperada)) > 0.999]
            self.assertEqual(len(iguales), 1, f"falta la componente {esperada}")

    def test_las_componentes_miden_sen_y_cos_del_angulo(self):
        plano, normal = self._planos(30)
        largos = []
        for flecha in self._flechas(self._dibujar()):
            d = self._direccion(flecha)
            if max(float(np.dot(d, plano)), float(np.dot(d, -normal))) > 0.999:
                largos.append(float(np.linalg.norm(flecha.get_end() - flecha.get_start())))
        self.assertEqual(len(largos), 2)
        self.assertAlmostEqual(min(largos) / max(largos), float(np.tan(np.radians(30))), places=2)

    def test_las_componentes_nacen_del_mismo_punto_que_el_peso(self):
        peso = next(f for f in self._flechas(self._dibujar()) if self._direccion(f)[1] < -0.999)
        for flecha in self._flechas(self._dibujar()):
            d = self._direccion(flecha)
            plano, normal = self._planos(30)
            if max(float(np.dot(d, plano)), float(np.dot(d, -normal))) > 0.999:
                self.assertLess(float(np.linalg.norm(flecha.get_start() - peso.get_start())), 1e-6)


if __name__ == "__main__":
    unittest.main()
