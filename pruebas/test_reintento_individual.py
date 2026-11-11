import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from nicegui import ui

from tpi_videos import cli, cola
from tpi_videos.errores import ErrorMotor
from tpi_videos.ideas import Idea
from tpi_videos.panel.paginas.fabrica import ColaLotes, PaginaFabrica
from tpi_videos.panel.tareas import Tarea

RAIZ = Path(__file__).resolve().parents[1]


class ReintentoIndividualTest(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        entorno = patch.dict(os.environ, {"TPI_RAIZ": temporal.name})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.ajustes = {
            "proveedor": "silencio",
            "voz": "es-CL-CatalinaNeural",
            "velocidad": "-12%",
            "calidad": "borrador",
            "estilo": "pizarra_nocturna",
            "subtitulos": False,
            "sincronizar": "estimado",
            "revisar_con_ia": False,
            "con_kit": False,
        }
        idea = Idea(
            angulo="reto", titulo="Mismo título", gancho="¿Cuánto tarda?",
            enunciado="Una caída libre", materia="fisica", nivel="2° medio",
            porque="Diagnóstico", segundos=45,
        )
        self.lote_id = cola.nuevo_lote("Lote ficticio", self.ajustes, ideas=[idea, idea, idea])
        self.guiones = []
        datos = (RAIZ / "guiones/ejemplos/fisica_caida_libre.yaml").read_bytes()
        for ficha, nombre in zip(cola.videos_del_lote(self.lote_id), ("uno", "dos", "tres"), strict=True):
            guion = self.raiz / "guiones" / f"{nombre}.yaml"
            guion.parent.mkdir(exist_ok=True)
            guion.write_bytes(datos)
            self.guiones.append(guion)
            cola.hito(ficha["id"], "guion", {"ruta": str(guion)})
            cola.actualizar_video(ficha["id"], estado="fallo", error="Fallo ficticio")
        self._video_guardado(1)
        cola.actualizar_video(f"{self.lote_id}-1", estado="listo", error=None)
        cola.recalcular_lote(self.lote_id)
        self.antes = copy.deepcopy(cola.videos_del_lote(self.lote_id))
        self.archivos_antes = self._archivos()
        self.renderizados = []
        self.fallar_render = False
        self.ultimo_resultado = {}
        self.panel = ColaLotes(self._lanzar)
        self.addCleanup(self.panel.zona.delete)
        for parche in (
            patch("tpi_videos.ideas.redactar", side_effect=AssertionError("No se debe regenerar el guion")),
            patch("tpi_videos.ideas.proponer_ideas", side_effect=AssertionError("No se deben pedir otras ideas")),
            patch("tpi_videos.render.crear_video", side_effect=self._renderizar),
        ):
            parche.start()
            self.addCleanup(parche.stop)

    def _archivos(self):
        return {
            str(archivo.relative_to(self.raiz)): archivo.read_bytes()
            for carpeta in (self.raiz / "guiones", self.raiz / "salida")
            for archivo in carpeta.rglob("*")
            if archivo.is_file() and ".cola" not in archivo.parts
        }

    def _video_guardado(self, posicion):
        guion = self.guiones[posicion - 1]
        carpeta = self.raiz / "salida" / guion.stem
        carpeta.mkdir(parents=True, exist_ok=True)
        video = carpeta / f"{guion.stem}.mp4"
        video.write_bytes(b"Video ya producido")
        cola.hito(f"{self.lote_id}-{posicion}", "video", {
            "video": str(video), "carpeta": str(carpeta), "duracion": 42.0,
            "lectura": 4.0, "segundos_proceso": 1.0, "srt": None,
            "fuentes_tiempo": [], "tema": "Pizarra nocturna",
        })
        return video

    def _renderizar(self, guion, **opciones):
        self.renderizados.append((guion.name, {
            campo: opciones[campo]
            for campo in ("proveedor", "voz", "velocidad", "calidad", "tema", "subtitulos", "sincronizar")
        }))
        if self.fallar_render:
            raise ErrorMotor("Fallo de render ficticio")
        carpeta = self.raiz / "salida" / guion.stem
        carpeta.mkdir(parents=True, exist_ok=True)
        video = carpeta / f"{guion.stem}.mp4"
        video.write_bytes(b"Render ficticio: " + guion.name.encode())
        return SimpleNamespace(
            video=video, carpeta=carpeta, duracion=42.0, lectura=4.0,
            segundos_proceso=1.0, srt=None, fuentes_tiempo=set(), tema="Pizarra nocturna",
        )

    def _correr(self, argumentos):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
            try:
                args = cli.construir_parser().parse_args([*argumentos, "--progreso-json", "--espera", "0"])
            except SystemExit:
                self.fail("El comando no admite seleccionar el video que se reintenta")
            codigo = cli.cmd_lote(args)
        for linea in salida.getvalue().splitlines():
            try:
                evento = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if evento.get("etapa") == "resultado":
                self.ultimo_resultado = evento
        return codigo

    def _lanzar(self, argumentos, nombre):
        self.assertEqual(self._correr(argumentos), 0)

    @staticmethod
    def _clic(zona, indice=0):
        botones = [elemento for elemento in zona.descendants() if getattr(elemento, "text", "") == "Intentar solo este"]
        if not botones:
            raise AssertionError("No está el botón de reintento")
        evento = next(e for e in botones[indice]._event_listeners.values() if e.type == "click")
        evento.handler(None)

    def _clic_cola(self, posicion):
        with self.panel.zona:
            self.panel._tarjeta(cola.elegir_lote(cola_id=self.lote_id))
        self._clic(self.panel.zona, posicion - 2)

    def _comprobar_otros(self, posicion):
        despues = cola.videos_del_lote(self.lote_id)
        for indice, ficha in enumerate(despues, start=1):
            if indice != posicion:
                self.assertEqual(ficha, self.antes[indice - 1])
        for nombre, datos in self.archivos_antes.items():
            self.assertEqual((self.raiz / nombre).read_bytes(), datos)
        self.assertEqual(len(cola.cargar()["lotes"]), 1)

    def test_el_boton_retoma_solo_el_segundo_video_y_sus_ajustes(self):
        self._clic_cola(2)
        fichas = cola.videos_del_lote(self.lote_id)
        self.assertEqual(fichas[1]["estado"], "listo")
        self.assertEqual(fichas[1]["hitos"]["guion"]["ruta"], str(self.guiones[1]))
        self.assertEqual(self.renderizados, [("dos.yaml", {
            "proveedor": "silencio", "voz": "es-CL-CatalinaNeural", "velocidad": "-12%",
            "calidad": "borrador", "tema": "pizarra_nocturna", "subtitulos": False,
            "sincronizar": "estimado",
        })])
        self.assertEqual(self.ultimo_resultado["lote"][0]["video_id"], f"{self.lote_id}-2")
        self._comprobar_otros(2)

    def test_el_tercer_video_no_se_confunde_con_los_de_igual_titulo(self):
        self._clic_cola(3)
        fichas = cola.videos_del_lote(self.lote_id)
        self.assertEqual(fichas[2]["estado"], "listo")
        self.assertEqual([nombre for nombre, _ in self.renderizados], ["tres.yaml"])
        self.assertEqual(self.ultimo_resultado["lote"][0]["video_id"], f"{self.lote_id}-3")
        self._comprobar_otros(3)

    def test_un_nuevo_fallo_conserva_el_guion_y_la_ficha_original(self):
        self.fallar_render = True
        self._clic_cola(2)
        ficha = cola.videos_del_lote(self.lote_id)[1]
        self.assertEqual(ficha["estado"], "fallo")
        self.assertEqual(ficha["error"], "Fallo de render ficticio")
        self.assertEqual(ficha["hitos"], self.antes[1]["hitos"])
        self._comprobar_otros(2)

    def test_el_boton_del_resultado_reintenta_la_misma_ficha_tras_otro_fallo(self):
        self.fallar_render = True
        self._clic_cola(2)
        self.assertFalse(self.ultimo_resultado.get("pendiente"), "El reintento de uno no debe esperar resultados de los otros dos")
        self.renderizados.clear()
        pagina = PaginaFabrica()
        pagina.cola_lotes = self.panel
        pagina.zona_resultado = ui.column()
        self.addCleanup(pagina.zona_resultado.delete)
        tarea = Tarea("Reintento", [], terminada=True, cola_id=self.lote_id, resultado=self.ultimo_resultado)
        pagina._mostrar_resultado(tarea)
        self.fallar_render = False
        self._clic(pagina.zona_resultado)
        self.assertEqual([nombre for nombre, _ in self.renderizados], ["dos.yaml"])
        self.assertEqual(cola.videos_del_lote(self.lote_id)[1]["estado"], "listo")
        self._comprobar_otros(2)

    def test_si_solo_falla_el_kit_no_se_repite_el_video(self):
        video = self._video_guardado(2)
        cola.actualizar_lote(self.lote_id, ajustes={**self.ajustes, "con_kit": True})
        datos = video.read_bytes()
        with patch("tpi_videos.publicar.crear_kit", side_effect=ErrorMotor("Fallo de kit ficticio")):
            self._clic_cola(2)
        ficha = cola.videos_del_lote(self.lote_id)[1]
        self.assertEqual(ficha["error"], "Fallo de kit ficticio")
        self.assertEqual(ficha["hitos"]["video"]["video"], str(video))
        self.assertEqual(video.read_bytes(), datos)
        self.assertEqual(self.renderizados, [])
        self._comprobar_otros(2)

    def test_un_video_de_otro_lote_no_modifica_ninguno(self):
        ajeno = cola.nuevo_lote("Otro lote", {}, ideas=[Idea.model_validate(self.antes[0]["idea"])])
        antes = copy.deepcopy(cola.cargar())
        with self.assertRaises(ErrorMotor):
            self._correr(["lote", "--reanudar", "--cola-id", self.lote_id, "--video-id", f"{ajeno}-1"])
        self.assertEqual(cola.cargar(), antes)
        self.assertEqual(self.renderizados, [])

    def test_el_reintento_no_poda_lotes_ajenos(self):
        idea = Idea.model_validate(self.antes[0]["idea"])
        for numero in range(21):
            lote_id = cola.nuevo_lote(f"Terminado {numero}", {}, ideas=[idea])
            cola.actualizar_video(f"{lote_id}-1", estado="listo")
            cola.recalcular_lote(lote_id)
        descartado = cola.nuevo_lote("Descartado", {}, ideas=[idea])
        cola.actualizar_lote(descartado, estado="descartado")
        antes = [lote for lote in cola.cargar()["lotes"] if lote["id"] != self.lote_id]
        self._correr(["lote", "--reanudar", "--cola-id", self.lote_id, "--video-id", f"{self.lote_id}-2"])
        despues = [lote for lote in cola.cargar()["lotes"] if lote["id"] != self.lote_id]
        self.assertEqual(despues, antes)
        self.assertEqual([nombre for nombre, _ in self.renderizados], ["dos.yaml"])

    def test_un_selector_vacio_se_rechaza_sin_modificar_la_cola(self):
        antes = copy.deepcopy(cola.cargar())
        for argumentos in (
            ["lote", "--video-id", ""],
            ["lote", "--reanudar", "--cola-id", self.lote_id, "--video-id", ""],
        ):
            with self.subTest(argumentos=argumentos), self.assertRaises(ErrorMotor):
                self._correr(argumentos)
        self.assertEqual(cola.cargar(), antes)
        self.assertEqual(self.renderizados, [])

    def test_el_selector_exige_reanudar_y_el_lote(self):
        for argumentos in (
            ["lote", "--video-id", f"{self.lote_id}-2"],
            ["lote", "--reanudar", "--video-id", f"{self.lote_id}-2"],
        ):
            with self.subTest(argumentos=argumentos), self.assertRaises(ErrorMotor):
                self._correr(argumentos)
        self.assertEqual(self.renderizados, [])
        self.assertEqual(cola.videos_del_lote(self.lote_id), self.antes)

    def test_un_reintento_individual_con_workers_dos_no_lanza_otros_videos(self):
        with patch("concurrent.futures.ProcessPoolExecutor", side_effect=AssertionError("No debe abrir un pool para un video")):
            self._correr(["lote", "--reanudar", "--cola-id", self.lote_id, "--video-id", f"{self.lote_id}-3", "--workers", "2"])
        self.assertEqual([nombre for nombre, _ in self.renderizados], ["tres.yaml"])
        self._comprobar_otros(3)

    def test_el_tablero_muestra_el_avance_del_video_seleccionado(self):
        from tpi_videos.panel.paginas.tablero import _en_vivo

        tarea = Tarea("Reintento", ["lote", "--reanudar", "--cola-id", self.lote_id, "--video-id", f"{self.lote_id}-3"])
        tarea.videos = {1: {"estado": "animando", "video_avance": 0.6, "detalle": "En curso"}}
        with patch("tpi_videos.panel.paginas.tablero.TAREAS.actual", tarea):
            self.assertEqual(_en_vivo(), {
                f"{self.lote_id}-3": {"estado": "animando", "avance": 0.6, "detalle": "En curso"},
            })

    def test_el_tablero_conserva_las_posiciones_del_lote_completo(self):
        from tpi_videos.panel.paginas.tablero import _en_vivo

        tarea = Tarea("Lote", ["lote", "--reanudar", "--cola-id", self.lote_id])
        tarea.videos = {1: {"estado": "listo"}, 2: {"estado": "animando", "avance": 0.6}}
        with patch("tpi_videos.panel.paginas.tablero.TAREAS.actual", tarea):
            self.assertEqual(set(_en_vivo()), {f"{self.lote_id}-1", f"{self.lote_id}-2"})

    def test_los_resultados_conservan_la_identidad_de_cada_video(self):
        self._correr(["lote", "--reanudar", "--cola-id", self.lote_id])
        self.assertEqual(
            [item.get("video_id") for item in self.ultimo_resultado["lote"]],
            [f"{self.lote_id}-1", f"{self.lote_id}-2", f"{self.lote_id}-3"],
        )

    def test_reanudar_el_lote_completo_sigue_funcionando(self):
        self._correr(["lote", "--reanudar", "--cola-id", self.lote_id])
        self.assertEqual([nombre for nombre, _ in self.renderizados], ["dos.yaml", "tres.yaml"])
        self.assertEqual([ficha["estado"] for ficha in cola.videos_del_lote(self.lote_id)], ["listo", "listo", "listo"])
        self.assertEqual(len(cola.cargar()["lotes"]), 1)


if __name__ == "__main__":
    unittest.main()
