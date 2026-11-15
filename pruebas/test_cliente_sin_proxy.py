"""El cliente de Gemini no debe caer si el entorno trae NO_PROXY con IPv6 («[::1]»).

httpx (el transporte del SDK) parsea cada entrada de NO_PROXY como URL y revienta con
«Invalid port: ':1]'» al construir el cliente, tanto el sync como el async. El motor arma su
cliente sin leer ese entorno: NO_PROXY solo exime direcciones locales y la API de Gemini es
remota, así que no hace falta; si hay un proxy real, se conserva.
"""

import os
import unittest
from unittest.mock import patch

NO_PROXY_HOSTIL = "localhost,.localhost,127.0.0.1,127.0.0.0/8,[::1],::1"
VARS_PROXY = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")


class ClienteSinProxyTest(unittest.TestCase):
    def setUp(self):
        self._prev = {k: os.environ.get(k) for k in ("NO_PROXY", "no_proxy", *VARS_PROXY)}
        os.environ["NO_PROXY"] = NO_PROXY_HOSTIL
        os.environ["no_proxy"] = NO_PROXY_HOSTIL
        for k in VARS_PROXY:  # este Mac no trae proxy real: solo NO_PROXY
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_el_redactor_crea_su_cliente_sin_caer(self):
        from tpi_videos import ia

        cliente = ia.cliente(clave="falsa")  # construir el cliente no llama a la red
        self.addCleanup(cliente.close)
        self.assertIsNotNone(cliente)

    def test_la_voz_crea_su_cliente_sin_caer(self):
        from tpi_videos import voz_gemini

        with patch("tpi_videos.ia.clave_obligatoria", return_value="falsa"):
            cliente = voz_gemini.cliente_tts()
        self.addCleanup(cliente.close)
        self.assertIsNotNone(cliente)

    def test_el_cliente_no_lee_el_entorno_pero_conserva_un_proxy_real(self):
        from tpi_videos.ia import args_httpx

        self.assertFalse(args_httpx()["trust_env"])
        self.assertNotIn("proxy", args_httpx())  # sin proxy configurado, no se inventa uno
        os.environ["HTTPS_PROXY"] = "http://proxy.local:8080"
        self.assertEqual(args_httpx()["proxy"], "http://proxy.local:8080")
        self.assertFalse(args_httpx()["trust_env"])