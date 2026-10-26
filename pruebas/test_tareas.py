import unittest

from tpi_videos.panel.tareas import Tarea, Tareas


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
        Tareas._aplicar(
            tarea, {"etapa": "redactando", "avance": 0.0, "detalle": "Gemini está pensando"}
        )

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


if __name__ == "__main__":
    unittest.main()
