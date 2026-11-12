import asyncio
import inspect
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from nicegui import ui

from tpi_videos.errores import ErrorMotor
from tpi_videos.panel import biblioteca
from tpi_videos.panel.paginas.videos import PaginaVideos
from tpi_videos.panel.tareas import TAREAS, Tarea


class PapeleraTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.carpeta = self.raiz / "salida" / "video ficticio 'uno'"
        self.carpeta.mkdir(parents=True)
        self.guion = self.raiz / "guiones" / "uno.yaml"
        self.guion.parent.mkdir()
        self.guion.write_text("titulo: Guion intacto\n", encoding="utf-8")
        self.archivos = {
            f"{self.carpeta.name}.mp4": b"video ficticio",
            f"{self.carpeta.name}_borrador.mp4": b"borrador ficticio",
            "subtitulos.srt": b"subtitulos ficticios",
            "publicacion.json": b"{}",
            "linea_de_tiempo.json": json.dumps({
                "titulo": "Video ficticio",
                "duracion_total": 1,
                "bloques": [{"seccion": "gancho", "inicio": 0, "duracion": 1}],
            }).encode(),
            "media/segmento.mp4": b"segmento ficticio",
        }
        for nombre, datos in self.archivos.items():
            archivo = self.carpeta / nombre
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_bytes(datos)
        self.video = biblioteca.Video(
            self.carpeta, "Video ficticio", "Prueba", 1, 1,
            self.carpeta / f"{self.carpeta.name}.mp4",
            self.carpeta / f"{self.carpeta.name}_borrador.mp4", self.guion, None,
        )
        self.papelera = self.raiz / "papelera_ficticia"
        self.papelera.mkdir()
        self.respuesta = self._trasladar
        modulo = SimpleNamespace(
            NSURL=SimpleNamespace(fileURLWithPath_=lambda ruta: SimpleNamespace(path=lambda: ruta)),
            NSFileManager=SimpleNamespace(defaultManager=lambda: SimpleNamespace(
                trashItemAtURL_resultingItemURL_error_=lambda *args: self.respuesta(*args)
            )),
        )
        for parche in (
            patch("tpi_videos.panel.biblioteca.raiz_proyecto", return_value=self.raiz),
            patch("platform.system", return_value="Darwin"),
            patch.dict("sys.modules", {"Foundation": modulo}),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        self.pagina = PaginaVideos()
        self.addCleanup(self.pagina.capa.delete)
        self.avisos = []
        parche = patch("tpi_videos.panel.paginas.videos.ui.notify", side_effect=self._aviso)
        parche.start()
        self.addCleanup(parche.stop)

    def _aviso(self, texto, **opciones):
        self.avisos.append((texto, opciones.get("type")))

    def _trasladar(self, url, resultado, error):
        origen = Path(url.path())
        destino = self.papelera / origen.name
        indice = 1
        while destino.exists():
            destino = self.papelera / f"{origen.name}_{indice}"
            indice += 1
        origen.rename(destino)
        return True, SimpleNamespace(path=lambda: str(destino)), None

    def _contenido(self, carpeta):
        return {
            archivo.relative_to(carpeta).as_posix(): archivo.read_bytes()  # «media/x» también en Windows
            for archivo in carpeta.rglob("*") if archivo.is_file()
        }

    async def _confirmar(self):
        acciones = []
        with patch("tpi_videos.panel.paginas.videos.confirmar", side_effect=lambda pregunta, accion, **kw: acciones.append(accion)), patch.object(self.pagina.lista, "refresh"):
            self.pagina._borrar(self.video)
            if acciones:
                resultado = acciones[0]()
                if inspect.isawaitable(resultado):
                    await resultado

    def test_trasladar_conserva_todos_los_archivos_y_el_guion(self):
        destino = biblioteca.borrar(self.video)
        self.assertEqual(destino, self.papelera / self.carpeta.name)
        self.assertFalse(self.carpeta.exists())
        self.assertEqual(self._contenido(destino), self.archivos)
        self.assertEqual(self.guion.read_text(encoding="utf-8"), "titulo: Guion intacto\n")
        self.assertEqual(biblioteca.videos(), [])

    def test_un_homonimo_en_la_papelera_no_se_sobrescribe(self):
        anterior = self.papelera / self.carpeta.name
        anterior.mkdir()
        (anterior / "anterior.txt").write_bytes(b"conservar")
        destino = biblioteca.borrar(self.video)
        self.assertEqual((anterior / "anterior.txt").read_bytes(), b"conservar")
        self.assertEqual(destino, self.papelera / f"{self.carpeta.name}_1")
        self.assertEqual(self._contenido(destino), self.archivos)

    def test_rutas_ajenas_anidadas_y_enlaces_no_se_trasladan(self):
        fuera = self.raiz / "ajeno"
        fuera.mkdir()
        anidada = self.carpeta / "media"
        enlace = self.raiz / "salida" / "enlace"
        enlace.symlink_to(self.carpeta, target_is_directory=True)
        for ruta in (fuera, self.raiz / "salida", anidada, enlace):
            with self.subTest(ruta=ruta):
                self.video.carpeta = ruta
                with self.assertRaises(ErrorMotor):
                    biblioteca.borrar(self.video)
                self.assertTrue(ruta.exists())
                self.assertEqual(list(self.papelera.iterdir()), [])

    def test_un_video_que_ya_no_existe_no_reporta_exito(self):
        self.carpeta.rename(self.raiz / "apartado")
        with self.assertRaises(ErrorMotor):
            biblioteca.borrar(self.video)

    def test_si_macos_rechaza_el_traslado_no_se_pierde_nada(self):
        self.respuesta = lambda *args: (False, None, SimpleNamespace(localizedDescription=lambda: "Sin permiso"))
        with self.assertRaises(ErrorMotor):
            biblioteca.borrar(self.video)
        self.assertEqual(self._contenido(self.carpeta), self.archivos)

    def test_fuera_de_mac_no_hay_borrado_definitivo_de_reserva(self):
        with patch("platform.system", return_value="Linux"), self.assertRaises(ErrorMotor):
            biblioteca.borrar(self.video)
        self.assertEqual(self._contenido(self.carpeta), self.archivos)

    def test_si_falta_el_puente_nativo_no_se_borra_el_video(self):
        with patch.dict("sys.modules", {"Foundation": None}), self.assertRaises(ErrorMotor):
            biblioteca.borrar(self.video)
        self.assertEqual(self._contenido(self.carpeta), self.archivos)

    async def test_el_panel_informa_el_fallo_sin_anunciar_exito(self):
        self.respuesta = lambda *args: (False, None, SimpleNamespace(localizedDescription=lambda: "Sin permiso"))
        await self._confirmar()
        self.assertEqual(self._contenido(self.carpeta), self.archivos)
        self.assertEqual([tipo for _, tipo in self.avisos], ["negative"])

    async def test_el_panel_confirma_el_traslado_recuperable(self):
        await self._confirmar()
        self.assertFalse(self.carpeta.exists())
        self.assertEqual(self._contenido(self.papelera / self.carpeta.name), self.archivos)
        self.assertEqual(len(self.avisos), 1)
        self.assertIn("Papelera", self.avisos[0][0])

    async def test_no_se_traslada_mientras_hay_un_trabajo(self):
        with patch.object(TAREAS, "actual", Tarea("Render ficticio", ["crear", "uno.yaml"])):
            await self._confirmar()
        self.assertEqual(self._contenido(self.carpeta), self.archivos)
        self.assertEqual([tipo for _, tipo in self.avisos], ["warning"])

    async def test_se_revisa_el_trabajo_al_confirmar_no_solo_al_abrir(self):
        acciones = []
        with patch("tpi_videos.panel.paginas.videos.confirmar", side_effect=lambda pregunta, accion, **kw: acciones.append(accion)):
            self.pagina._borrar(self.video)
        with patch.object(TAREAS, "actual", Tarea("Render ficticio", ["crear", "uno.yaml"])), patch.object(self.pagina.lista, "refresh"):
            resultado = acciones[0]()
            if inspect.isawaitable(resultado):
                await resultado
        self.assertEqual(self._contenido(self.carpeta), self.archivos)
        self.assertEqual([tipo for _, tipo in self.avisos], ["warning"])

    async def test_el_traslado_no_bloquea_el_bucle_del_panel(self):
        latido = threading.Event()
        atendido = []

        def trasladar(url, resultado, error):
            atendido.append(latido.wait(0.5))
            return self._trasladar(url, resultado, error)

        self.respuesta = trasladar
        asyncio.get_running_loop().call_soon(latido.set)
        await self._confirmar()
        self.assertEqual(atendido, [True], "El traslado bloqueó el bucle del panel")
        self.assertEqual(self._contenido(self.papelera / self.carpeta.name), self.archivos)

    def test_un_trabajo_iniciado_durante_la_espera_impide_el_traslado(self):
        iniciado = threading.Event()

        def trasladar():
            iniciado.set()
            return biblioteca.borrar(self.video)

        with ThreadPoolExecutor(max_workers=1) as hilos:
            biblioteca._ARCHIVOS_VIDEO.acquire()
            try:
                traslado = hilos.submit(trasladar)
                self.assertTrue(iniciado.wait(3))
                with patch.object(TAREAS, "actual", Tarea("Render ficticio", ["crear", "uno.yaml"])):
                    biblioteca._ARCHIVOS_VIDEO.release()
                    with self.assertRaises(ErrorMotor):
                        traslado.result(timeout=3)
            finally:
                if biblioteca._ARCHIVOS_VIDEO.locked():
                    biblioteca._ARCHIVOS_VIDEO.release()
        self.assertEqual(self._contenido(self.carpeta), self.archivos)

    def test_una_miniatura_pendiente_no_recrea_una_carpeta_trasladada(self):
        self.carpeta.rename(self.papelera / self.carpeta.name)
        with self.assertRaises(FileNotFoundError):
            biblioteca.miniatura(self.video)
        self.assertFalse(self.carpeta.exists())

    async def test_el_muro_omite_miniaturas_de_videos_que_ya_no_estan(self):
        self.carpeta.rename(self.papelera / self.carpeta.name)
        with self.pagina.capa:
            imagen = ui.image("")
        await self.pagina._miniaturas([(self.video, imagen)])
        self.assertFalse(self.carpeta.exists())
        self.assertEqual(imagen.source, "")

    def test_el_traslado_espera_la_miniatura_en_curso(self):
        extrayendo = threading.Event()
        continuar = threading.Event()
        traslado_iniciado = threading.Event()

        def trasladar():
            traslado_iniciado.set()
            return biblioteca.borrar(self.video)

        def extraer(archivo, momento, destino, **opciones):
            extrayendo.set()
            if not continuar.wait(3):
                raise AssertionError("La prueba no liberó la extracción")
            destino.write_bytes(b"miniatura ficticia")
            return destino

        with patch("tpi_videos.postproduccion.extraer_cuadro", side_effect=extraer), patch("tpi_videos.publicar._video_sin_subtitulos", return_value=self.video.final), ThreadPoolExecutor(max_workers=2) as hilos:
            miniatura = hilos.submit(biblioteca.miniatura, self.video)
            self.assertTrue(extrayendo.wait(3))
            traslado = hilos.submit(trasladar)
            try:
                self.assertTrue(traslado_iniciado.wait(3))
                with self.assertRaises(TimeoutError):
                    traslado.result(timeout=0.1)
                self.assertTrue(self.carpeta.exists())
            finally:
                continuar.set()
            miniatura.result(timeout=3)
            destino = traslado.result(timeout=3)
        self.assertFalse(self.carpeta.exists())
        self.assertEqual((destino / "miniatura.jpg").read_bytes(), b"miniatura ficticia")
        self.assertEqual(self._contenido(destino), {**self.archivos, "miniatura.jpg": b"miniatura ficticia"})
