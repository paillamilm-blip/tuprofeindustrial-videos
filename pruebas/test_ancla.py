import unittest

from tpi_videos.escena import Linea, olvida_en_ancla


def _linea() -> Linea:
    eq = object()
    return Linea(mobs=[eq], eq=eq)


class OlvidaEnAnclaTest(unittest.TestCase):
    def test_deja_solo_la_ultima_correcta(self):
        a, b, c = _linea(), _linea(), _linea()
        self.assertEqual(olvida_en_ancla([a, b, c], c.eq), [a, b])

    def test_sin_ancla_no_queda_nada_en_la_pizarra(self):
        """Un guion que arranca con errores tachados no tiene de dónde venir todavía."""
        a, b = _linea(), _linea()
        self.assertEqual(olvida_en_ancla([a, b], None), [a, b])

    def test_una_sola_linea_no_se_olvida_a_si_mesma(self):
        a = _linea()
        self.assertEqual(olvida_en_ancla([a], a.eq), [])

    def test_vacia_sigue_vacia(self):
        self.assertEqual(olvida_en_ancla([], None), [])


if __name__ == "__main__":
    unittest.main()
