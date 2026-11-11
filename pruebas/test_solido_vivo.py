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


@unittest.skipUnless(MANIM, "manim no está instalado")
class EstiloTecnicoTest(unittest.TestCase):
    def _dibujo(self, tipo="cubo", **extra):
        if tipo == "tolva":
            datos = {"tipo": "tolva_3d", "radio": "0,4 m", "altura": "0,6 m",
                     "radio_salida": "0,1 m", "altura_cono": "0,4 m"}
        else:
            datos = {"tipo": "solido_3d", "figura": "cubo", "lado": "4 cm"}
        visual = Visual.model_validate({**datos, **extra})
        return dibujar_visual(visual, TEMA.colores, ANCHO_UTIL, ALTO_DIBUJO, TEMA.hoja.color)

    def _cotas(self, dib):
        from manim import Line
        return [m for m in dib.mobs.get_family() if isinstance(m, Line) and len(m.points)]

    def _rayas(self, dib):
        return [m for m in dib.aparece[0].get_family()
                if isinstance(m, VMobject) and len(m.points) and m.get_fill_opacity() < 0.01
                and m.get_stroke_opacity() > 0.5
                and m.get_stroke_color().to_hex() == TEMA.colores.acento]

    def test_cubo_y_tolva_tienen_cotas_conectadas(self):
        for tipo, minimo in (("cubo", 5), ("tolva", 20)):
            with self.subTest(tipo=tipo):
                self.assertGreaterEqual(len(self._cotas(self._dibujo(tipo))), minimo)

    def test_cota_del_cubo_parte_de_los_vertices_reales(self):
        dib = self._dibujo()
        vertices = np.vstack([m.points for m in _caras_visibles(dib)])
        ancladas = sum(any(np.linalg.norm(linea.get_start() - p) < 1e-6 for p in vertices)
                       for linea in self._cotas(dib))
        self.assertGreaterEqual(ancladas, 2)

    def test_corte_del_cubo_se_raya_sin_cambiar_su_geometria(self):
        dib = self._dibujo(corte="mitad")
        self.assertGreaterEqual(len(self._rayas(dib)), 1)
        for raya in self._rayas(dib):
            self.assertGreaterEqual(raya.get_num_curves(), 6)
        piezas = _piezas_vivas("cubo", "mitad", False, 1.0, 1.0, 2.6)
        self.assertEqual(len(piezas), 2)
        self.assertEqual(len(piezas[0].caras), 6)

    def test_rayado_sigue_la_seccion_y_no_se_pinta_sobre_la_mitad_superior(self):
        dib = self._dibujo(corte="mitad")
        for t in (0.0, 0.4, 0.8, 1.0):
            dib.vivo(t)
            caras = _caras_visibles(dib)
            for raya in self._rayas(dib):
                seccion = max((cara for cara in caras if cara.z_index < raya.z_index),
                              key=lambda cara: cara.z_index)
                self.assertLess(raya.z_index, max(cara.z_index for cara in caras))
                borde = seccion.get_start_anchors()[:, :2]
                aristas = np.roll(borde, -1, axis=0) - borde
                for punto in raya.points[:, :2]:
                    relativo = punto - borde
                    giros = aristas[:, 0] * relativo[:, 1] - aristas[:, 1] * relativo[:, 0]
                    self.assertTrue(np.all(giros >= -1e-6) or np.all(giros <= 1e-6))
        dib = self._dibujo(corte="mitad", vista="frente")
        self.assertFalse(self._rayas(dib))

    def test_alturas_de_tolva_miden_altura_y_no_la_pared_inclinada(self):
        dib = self._dibujo("tolva", despiece=True)
        for t in (0.0, 0.3, 0.7, 1.0):
            dib.vivo(t)
            lineas = self._cotas(dib)
            cilindro = lineas[7].get_end() - lineas[7].get_start()
            cono = lineas[12].get_end() - lineas[12].get_start()
            self.assertAlmostEqual(float(np.linalg.norm(cilindro) / np.linalg.norm(cono)), 1.5)
            self.assertTrue(np.allclose(cilindro / np.linalg.norm(cilindro), cono / np.linalg.norm(cono)))

    def test_cubo_sin_corte_no_muestra_rayado(self):
        self.assertFalse(self._rayas(self._dibujo()))

    def test_cantos_del_cubo_no_tapan_las_caras(self):
        dib = self._dibujo()
        self.assertTrue(_caras_visibles(dib))
        self.assertLessEqual(max(float(m.get_stroke_width()) for m in _caras_visibles(dib)), 1.8)

    def test_luz_del_cubo_no_quema_las_caras(self):
        dib = self._dibujo()
        self.assertLess(max(float(m.get_fill_color().to_rgb().max())
                            for m in _caras_visibles(dib)), 0.93)

    def test_colocar_el_cubo_no_saca_la_cota_del_cuadro_durante_la_orbita(self):
        dib = self._dibujo(vista="ala", corte="mitad", despiece=True).place(0, 0)
        dib.vivo(0.325)
        self.assertGreaterEqual(dib.mobs.get_bottom()[1], -ALTO_DIBUJO / 2)
        self.assertLessEqual(dib.mobs.get_top()[1], ALTO_DIBUJO / 2)

    def test_los_radios_de_tolva_no_saltan_de_costado_al_girar(self):
        dib = self._dibujo("tolva")
        rotulos = [m for m in dib.aparece if getattr(m, "original_text", "").startswith(("R =", "r ="))]
        self.assertEqual(len(rotulos), 2)
        dib.vivo(0.338866 - 1e-6)
        antes = [m.get_center().copy() for m in rotulos]
        dib.vivo(0.338866 + 1e-6)
        for rotulo, punto in zip(rotulos, antes, strict=True):
            self.assertLess(float(np.linalg.norm(rotulo.get_center() - punto)), 0.01)

    def test_alturas_colapsadas_de_tolva_se_ocultan_antes_de_superponerse(self):
        dib = self._dibujo("tolva", vista="piso")
        alturas = [m for m in dib.aparece if getattr(m, "original_text", "").startswith(("H =", "h ="))]
        self.assertEqual(len(alturas), 2)
        dib.vivo(0.97)
        for rotulo in alturas:
            self.assertLess(max(m.get_fill_opacity() for m in rotulo.get_family()), 0.05)

    def test_radio_pequeno_no_tapa_alturas_mientras_rodea_la_tolva(self):
        dib = self._dibujo("tolva")
        rotulos = [m for m in dib.aparece if getattr(m, "original_text", "")]
        radio = next(m for m in rotulos if m.original_text.startswith("r ="))
        for t in (0.275, 0.325):
            dib.vivo(t)
            self.assertLess(max(m.get_fill_opacity() for m in radio.get_family()), 0.05)

    def test_notas_de_tolva_no_tapan_las_cotas_en_vista_superior(self):
        dib = self._dibujo("tolva", vista="piso", anotar=["volumen", "chapa"])
        rotulos = [m for m in dib.aparece if getattr(m, "original_text", "")]
        radio = next(m for m in rotulos if m.original_text.startswith("R ="))
        notas = [m for m in rotulos if m.original_text.startswith(("V =", "Chapa ="))]
        self.assertEqual(len(notas), 2)
        for t in (0.0, 0.3, 0.7, 1.0):
            dib.vivo(t)
            for nota in notas:
                overlap_x = min(radio.get_right()[0], nota.get_right()[0]) - max(radio.get_left()[0], nota.get_left()[0])
                overlap_y = min(radio.get_top()[1], nota.get_top()[1]) - max(radio.get_bottom()[1], nota.get_bottom()[1])
                self.assertTrue(overlap_x <= 0 or overlap_y <= 0)

    def test_cotas_y_rotulos_caben_durante_orbita_y_despiece(self):
        for tipo in ("cubo", "tolva"):
            for vista in ("frente", "ala", "piso", "axonometrica"):
                extras = {"vista": vista, "despiece": True}
                if tipo == "cubo":
                    extras["corte"] = "mitad"
                dib = self._dibujo(tipo, **extras)
                for t in np.linspace(0, 1, 11):
                    with self.subTest(tipo=tipo, vista=vista, t=t):
                        dib.vivo(float(t))
                        self.assertLessEqual(dib.mobs.width, ANCHO_UTIL + 0.05)
                        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 0.05)
                        puntos = np.vstack([m.points for m in dib.mobs.get_family() if len(m.points)])
                        self.assertTrue(np.all(np.isfinite(puntos)))


if __name__ == "__main__":
    unittest.main()
