import os
import subprocess
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
