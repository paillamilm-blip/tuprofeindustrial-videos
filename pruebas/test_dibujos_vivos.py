"""Los dibujos que se mueven: contrato, tiempo real y vectores reactivos."""

import unittest

import numpy as np

from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import (
    DURACION_RESORTE,
    analizar_oscilador,
    analizar_pendulo,
    analizar_pendulo_doble,
    analizar_poligono,
    analizar_proyectil,
    analizar_resorte,
)

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import Arrow, Dot

    from tpi_videos.dibujos import (
        ALTO_DIBUJO,
        oscilador,
        pendulo,
        pendulo_doble,
        poligono_regular,
        proyectil,
        resorte,
    )

ANCHO_HOJA = 7.0


@unittest.skipUnless(MANIM, "manim no está instalado")
class ContratoVivoTest(unittest.TestCase):
    def test_los_cinco_dibujos_declaran_su_tiempo_y_su_estela(self):
        figuras = [
            proyectil(analizar_proyectil("20 m/s", 30), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO),
            pendulo(analizar_pendulo("1 m", 20), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO),
            resorte(analizar_resorte("200 N/m", "10 cm"), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO),
            oscilador(
                analizar_oscilador("2 kg", "200 N/m", "10 cm"), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
            ),
            pendulo_doble(
                analizar_pendulo_doble("1 kg", "1 kg", "1 m", "1 m", 170.0, 170.0),
                [],
                ColoresTema(),
                ANCHO_HOJA,
                ALTO_DIBUJO,
            ),
        ]
        for dib in figuras:
            with self.subTest(estela=dib.estela is not None):
                self.assertIsNotNone(dib.vivo)
                self.assertGreater(dib.duracion or 0.0, 0.0)
                self.assertIsNotNone(dib.estela)
                self.assertIn(dib.estela, dib.mobs.submobjects)

    def test_un_dibujo_quieto_sigue_sin_movimiento(self):
        dib = poligono_regular(analizar_poligono(5, "12 cm"), [], ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        self.assertIsNone(dib.vivo)
        self.assertIsNone(dib.duracion)


@unittest.skipUnless(MANIM, "manim no está instalado")
class ProyectilVivoTest(unittest.TestCase):
    def _dib(self, marcas=()):
        return proyectil(
            analizar_proyectil("20 m/s", 30), list(marcas), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO
        )

    def _bola(self, dib):
        return min(
            (m for m in dib.mobs.get_family() if isinstance(m, Dot)),
            key=lambda m: m.get_center()[0],
        )

    def test_la_bola_sube_y_baja_en_el_orden_correcto(self):
        dib = self._dib()
        ys = []
        for p in (0.0, 0.25, 0.5, 0.75, 1.0):
            dib.vivo(p)
            ys.append(self._bola(dib).get_center()[1])
        self.assertLess(ys[0], ys[1])
        self.assertLess(ys[1], ys[2])
        self.assertGreater(ys[2], ys[3])
        self.assertGreater(ys[3], ys[4])
        self.assertAlmostEqual(ys[0], ys[4], places=3)

    def test_la_vy_se_apaga_y_se_invierte_en_la_bajada(self):
        def vertical(dib):
            return next(
                f
                for f in dib.mobs.get_family()
                if isinstance(f, Arrow) and abs((f.get_end() - f.get_start())[0]) < 1e-6
            )

        dib = self._dib(("componentes",))
        dib.vivo(0.0)
        arriba = vertical(dib).get_end()[1] - vertical(dib).get_start()[1]
        dib.vivo(0.9)
        abajo = vertical(dib).get_end()[1] - vertical(dib).get_start()[1]
        self.assertGreater(arriba, 0)
        self.assertLess(abajo, 0)


@unittest.skipUnless(MANIM, "manim no está instalado")
class PenduloVivoTest(unittest.TestCase):
    def _dib(self, marcas=()):
        return pendulo(analizar_pendulo("1 m", 20), list(marcas), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)

    def _bola(self, dib):
        return max((m for m in dib.mobs.get_family() if isinstance(m, Dot)), key=lambda m: m.radius)

    def test_una_vuelta_completa_dura_el_periodo(self):
        figura = analizar_pendulo("1 m", 20)
        self.assertAlmostEqual(self._dib().duracion, figura.periodo, places=6)

    def test_la_bola_cruza_la_vertical_a_media_vuelta(self):
        dib = self._dib()
        dib.vivo(0.0)
        x0 = self._bola(dib).get_center()[0]
        dib.vivo(0.5)
        self.assertGreater(self._bola(dib).get_center()[0], x0 + 0.2)

    def test_la_velocidad_se_mueve_solo_si_la_piden(self):
        self.assertFalse([m for m in self._dib().mobs.get_family() if isinstance(m, Arrow)])
        flechas = [m for m in self._dib(("velocidad",)).mobs.get_family() if isinstance(m, Arrow)]
        self.assertEqual(len(flechas), 1)

    def test_la_velocidad_es_maxima_en_el_punto_mas_bajo(self):
        dib = self._dib(("velocidad",))
        flecha = next(m for m in dib.mobs.get_family() if isinstance(m, Arrow))
        dib.vivo(0.0)
        quieta = flecha.get_length()
        dib.vivo(0.25)
        self.assertGreater(flecha.get_length(), quieta)


@unittest.skipUnless(MANIM, "manim no está instalado")
class ResorteVivoTest(unittest.TestCase):
    def _dib(self):
        return resorte(
            analizar_resorte("200 N/m", "10 cm"),
            ["fuerza"],
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
        )

    def test_el_extremo_libre_avanza_de_la_reposo_a_la_estirda(self):
        dib = self._dib()
        espira = dib.trazo[2]
        dib.vivo(0.0)
        x0 = max(p[0] for p in espira.get_anchors())
        dib.vivo(1.0)
        x1 = max(p[0] for p in espira.get_anchors())
        self.assertGreater(x1, x0 + 0.2)

    def test_la_fuerza_crece_con_la_extension(self):
        dib = self._dib()
        dib.vivo(0.0)
        horizontales = [
            m
            for m in dib.mobs.get_family()
            if isinstance(m, Arrow) and abs(m.get_end()[1] - m.get_start()[1]) < 1e-6
        ]
        flecha = min(horizontales, key=lambda f: f.get_length())
        antes = flecha.get_length()
        dib.vivo(1.0)
        self.assertGreater(flecha.get_length(), antes + 0.1)

    def test_dura_lo_que_dice_la_constante(self):
        self.assertAlmostEqual(self._dib().duracion, DURACION_RESORTE)


@unittest.skipUnless(MANIM, "manim no está instalado")
class OsciladorVivoTest(unittest.TestCase):
    def _dib(self):
        return oscilador(
            analizar_oscilador("2 kg", "200 N/m", "10 cm", "8 N·s/m", 4.0),
            ["regimen"],
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
        )

    def test_la_curva_guia_queda_tenue_y_el_punto_la_recorre(self):
        dib = self._dib()
        punto = max((m for m in dib.mobs.get_family() if isinstance(m, Dot)), key=lambda m: m.radius)
        dib.vivo(0.0)
        x0 = punto.get_center()[0]
        dib.vivo(0.5)
        self.assertGreater(punto.get_center()[0], x0)
        self.assertLessEqual(dib.trazo[2].get_stroke_width(), 3.5)

    def test_dura_los_segundos_integrados(self):
        figura = analizar_oscilador("2 kg", "200 N/m", "10 cm", "8 N·s/m", 4.0)
        self.assertAlmostEqual(self._dib().duracion, figura.hasta)


@unittest.skipUnless(MANIM, "manim no está instalado")
class PenduloDobleVivoTest(unittest.TestCase):
    def _dib(self):
        return pendulo_doble(
            analizar_pendulo_doble("1 kg", "1 kg", "1 m", "1 m", 170.0, 170.0, duracion=3.0),
            [],
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
        )

    def test_los_brazos_se_mueven_con_la_integral(self):
        dib = self._dib()
        bola = max((m for m in dib.mobs.get_family() if isinstance(m, Dot)), key=lambda m: m.radius)
        dib.vivo(0.0)
        inicio = bola.get_center().copy()
        dib.vivo(0.5)
        self.assertGreater(float(np.linalg.norm(bola.get_center() - inicio)), 0.1)

    def test_la_duracion_es_el_tiempo_integrado(self):
        figura = analizar_pendulo_doble("1 kg", "1 kg", "1 m", "1 m", 170.0, 170.0, duracion=3.0)
        self.assertAlmostEqual(self._dib().duracion, figura.t[-1] - figura.t[0])


if __name__ == "__main__":
    unittest.main()
