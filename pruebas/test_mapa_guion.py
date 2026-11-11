import unittest

from pydantic import ValidationError

from tpi_videos.guion import MapaColor, Paso


class MapaGuionTest(unittest.TestCase):
    def test_mapa_vacio_por_defecto(self):
        p = Paso(voz="hola")
        self.assertEqual(p.mapa, [])

    def test_mapa_con_termino_presente_valida(self):
        p = Paso(voz="hola", tex="x = 150 + 780 t", mapa=[{"termino": "780", "concepto": "velocidad"}])
        self.assertEqual(p.mapa[0].concepto, "velocidad")
        self.assertIsNone(p.mapa[0].color)

    def test_mapa_con_termino_ausente_falla(self):
        with self.assertRaises(ValidationError):
            Paso(voz="hola", tex="x = 150", mapa=[{"termino": "999", "concepto": "nada"}])

    def test_color_invalido_se_rechaza_antes_de_renderizar(self):
        with self.assertRaises(ValidationError):
            MapaColor(termino="x", concepto="posición", color="not-a-color")

    def test_color_hex_se_normaliza(self):
        self.assertEqual(MapaColor(termino="x", concepto="posición", color="#a78bfa").color, "#A78BFA")

    def test_mapa_no_admite_un_termino_de_solo_espaciado(self):
        for termino in (" ", r"\,", r"\quad"):
            with self.subTest(termino=termino), self.assertRaises(ValidationError):
                Paso(voz="hola", tex="x = 1", mapa=[{"termino": termino, "concepto": "vacío"}])

    def test_mapa_sin_tex_falla(self):
        with self.assertRaises(ValidationError):
            Paso(voz="hola", mapa=[{"termino": "780", "concepto": "velocidad"}])


if __name__ == "__main__":
    unittest.main()