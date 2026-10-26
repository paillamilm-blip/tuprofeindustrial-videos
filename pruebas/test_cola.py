import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tpi_videos import cola
from tpi_videos.ideas import GanchoIdea, Idea


def _idea(titulo: str = "Reto de Ohm") -> Idea:
    return Idea(
        angulo="reto",
        titulo=titulo,
        gancho="¿Cuánto vale la corriente?",
        enunciado="Un circuito de 12 V y 4 ohm: ¿cuál es la corriente eléctrica?",
        materia="fisica",
        nivel="2° medio",
        porque="Porque reta al que mira.",
        segundos=45,
        molde="reto",
        ganchos=[GanchoIdea(texto="¿Cuánto vale la corriente?", estilo="curiosidad")],
    )


class BaseCola(unittest.TestCase):
    """Lo común a las dos clases de prueba: una carpeta temporal como raíz del motor."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.viejo = os.environ.get("TPI_RAIZ")
        os.environ["TPI_RAIZ"] = self.tmp.name
        self.raiz = Path(self.tmp.name)

    def tearDown(self) -> None:
        if self.viejo is None:
            os.environ.pop("TPI_RAIZ", None)
        else:
            os.environ["TPI_RAIZ"] = self.viejo
        self.tmp.cleanup()

    def _lote_con_video(self) -> str:
        lote_id = cola.nuevo_lote("Porcentajes", {"modelo": "gemini-3.8-flash"})
        cola.agregar_videos(lote_id, [_idea()])
        return lote_id


class ColaTest(BaseCola):
    def test_crear_actualizar_y_releer(self) -> None:
        lote_id = self._lote_con_video()
        video_id = cola.videos_del_lote(lote_id)[0]["id"]
        cola.actualizar_video(video_id, estado="animando", fase="animando", avance=0.5)
        cola.actualizar_lote(lote_id, estado="en_curso", fase="animando")

        lote = cola.cargar()["lotes"][0]
        self.assertEqual(lote["id"], lote_id)
        self.assertEqual(lote["estado"], "en_curso")
        self.assertEqual(lote["videos"][0]["estado"], "animando")
        self.assertEqual(lote["videos"][0]["avance"], 0.5)
        self.assertEqual(lote["ajustes"]["modelo"], "gemini-3.8-flash")

    def test_escritura_atomica_conserva_el_anterior(self) -> None:
        lote_id = self._lote_con_video()
        with patch("tpi_videos.cola.os.replace", side_effect=OSError("disco lleno")):
            with self.assertRaises(OSError):
                cola.actualizar_lote(lote_id, estado="fallo")
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "en_curso")

    def test_json_corrupto_se_aparta(self) -> None:
        ruta = self.raiz / "salida" / ".cola" / "trabajos.json"
        ruta.parent.mkdir(parents=True)
        ruta.write_text("{esto no es json", encoding="utf-8")

        self.assertEqual(cola.cargar()["lotes"], [])
        self.assertTrue(list(ruta.parent.glob("trabajos.json.roto-*")))

    def test_hito_se_guarda_y_se_relee(self) -> None:
        lote_id = self._lote_con_video()
        video_id = cola.videos_del_lote(lote_id)[0]["id"]
        cola.hito(video_id, "guion", {"ruta": "guiones/x.yaml"})

        hitos = cola.videos_del_lote(lote_id)[0]["hitos"]
        self.assertEqual(hitos["guion"]["ruta"], "guiones/x.yaml")

    def test_podar_conserva_veinte_terminados_y_lo_pendiente(self) -> None:
        pendiente = self._lote_con_video()
        for _ in range(22):
            lote_id = self._lote_con_video()
            video_id = cola.videos_del_lote(lote_id)[0]["id"]
            cola.actualizar_video(video_id, estado="listo")
            cola.actualizar_lote(lote_id, estado="listo")

        self.assertGreater(cola.podar(), 0)
        ids = [lote["id"] for lote in cola.cargar()["lotes"]]
        self.assertIn(pendiente, ids)
        self.assertEqual(len([i for i in ids if i != pendiente]), 20)

    def test_version_futura_no_se_sobrescribe(self) -> None:
        datos = {"version": 99, "lotes": []}
        with self.assertRaises(Exception):
            cola.guardar(datos)


if __name__ == "__main__":
    unittest.main()
