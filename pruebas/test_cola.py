import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tpi_videos import cola
from tpi_videos.errores import ErrorMotor
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


class ColaLifecycleTest(BaseCola):
    def _video(self, lote_id: str) -> str:
        return cola.videos_del_lote(lote_id)[0]["id"]

    def _ruta_candado(self) -> Path:
        ruta = self.raiz / "salida" / ".cola" / "lote.lock"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        return ruta

    def _hijo_vivo(self) -> subprocess.Popen:
        proceso = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(proceso.kill)
        self.addCleanup(proceso.wait)
        return proceso

    def _escribir_candado(self, pid: int, hace: float = 0.0) -> None:
        self._ruta_candado().write_text(
            json.dumps({"pid": pid, "inicio": time.time() - hace}), encoding="utf-8"
        )

    def test_pid_vivo_reconoce_el_propio_y_el_cero(self) -> None:
        self.assertTrue(cola._pid_vivo(os.getpid()))
        self.assertFalse(cola._pid_vivo(0))

    def test_no_pisa_un_candado_vivo_aunque_no_se_pueda_leer(self) -> None:
        hijo = self._hijo_vivo()
        self._escribir_candado(hijo.pid)

        with patch("tpi_videos.cola._candado", return_value=None):
            self.assertFalse(cola.tomar_candado())
        self.assertEqual(json.loads(self._ruta_candado().read_text(encoding="utf-8"))["pid"], hijo.pid)

    def test_reescribe_el_candado_abandonado_con_su_pid(self) -> None:
        proceso = subprocess.Popen([sys.executable, "-c", ""])
        proceso.wait()
        self._escribir_candado(proceso.pid)

        self.assertTrue(cola.tomar_candado())
        self.assertEqual(json.loads(self._ruta_candado().read_text(encoding="utf-8"))["pid"], os.getpid())
        cola.soltar_candado()

    def test_soltar_no_borra_el_candado_ajeno(self) -> None:
        hijo = self._hijo_vivo()
        self._escribir_candado(hijo.pid)

        cola.soltar_candado()
        self.assertTrue(self._ruta_candado().exists())

    def test_guardar_renueva_el_candado_propio(self) -> None:
        self.assertTrue(cola.tomar_candado())
        try:
            self._escribir_candado(os.getpid(), hace=11 * 3600)
            cola.guardar(cola.cargar())

            inicio = json.loads(self._ruta_candado().read_text(encoding="utf-8"))["inicio"]
            self.assertTrue(cola.candado_tomado())
            self.assertLess(time.time() - inicio, 60)
        finally:
            cola.soltar_candado()

    def test_guardar_no_renueva_el_candado_ajeno(self) -> None:
        hijo = self._hijo_vivo()
        self._escribir_candado(hijo.pid, hace=11 * 3600)

        cola.guardar(cola.cargar())
        datos = json.loads(self._ruta_candado().read_text(encoding="utf-8"))
        self.assertEqual(datos["pid"], hijo.pid)
        self.assertGreater(time.time() - datos["inicio"], 10 * 3600)

    def test_candado_propio_y_liberado(self) -> None:
        self.assertTrue(cola.tomar_candado())
        self.assertTrue(cola.candado_tomado())
        cola.soltar_candado()
        self.assertFalse(cola.candado_tomado())

    def test_candado_de_un_proceso_muerto_se_toma(self) -> None:
        ruta = self.raiz / "salida" / ".cola" / "lote.lock"
        ruta.parent.mkdir(parents=True)
        proceso = subprocess.Popen([sys.executable, "-c", ""])
        proceso.wait()
        ruta.write_text(
            json.dumps({"pid": proceso.pid, "inicio": time.time()}), encoding="utf-8"
        )

        self.assertFalse(cola.candado_tomado())
        self.assertTrue(cola.tomar_candado())

    def test_candado_viejo_se_considera_abandonado(self) -> None:
        ruta = self.raiz / "salida" / ".cola" / "lote.lock"
        ruta.parent.mkdir(parents=True)
        ruta.write_text(
            json.dumps({"pid": os.getpid(), "inicio": time.time() - 13 * 3600}),
            encoding="utf-8",
        )
        self.assertFalse(cola.candado_tomado())

    def test_normalizar_no_toca_nada_con_el_candado_tomado(self) -> None:
        lote_id = self._lote_con_video()
        cola.actualizar_video(self._video(lote_id), estado="animando", fase="animando", avance=0.55)
        cola.tomar_candado()
        try:
            self.assertEqual(cola.normalizar_interrumpidos(), 0)
            self.assertEqual(cola.videos_del_lote(lote_id)[0]["estado"], "animando")
        finally:
            cola.soltar_candado()

    def test_normalizar_marca_interrumpido_y_deriva_el_lote(self) -> None:
        lote_id = self._lote_con_video()
        cola.actualizar_video(self._video(lote_id), estado="animando", fase="animando", avance=0.55)

        self.assertEqual(cola.normalizar_interrumpidos(), 1)
        video = cola.videos_del_lote(lote_id)[0]
        self.assertEqual(video["estado"], "interrumpido")
        self.assertIn("55", video["detalle"])
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "interrumpido")

    def test_normalizar_un_lote_sin_ideas_lo_deja_pendiente(self) -> None:
        lote_id = cola.nuevo_lote("Porcentajes", {})
        cola.normalizar_interrumpidos()
        lote = cola.cargar()["lotes"][0]
        self.assertEqual(lote["id"], lote_id)
        self.assertEqual(lote["estado"], "pendiente_ia")

    def test_elegir_lote_pendiente_y_saltar_interrumpido(self) -> None:
        listo = self._lote_con_video()
        cola.actualizar_video(self._video(listo), estado="listo")
        cola.recalcular_lote(listo)

        pendiente = self._lote_con_video()
        video_id = self._video(pendiente)
        cola.actualizar_video(video_id, estado="pendiente_ia")
        cola.recalcular_lote(pendiente)

        self.assertEqual(cola.elegir_lote(solo_pendientes=True)["id"], pendiente)

        cola.actualizar_video(video_id, estado="interrumpido")
        cola.recalcular_lote(pendiente)
        self.assertIsNone(cola.elegir_lote(solo_pendientes=True))
        self.assertEqual(cola.elegir_lote(cola_id=pendiente)["id"], pendiente)

    def test_pendientes_ia_encuentra_lotes_y_videos(self) -> None:
        sin_ideas = cola.nuevo_lote("Porcentajes", {})
        cola.normalizar_interrumpidos()
        con_video = self._lote_con_video()
        cola.actualizar_video(self._video(con_video), estado="pendiente_ia")
        cola.recalcular_lote(con_video)

        ids = [lote["id"] for lote in cola.pendientes_ia()]
        self.assertEqual(ids, [sin_ideas, con_video])

    def test_descartar_con_el_candado_tomado_avisa(self) -> None:
        lote_id = self._lote_con_video()
        cola.tomar_candado()
        try:
            with self.assertRaises(ErrorMotor):
                cola.descartar_lote(lote_id)
        finally:
            cola.soltar_candado()
        cola.descartar_lote(lote_id)
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "descartado")
        self.assertEqual(cola.lotes_visibles(), [])

    def test_lotes_visibles_muestra_pendientes_y_el_ultimo(self) -> None:
        viejo = self._lote_con_video()
        cola.actualizar_video(self._video(viejo), estado="listo")
        cola.recalcular_lote(viejo)
        nuevo = self._lote_con_video()

        ids = [lote["id"] for lote in cola.lotes_visibles()]
        self.assertEqual(ids, [nuevo])
        self.assertEqual(cola.ultimo_lote()["id"], nuevo)

    def test_podar_no_toca_nada_si_otro_proceso_trabaja(self) -> None:
        self._lote_con_video()
        with (
            patch("tpi_videos.cola.candado_tomado", return_value=True),
            patch("tpi_videos.cola._candado_es_mio", return_value=False),
        ):
            self.assertEqual(cola.podar(), 0)


if __name__ == "__main__":
    unittest.main()
