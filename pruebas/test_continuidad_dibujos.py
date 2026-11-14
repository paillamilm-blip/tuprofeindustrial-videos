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


@unittest.skipUnless(MANIM, "manim no está instalado")
class PorteYLuzQueSeQuedanTest(unittest.TestCase):
    """El cuerpo 3D no cambia de tamaño ni de brillo al pasar a otra vista del mismo cuerpo."""

    def _lata(self, **campos):
        from tpi_videos.dibujos import dibujar_visual
        from tpi_videos.guion import Visual

        visual = Visual(tipo="solido_3d", figura="cilindro", radio="3 cm", altura="5 cm", **campos)
        return dibujar_visual(visual, ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)

    def _sigue(self, previo, **campos):
        """Lo mismo que hace la escena: el paso nuevo sabe con qué porte y luz quedó el anterior."""
        from tpi_videos import dibujos as d

        marca = d.desde_encuadre.set((previo.escala_3d, previo.luz_3d))
        try:
            return self._lata(**campos)
        finally:
            d.desde_encuadre.reset(marca)

    def test_cada_vista_tiene_su_porte(self):
        self.assertNotEqual(self._lata(vista="piso").escala_3d, self._lata(vista="ala").escala_3d)

    def test_el_porte_del_paso_anterior_se_conserva(self):
        piso = self._lata(vista="piso")
        ala = self._sigue(piso, vista="ala")
        self.assertAlmostEqual(ala.escala_3d, piso.escala_3d)

    def test_el_brillo_no_cambia_de_una_vista_a_otra(self):
        piso = self._lata(vista="piso")
        ala = self._sigue(piso, vista="ala")
        self.assertEqual(ala.luz_3d, piso.luz_3d)

    def test_si_la_vista_nueva_no_cabe_se_achica_lo_justo(self):
        ala = self._lata(vista="ala")  # el porte más grande de los dos
        piso = self._sigue(ala, vista="piso")
        self.assertLess(piso.escala_3d, ala.escala_3d)
        self.assertAlmostEqual(piso.escala_3d, self._lata(vista="piso").escala_3d)

    def test_el_encuadre_no_queda_puesto_para_el_dibujo_siguiente(self):
        from tpi_videos import dibujos as d

        self.assertIsNone(d.desde_encuadre.get())

@unittest.skipUnless(MANIM, "manim no está instalado")
class PorteDeLaSerieTest(unittest.TestCase):
    """Una serie 3D fija su porte antes de dibujar: cada paso entra con el mismo, no con el suyo.

    Al agregar notas o despiezar el grupo se ensancha y el encaje lo achicaría: el cuerpo se vería
    encoger de un paso a otro aunque la cámara no se haya movido.
    """

    def _portes(self, visuales):
        from types import SimpleNamespace

        from tpi_videos.escena import VideoEjercicio

        pasos = [SimpleNamespace(visual=v) for v in visuales]
        franja = {id(p): (0.0, -2.0, ALTO_DIBUJO) for p in pasos}
        escena = SimpleNamespace(
            receta=SimpleNamespace(partida="pila"),
            tema=SimpleNamespace(marco="pizarra"),
            col=ColoresTema(),
            guion=SimpleNamespace(pasos=pasos),
            _franja_del_dibujo=lambda paso, tope, techo=None: franja[id(paso)],
        )
        return VideoEjercicio._portes_de_las_series(escena, -1.0)

    def _lata(self, **campos):
        from tpi_videos.guion import Visual

        return Visual(tipo="solido_3d", figura="cilindro", radio="3 cm", altura="5 cm", **campos)

    def _escalas(self, visuales, portes=None):
        """El porte con que sale cada dibujo, medido en la misma franja y ancho que usa la escena."""
        from tpi_videos import componentes as c
        from tpi_videos import dibujos as d
        from tpi_videos.dibujos import dibujar_visual

        col = ColoresTema()
        escalas = []
        for i, visual in enumerate(visuales, 1):
            porte = (portes or {}).get(i)
            marca = d.desde_encuadre.set((porte, None)) if porte is not None else None
            try:
                dibujo = dibujar_visual(visual, col, c.ANCHO_UTIL, ALTO_DIBUJO, col.panel)
                escalas.append(dibujo.escala_3d)
            finally:
                if marca is not None:
                    d.desde_encuadre.reset(marca)
        return escalas

    def test_toda_la_serie_entra_con_el_mismo_porte(self):
        visuales = [
            self._lata(vista="piso"),
            self._lata(vista="axonometrica", anotar=["volumen"]),
            self._lata(vista="axonometrica", despiece=True, anotar=["area"]),
        ]
        propios = self._escalas(visuales)
        self.assertGreater(
            len({round(e, 4) for e in propios}), 1, "las notas deben cambiar el encaje; si no, la prueba no dice nada"
        )
        portes = self._portes(visuales)
        self.assertEqual(set(portes), {1, 2, 3})
        self.assertAlmostEqual(portes[1], min(propios))
        self.assertEqual(self._escalas(visuales, portes), [portes[1], portes[2], portes[3]])
        self.assertEqual(len({round(e, 6) for e in self._escalas(visuales, portes)}), 1)

    def test_un_cuerpo_en_un_solo_paso_no_se_toca(self):
        self.assertEqual(self._portes([self._lata(vista="piso")]), {})

    def test_otro_dibujo_en_medio_corta_la_serie(self):
        from tpi_videos.guion import Visual

        barras = Visual(tipo="barras", categorias=["Fútbol 12", "Básquetbol 8"])
        portes = self._portes([self._lata(vista="piso"), barras, self._lata(vista="piso")])
        self.assertEqual(portes, {})


if __name__ == "__main__":
    unittest.main()
