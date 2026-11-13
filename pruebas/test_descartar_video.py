"""Sacar UN video de la cola sin llevarse a los demás de su lote."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tpi_videos import cola
from tpi_videos.errores import ErrorMotor
from tpi_videos.panel.supervision import COMPLETADOS, PENDIENTES, columnas


def _lote(*estados):
    return {
        "id": "L1",
        "tema": "Tema",
        "estado": "en_curso",
        "fase": "en_curso",
        "videos": [
            {"id": f"L1-{n}", "posicion": n, "estado": e, "avance": 0.0, "idea": {"titulo": f"Video {n}"}}
            for n, e in enumerate(estados, 1)
        ],
    }


class DescartarVideoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.viejo = os.environ.get("TPI_RAIZ")
        os.environ["TPI_RAIZ"] = self.tmp.name
        (Path(self.tmp.name) / "salida").mkdir()

    def tearDown(self) -> None:
        if self.viejo is None:
            os.environ.pop("TPI_RAIZ", None)
        else:
            os.environ["TPI_RAIZ"] = self.viejo
        self.tmp.cleanup()

    def _guardar(self, *estados):
        cola.guardar({"version": 1, "lotes": [_lote(*estados)]})

    def test_saca_solo_ese_video_y_deja_los_demas(self):
        self._guardar("en_cola", "en_cola", "listo")
        cola.descartar_video("L1-1")
        fichas = columnas(cola.cargar())
        self.assertEqual([f.video_id for f in fichas[PENDIENTES]], ["L1-2"])
        self.assertEqual([f.video_id for f in fichas[COMPLETADOS]], ["L1-3"])

    def test_un_video_listo_tambien_se_puede_sacar(self):
        self._guardar("listo", "listo")
        cola.descartar_video("L1-2")
        self.assertEqual([f.video_id for f in columnas(cola.cargar())[COMPLETADOS]], ["L1-1"])

    def test_si_era_el_ultimo_el_lote_queda_descartado(self):
        self._guardar("fallo")
        cola.descartar_video("L1-1")
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "descartado")

    def test_un_video_que_esta_produciendose_no_se_saca(self):
        self._guardar("animando", "en_cola")
        with self.assertRaises(ErrorMotor):
            cola.descartar_video("L1-1")
        self.assertEqual(cola.cargar()["lotes"][0]["videos"][0]["estado"], "animando")

    def test_con_un_lote_trabajando_no_se_toca_la_cola(self):
        self._guardar("en_cola")
        with patch.object(cola, "candado_tomado", return_value=True), self.assertRaises(ErrorMotor):
            cola.descartar_video("L1-1")
        self.assertEqual(cola.cargar()["lotes"][0]["videos"][0]["estado"], "en_cola")

    def test_un_video_que_no_existe_se_explica(self):
        self._guardar("en_cola")
        with self.assertRaises(ErrorMotor):
            cola.descartar_video("L9-9")


if __name__ == "__main__":
    unittest.main()
