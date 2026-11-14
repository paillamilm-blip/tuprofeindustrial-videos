"""Avanzado: las cinco herramientas y cómo llegan las rutas antiguas (sin abrir el panel)."""

import unittest

from tpi_videos.panel.herramientas import HERRAMIENTAS, herramienta_de


class HerramientasTest(unittest.TestCase):
    def test_son_cinco_y_cada_una_dice_para_que_sirve(self):
        self.assertEqual(list(HERRAMIENTAS), ["crear", "cola", "videos", "estilos", "ajustes"])
        for clave, (nombre, icono, ayuda) in HERRAMIENTAS.items():
            with self.subTest(clave=clave):
                self.assertTrue(nombre and icono and ayuda)

    def test_una_ruta_antigua_abre_su_herramienta(self):
        for clave in HERRAMIENTAS:
            self.assertEqual(herramienta_de(clave), clave)

    def test_sin_ruta_o_con_una_desconocida_se_ven_las_tarjetas(self):
        self.assertIsNone(herramienta_de(None))
        self.assertIsNone(herramienta_de(""))
        self.assertIsNone(herramienta_de("no-existe"))


if __name__ == "__main__":
    unittest.main()
