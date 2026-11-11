"""El tono (pitch) de la voz: configurable en la marca y cableado hasta el sintetizador edge-tts."""

import unittest
from pathlib import Path

from pydantic import ValidationError

from tpi_videos.config import Voz
from tpi_videos.escena import OpcionesEscena
from tpi_videos.voces import crear_servicio


class TonoEnMarcaTest(unittest.TestCase):
    def test_la_voz_acepta_tono_con_signo_y_hz(self):
        self.assertEqual(Voz(tono="+25Hz").tono, "+25Hz")
        self.assertEqual(Voz(tono="-10Hz").tono, "-10Hz")

    def test_un_tono_sin_formato_se_rechaza(self):
        with self.assertRaises(ValidationError):
            Voz(tono="25")
        with self.assertRaises(ValidationError):
            Voz(tono="+25%")

    def test_sin_decir_tono_queda_neutro(self):
        self.assertEqual(Voz().tono, "+0Hz")


class TonoHastaElServicioTest(unittest.TestCase):
    def test_crear_servicio_pasa_el_tono_al_sintetizador(self):
        servicio = crear_servicio("edge", "es-CL-LorenzoNeural", "-20%", "+25Hz")
        self.assertEqual(servicio.base.tono, "+25Hz")
        self.assertEqual(servicio.base.velocidad, "-20%")

    def test_sin_tono_el_servicio_queda_neutro(self):
        servicio = crear_servicio("edge", "es-CL-LorenzoNeural", "+5%")
        self.assertEqual(servicio.base.tono, "+0Hz")

    def test_las_opciones_de_escena_llevan_el_tono(self):
        op = OpcionesEscena("edge", "es-CL-LorenzoNeural", "-20%", Path("linea.json"), tono="+25Hz")
        self.assertEqual(op.tono, "+25Hz")


if __name__ == "__main__":
    unittest.main()