import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tpi_videos.cli import cmd_ganchos, construir_parser
from tpi_videos.config import Marca
from tpi_videos.ganchos import idea_desde_guion
from tpi_videos.guion import Guion, a_yaml
from pruebas.test_ganchos import guion_datos

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "guiones" / "ejemplos" / "visuales_tres_tipos.yaml"


class CliGanchosTest(unittest.TestCase):
    def _args(self):
        return construir_parser().parse_args(["ganchos", str(GUION), "--borrador", "--voz", "silencio"])

    def test_acepta_borrador_y_voz(self) -> None:
        args = self._args()
        self.assertTrue(args.borrador)
        self.assertEqual(args.voz, "silencio")

    def test_voz_silencio_renderiza_sin_voz(self) -> None:
        args = self._args()
        manifiesto = {"titulo": "Tres dibujos", "clips": []}
        with (
            patch("tpi_videos.ganchos.renderizar_ganchos", return_value=manifiesto) as rendir,
            patch("tpi_videos.cli._mostrar_ganchos"),
        ):
            self.assertEqual(cmd_ganchos(args), 0)

        self.assertTrue(rendir.call_args.kwargs["sin_voz"])
        self.assertEqual(rendir.call_args.kwargs["calidad"], "borrador")


class HerenciaGanchosTest(unittest.TestCase):
    def _datos(self):
        datos = guion_datos()
        datos.update(
            materia="fisica", molde=None, tema="kraft_claro", camara="quieta",
            voz="es-CL-CatalinaNeural", velocidad="-20%",
        )
        datos["gancho_variantes"][0]["visual"] = {
            "tipo": "circuito", "fuente": "9 V", "resistencias": ["4 Ω", "6 Ω"],
        }
        return datos

    def _correr(self, datos=None, argumentos=(), *, directo=False, desde_idea=False, proveedor="edge"):
        datos = self._datos() if datos is None else datos
        original = Guion.model_validate(datos)
        marca = Marca(voz={
            "proveedor": proveedor, "nombre": "es-CL-LorenzoNeural",
            "velocidad": "+5%", "tono": "+25Hz",
        })
        recibidos = []
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            ruta = raiz / "guion.yaml"
            ruta.write_text(a_yaml(datos), encoding="utf-8")
            antes = ruta.read_bytes()
            crudo = raiz / "crudo.mp4"
            crudo.write_bytes(b"Clip de prueba")

            def renderizar(guion, marca, tema, calidad, proveedor, voz, velocidad, carpeta, **opciones):
                recibidos.append({
                    "guion": guion.model_dump(), "estilo": tema.nombre,
                    "proveedor": proveedor, "voz": voz, "velocidad": velocidad,
                    "tono": opciones.get("tono"), "solo_gancho": opciones.get("solo_gancho"),
                })
                return crudo, {}

            with (
                patch.dict(os.environ, {"TPI_RAIZ": temporal}),
                patch("tpi_videos.cli._JSON", {"activo": False}),
                patch("tpi_videos.cli.consola._file", io.StringIO()),
                patch("tpi_videos.render.cargar_marca", return_value=marca),
                patch("tpi_videos.render.verificar_requisitos"),
                patch("tpi_videos.render.renderizar_manim", side_effect=renderizar),
                patch("tpi_videos.postproduccion.duracion", return_value=5.0),
                contextlib.redirect_stdout(io.StringIO()) as salida,
            ):
                if directo:
                    from tpi_videos.render import crear_clip_gancho

                    crear_clip_gancho(original, salida=raiz / "directo.mp4")
                    self.assertEqual((raiz / "directo.mp4").read_bytes(), b"Clip de prueba")
                else:
                    fuente = [str(ruta)]
                    if desde_idea:
                        fuente = ["--idea-json", json.dumps(idea_desde_guion(original).model_dump())]
                    args = construir_parser().parse_args(["ganchos", *fuente, "--progreso-json", *argumentos])
                    self.assertEqual(cmd_ganchos(args), 0)
                    resultado = next(
                        json.loads(linea) for linea in salida.getvalue().splitlines()
                        if json.loads(linea).get("etapa") == "resultado"
                    )
                    self.assertEqual(len(resultado["clips"]), 3)
                    for clip in resultado["clips"]:
                        self.assertEqual(Path(clip["archivo"]).read_bytes(), b"Clip de prueba")
                self.assertEqual(ruta.read_bytes(), antes)
        self.assertTrue(all(clip["solo_gancho"] for clip in recibidos))
        return recibidos

    def test_los_clips_heredan_la_voz_del_guion(self):
        self.assertEqual([clip["voz"] for clip in self._correr()], ["es-CL-CatalinaNeural"] * 3)

    def test_los_clips_heredan_la_velocidad_del_guion(self):
        self.assertEqual([clip["velocidad"] for clip in self._correr()], ["-20%"] * 3)

    def test_todas_las_variantes_respetan_el_estilo_elegido(self):
        self.assertEqual([clip["estilo"] for clip in self._correr()], ["Kraft claro"] * 3)

    def test_el_estilo_automatico_conserva_el_contexto_del_video(self):
        datos = self._datos()
        datos.pop("tema")
        clips = self._correr(datos)
        # el guion completo corrige un error: todas las variantes salen en «Error», aunque el gancho
        # de una traiga un circuito (en la familia Consola neón el dibujo ya no cambia el estilo)
        self.assertEqual([clip["estilo"] for clip in clips], ["Consola · Error"] * 3)

    def test_los_clips_heredan_el_tono_de_ajustes(self):
        self.assertEqual([clip["tono"] for clip in self._correr()], ["+25Hz"] * 3)

    def test_el_render_directo_respeta_los_ajustes_del_guion(self):
        clip = self._correr(directo=True)[0]
        self.assertEqual(clip["voz"], "es-CL-CatalinaNeural")
        self.assertEqual(clip["velocidad"], "-20%")
        self.assertEqual(clip["tono"], "+25Hz")

    def test_cada_gancho_conserva_su_texto_y_su_dibujo(self):
        clips = self._correr()
        self.assertEqual(clips[0]["guion"]["gancho"]["voz"], "¿Pitágoras era a más b igual a c?")
        self.assertEqual(clips[1]["guion"]["gancho"]["texto"], "El error que casi todos cometen")
        self.assertEqual(clips[1]["guion"]["gancho"]["visual"]["tipo"], "circuito")
        self.assertEqual(clips[2]["guion"]["gancho"]["tex"], "3 + 4 \\neq 7")

    def test_una_voz_explicita_gana_al_guion_y_al_proveedor_guardado(self):
        clips = self._correr(argumentos=("--voz", "es-CL-LorenzoNeural"), proveedor="gtts")
        self.assertEqual([clip["voz"] for clip in clips], ["es-CL-LorenzoNeural"] * 3)
        self.assertEqual([clip["proveedor"] for clip in clips], ["edge"] * 3)

    def test_sin_voz_sigue_ganando_a_la_voz_del_guion(self):
        for argumentos in (("--sin-voz",), ("--voz", "silencio")):
            with self.subTest(argumentos=argumentos):
                clips = self._correr(argumentos=argumentos)
                self.assertEqual([clip["proveedor"] for clip in clips], ["silencio"] * 3)
                self.assertEqual([clip["voz"] for clip in clips], ["silencio"] * 3)

    def test_un_guion_sin_voz_ni_velocidad_usa_ajustes(self):
        datos = self._datos()
        datos.pop("voz")
        datos.pop("velocidad")
        for proveedor in ("edge", "gtts", "silencio"):
            with self.subTest(proveedor=proveedor):
                clips = self._correr(datos, proveedor=proveedor)
                self.assertEqual([clip["proveedor"] for clip in clips], [proveedor] * 3)
                self.assertEqual([clip["voz"] for clip in clips], ["es-CL-LorenzoNeural"] * 3)
                self.assertEqual([clip["velocidad"] for clip in clips], ["+5%"] * 3)

    def test_el_laboratorio_desde_una_idea_sigue_usando_ajustes(self):
        clips = self._correr(desde_idea=True)
        self.assertEqual([clip["voz"] for clip in clips], ["es-CL-LorenzoNeural"] * 3)
        self.assertEqual([clip["velocidad"] for clip in clips], ["+5%"] * 3)
        self.assertEqual([clip["tono"] for clip in clips], ["+25Hz"] * 3)
        self.assertEqual(clips[0]["estilo"], "Consola · Paso a paso")  # una idea suelta: paso a paso


if __name__ == "__main__":
    unittest.main()
