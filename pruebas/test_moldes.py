import unittest

from tpi_videos.moldes import (
    MOLDE_POR_DEFECTO,
    MOLDES,
    moldes_para_ia,
    normalizar_molde,
    opciones_de_moldes,
)


class MoldesTest(unittest.TestCase):
    def test_normaliza_tildes_mayusculas_y_guiones(self):
        self.assertEqual(normalizar_molde("3 Errores"), "tres_errores")
        self.assertEqual(normalizar_molde("tres-errores"), "tres_errores")
        self.assertEqual(normalizar_molde("MITO vs REALIDAD"), "mito_realidad")
        self.assertEqual(normalizar_molde("Nadie te enseñó esto"), "nadie_te_enseno")
        self.assertEqual(normalizar_molde("POV"), "pov")
        self.assertEqual(normalizar_molde("reto"), "reto")

    def test_desconocido_no_se_inventa(self):
        self.assertEqual(normalizar_molde("bailar"), "")
        self.assertEqual(normalizar_molde(None), "")
        self.assertEqual(normalizar_molde(""), "")

    def test_catalogo_y_texto_para_la_ia(self):
        self.assertEqual(
            set(MOLDES), {"mito_realidad", "tres_errores", "pov", "reto", "nadie_te_enseno"}
        )
        self.assertEqual(MOLDE_POR_DEFECTO, "libre")
        tabla = moldes_para_ia()
        for clave in MOLDES:
            self.assertIn(clave, tabla)
            self.assertIn(clave, opciones_de_moldes())


if __name__ == "__main__":
    unittest.main()
