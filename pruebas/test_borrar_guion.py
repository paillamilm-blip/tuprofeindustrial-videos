"""Borrar un guion en «Aprobar guiones»: va a la Papelera, nunca se borra de verdad."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tpi_videos.errores import ErrorMotor
from tpi_videos.panel import qc

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLO = RAIZ / "guiones" / "ejemplos" / "motor_vivo.yaml"


class BorrarGuionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.viejo = os.environ.get("TPI_RAIZ")
        os.environ["TPI_RAIZ"] = self.tmp.name
        self.raiz = Path(self.tmp.name).resolve()
        (self.raiz / "salida").mkdir()
        (self.raiz / "guiones" / "ejemplos").mkdir(parents=True)
        self.guion = self.raiz / "guiones" / "motor_vivo.yaml"
        shutil.copy(EJEMPLO, self.guion)
        self.papelera = self.raiz / "papelera"
        self.papelera.mkdir()
        self.pedidos = []

        def trasladar(url, resultado, error):
            origen = Path(url.path())
            self.pedidos.append(origen)
            destino = self.papelera / origen.name
            origen.rename(destino)
            return True, SimpleNamespace(path=lambda: str(destino)), None

        modulo = SimpleNamespace(
            NSURL=SimpleNamespace(fileURLWithPath_=lambda ruta: SimpleNamespace(path=lambda: ruta)),
            NSFileManager=SimpleNamespace(
                defaultManager=lambda: SimpleNamespace(trashItemAtURL_resultingItemURL_error_=trasladar)
            ),
        )
        for parche in (
            patch("platform.system", return_value="Darwin"),
            patch.dict("sys.modules", {"Foundation": modulo}),
        ):
            parche.start()
            self.addCleanup(parche.stop)

    def tearDown(self) -> None:
        if self.viejo is None:
            os.environ.pop("TPI_RAIZ", None)
        else:
            os.environ["TPI_RAIZ"] = self.viejo
        self.tmp.cleanup()

    def test_el_guion_va_a_la_papelera_y_sale_de_la_lista(self):
        destino = qc.borrar_guion(self.guion)
        self.assertEqual(destino, self.papelera / "motor_vivo.yaml")
        self.assertFalse(self.guion.exists())
        self.assertEqual(qc.guiones(incluir_decididos=True), [])
        self.assertEqual(destino.read_text(encoding="utf-8"), EJEMPLO.read_text(encoding="utf-8"))

    def test_un_guion_rechazado_tambien_se_puede_borrar(self):
        qc.rechazar(self.guion, "falta el reto")
        qc.borrar_guion(self.guion)
        self.assertFalse(self.guion.exists())

    def test_un_guion_aprobado_esta_en_la_cola_y_no_se_borra(self):
        qc.aprobar(self.guion, "lote-1")
        with self.assertRaises(ErrorMotor):
            qc.borrar_guion(self.guion)
        self.assertTrue(self.guion.exists())
        self.assertEqual(self.pedidos, [])

    def test_los_ejemplos_y_lo_de_afuera_no_se_borran(self):
        ejemplo = self.raiz / "guiones" / "ejemplos" / "x.yaml"
        shutil.copy(EJEMPLO, ejemplo)
        afuera = self.raiz / "otro.yaml"
        shutil.copy(EJEMPLO, afuera)
        for ruta in (ejemplo, afuera):
            with self.subTest(ruta=ruta), self.assertRaises(ErrorMotor):
                qc.borrar_guion(ruta)
            self.assertTrue(ruta.exists())
        self.assertEqual(self.pedidos, [])

    def test_si_macos_rechaza_el_traslado_no_se_pierde_nada(self):
        modulo = SimpleNamespace(
            NSURL=SimpleNamespace(fileURLWithPath_=lambda ruta: SimpleNamespace(path=lambda: ruta)),
            NSFileManager=SimpleNamespace(
                defaultManager=lambda: SimpleNamespace(
                    trashItemAtURL_resultingItemURL_error_=lambda *a: (
                        False,
                        None,
                        SimpleNamespace(localizedDescription=lambda: "Sin permiso"),
                    )
                )
            ),
        )
        with patch.dict("sys.modules", {"Foundation": modulo}), self.assertRaises(ErrorMotor):
            qc.borrar_guion(self.guion)
        self.assertTrue(self.guion.exists())

    def test_fuera_de_mac_no_hay_borrado_definitivo_de_reserva(self):
        with patch("platform.system", return_value="Linux"), self.assertRaises(ErrorMotor):
            qc.borrar_guion(self.guion)
        self.assertTrue(self.guion.exists())


if __name__ == "__main__":
    unittest.main()
