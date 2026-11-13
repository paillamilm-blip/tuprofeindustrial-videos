"""Los chequeos de un guion antes de aprobarlo (sin abrir el panel)."""

import unittest

from tpi_videos.panel.revision import AVISO, ERROR, HECHA, chequeos, hay_errores


def _marcas(**cambios):
    datos = {
        "error": None,
        "voces": 4,
        "tiene_metadatos": True,
        "estilo_disponible": True,
        "observaciones": 0,
    }
    return chequeos(**{**datos, **cambios})


def _estados(marcas):
    return {m.clave: m.estado for m in marcas}


class ChequeosTest(unittest.TestCase):
    def test_un_guion_sano_sale_todo_en_verde(self):
        marcas = _marcas()
        self.assertEqual({m.estado for m in marcas}, {HECHA})
        self.assertFalse(hay_errores(marcas))

    def test_un_guion_que_no_valida_sale_en_rojo(self):
        marcas = _marcas(error="falta el gancho", estilo_disponible=None)
        self.assertEqual(_estados(marcas)["valido"], ERROR)
        self.assertTrue(hay_errores(marcas))
        self.assertNotIn("estilo", _estados(marcas))  # sin guion válido no hay estilo que revisar

    def test_sin_voz_es_un_error(self):
        self.assertEqual(_estados(_marcas(voces=0))["voz"], ERROR)

    def test_sin_hashtags_es_un_aviso_no_un_error(self):
        marcas = _marcas(tiene_metadatos=False)
        self.assertEqual(_estados(marcas)["redes"], AVISO)
        self.assertFalse(hay_errores(marcas))  # el kit los escribe al publicar

    def test_un_estilo_que_no_esta_en_este_equipo_es_un_error(self):
        self.assertEqual(_estados(_marcas(estilo_disponible=False))["estilo"], ERROR)

    def test_las_dudas_de_la_ia_se_cuentan(self):
        uno = next(m for m in _marcas(observaciones=1) if m.clave == "dudas")
        varias = next(m for m in _marcas(observaciones=3) if m.clave == "dudas")
        self.assertEqual((uno.estado, uno.texto), (AVISO, "1 duda de la IA"))
        self.assertEqual(varias.texto, "3 dudas de la IA")

    def test_el_texto_para_lectores_de_pantalla(self):
        self.assertEqual(_marcas()[0].aria, "Guion válido: bien")
        self.assertEqual(
            _marcas(tiene_metadatos=False)[2].aria, "Sin hashtags: el kit los escribe: conviene revisarlo"
        )
        self.assertEqual(_marcas(voces=0)[1].aria, "Sin texto para la voz: hay que corregirlo")


if __name__ == "__main__":
    unittest.main()
