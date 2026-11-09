import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


class CliColaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(
            os.environ,
            TPI_RAIZ=self.tmp.name,
            NO_COLOR="1",
            PYTHONIOENCODING="utf-8",
            PYTHONPATH=str(RAIZ / "src"),
        )
        (Path(self.tmp.name) / "salida").mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _correr(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "tpi_videos", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=self.env,
            timeout=60,
        )

    def test_reanudar_sin_pendientes_sale_limpio(self) -> None:
        resultado = self._correr("lote", "--reanudar")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("No hay videos pendientes", resultado.stdout)

    def test_reanudar_no_acepta_tema(self) -> None:
        resultado = self._correr("lote", "--reanudar", "Porcentajes")
        self.assertEqual(resultado.returncode, 1)
        self.assertIn("no indiques tema", resultado.stdout)

    def test_solo_pendientes_va_con_reanudar(self) -> None:
        resultado = self._correr("lote", "--solo-pendientes", "Porcentajes")
        self.assertEqual(resultado.returncode, 1)
        self.assertIn("van con --reanudar", resultado.stdout)

    def test_lote_no_arranca_con_el_candado_tomado(self) -> None:
        candado = Path(self.tmp.name) / "salida" / ".cola" / "lote.lock"
        candado.parent.mkdir(parents=True, exist_ok=True)
        candado.write_text(json.dumps({"pid": os.getpid(), "inicio": time.time()}), encoding="utf-8")
        resultado = self._correr("lote", "Porcentajes")
        self.assertEqual(resultado.returncode, 1)
        self.assertIn("Ya hay un lote en curso", resultado.stdout)

    def test_reanudar_con_cola_dañada_avisa_y_sale_bien(self) -> None:
        carpeta = Path(self.tmp.name) / "salida" / ".cola"
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "trabajos.json").write_text("{esto no es json", encoding="utf-8")
        resultado = self._correr("lote", "--reanudar")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("dañada", resultado.stdout)
        self.assertIn("No hay videos pendientes", resultado.stdout)

    def test_workers_por_defecto_es_uno(self) -> None:
        from tpi_videos import cli

        args = cli.construir_parser().parse_args(["lote", "Porcentajes"])
        self.assertEqual(args.workers, 1)

    def test_workers_dos_se_acepta(self) -> None:
        from tpi_videos import cli

        args = cli.construir_parser().parse_args(["lote", "Porcentajes", "--workers", "2"])
        self.assertEqual(args.workers, 2)

    def test_una_carpeta_de_guiones_se_produce_sin_ia_y_con_workers(self) -> None:
        import shutil
        from unittest.mock import patch

        from tpi_videos import cli, cola

        carpeta = Path(self.tmp.name) / "mis-guiones"
        carpeta.mkdir()
        for nombre in ("fisica_caida_libre.yaml", "ingenieria_ley_de_ohm.yaml"):
            shutil.copy(RAIZ / "guiones" / "ejemplos" / nombre, carpeta / nombre)

        args = cli.construir_parser().parse_args(
            ["lote", str(carpeta), "--borrador", "--voz", "silencio", "--workers", "2"]
        )
        with (
            patch.dict(os.environ, self.env),
            patch("tpi_videos.lote.producir_lote", return_value=[]) as producir,
            patch("tpi_videos.ideas.proponer_ideas", side_effect=AssertionError("no debe llamar a la IA")),
        ):
            self.assertEqual(cli.cmd_lote(args), 0)
            lote = cola.cargar()["lotes"][0]

        ideas = producir.call_args.args[0]
        self.assertEqual(
            [idea.titulo for idea in ideas],
            ["Caída libre: ¿cuánto tarda en caer?", "Ley de Ohm: ¿cuánta potencia disipa?"],
        )
        self.assertEqual(producir.call_args.kwargs["workers"], 2)
        self.assertEqual(producir.call_args.kwargs["calidad"], "borrador")
        self.assertEqual(producir.call_args.kwargs["proveedor"], "silencio")

        self.assertEqual(len(lote["videos"]), 2)
        for video in lote["videos"]:
            ruta = Path(video["hitos"]["guion"]["ruta"])
            self.assertTrue(ruta.is_file(), ruta)


if __name__ == "__main__":
    unittest.main()
