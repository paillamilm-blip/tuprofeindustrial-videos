import unittest
from pathlib import Path
from unittest.mock import patch

from tpi_videos.cli import cmd_ganchos, construir_parser

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


if __name__ == "__main__":
    unittest.main()
