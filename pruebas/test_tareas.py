import asyncio
import json
import os
import unittest
from unittest import mock

from tpi_videos.errores import ErrorMotor
from tpi_videos.panel.tareas import Tarea, Tareas, consultar


def _proceso_falso(con_evento: bool = True):
    """Un subprocess de mentira que emite (opcionalmente) un evento «listo» y termina en 0."""

    class _Stream:
        def __aiter__(self):
            async def gen():
                if con_evento:
                    yield json.dumps({"etapa": "listo", "avance": 1.0}).encode() + b"\n"

            return gen()

    class _Proc:
        def __init__(self):
            self.stdout, self.stderr = _Stream(), _Stream()
            self.returncode, self.pid = 0, 999_999  # un pid que no existe: killpg nunca aplica

        async def wait(self):
            return 0

    async def _exec(*_a, **_kw):
        return _Proc()

    return _exec


class TareasTest(unittest.TestCase):
    def test_evento_con_video_actualiza_su_ficha(self) -> None:
        tarea = Tarea(nombre="Lote", args=[])
        Tareas._aplicar(
            tarea,
            {
                "etapa": "animacion",
                "avance": 0.3,
                "detalle": "Video 2 de 3 · animando",
                "video": 2,
                "total": 3,
                "video_avance": 0.55,
                "fase": "animando",
                "estado": "animando",
            },
        )

        self.assertEqual(tarea.videos[2]["estado"], "animando")
        self.assertEqual(tarea.videos[2]["total"], 3)
        self.assertAlmostEqual(tarea.videos[2]["avance"], 0.55)
        self.assertAlmostEqual(tarea.avance, 0.3)

    def test_un_avance_menor_no_retrocede(self) -> None:
        tarea = Tarea(nombre="Lote", args=[])
        Tareas._aplicar(
            tarea,
            {"etapa": "animacion", "avance": 0.5, "video": 1, "total": 3, "video_avance": 0.6},
        )
        Tareas._aplicar(
            tarea,
            {"etapa": "animacion", "avance": 0.4, "video": 1, "total": 3, "video_avance": 0.2},
        )

        self.assertAlmostEqual(tarea.videos[1]["avance"], 0.6)
        self.assertAlmostEqual(tarea.avance, 0.5)

    def test_evento_sin_video_mantiene_el_comportamiento(self) -> None:
        tarea = Tarea(nombre="Lote", args=[])
        Tareas._aplicar(tarea, {"etapa": "redactando", "avance": 0.0, "detalle": "Gemini está pensando"})

        self.assertEqual(tarea.etapa, "redactando")
        self.assertEqual(tarea.detalle, "Gemini está pensando")
        self.assertEqual(tarea.videos, {})

    def test_resultado_conserva_pendiente_y_cola(self) -> None:
        tarea = Tarea(nombre="Lote", args=[])
        Tareas._aplicar(
            tarea,
            {"etapa": "resultado", "avance": 1.0, "pendiente": True, "cola_id": "abc", "lote": []},
        )

        self.assertTrue(tarea.resultado["pendiente"])
        self.assertEqual(tarea.cola_id, "abc")


class CorrerTest(unittest.IsolatedAsyncioTestCase):
    """Un trabajo que estalla al leer del motor NO debe tapar la fila de TAREAS para siempre."""

    async def test_un_fallo_al_aplicar_deja_la_fila_libre(self) -> None:
        t = Tareas()
        with (
            mock.patch.object(asyncio, "create_subprocess_exec", _proceso_falso()),
            mock.patch.object(os, "killpg", lambda *a, **kw: None),
        ):

            def boom(_tarea):
                raise RuntimeError("callback roto")

            tarea = t._prender("X", ["ideas"])
            resultado = await t._correr(tarea, boom)

        self.assertTrue(resultado.terminada)
        self.assertIsNotNone(resultado.error)
        self.assertFalse(t.ocupado())
        # un trabajo nuevo puede arrancar sin que _prender reclame
        t._prender("Y", ["ideas"])

    async def test_un_trabajo_normal_se_cierra_y_libera(self) -> None:
        t = Tareas()
        with mock.patch.object(asyncio, "create_subprocess_exec", _proceso_falso()):
            tarea = t._prender("X", ["ideas"])
            resultado = await t._correr(tarea, None)

        self.assertTrue(resultado.ok)
        self.assertFalse(t.ocupado())


def _proceso_con_avisos(eventos: list[dict]):
    """Un subprocess de mentira que emite varios avisos por stdout y termina en 0."""

    class _Stream:
        def __aiter__(self):
            async def gen():
                for evento in eventos:
                    yield json.dumps(evento).encode() + b"\n"

            return gen()

    class _Proc:
        def __init__(self):
            self.stdout, self.stderr = _Stream(), _Stream()
            self.returncode, self.pid = 0, 999_999

        async def wait(self):
            return 0

        def kill(self):
            pass

    async def _exec(*_a, **_kw):
        return _Proc()

    return _exec


class ConsultarTest(unittest.IsolatedAsyncioTestCase):
    """`consultar` pinta en vivo lo que el motor avisa, no sólo lo que trae al volver."""

    async def test_cada_aviso_llega_y_el_final_es_el_resultado(self) -> None:
        vistos: list[dict] = []
        eventos = [
            {"etapa": "redactando", "avance": 0.0, "detalle": "Gemini está pensando 3 ideas…"},
            {"etapa": "resultado", "avance": 1.0, "ideas": [{"titulo": "Uno"}]},
        ]
        with mock.patch.object(asyncio, "create_subprocess_exec", _proceso_con_avisos(eventos)):
            final = await consultar(["ideas", "--", "Porcentajes"], al_evento=vistos.append)

        self.assertEqual([e["etapa"] for e in vistos], ["redactando", "resultado"])
        self.assertEqual(final["ideas"], [{"titulo": "Uno"}])

    async def test_un_aviso_de_error_se_vuelve_error_del_motor(self) -> None:
        eventos = [{"etapa": "error", "mensaje": "Sin clave de Gemini", "ayuda": "Mírala en Ajustes"}]
        with mock.patch.object(asyncio, "create_subprocess_exec", _proceso_con_avisos(eventos)):
            with self.assertRaises(ErrorMotor) as sube:
                await consultar(["ideas", "--", "Porcentajes"])

        self.assertIn("Sin clave de Gemini", str(sube.exception))


if __name__ == "__main__":
    unittest.main()
