import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tpi_videos import cola
from tpi_videos.ideas import GanchoIdea, Idea
from tpi_videos.lote import producir_lote

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "guiones" / "ejemplos" / "fisica_caida_libre.yaml"


def _idea(n: int) -> Idea:
    return Idea(
        angulo=("reto", "dato_curioso", "error_tipico")[n - 1],
        titulo=f"Idea {n}",
        gancho="¿Cuánto vale la corriente?",
        enunciado="Un circuito de 12 V y 4 ohm: ¿cuál es la corriente eléctrica?",
        materia="fisica",
        nivel="2° medio",
        porque="Porque reta al que mira.",
        segundos=45,
        molde=("reto", "mito_realidad", "tres_errores")[n - 1],
        ganchos=[GanchoIdea(texto="¿Cuánto vale la corriente?", estilo="curiosidad")],
    )


def _video_en(raiz: Path, nombre: str) -> SimpleNamespace:
    carpeta = raiz / "salida" / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    video = carpeta / f"{nombre}.mp4"
    video.write_bytes(b"x")
    return SimpleNamespace(
        video=video,
        carpeta=carpeta,
        duracion=42.0,
        segundos_proceso=1.0,
        srt=None,
        fuentes_tiempo=set(),
        tema="Hoja de desarrollo",
    )


def _kit_en(raiz: Path, nombre: str) -> SimpleNamespace:
    carpeta = raiz / "salida" / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    portada = carpeta / "portada.png"
    portada.write_bytes(b"x")
    archivo = carpeta / "publicacion.md"
    archivo.write_text("hola", encoding="utf-8")
    textos = SimpleNamespace(
        titulo_youtube="T",
        descripcion_youtube="D",
        texto_tiktok="TT",
        texto_instagram="I",
        hashtags=["#a"],
    )
    return SimpleNamespace(
        carpeta=carpeta, portada=portada, textos=textos, con_ia=True, archivo=archivo, aviso=None
    )


def _hito_guion() -> dict:
    return {
        "ruta": str(GUION),
        "pendientes": [],
        "supuestos": [],
        "rondas": 1,
        "modelo": "gemini-3.8-flash",
        "revisado_por_ia": True,
    }


def _hito_video(video: SimpleNamespace) -> dict:
    return {
        "video": str(video.video),
        "carpeta": str(video.carpeta),
        "duracion": video.duracion,
        "segundos_proceso": video.segundos_proceso,
        "srt": None,
        "fuentes_tiempo": [],
        "tema": video.tema,
    }


def _redaccion() -> SimpleNamespace:
    return SimpleNamespace(
        ruta=GUION,
        guion=None,
        supuestos=[],
        pendientes=[],
        rondas=1,
        modelo="gemini-3.8-flash",
        revisado_por_ia=True,
        historial=[],
    )


class ReanudarLoteTest(unittest.TestCase):
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

    def test_el_video_con_hitos_no_se_vuelve_a_renderizar(self) -> None:
        ideas = [_idea(1), _idea(2)]
        lote_id = cola.nuevo_lote("Tema", {})
        cola.agregar_videos(lote_id, ideas)
        primero = cola.videos_del_lote(lote_id)[0]
        # El video 1 ya tiene guion y video guardados de una pasada anterior: solo le falta el kit.
        cola.hito(primero["id"], "guion", _hito_guion())
        cola.hito(primero["id"], "video", _hito_video(_video_en(self.raiz, "v1")))

        with (
            patch("tpi_videos.ideas.redactar") as redactar,
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit") as crear_kit,
        ):
            redactar.return_value = _redaccion()
            crear_video.side_effect = lambda *a, **k: _video_en(self.raiz, "v2")
            crear_kit.side_effect = lambda *a, **k: _kit_en(self.raiz, "kit")
            items = producir_lote(ideas, cola_id=lote_id)

        # Solo el video 2 (sin hitos) pasa por la IA y el render; el 1 se reanuda desde el kit.
        redactar.assert_called_once()
        crear_video.assert_called_once()
        self.assertEqual([item.ok for item in items], [True, True])
        self.assertEqual(
            [video["estado"] for video in cola.videos_del_lote(lote_id)], ["listo", "listo"]
        )

    def test_cmd_lote_libera_el_candado_si_producir_falla(self) -> None:
        from tpi_videos import cli

        idea_json = json.dumps({"ideas": [json.loads(_idea(1).model_dump_json())]})
        args = cli.construir_parser().parse_args(["lote", "--ideas-json", idea_json, "Tema"])
        with (
            patch("tpi_videos.cli.consola"),  # la consola real no traga el emoji 📦 en cp1252
            patch("tpi_videos.cli._dividir_voz", return_value=(None, None)),
            patch("tpi_videos.lote.producir_lote", side_effect=RuntimeError("render roto")),
        ):
            with self.assertRaises(RuntimeError):
                cli.cmd_lote(args)
        self.assertFalse(cola.candado_tomado())

    def test_reanudar_libera_el_candado_si_producir_falla(self) -> None:
        from tpi_videos import cli

        lote_id = cola.nuevo_lote("Tema", {})
        cola.agregar_videos(lote_id, [_idea(1)])
        video_id = cola.videos_del_lote(lote_id)[0]["id"]
        cola.actualizar_video(video_id, estado="pendiente_ia")
        cola.recalcular_lote(lote_id)

        args = cli.construir_parser().parse_args(["lote", "--reanudar", "--solo-pendientes"])
        with patch("tpi_videos.lote.producir_lote", side_effect=RuntimeError("render roto")):
            with self.assertRaises(RuntimeError):
                cli.cmd_lote(args)
        self.assertFalse(cola.candado_tomado())


if __name__ == "__main__":
    unittest.main()
