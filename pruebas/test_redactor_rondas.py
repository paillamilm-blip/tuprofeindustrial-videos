"""El bucle de corrección no bota un guion bueno porque la última corrección vino rota."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tpi_videos import redactor
from tpi_videos.redactor import EJEMPLO, RevisionIA


class RondasTest(unittest.TestCase):
    def _redactar(self, respuestas):
        with tempfile.TemporaryDirectory() as carpeta:
            with (
                mock.patch.object(redactor.ia, "cliente", return_value=object()),
                mock.patch.object(redactor, "raiz_proyecto", return_value=Path(carpeta)),
                mock.patch.object(redactor, "pedir_json", side_effect=respuestas),
                mock.patch.object(redactor, "errores_latex", return_value=[]),
                mock.patch.object(redactor, "problemas_de_formato", return_value=[]),
            ):
                r = redactor.redactar("Una piedra cae desde 20 metros.", revisar_con_ia=True)
                texto = r.ruta.read_text(encoding="utf-8")
        return r, texto

    def test_si_la_ultima_correccion_viene_rota_queda_la_ultima_que_valido(self):
        rota = EJEMPLO.model_copy(update={"pasos": []})  # un guion sin pasos no valida
        rechazo = RevisionIA(aprobado=False, problemas=["paso 2: falta decir para qué se despeja t"])
        r, texto = self._redactar([EJEMPLO, rechazo, rota, rota])
        self.assertEqual(r.guion.titulo, EJEMPLO.titulo)
        self.assertEqual(len(r.guion.pasos), len(EJEMPLO.pasos))
        self.assertIn("revisor: paso 2: falta decir para qué se despeja t", r.pendientes)
        self.assertIn("Quedaron observaciones por revisar", texto)  # el profe ve qué revisar

    def test_si_ninguna_ronda_valida_avisa_como_siempre(self):
        rota = EJEMPLO.model_copy(update={"pasos": []})
        from tpi_videos.errores import ErrorMotor

        with self.assertRaisesRegex(ErrorMotor, "No logré un guion válido"):
            self._redactar([rota, rota, rota])

    def test_el_resultado_dice_el_modelo_que_escribio_de_verdad(self):
        def con_respaldo(*args, avisar=None, **kwargs):
            if avisar:
                avisar("gemini-3.8-flash se quedó sin cupo: sigo con gemini-3.6-flash.", "gemini-3.6-flash")
            return EJEMPLO

        with tempfile.TemporaryDirectory() as carpeta:
            with (
                mock.patch.object(redactor.ia, "cliente", return_value=object()),
                mock.patch.object(redactor, "raiz_proyecto", return_value=Path(carpeta)),
                mock.patch.object(redactor, "pedir_json", side_effect=con_respaldo),
                mock.patch.object(redactor, "errores_latex", return_value=[]),
                mock.patch.object(redactor, "problemas_de_formato", return_value=[]),
            ):
                r = redactor.redactar("Una piedra cae desde 20 metros.", revisar_con_ia=False)
                cabecera = r.ruta.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(r.modelo, "gemini-3.6-flash")
        self.assertIn("gemini-3.6-flash", cabecera)  # el archivo y el resultado dicen lo mismo


if __name__ == "__main__":
    unittest.main()
