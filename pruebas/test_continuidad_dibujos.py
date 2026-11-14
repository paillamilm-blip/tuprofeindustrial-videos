"""El dibujo que se queda entre pasos, con piezas reales de Manim: lo igual se reconoce y solo cambia lo demás.

Necesita Manim (corre en el Mac). La parte sin Manim está en ``test_continuidad.py``.
"""

import unittest

from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import analizar_bloques

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:
    MANIM = False

if MANIM:
    from manim import Text

    from tpi_videos.continuidad import emparejar
    from tpi_videos.dibujos import ALTO_DIBUJO, bloques
    from tpi_videos.escena import clave_de_pieza, piezas_de

    ANCHO_HOJA = 6.2


@unittest.skipUnless(MANIM, "manim no está instalado")
class LazoQueSeQuedaTest(unittest.TestCase):
    def _lazo(self, marcas):
        dibujo = bloques(analizar_bloques("8", "0.5"), marcas, ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)
        dibujo.place(0, -2.0)
        return dibujo

    def _alinear(self, previo, dibujo):
        """Lo mismo que hace la escena: alinear por la base de la estructura (la caja G), no por el grupo."""
        delta = previo.trazo[0].get_center() - dibujo.trazo[0].get_center()
        destino = dibujo.mobs.get_center() + delta
        dibujo.place(float(destino[0]), float(destino[1]))

    def _letras_de(self, dibujo, empieza):
        """Las piezas (las letras) del rótulo que empieza así, ej. «GH =»."""
        rotulos = [
            m for m in dibujo.mobs.get_family() if isinstance(m, Text) and m.original_text.startswith(empieza)
        ]
        self.assertTrue(rotulos, f"el dibujo no tiene un rótulo «{empieza}…»")
        return {id(p) for r in rotulos for p in piezas_de(r)}

    def _repartir(self, previo, dibujo):
        return emparejar(piezas_de(previo.mobs), piezas_de(dibujo.mobs), clave_de_pieza, clave_de_pieza)

    def test_el_mismo_lazo_dos_veces_no_cambia_nada(self):
        previo, dibujo = self._lazo(["malla"]), self._lazo(["malla"])
        self._alinear(previo, dibujo)
        quedan, salen, entran = self._repartir(previo, dibujo)
        self.assertTrue(quedan)
        self.assertEqual((salen, entran), ([], []))

    def test_de_la_malla_al_lazo_cerrado_las_cajas_se_quedan(self):
        previo = self._lazo(["malla"])
        dibujo = self._lazo(["lazo_cerrado"])
        self._alinear(previo, dibujo)
        quedan, salen, entran = self._repartir(previo, dibujo)
        quietas = {id(n) for _, n in quedan}
        # Las cajas G y H, el comparador y las flechas no se vuelven a trazar.
        for pieza in dibujo.trazo:
            for p in piezas_de(pieza):
                self.assertIn(id(p), quietas, "una pieza de la estructura se habría vuelto a dibujar")
        # «G = 8» sigue escrito igual: sus letras se quedan quietas.
        self.assertLessEqual(self._letras_de(dibujo, "G = "), quietas)
        # Cambia solo lo escrito abajo: se va «GH = 4» y llega «T = …».
        self.assertLessEqual(self._letras_de(previo, "GH = "), {id(p) for p in salen})
        self.assertLessEqual(self._letras_de(dibujo, "T = "), {id(p) for p in entran})

    def test_sin_alinear_el_rotulo_nuevo_correria_el_lazo(self):
        """Por qué hace falta alinear: con el centro del grupo, el lazo entero se mueve y nada calza."""
        previo, dibujo = self._lazo([]), self._lazo(["malla"])
        quedan_sin, _, _ = self._repartir(previo, dibujo)
        self._alinear(previo, dibujo)
        quedan_con, _, _ = self._repartir(previo, dibujo)
        self.assertGreater(len(quedan_con), len(quedan_sin))


@unittest.skipUnless(MANIM, "manim no está instalado")
class CuerpoQueNoVuelveAGirarTest(unittest.TestCase):
    """La lata en 3D: el paso siguiente parte de la vista donde quedó el anterior."""

    def _lata(self, **campos):
        from tpi_videos.dibujos import dibujar_visual
        from tpi_videos.guion import Visual

        visual = Visual(tipo="solido_3d", figura="cilindro", radio="3 cm", altura="5 cm", **campos)
        return dibujar_visual(visual, ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)

    def _puntos(self, dibujo, t):
        import numpy as np
        from manim import VMobject

        dibujo.vivo(t)
        return np.concatenate([m.points for m in piezas_de(dibujo.mobs) if isinstance(m, VMobject)])

    def test_dice_en_que_vista_termina(self):
        self.assertEqual(self._lata(vista="axonometrica").vista_final, (60.0, -55.0))

    def test_sin_paso_anterior_gira_como_siempre(self):
        import numpy as np

        lata = self._lata(vista="axonometrica")
        self.assertFalse(np.allclose(self._puntos(lata, 0.0), self._puntos(lata, 1.0)))

    def test_si_sigue_en_la_misma_vista_no_vuelve_a_girar(self):
        import numpy as np

        from tpi_videos import dibujos as d

        marca = d.desde_vista.set((60.0, -55.0, False))
        try:
            lata = self._lata(vista="axonometrica")
        finally:
            d.desde_vista.reset(marca)
        self.assertTrue(np.allclose(self._puntos(lata, 0.0), self._puntos(lata, 1.0)))

    def test_la_variable_no_queda_puesta_para_el_dibujo_siguiente(self):
        from tpi_videos import dibujos as d

        self.assertIsNone(d.desde_vista.get())


if __name__ == "__main__":
    unittest.main()
