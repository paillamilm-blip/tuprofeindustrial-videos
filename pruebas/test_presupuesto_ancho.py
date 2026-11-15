"""Presupuesto de ancho de la fila (nota + fórmula): el resplandor, el recuadro y el emoji
tienen que caber dentro del ancho útil, no salirse de él ni montarse uno sobre otro."""

import unittest

from tpi_videos import componentes as c

try:
    from manim import LEFT, RIGHT, Rectangle, VGroup

    MANIM = True
except ModuleNotFoundError:  # Manim no está instalado en este equipo: esto se prueba en CI
    MANIM = False


class PresupuestoAnchoTest(unittest.TestCase):
    def test_sin_emoji_reserva_el_resplandor_por_lado(self):
        # La fila ocupa el ancho útil menos el halo (HOLGURA_HALO) a cada lado.
        self.assertAlmostEqual(c.ancho_para_fila(7.0), 7.0 - 2 * c.HOLGURA_HALO)

    def test_con_emoji_reserva_halo_mas_emoji_y_su_aire(self):
        ancho = c.ancho_para_fila(7.0, 0.8)
        # fila + halo (dos lados) + emoji + separación = ancho útil exacto
        self.assertAlmostEqual(ancho + 2 * c.HOLGURA_HALO + 0.8 + c.BUFF_EMOJI, 7.0)

    def test_el_emoji_queda_fuera_del_resplandor(self):
        # El separador del emoji tiene que ser mayor que el halo: si no, el emoji se monta encima.
        self.assertGreater(c.BUFF_EMOJI, c.HOLGURA_HALO)


@unittest.skipIf(not MANIM, "manim no está instalado")
class FilaConHaloYEmojiTest(unittest.TestCase):
    """Una fila ajustada con ``ancho_para_fila``, con un halo en su término derecho y el emoji
    pegado, no se sale del ancho útil y el emoji no toca el resplandor."""

    def _fila(self, ancho_util: float, con_emoji: bool):
        ancho = c.ancho_para_fila(ancho_util, 0.8 if con_emoji else 0.0)
        termino = Rectangle(width=ancho, height=0.6)  # un término que llega justo al borde
        fila = VGroup(termino)
        emoji = Rectangle(width=0.8, height=0.78) if con_emoji else None
        hueco = 0.8 + c.BUFF_EMOJI if con_emoji else 0.0
        fila.shift(LEFT * hueco / 2)
        if emoji is not None:
            emoji.next_to(fila, RIGHT, buff=c.BUFF_EMOJI)
        halo = c.halo_de(termino, "#FFFFFF")  # el halo se crea ya ubicada la fila, como en la escena
        return fila, halo, emoji

    def test_sin_emoji_el_halo_no_se_sale_del_ancho_util(self):
        _, halo, _ = self._fila(7.0, False)
        self.assertLessEqual(halo.get_right()[0], 3.5 + 1e-6)
        self.assertGreaterEqual(halo.get_left()[0], -3.5 - 1e-6)

    def test_con_emoji_todo_cabe_y_el_emoji_no_toca_el_halo(self):
        _, halo, emoji = self._fila(7.0, True)
        self.assertLessEqual(emoji.get_right()[0], 3.5 + 1e-6)
        self.assertGreaterEqual(halo.get_left()[0], -3.5 - 1e-6)
        self.assertGreaterEqual(emoji.get_left()[0], halo.get_right()[0] - 1e-6)


if __name__ == "__main__":
    unittest.main()