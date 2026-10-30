import unittest

from tpi_videos.escena import AIRE_TAPA, CAIDA_CAJA, COLA_DE_VOZ, momento_del_destape


class MomentoDelDestapeTest(unittest.TestCase):
    def test_el_numero_queda_tapado_despues_de_que_la_caja_se_arma(self):
        """El bloque del hexágono dura 2,712 s: la tapa aguanta un rato más que la caída de la caja."""
        destape = momento_del_destape(2.712)
        self.assertGreaterEqual(destape, CAIDA_CAJA + AIRE_TAPA)
        self.assertLess(destape, 2.712)

    def test_una_frase_larga_no_guarda_el_numero_hasta_el_final(self):
        destape = momento_del_destape(8.0)
        self.assertLess(destape, 8.0 - COLA_DE_VOZ)

    def test_un_bloque_breve_no_se_levanta_antes_de_tapar(self):
        """Con el 55 % a secas, un bloque de dos segundos destapaba antes de que cayera la caja."""
        self.assertGreaterEqual(momento_del_destape(1.0), CAIDA_CAJA)
        self.assertGreaterEqual(momento_del_destape(2.0), CAIDA_CAJA)

    def test_a_frase_mas_larga_destape_mas_tarde(self):
        self.assertGreaterEqual(momento_del_destape(5.0), momento_del_destape(3.0))

    def test_el_destape_cae_dentro_de_la_voz(self):
        for duracion in (1.8, 2.712, 3.744, 6.0):
            self.assertLessEqual(momento_del_destape(duracion), duracion)


if __name__ == "__main__":
    unittest.main()
