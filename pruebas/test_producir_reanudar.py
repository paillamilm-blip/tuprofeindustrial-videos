import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tpi_videos.ideas import producir

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "guiones" / "ejemplos" / "fisica_caida_libre.yaml"


def _video_falso(raiz: Path) -> SimpleNamespace:
    carpeta = raiz / "salida" / "demo"
    carpeta.mkdir(parents=True, exist_ok=True)
    video = carpeta / "demo.mp4"
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


def _kit_falso(raiz: Path) -> SimpleNamespace:
    carpeta = raiz / "salida" / "demo"
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
        "pendientes": ["revisar el signo"],
        "supuestos": [],
        "rondas": 2,
        "modelo": "gemini-3.8-flash",
        "revisado_por_ia": True,
    }


class ProducirReanudarTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_con_hito_guion_no_llama_a_la_ia(self) -> None:
        nombres: list[str] = []
        with (
            patch("tpi_videos.ideas.redactar") as redactar,
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit") as crear_kit,
        ):
            crear_video.return_value = _video_falso(self.raiz)
            crear_kit.return_value = _kit_falso(self.raiz)
            resultado = producir("x", reanudar={"guion": _hito_guion()}, hito=lambda n, d: nombres.append(n))

        redactar.assert_not_called()
        crear_video.assert_called_once()
        crear_kit.assert_called_once()
        self.assertEqual(nombres, ["video", "kit"])
        self.assertEqual(resultado.duracion, 42.0)
        self.assertEqual(resultado.redaccion.pendientes, ["revisar el signo"])

    def test_con_hito_video_no_renderiza(self) -> None:
        video = _video_falso(self.raiz)
        hito_video = {
            "video": str(video.video),
            "carpeta": str(video.carpeta),
            "duracion": 42.0,
            "segundos_proceso": 1.0,
            "srt": None,
            "fuentes_tiempo": [],
            "tema": "Hoja de desarrollo",
        }
        nombres: list[str] = []
        with (
            patch("tpi_videos.ideas.redactar"),
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit") as crear_kit,
        ):
            crear_kit.return_value = _kit_falso(self.raiz)
            producir(
                "x",
                reanudar={"guion": _hito_guion(), "video": hito_video},
                hito=lambda n, d: nombres.append(n),
            )

        crear_video.assert_not_called()
        crear_kit.assert_called_once()
        self.assertEqual(nombres, ["kit"])

    def test_con_hito_kit_no_llama_a_nadie(self) -> None:
        video = _video_falso(self.raiz)
        kit = _kit_falso(self.raiz)
        reanudar = {
            "guion": _hito_guion(),
            "video": {
                "video": str(video.video),
                "carpeta": str(video.carpeta),
                "duracion": 42.0,
                "segundos_proceso": 1.0,
                "srt": None,
                "fuentes_tiempo": [],
                "tema": "Hoja de desarrollo",
            },
            "kit": {
                "carpeta": str(kit.carpeta),
                "portada": str(kit.portada),
                "publicacion": str(kit.archivo),
                "texto_kit": "YouTube: T",
                "aviso": None,
            },
        }
        with (
            patch("tpi_videos.ideas.redactar") as redactar,
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit") as crear_kit,
        ):
            resultado = producir("x", reanudar=reanudar)

        redactar.assert_not_called()
        crear_video.assert_not_called()
        crear_kit.assert_not_called()
        self.assertEqual(resultado.texto_kit, "YouTube: T")
        self.assertEqual(resultado.publicacion, kit.archivo)

    def test_si_falta_el_archivo_del_hito_se_rehace(self) -> None:
        with (
            patch("tpi_videos.ideas.redactar") as redactar,
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit") as crear_kit,
        ):
            redactar.return_value = SimpleNamespace(
                ruta=GUION,
                guion=None,
                supuestos=[],
                pendientes=[],
                rondas=1,
                modelo="m",
                revisado_por_ia=True,
                historial=[],
            )
            crear_video.return_value = _video_falso(self.raiz)
            crear_kit.return_value = _kit_falso(self.raiz)
            producir("x", reanudar={"guion": {**_hito_guion(), "ruta": str(self.raiz / "nada.yaml")}})

        redactar.assert_called_once()

    def test_hito_se_llama_en_orden(self) -> None:
        nombres: list[str] = []
        with (
            patch("tpi_videos.ideas.redactar") as redactar,
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit") as crear_kit,
        ):
            redactar.return_value = SimpleNamespace(
                ruta=GUION,
                guion=None,
                supuestos=[],
                pendientes=[],
                rondas=1,
                modelo="m",
                revisado_por_ia=True,
                historial=[],
            )
            crear_video.return_value = _video_falso(self.raiz)
            crear_kit.return_value = _kit_falso(self.raiz)
            producir("x", hito=lambda n, d: nombres.append(n))

        self.assertEqual(nombres, ["guion", "video", "kit"])

    def test_kit_a_medias_conserva_el_video(self) -> None:
        hito_video = {
            "video": str(_video_falso(self.raiz).video),
            "carpeta": str(self.raiz / "salida" / "demo"),
            "duracion": 42.0,
            "segundos_proceso": 1.0,
            "srt": None,
            "fuentes_tiempo": [],
            "tema": "Hoja de desarrollo",
        }
        with (
            patch("tpi_videos.ideas.redactar"),
            patch("tpi_videos.render.crear_video") as crear_video,
            patch("tpi_videos.publicar.crear_kit", side_effect=RuntimeError("sin cupo")),
        ):
            with self.assertRaises(RuntimeError):
                producir("x", reanudar={"guion": _hito_guion(), "video": hito_video})
        crear_video.assert_not_called()
        self.assertTrue(Path(hito_video["video"]).exists())


if __name__ == "__main__":
    unittest.main()
