import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from tpi_videos.mantenimiento import podar_temporales


def _viejo(ruta: Path, dias: int = 30) -> None:
    pasado = time.time() - dias * 86400
    os.utime(ruta, (pasado, pasado))


def _nuevo(ruta: Path) -> None:
    ahora = time.time()
    os.utime(ruta, (ahora, ahora))


class PodaTemporalesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.tres_de = self.raiz / "salida" / "_3d"
        self.tres_de.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_borra_png_y_json_viejos_y_conserva_los_nuevos(self) -> None:
        viejo = self.tres_de / "cubo_frente_sin_corte_1.png"
        lado = self.tres_de / "cubo_frente_sin_corte_1.json"
        nuevo = self.tres_de / "esfera_ala_sin_corte_2.png"
        for ruta in (viejo, lado, nuevo):
            ruta.write_bytes(b"x")
        _viejo(viejo)
        _viejo(lado)
        _nuevo(nuevo)

        poda = podar_temporales(dias=7, max_tamano_mb=500, raiz=self.raiz)

        self.assertFalse(viejo.exists())
        self.assertFalse(lado.exists())
        self.assertTrue(nuevo.exists())
        self.assertEqual(set(poda.archivos), {viejo, lado})
        self.assertEqual(poda.bytes, 2)

    def test_simular_no_borra_nada(self) -> None:
        viejo = self.tres_de / "cubo_frente_sin_corte_1.png"
        viejo.write_bytes(b"x")
        _viejo(viejo)

        poda = podar_temporales(dias=7, raiz=self.raiz, aplicar=False)

        self.assertTrue(viejo.exists())
        self.assertEqual(poda.archivos, [viejo])

    def test_la_cuota_borra_los_mas_viejos_aunque_sean_recientes(self) -> None:
        archivos = []
        for n in range(3):
            ruta = self.tres_de / f"cuerpo_axonometrica_sin_corte_{n}.png"
            ruta.write_bytes(b"x" * 400_000)
            _nuevo(ruta)
            pasado = time.time() - (3 - n) * 60  # el 0 es el más viejo de los tres
            os.utime(ruta, (pasado, pasado))
            archivos.append(ruta)

        poda = podar_temporales(dias=7, max_tamano_mb=1, raiz=self.raiz)

        self.assertFalse(archivos[0].exists())
        self.assertEqual(poda.bytes, 400_000)
        self.assertLessEqual(sum(p.stat().st_size for p in self.tres_de.iterdir()), 1024 * 1024)

    def test_no_toca_otros_archivos_ni_symlinks(self) -> None:
        nota = self.tres_de / "nota.txt"
        nota.write_text("no es cache", encoding="utf-8")
        _viejo(nota)
        blanco = self.raiz / "afuera.png"
        blanco.write_bytes(b"x")
        _viejo(blanco)
        enlace = self.tres_de / "atajo.png"
        enlace.symlink_to(blanco)

        podar_temporales(dias=7, raiz=self.raiz)

        self.assertTrue(nota.exists())
        self.assertTrue(blanco.exists())
        self.assertTrue(enlace.is_symlink())

    def _voz(self, nombre: str = "video") -> Path:
        carpeta = self.raiz / "salida" / nombre / "manim" / "voiceovers"
        carpeta.mkdir(parents=True)
        (carpeta / "cache.json").write_text(
            json.dumps(
                [
                    {
                        "input_text": "hola",
                        "original_audio": "a.mp3",
                        "final_audio": "a.mp3",
                        "word_boundaries": [],
                    }
                ]
            ),
            encoding="utf-8",
        )
        return carpeta

    def test_borra_audios_huerfanos_y_conserva_los_referenciados(self) -> None:
        carpeta = self._voz()
        referido = carpeta / "a.mp3"
        huerfano = carpeta / "huerfano.mp3"
        resto = carpeta / "resto.wav"
        for ruta in (referido, huerfano, resto):
            ruta.write_bytes(b"x")
            _viejo(ruta)

        podar_temporales(dias=7, raiz=self.raiz)

        self.assertTrue(referido.exists())
        self.assertFalse(huerfano.exists())
        self.assertFalse(resto.exists())
        self.assertTrue((carpeta / "cache.json").exists())

    def test_no_borra_audio_reciente_aunque_no_este_en_el_manifiesto(self) -> None:
        carpeta = self._voz()
        huerfano = carpeta / "huerfano.mp3"
        huerfano.write_bytes(b"x")
        _nuevo(huerfano)

        podar_temporales(dias=7, raiz=self.raiz)

        self.assertTrue(huerfano.exists())

    def test_sin_nada_viejo_no_hay_poda(self) -> None:
        nuevo = self.tres_de / "cubo_frente_sin_corte_1.png"
        nuevo.write_bytes(b"x")
        _nuevo(nuevo)

        poda = podar_temporales(dias=7, raiz=self.raiz)

        self.assertEqual(poda.archivos, [])
        self.assertEqual(poda.bytes, 0)


if __name__ == "__main__":
    unittest.main()
