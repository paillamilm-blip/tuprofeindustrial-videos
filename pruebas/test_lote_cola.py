import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tpi_videos import cola
from tpi_videos.errores import ErrorMotor
from tpi_videos.ideas import GanchoIdea, Idea
from tpi_videos.lote import producir_lote


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


def _resultado(raiz: Path) -> SimpleNamespace:
    video = raiz / "salida" / "demo" / "demo.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"x")
    return SimpleNamespace(
        ruta_guion=raiz / "guiones" / "demo.yaml",
        video=video,
        portada=None,
        publicacion=None,
        duracion=42.0,
        redaccion=SimpleNamespace(pendientes=[]),
    )


class LoteColaTest(unittest.TestCase):
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

    def _lote(self) -> tuple[str, list[Idea]]:
        ideas = [_idea(1), _idea(2)]
        lote_id = cola.nuevo_lote("Tema", {})
        cola.agregar_videos(lote_id, ideas)
        return lote_id, ideas

    def test_transitorio_queda_pendiente_y_pausa_el_lote(self) -> None:
        lote_id, ideas = self._lote()
        dormidos: list[float] = []
        with patch("tpi_videos.lote.producir", side_effect=ErrorMotor("sin red", transitorio=True)):
            items = producir_lote(ideas, cola_id=lote_id, espera=60, reintentos=3, dormir=dormidos.append)

        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].pendiente)
        self.assertEqual(dormidos, [60.0, 120.0, 300.0])
        videos = cola.videos_del_lote(lote_id)
        self.assertEqual(videos[0]["estado"], "pendiente_ia")
        self.assertEqual(videos[0]["intentos"], 4)
        self.assertTrue(videos[0]["proximo_intento"])
        self.assertEqual(videos[1]["estado"], "en_cola")
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "pendiente_ia")

    def test_al_volver_la_ia_sigue_con_los_demas(self) -> None:
        lote_id, ideas = self._lote()
        dormidos: list[float] = []
        with patch(
            "tpi_videos.lote.producir",
            side_effect=[
                ErrorMotor("sin red", transitorio=True),
                _resultado(self.raiz),
                _resultado(self.raiz),
            ],
        ):
            items = producir_lote(ideas, cola_id=lote_id, espera=60, dormir=dormidos.append)

        self.assertEqual([item.ok for item in items], [True, True])
        self.assertEqual(dormidos, [60.0])
        self.assertEqual([video["estado"] for video in cola.videos_del_lote(lote_id)], ["listo", "listo"])
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "listo")

    def test_error_no_transitorio_marca_fallo_y_no_espera(self) -> None:
        lote_id, ideas = self._lote()
        dormidos: list[float] = []
        with patch("tpi_videos.lote.producir", side_effect=ErrorMotor("LaTeX roto")):
            items = producir_lote(ideas, cola_id=lote_id, espera=60, dormir=dormidos.append)

        self.assertEqual(dormidos, [])
        self.assertTrue(all(not item.ok and not item.pendiente for item in items))
        self.assertEqual([video["estado"] for video in cola.videos_del_lote(lote_id)], ["fallo", "fallo"])
        self.assertEqual(cola.cargar()["lotes"][0]["estado"], "fallo")

    def test_espera_cero_marca_pendiente_sin_dormir(self) -> None:
        lote_id, ideas = self._lote()
        dormidos: list[float] = []
        with patch("tpi_videos.lote.producir", side_effect=ErrorMotor("sin red", transitorio=True)):
            items = producir_lote(ideas, cola_id=lote_id, espera=0, dormir=dormidos.append)

        self.assertEqual(dormidos, [])
        self.assertTrue(items[0].pendiente)

    def test_eventos_traen_el_video_y_su_avance(self) -> None:
        lote_id, ideas = self._lote()
        eventos: list[dict] = []

        def progreso(etapa, avance, detalle, **extra):
            eventos.append({"etapa": etapa, "avance": avance, "detalle": detalle, **extra})

        with patch("tpi_videos.lote.producir", side_effect=[_resultado(self.raiz), _resultado(self.raiz)]):
            producir_lote(ideas, cola_id=lote_id, progreso=progreso)

        primero = eventos[0]
        self.assertEqual(primero["video"], 1)
        self.assertEqual(primero["total"], 2)
        self.assertEqual(primero["estado"], "redactando")
        self.assertAlmostEqual(primero["video_avance"], 0.05)
        self.assertAlmostEqual(primero["avance"], 0.025)

    def test_el_aviso_del_kit_no_retrocede_la_fase(self) -> None:
        lote_id, ideas = self._lote()
        eventos: list[dict] = []

        def progreso(etapa, avance, detalle, **extra):
            eventos.append({"etapa": etapa, "avance": avance, **extra})

        def producir_falso(enunciado, **kwargs):
            kwargs["progreso"]("kit", 0.95, "portada y textos de publicación")
            kwargs["avisar"]("Creando la portada…")
            kwargs["progreso"]("kit", 1.0, "kit listo")
            return _resultado(self.raiz)

        with patch("tpi_videos.lote.producir", side_effect=producir_falso):
            producir_lote(ideas[:1], cola_id=lote_id, progreso=progreso)

        # El primer evento es «redactando» (el paso inicial); de ahí en adelante nunca vuelve atrás.
        fases = [evento["fase"] for evento in eventos[1:]]
        self.assertNotIn("redactando", fases)
        self.assertEqual(fases[-1], "kit")
        avances = [evento["video_avance"] for evento in eventos]
        self.assertEqual(avances, sorted(avances))

    def test_si_la_cola_no_se_puede_escribir_el_video_sigue(self) -> None:
        lote_id, ideas = self._lote()
        avisos: list[str] = []
        with (
            patch(
                "tpi_videos.lote.producir",
                side_effect=[_resultado(self.raiz), _resultado(self.raiz)],
            ),
            patch("tpi_videos.cola.guardar", side_effect=OSError("disco lleno")),
        ):
            items = producir_lote(ideas, cola_id=lote_id, avisar=avisos.append)

        self.assertEqual([item.ok for item in items], [True, True])
        self.assertEqual(sum("No pude guardar" in aviso for aviso in avisos), 1)


if __name__ == "__main__":
    unittest.main()
