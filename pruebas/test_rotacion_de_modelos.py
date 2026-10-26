"""La cuota gratuita de Gemini se agota por modelo: el motor tiene que pasar al siguiente.

Un guion son 3-6 llamadas. Si el modelo por defecto queda sin cupo diario, `pedir_json`
debe reintentar con otro modelo gratuito (cada uno tiene su propio cupo) en vez de
abandonar el lote a la mitad.
"""

import unittest

from google.genai import errors
from pydantic import BaseModel

from tpi_videos import ia
from tpi_videos.errores import ErrorMotor
from tpi_videos.redactor import pedir_json


class _Respuesta:
    def __init__(self, texto: str):
        self.text = texto
        self.candidates = []
        self.prompt_feedback = None


class _ClienteFalso:
    """Devuelve `texto` solo con los modelos de `vivos`; los demás contestan 429 (o `errores`)."""

    def __init__(self, texto: str, vivos, errores=None):
        self.vivos = set(vivos)
        self.texto = texto
        self.errores = errores or {}
        self.llamados: list[str] = []

        class _Models:
            def __init__(self, dueno):
                self.dueno = dueno

            def generate_content(self, model, contents, config):
                self.dueno.llamados.append(model)
                if model in self.dueno.errores:
                    raise self.dueno.errores[model]
                if model in self.dueno.vivos:
                    return _Respuesta(self.dueno.texto)
                raise errors.ClientError(429, {"error": {"message": "RESOURCE_EXHAUSTED"}})

        self.models = _Models(self)


def _sin_servicio() -> errors.APIError:
    return errors.ServerError(503, {"error": {"message": "UNAVAILABLE: high demand"}})


class _Salida(BaseModel):
    titulo: str


def _pedir(cliente, modelo="gemini-3.8-flash", avisar=None):
    return pedir_json(cliente, modelo, "sistema", ["contenido"], _Salida, "low", avisar=avisar)


class CadenaDeModelosTest(unittest.TestCase):
    def test_el_pedido_va_primero_y_no_se_repite(self):
        cadena = ia.cadena_desde("gemini-3.6-flash")
        self.assertEqual(cadena[0], "gemini-3.6-flash")
        self.assertEqual(len(cadena), len(set(cadena)))

    def test_la_cadena_solo_usa_modelos_gratuitos(self):
        for modelo in ia.cadena_desde(ia.MODELO_POR_DEFECTO):
            with self.subTest(modelo=modelo):
                self.assertIn(modelo, ia.MODELOS_GRATUITOS)


class EsCuotaAgotadaTest(unittest.TestCase):
    def test_429_es_cuota_agotada(self):
        self.assertTrue(ia.es_cuota_agotada(errors.ClientError(429, {"error": {"message": "x"}})))

    def test_otros_codigos_no(self):
        self.assertFalse(ia.es_cuota_agotada(errors.ClientError(404, {"error": {"message": "x"}})))
        self.assertFalse(ia.es_cuota_agotada(ValueError("sin cupo")))


class RotacionTest(unittest.TestCase):
    def test_sin_cupo_pasa_al_siguente_modelo(self):
        cliente = _ClienteFalso('{"titulo": "ok"}', vivos=["gemini-3.6-flash"])
        salida = _pedir(cliente)
        self.assertEqual(salida.titulo, "ok")
        self.assertEqual(cliente.llamados[0], ia.MODELO_POR_DEFECTO)
        self.assertIn("gemini-3.6-flash", cliente.llamados)

    def test_avisa_que_cambio_de_modelo(self):
        oidos: list[tuple[str, str]] = []
        _pedir(
            _ClienteFalso('{"titulo": "ok"}', vivos=["gemini-3.5-flash-lite"]),
            avisar=lambda mensaje, usado: oidos.append((mensaje, usado)),
        )
        self.assertEqual(len(oidos), 1, oidos)
        mensaje, usado = oidos[0]
        self.assertEqual(usado, "gemini-3.5-flash-lite")
        self.assertIn(ia.MODELO_POR_DEFECTO, mensaje)

    def test_error_que_no_es_cuota_no_rota(self):
        cliente = _ClienteFalso("", vivos=[], errores={"gemini-3.8-flash": ValueError("sin internet")})
        with self.assertRaises(ErrorMotor):
            _pedir(cliente)
        self.assertEqual(cliente.llamados, ["gemini-3.8-flash"])

    def test_modelo_saturado_tambien_deja_paso_al_siguiente(self):
        # 503 «high demand» no es tu cuota: es ese modelo saturado, y otro gratuito responde.
        cliente = _ClienteFalso(
            '{"titulo": "ok"}',
            vivos=["gemini-3.6-flash"],
            errores={"gemini-3.8-flash": _sin_servicio()},
        )
        self.assertEqual(_pedir(cliente).titulo, "ok")
        self.assertEqual(cliente.llamados, ["gemini-3.8-flash", "gemini-3.6-flash"])

    def test_agotada_toda_la_cadena_lo_dice_claro(self):
        with self.assertRaises(ErrorMotor) as caja:
            _pedir(_ClienteFalso("", vivos=[]))
        self.assertIn("cupo", str(caja.exception).lower())
        self.assertTrue(caja.exception.transitorio)

    def test_si_ninguno_fallo_por_cuota_manda_el_primer_error(self):
        # Un 400 (pedido mal formado) se repetiría en los cuatro: hay que ver el primero.
        cliente = _ClienteFalso(
            "",
            vivos=[],
            errores={
                "gemini-3.8-flash": errors.ClientError(400, {"error": {"message": "schema inválida"}}),
                "gemini-3.6-flash": _sin_servicio(),
                "gemini-3.5-flash-lite": _sin_servicio(),
                "gemini-3.1-flash-lite": _sin_servicio(),
            },
        )
        with self.assertRaises(ErrorMotor) as caja:
            _pedir(cliente)
        self.assertIn("400", str(caja.exception) + str(caja.exception.ayuda or ""))
        self.assertEqual(cliente.llamados, ["gemini-3.8-flash"])

    def test_con_cupo_en_el_primero_no_gira_nada(self):
        oidos: list[str] = []
        cliente = _ClienteFalso('{"titulo": "ok"}', vivos=[ia.MODELO_POR_DEFECTO])
        _pedir(cliente, avisar=lambda mensaje, usado: oidos.append(mensaje))
        self.assertEqual(cliente.llamados, [ia.MODELO_POR_DEFECTO])
        self.assertEqual(oidos, [])


class EstadoDeCuotaTest(unittest.TestCase):
    def test_clasifica_modelo_por_modelo(self):
        cliente = _ClienteFalso(
            "OK",
            vivos=["gemini-3.5-flash-lite"],
            errores={"gemini-3.6-flash": _sin_servicio()},
        )
        cadena = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
        estado = dict(ia.estado_de_cuota(cliente, cadena))
        self.assertEqual(estado["gemini-3.8-flash"], "sin cupo")
        self.assertEqual(estado["gemini-3.6-flash"], "saturado")
        self.assertEqual(estado["gemini-3.5-flash-lite"], "ok")


if __name__ == "__main__":
    unittest.main()
