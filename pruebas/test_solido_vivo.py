"""El sólido 3D vivo: órbita continua hasta la vista pedida, luz que resbala y despiece."""

import unittest

import numpy as np

from tpi_videos.componentes import ANCHO_UTIL
from tpi_videos.config import cargar_marca
from tpi_videos.guion import Visual
from tpi_videos.temas import cargar_tema

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import VMobject

    from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual
    from tpi_videos.dibujos_3d import _ejes_de_camara, _piezas_vivas

TEMA = cargar_tema("hoja_de_desarrollo", cargar_marca())


def _visual(**datos):
    base = {"tipo": "solido_3d", "figura": "cilindro", "radio": "3 cm", "altura": "5 cm"}
    return Visual.model_validate({**base, **datos})


def _dibujo(**datos):
    return dibujar_visual(_visual(**datos), TEMA.colores, ANCHO_UTIL, ALTO_DIBUJO, TEMA.hoja.color)


def _caras_visibles(dib):
    cuerpo = dib.aparece[0]
    return [
        m
        for m in cuerpo.submobjects
        if isinstance(m, VMobject) and m.get_fill_opacity() > 0.5 and len(m.points)
    ]


@unittest.skipUnless(MANIM, "manim no está instalado")
class SolidoVivoTest(unittest.TestCase):
    def test_se_mueve_sin_reloj_fisico_y_ya_no_es_un_png(self):
        from manim import ImageMobject

        dib = _dibujo()
        self.assertIsNotNone(dib.vivo)
        self.assertFalse(dib.fisico)
        self.assertFalse(any(isinstance(m, ImageMobject) for m in dib.mobs.get_family()))

    def test_la_camara_orbita_y_termina_en_la_vista_pedida(self):
        dib = _dibujo(vista="frente")
        siluetas = []
        for t in (0.0, 0.5, 1.0):
            dib.vivo(t)
            pts = np.vstack([m.points for m in _caras_visibles(dib)])
            self.assertTrue(np.all(np.isfinite(pts)))
            siluetas.append(pts[:, :2].mean(axis=0).round(3).tolist() + [round(float(np.ptp(pts[:, 0])), 3)])
        self.assertNotEqual(siluetas[0], siluetas[2], "la órbita no cambió el encuadre")
        # De frente el cilindro es un rectángulo: no se ve ni la tapa ni la base.
        dib.vivo(1.0)
        _, _, hacia = _ejes_de_camara(90.0, -90.0)
        self.assertAlmostEqual(float(hacia[2]), 0.0, places=6)

    def test_la_luz_hace_que_las_caras_no_tengan_todas_el_mismo_tono(self):
        dib = _dibujo(vista="axonometrica")
        tonos = {m.get_fill_color().to_hex() for m in _caras_visibles(dib)}
        self.assertGreater(len(tonos), 6, "sin sombreado el manto sale de un solo color")

    def test_el_despiece_aparta_las_tapas_del_manto(self):
        piezas = _piezas_vivas("cilindro", "sin_corte", True, 1.0, 3.0, 0.0)
        self.assertEqual(len(piezas), 3)
        self.assertLess(piezas[0].salida[2], 0)
        self.assertGreater(piezas[2].salida[2], 0)
        juntas = _dibujo(despiece=True)
        juntas.vivo(0.0)
        alto_junto = juntas.aparece[0].height
        juntas.vivo(1.0)
        self.assertGreater(juntas.aparece[0].height, alto_junto * 0.9)

    def test_el_cubo_partido_levanta_la_mitad_de_arriba(self):
        piezas = _piezas_vivas("cubo", "mitad", False, 1.0, 1.0, 2.6)
        self.assertEqual(len(piezas), 2)
        self.assertEqual(sum(1 for p in piezas for c in p.caras if c.clase == "corte"), 2)
        self.assertGreater(piezas[1].salida[2], 0)

    def test_la_esfera_y_el_cono_tambien_viven(self):
        for figura, extra in (("esfera", {"radio": "2 cm"}), ("cono", {"radio": "2 cm", "altura": "4 cm"})):
            datos = {"figura": figura, **extra}
            if figura == "esfera":
                datos["altura"] = None
            dib = _dibujo(**datos)
            for t in (0.0, 0.3, 0.7, 1.0):
                dib.vivo(t)
                self.assertTrue(_caras_visibles(dib), f"{figura} sin caras a t={t}")

    def test_ninguna_pose_se_sale_de_la_franja(self):
        for datos in ({"vista": "axonometrica"}, {"vista": "piso", "despiece": True}):
            dib = _dibujo(**datos)
            for t in np.linspace(0, 1, 7):
                dib.vivo(float(t))
                self.assertLessEqual(dib.mobs.width, ANCHO_UTIL + 0.05, datos)
                self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 0.05, datos)


if __name__ == "__main__":
    unittest.main()
