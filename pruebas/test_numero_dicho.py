"""El resaltado cuando la voz dice el número en letras, no en dígitos.

El gancho se escribe «3 + 4 + 12 = 19» y la voz lo lee «tres más cuatro más doce son diecinueve».
Si el motor busca el dígito en la transcripción no lo encuentra y el ping nunca suena: hay que
buscar también cómo se dice ese número.
"""

import unittest

from tpi_videos.componentes import busca_en_la_voz, numero_en_palabras

VOZ_DEL_GANCHO = "Tres más cuatro más doce son diecinueve. Pero un vector no mide diecinueve."


class NumeroEnPalabrasTest(unittest.TestCase):
    def test_del_cero_al_quince_salen_de_corrida(self):
        self.assertEqual(numero_en_palabras("0"), "cero")
        self.assertEqual(numero_en_palabras("7"), "siete")
        self.assertEqual(numero_en_palabras("12"), "doce")
        self.assertEqual(numero_en_palabras("15"), "quince")

    def test_del_dieciseis_al_veintinueve_se_escriben_juntos(self):
        self.assertEqual(numero_en_palabras("16"), "dieciséis")
        self.assertEqual(numero_en_palabras("19"), "diecinueve")
        self.assertEqual(numero_en_palabras("20"), "veinte")
        self.assertEqual(numero_en_palabras("21"), "veintiuno")
        self.assertEqual(numero_en_palabras("25"), "veinticinco")

    def test_de_treinta_en_adelante_llevan_y(self):
        self.assertEqual(numero_en_palabras("30"), "treinta")
        self.assertEqual(numero_en_palabras("31"), "treinta y uno")
        self.assertEqual(numero_en_palabras("45"), "cuarenta y cinco")
        self.assertEqual(numero_en_palabras("99"), "noventa y nueve")

    def test_las_centenas_tienen_su_nombre_propio(self):
        self.assertEqual(numero_en_palabras("100"), "cien")
        self.assertEqual(numero_en_palabras("101"), "ciento uno")
        self.assertEqual(numero_en_palabras("300"), "trescientos")
        self.assertEqual(numero_en_palabras("500"), "quinientos")
        self.assertEqual(numero_en_palabras("345"), "trescientos cuarenta y cinco")

    def test_los_miles_se_agrupan_de_a_tres(self):
        self.assertEqual(numero_en_palabras("1000"), "mil")
        self.assertEqual(numero_en_palabras("1500"), "mil quinientos")
        self.assertEqual(numero_en_palabras("2000"), "dos mil")
        self.assertEqual(numero_en_palabras("12345"), "doce mil trescientos cuarenta y cinco")

    def test_un_decimal_se_lee_coma(self):
        self.assertEqual(numero_en_palabras("9,8"), "nueve coma ocho")

    def test_lo_que_no_es_un_numero_no_se_inventa(self):
        self.assertIsNone(numero_en_palabras("vector"))
        self.assertIsNone(numero_en_palabras("1.000.000"))
        self.assertIsNone(numero_en_palabras("3.5"))


class BuscaEnLaVozTest(unittest.TestCase):
    def test_si_esta_escrito_lo_encontramos_como_esta(self):
        self.assertEqual(busca_en_la_voz("el largo es 12 cm", "12"), 12)

    def test_si_la_voz_lo_dice_en_letras_buscamos_como_suena(self):
        self.assertEqual(busca_en_la_voz(VOZ_DEL_GANCHO, "12"), VOZ_DEL_GANCHO.lower().index("doce"))
        self.assertEqual(busca_en_la_voz(VOZ_DEL_GANCHO, "3"), 0)
        self.assertEqual(busca_en_la_voz(VOZ_DEL_GANCHO, "19"), VOZ_DEL_GANCHO.lower().index("diecinueve"))

    def test_uno_se_dice_un_cuando_acompana_a_algo(self):
        self.assertEqual(busca_en_la_voz("avanza un centímetro", "1"), 7)

    def test_con_varios_un_no_se_adivina_cual_es_el_numero(self):
        """«Un vector avanza un centímetro» tiene dos «un»: resaltar el primero sonaría en la
        palabra equivocada, así que ese pingo no suena."""
        self.assertEqual(busca_en_la_voz("Un vector avanza un centímetro", "1"), -1)

    def test_no_cualquier_letra_es_el_numero(self):
        """'unidos' lleva 'dos' adentro: el ping no puede sonar ahí."""
        self.assertEqual(busca_en_la_voz("estamos unidos", "2"), -1)

    def test_lo_que_no_se_dijo_no_suena(self):
        self.assertEqual(busca_en_la_voz(VOZ_DEL_GANCHO, "7"), -1)
        self.assertEqual(busca_en_la_voz("hola", "vector"), -1)

    def test_una_palabra_normal_se_busca_como_se_busco_siempre(self):
        self.assertEqual(busca_en_la_voz("un vector que avanza", "vector"), 3)


if __name__ == "__main__":
    unittest.main()
