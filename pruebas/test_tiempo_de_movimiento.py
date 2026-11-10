"""El movimiento nunca comprime la física: o entra en la voz o se corta y se avisa."""

import unittest

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from tpi_videos.escena import avance_de_movimiento, plan_de_movimiento


@unittest.skipUnless(MANIM, "manim no está instalado")
class VentanaDeMovimientoTest(unittest.TestCase):
    def test_si_la_voz_alcanza_se_ve_toda(self):
        self.assertEqual(avance_de_movimiento(2.5, 6.0), (1.0, False))

    def test_si_la_voz_no_alcanza_se_corta_y_se_avisa(self):
        avance, cortado = avance_de_movimiento(10.0, 7.0)
        self.assertAlmostEqual(avance, 0.7)
        self.assertTrue(cortado)

    def test_una_duracion_absurda_no_divide_por_cero(self):
        self.assertEqual(avance_de_movimiento(0.0, 3.0), (1.0, False))

    def test_el_plan_reserva_un_cuarto_para_que_entre_el_dibujo(self):
        entrada, ventana, avance, cortado = plan_de_movimiento(10.0, 8.0)
        self.assertAlmostEqual(entrada, 2.0)
        self.assertAlmostEqual(ventana, 6.0)
        self.assertAlmostEqual(avance, 0.6)
        self.assertTrue(cortado)

    def test_el_plan_nunca_se_come_la_voz(self):
        for restante in (1.0, 1.4, 3.0, 8.0, 20.0):
            entrada, ventana, _, _ = plan_de_movimiento(5.0, restante)
            self.assertAlmostEqual(entrada + ventana, restante)


@unittest.skipUnless(MANIM, "manim no está instalado")
class ElDibujoVivoTest(unittest.TestCase):
    """La rama viva no toca la física: la recorre y deja la pose final puesta."""

    def _trampa(self):
        from manim import VGroup

        from tpi_videos.dibujos import Dibujo
        from tpi_videos.escena import VideoEjercicio

        posiciones: list[float] = []

        class _Trampa:
            def __init__(self):
                self.jugadas = []

            def play(self, *animaciones, run_time=None, **_kwargs):
                self.jugadas.append(run_time)

            def add(self, *_mobs):
                pass

            def remove(self, *_mobs):
                pass

        return VideoEjercicio, Dibujo, VGroup, posiciones, _Trampa()

    def test_la_rama_viva_usa_el_tiempo_fisico_y_no_el_de_la_voz(self):
        VideoEjercicio, Dibujo, VGroup, posiciones, trampa = self._trampa()
        # 6 s de física caben justos en la ventana de 6 s (voz de 8 s): se ve entera, sin estirar.
        dib = Dibujo(mobs=VGroup(), vivo=posiciones.append, duracion=6.0)
        VideoEjercicio._mover_dibujo(trampa, dib, 6.0, 8.0, [])
        self.assertIn(6.0, trampa.jugadas)  # la física entera, no los 8 s de voz
        self.assertEqual(posiciones[-1], 1.0)

    def test_si_la_fisica_no_cabe_deja_la_pose_del_corte(self):
        VideoEjercicio, Dibujo, VGroup, posiciones, trampa = self._trampa()
        dib = Dibujo(mobs=VGroup(), vivo=posiciones.append, duracion=10.0)
        VideoEjercicio._mover_dibujo(trampa, dib, 10.0, 8.0, [])
        self.assertIn(6.0, trampa.jugadas)  # sólo el trozo que cabe en la voz
        self.assertAlmostEqual(posiciones[-1], 0.6)  # la pose del corte, nunca la física comprimida

    def test_lo_que_se_anima_es_el_dibujo_y_no_un_reloj_aparte(self):
        """Manim congela en una imagen todo lo que no es el objeto animado: con un reloj aparte la
        pose cambiaba pero el dibujo no se volvía a pintar y el video salía quieto."""
        VideoEjercicio, Dibujo, VGroup, posiciones, trampa = self._trampa()
        animadas = []
        trampa.play = lambda *anims, run_time=None, **_k: (
            animadas.extend(anims),
            trampa.jugadas.append(run_time),
        )
        dib = Dibujo(mobs=VGroup(), vivo=posiciones.append, duracion=6.0)
        VideoEjercicio._mover_dibujo(trampa, dib, 6.0, 8.0, [])
        self.assertIs(animadas[-1].mobject, dib.mobs)

    def test_sin_fisica_el_recorrido_llena_la_voz_y_llega_al_final(self):
        VideoEjercicio, Dibujo, VGroup, posiciones, trampa = self._trampa()
        dib = Dibujo(mobs=VGroup(), vivo=posiciones.append, duracion=4.0, fisico=False)
        VideoEjercicio._mover_dibujo(trampa, dib, 4.0, 12.0, [])
        self.assertIn(9.0, trampa.jugadas)  # 12 s de voz − 3 s de entrada: no se queda en 4 s
        self.assertEqual(posiciones[0], 0.0)
        self.assertEqual(posiciones[-1], 1.0)


if __name__ == "__main__":
    unittest.main()
