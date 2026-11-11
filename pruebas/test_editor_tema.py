import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import yaml
from nicegui import ui

from tpi_videos.panel.paginas.estilos import EditorTema


class EditorTemaTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        directorio = patch("tpi_videos.temas.temas_usuario_dir", return_value=Path(self.temporal.name))
        directorio.start()
        self.addCleanup(directorio.stop)
        self.contenedor = ui.element("div")
        self.addCleanup(self.contenedor.delete)

    def _campo(self, etiqueta):
        campos = [
            e for e in self.contenedor.descendants()
            if isinstance(e, ui.color_input) and etiqueta in e.label
        ]
        self.assertEqual(len(campos), 1, f"Falta el control de color para {etiqueta}")
        return campos[0]

    async def _guardar(self, editor):
        with patch("tpi_videos.panel.paginas.estilos.generar_vista", new_callable=AsyncMock), patch(
            "tpi_videos.panel.paginas.estilos.ui.notify"
        ):
            await editor.guardar_y_ver()
        return yaml.safe_load((Path(self.temporal.name) / f"{editor.id}.yaml").read_text(encoding="utf-8"))

    async def test_abrir_los_fondos_de_un_color_no_falla_ni_altera_el_estilo(self):
        for identificador in ("rotulador", "rotulador_fucsia", "cuaderno_con_sello", "cuaderno_tinta_roja"):
            with self.subTest(tema=identificador):
                self.contenedor.clear()
                editor = EditorTema(identificador)
                original = copy.deepcopy(editor.t)
                try:
                    with self.contenedor:
                        editor._fondo()
                except IndexError as error:
                    self.fail(f"No se pudo abrir el fondo del estilo: {error}")
                self.assertEqual(self._campo("arriba").value, original["fondo"]["degradado"][0])
                self.assertEqual(self._campo("abajo").value, original["fondo"]["degradado"][0])
                self.assertEqual(editor.t, original)

    async def test_cambiar_el_segundo_color_conserva_el_primero(self):
        editor = EditorTema("rotulador")
        with self.contenedor:
            try:
                editor._fondo()
            except IndexError as error:
                self.fail(f"No se pudo editar el degradado de un color: {error}")
        self._campo("abajo").set_value("#123456")
        self.assertEqual(editor.t["fondo"]["degradado"], ["#E9E7DF", "#123456"])

    async def test_un_degradado_vacio_usa_el_fondo_sin_guardarlo_al_abrir(self):
        editor = EditorTema("rotulador")
        editor.t["fondo"]["degradado"] = []
        with self.contenedor:
            try:
                editor._fondo()
            except IndexError as error:
                self.fail(f"No se pudo abrir un degradado vacío válido: {error}")
        self.assertEqual(self._campo("arriba").value, "#E9E7DF")
        self.assertEqual(self._campo("abajo").value, "#E9E7DF")
        self.assertEqual(editor.t["fondo"]["degradado"], [])
        self._campo("abajo").set_value("#123456")
        self.assertEqual(editor.t["fondo"]["degradado"], ["#E9E7DF", "#123456"])

    async def test_el_color_de_abajo_sigue_al_de_arriba_hasta_editarlo(self):
        for inicial in ([], ["#E9E7DF"]):
            with self.subTest(degradado=inicial):
                self.contenedor.clear()
                editor = EditorTema("rotulador")
                editor.t["fondo"]["degradado"] = inicial.copy()
                with self.contenedor:
                    editor._fondo()
                self._campo("arriba").set_value("#123456")
                self.assertEqual(self._campo("abajo").value, "#123456")
                self.assertEqual(editor.t["fondo"]["degradado"], ["#123456"])
                self._campo("abajo").set_value("#654321")
                self._campo("arriba").set_value("#22AA66")
                self.assertEqual(self._campo("abajo").value, "#654321")
                self.assertEqual(editor.t["fondo"]["degradado"], ["#22AA66", "#654321"])

    async def test_guardar_sin_editar_conserva_los_colores_de_cada_materia(self):
        editor = EditorTema("consola_neon")
        editor.t["materias"] = {
            "matematica": "#141414", "fisica": "#0F5FA8", "ingenieria": "#7A4E12"
        }
        editor.cuadros = self.contenedor
        editor.estado = None
        guardado = await self._guardar(editor)
        self.assertEqual(guardado["materias"], {
            "matematica": "#141414", "fisica": "#0F5FA8", "ingenieria": "#7A4E12"
        })

    async def test_cada_materia_se_edita_sin_cambiar_las_otras(self):
        materias = {"matematica": "#141414", "fisica": "#0F5FA8", "ingenieria": "#7A4E12"}
        for clave, etiqueta in (("matematica", "Matemática"), ("fisica", "Física"), ("ingenieria", "Ingeniería")):
            with self.subTest(materia=clave):
                self.contenedor.clear()
                editor = EditorTema("consola_neon")
                editor.t["materias"] = materias.copy()
                with self.contenedor:
                    editor.render()
                self._campo(etiqueta).set_value("#22AA66")
                guardado = await self._guardar(editor)
                esperado = materias.copy()
                esperado[clave] = "#22AA66"
                self.assertEqual(guardado["materias"], esperado)

    async def test_editar_dos_extremos_no_pierde_colores_adicionales(self):
        editor = EditorTema("consola_neon")
        editor.t["fondo"]["degradado"] = ["#111111", "#222222", "#333333"]
        with self.contenedor:
            editor._fondo()
        self._campo("arriba").set_value("#444444")
        self._campo("abajo").set_value("#555555")
        self.assertEqual(editor.t["fondo"]["degradado"], ["#444444", "#555555", "#333333"])


if __name__ == "__main__":
    unittest.main()
