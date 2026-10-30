import unittest

from tpi_videos.escena import (
    AIRE_TAPA,
    CAIDA_CAJA,
    COLA_DE_VOZ,
    momento_del_destape,
    tono_de_tapa,
)


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))


def _distancia(a: str, b: str) -> float:
    return sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b))) ** 0.5


def _luminosidad(color: str) -> float:
    return sum(_rgb(color)) / (3 * 255)


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


class TonoDeTapaTest(unittest.TestCase):
    """La tapa del resultado: en el tema de papel era un rectángulo blanco que borraba la rejilla.

    Tiene que parecer una nota pegada encima, no un hueco recortado en la hoja.
    """

    def test_se_aparta_del_papel_lo_suficiente_para_ver_el_borde(self):
        self.assertGreater(_distancia(tono_de_tapa("#FFFFFF", "#1F6FEB", 0.2), "#FFFFFF"), 8.0)

    def test_sigue_siendo_papel_y_no_el_acento_del_recuadro(self):
        tapa = tono_de_tapa("#FFFFFF", "#1F6FEB", 0.2)
        self.assertLess(_distancia(tapa, "#FFFFFF"), _distancia(tapa, "#1F6FEB"))

    def test_un_papel_oscuro_no_se_enciende(self):
        """El neón sobre azul noche: si la tapa tirara del cian se volvería un cartel, no una tapa."""
        tapa = tono_de_tapa("#0E1B26", "#22D3EE", 0.2)
        self.assertLess(_luminosidad(tapa), _luminosidad("#22D3EE"))
        self.assertLess(_luminosidad(tapa), 0.35)

    def test_mecharla_con_negro_la_oscurece(self):
        """La esquina doblada se saca de aquí: un pliegue es la misma nota más sombra."""
        self.assertLess(_luminosidad(tono_de_tapa("#FFFFFF", "#000000", 0.3)), _luminosidad("#FFFFFF"))

    def test_sin_mecla_es_el_papel_exacto(self):
        self.assertEqual(tono_de_tapa("#FFFFFF", "#1F6FEB", 0.0), "#FFFFFF")


if __name__ == "__main__":
    unittest.main()
