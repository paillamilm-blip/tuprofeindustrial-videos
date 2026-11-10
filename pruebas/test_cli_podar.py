import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _viejo(ruta: Path, dias: int = 30) -> None:
    pasado = time.time() - dias * 86400
    os.utime(ruta, (pasado, pasado))


class CliPodarTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.cache = self.raiz / "salida" / "_3d"
        self.cache.mkdir(parents=True)
        self.env = dict(
            os.environ,
            TPI_RAIZ=self.tmp.name,
            NO_COLOR="1",
            PYTHONIOENCODING="utf-8",
            PYTHONPATH=str(RAIZ / "src"),
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _correr(self, *args: str, entrada: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "tpi_videos", "podar", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=self.env,
            input=entrada,
            timeout=60,
        )

    def _viejo_y_nuevo(self) -> tuple[Path, Path]:
        viejo = self.cache / "cubo_frente_sin_corte_1.png"
        nuevo = self.cache / "esfera_ala_sin_corte_2.png"
        viejo.write_bytes(b"x")
        nuevo.write_bytes(b"x")
        _viejo(viejo)
        return viejo, nuevo

    def test_con_si_borra_sin_preguntar(self) -> None:
        viejo, nuevo = self._viejo_y_nuevo()
        resultado = self._correr("--si")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertFalse(viejo.exists())
        self.assertTrue(nuevo.exists())
        self.assertIn("Liberé", resultado.stdout)

    def test_sin_si_pregunta_y_respeta_el_no(self) -> None:
        viejo, _ = self._viejo_y_nuevo()
        resultado = self._correr(entrada="n\n")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertTrue(viejo.exists())
        self.assertIn("No borré nada", resultado.stdout)

    def test_sin_si_una_s_borra(self) -> None:
        viejo, _ = self._viejo_y_nuevo()
        resultado = self._correr(entrada="s\n")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertFalse(viejo.exists())

    def test_sin_entrada_no_borra(self) -> None:
        viejo, _ = self._viejo_y_nuevo()
        resultado = self._correr(entrada="")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertTrue(viejo.exists())

    def test_sin_nada_que_podar_lo_dice(self) -> None:
        nuevo = self.cache / "esfera_ala_sin_corte_2.png"
        nuevo.write_bytes(b"x")
        resultado = self._correr("--si")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("No hay nada que podar", resultado.stdout)
        self.assertTrue(nuevo.exists())


if __name__ == "__main__":
    unittest.main()
