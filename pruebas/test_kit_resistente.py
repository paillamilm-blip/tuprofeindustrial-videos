import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tpi_videos import publicar

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "guiones" / "ejemplos" / "fisica_caida_libre.yaml"


class KitResistenteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.carpeta = Path(self.tmp.name) / "salida" / "fisica-caida-libre"
        self.carpeta.mkdir(parents=True)
        (self.carpeta / "linea_de_tiempo.json").write_text(
            json.dumps({"guion": str(GUION), "calidad": "final"}), encoding="utf-8"
        )
        self.portada = self.carpeta / "portada.png"
        self.portada.write_bytes(b"x")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _kit_con(self, fallo: Exception) -> publicar.Kit:
        with (
            patch("tpi_videos.publicar.crear_portada", return_value=self.portada),
            patch("tpi_videos.ia.obtener_clave", return_value="clave"),
            patch("tpi_videos.publicar.textos_con_ia", side_effect=fallo),
        ):
            return publicar.crear_kit(self.carpeta, con_ia=True, modelo="gemini-3.8-flash")

    def test_un_error_raro_de_la_ia_no_bota_el_kit(self) -> None:
        kit = self._kit_con(ValueError("Invalid port: ':1]'"))
        self.assertFalse(kit.con_ia)
        self.assertTrue(kit.archivo.exists())
        self.assertIn("plantilla", kit.aviso)

    def test_el_error_esperado_tambien_cae_a_plantilla(self) -> None:
        from tpi_videos.errores import ErrorMotor

        kit = self._kit_con(ErrorMotor("sin cupo"))
        self.assertFalse(kit.con_ia)
        self.assertIn("sin cupo", kit.aviso)


if __name__ == "__main__":
    unittest.main()
