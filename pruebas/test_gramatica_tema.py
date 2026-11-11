import unittest

from pydantic import ValidationError

from tpi_videos.temas import ColoresTema, Gramatica, Tema


class GramaticaTemaTest(unittest.TestCase):
    def test_defaults_apagados(self):
        t = Tema(nombre="prueba")
        self.assertFalse(t.gramatica.tabs)
        self.assertFalse(t.gramatica.panel)
        self.assertFalse(t.gramatica.mapa_color)
        self.assertFalse(t.gramatica.micro)
        self.assertEqual(t.gramatica.paleta_pasos, [])
        self.assertEqual(t.layout.banda_panel, 0.0)

    def test_paleta_vacia_cicla_colores_del_tema(self):
        g = Gramatica(tabs=True)
        c = ColoresTema()
        self.assertEqual(g.paleta(c), [c.acento, c.cuadricula, c.exito, c.error, c.tenue])

    def test_paleta_propia_se_respeta(self):
        g = Gramatica(paleta_pasos=["#FF0000", "#00FF00"])
        self.assertEqual(g.paleta(ColoresTema()), ["#FF0000", "#00FF00"])

    def test_hex_invalido_falla(self):
        with self.assertRaises(ValidationError):
            Gramatica(paleta_pasos=["no-es-hex"])

    def test_banda_panel_fuera_de_rango_falla(self):
        with self.assertRaises(ValidationError):
            Tema(nombre="prueba", layout={"banda_panel": 9.0})

    def test_yaml_viejo_sigue_validando(self):
        t = Tema.model_validate({"nombre": "viejo", "marco": "pizarra"})
        self.assertFalse(t.gramatica.tabs)


if __name__ == "__main__":
    unittest.main()