"""El tablero de supervisión: aprobación de guiones (QC), columnas de la cola y producción en lote."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tpi_videos import cola
from tpi_videos.panel import qc
from tpi_videos.panel.supervision import (
    COMPLETADOS,
    EN_RENDER,
    PENDIENTES,
    LanzamientoEnLote,
    args_de_lote,
    columnas,
    lotes_por_producir,
)

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLO = RAIZ / "guiones" / "ejemplos" / "motor_vivo.yaml"


class ConRaiz(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.viejo = os.environ.get("TPI_RAIZ")
        os.environ["TPI_RAIZ"] = self.tmp.name
        self.raiz = Path(self.tmp.name).resolve()  # macOS: /var → /private/var
        (self.raiz / "salida").mkdir()
        (self.raiz / "guiones" / "ejemplos").mkdir(parents=True)
        self.guion = self.raiz / "guiones" / "motor_vivo.yaml"
        shutil.copy(EJEMPLO, self.guion)

    def tearDown(self) -> None:
        if self.viejo is None:
            os.environ.pop("TPI_RAIZ", None)
        else:
            os.environ["TPI_RAIZ"] = self.viejo
        self.tmp.cleanup()


class AprobacionTest(ConRaiz):
    def test_un_guion_nuevo_espera_revision(self):
        self.assertEqual(qc.estado(self.guion), qc.POR_REVISAR)
        self.assertEqual(qc.guiones(), [self.guion])

    def test_aprobar_lo_saca_de_la_lista_y_editarlo_lo_devuelve(self):
        qc.aprobar(self.guion, "lote-1")
        self.assertEqual(qc.estado(self.guion), qc.APROBADO)
        self.assertEqual(qc.guiones(), [])
        self.assertEqual(qc.guiones(incluir_decididos=True), [self.guion])
        self.guion.write_text(self.guion.read_text(encoding="utf-8") + "\n# editado\n", encoding="utf-8")
        self.assertEqual(qc.estado(self.guion), qc.POR_REVISAR)

    def test_rechazar_guarda_la_nota(self):
        qc.rechazar(self.guion, "  falta el reto  ")
        self.assertEqual(qc.estado(self.guion), qc.RECHAZADO)
        self.assertEqual(qc.decision(self.guion)["nota"], "falta el reto")

    def test_los_ejemplos_y_lo_de_afuera_no_se_aprueban(self):
        ejemplo = self.raiz / "guiones" / "ejemplos" / "x.yaml"
        shutil.copy(EJEMPLO, ejemplo)
        afuera = self.raiz / "otro.yaml"
        shutil.copy(EJEMPLO, afuera)
        self.assertFalse(qc.guion_revisable(ejemplo))
        self.assertFalse(qc.guion_revisable(afuera))
        from tpi_videos.errores import ErrorMotor

        with self.assertRaises(ErrorMotor):
            qc.aprobar(afuera, None)

    def test_la_ficha_muestra_lo_que_se_lee_y_esconde_lo_tecnico(self):
        f = qc.ficha(self.guion)
        self.assertEqual(f.titulo, "La pendiente, el área y el cilindro abierto")
        self.assertTrue(f.aprobable)
        self.assertEqual(f.voces[0].seccion, "gancho")
        self.assertTrue(all("<break" not in v.texto for v in f.voces))
        self.assertTrue(any("tangente" in linea for linea in f.tecnico))
        self.assertTrue(any("despiece" in linea for linea in f.tecnico))
        self.assertIn("titulo:", f.yaml)

    def test_las_pausas_quedan_aparte_del_texto(self):
        texto = self.guion.read_text(encoding="utf-8").replace(
            'voz: "La recta tangente baja', 'voz: "Mira. <break time=\\"1.5s\\"/> La recta tangente baja'
        )
        self.guion.write_text(texto, encoding="utf-8")
        voz = next(v for v in qc.ficha(self.guion).voces if v.seccion == "paso 1")
        self.assertEqual(voz.pausas, [1.5])
        self.assertTrue(voz.texto.startswith("Mira. La recta tangente"))

    def test_un_yaml_roto_se_puede_rechazar_pero_no_aprobar(self):
        self.guion.write_text("titulo: [sin cerrar\n", encoding="utf-8")
        f = qc.ficha(self.guion)
        self.assertFalse(f.aprobable)
        self.assertTrue(f.error)

    def test_aprobar_lo_deja_en_la_cola_sin_producirlo(self):
        from tpi_videos.cli import encolar_guion

        lote_id = encolar_guion(self.guion)
        lote = next(lote for lote in cola.cargar()["lotes"] if lote["id"] == lote_id)
        self.assertEqual(len(lote["videos"]), 1)
        video = lote["videos"][0]
        self.assertEqual(video["estado"], "en_cola")
        self.assertEqual(Path(video["hitos"]["guion"]["ruta"]), self.guion.resolve())
        self.assertEqual(lotes_por_producir(cola.cargar()), [lote_id])


def _datos(*videos_por_lote):
    lotes = []
    for i, videos in enumerate(videos_por_lote, 1):
        lotes.append(
            {
                "id": f"L{i}",
                "tema": f"Tema {i}",
                "estado": "en_curso",
                "actualizado": f"2026-11-10T10:0{i}:00",
                "videos": [
                    {
                        "id": f"L{i}-{n}",
                        "posicion": n,
                        "estado": estado,
                        "avance": 0.5 if estado == "animando" else 0.0,
                        "idea": {"titulo": f"Video {i}.{n}"},
                        "actualizado": f"2026-11-10T10:0{i}:{n:02d}",
                    }
                    for n, estado in enumerate(videos, 1)
                ],
            }
        )
    return {"version": 1, "lotes": lotes}


class ColumnasTest(unittest.TestCase):
    def test_cada_estado_cae_en_su_columna(self):
        datos = _datos(["en_cola", "animando", "listo"], ["fallo", "interrumpido"])
        fichas = columnas(datos)
        self.assertEqual({f.video_id for f in fichas[PENDIENTES]}, {"L1-1", "L2-1", "L2-2"})
        self.assertEqual([f.video_id for f in fichas[EN_RENDER]], ["L1-2"])
        self.assertEqual([f.video_id for f in fichas[COMPLETADOS]], ["L1-3"])
        self.assertTrue(next(f for f in fichas[PENDIENTES] if f.video_id == "L2-1").fallo)

    def test_lo_descartado_no_se_muestra(self):
        datos = _datos(["en_cola"])
        datos["lotes"][0]["estado"] = "descartado"
        self.assertEqual(sum(len(v) for v in columnas(datos).values()), 0)

    def test_el_avance_en_vivo_pisa_lo_guardado(self):
        datos = _datos(["en_cola"])
        fichas = columnas(datos, {"L1-1": {"estado": "animando", "avance": 0.8}})
        self.assertEqual(fichas[EN_RENDER][0].avance, 0.8)

    def test_completados_se_corta_en_lo_reciente(self):
        datos = _datos(["listo"] * 20)
        self.assertEqual(len(columnas(datos)[COMPLETADOS]), 12)


class LoteTest(unittest.TestCase):
    def test_solo_los_lotes_con_videos_esperando(self):
        datos = _datos(["listo"], ["en_cola"], ["fallo"], ["pendiente_ia", "listo"])
        self.assertEqual(lotes_por_producir(datos), ["L2", "L4"])
        self.assertEqual(args_de_lote("L2"), ["lote", "--reanudar", "--cola-id", "L2"])

    def test_el_lanzamiento_sigue_de_a_uno_y_no_repite(self):
        datos = _datos(["en_cola"], ["en_cola"])
        lanza = LanzamientoEnLote()
        self.assertIsNone(lanza.siguiente(datos, ocupado=False), "sin empezar no lanza nada")
        lanza.empezar()
        self.assertEqual(lanza.siguiente(datos, ocupado=False), args_de_lote("L1"))
        self.assertIsNone(lanza.siguiente(datos, ocupado=True), "espera a que la fila quede libre")
        # L1 quedó pendiente (la IA no respondió): no se relanza en esta pasada.
        self.assertEqual(lanza.siguiente(datos, ocupado=False), args_de_lote("L2"))
        self.assertIsNone(lanza.siguiente(datos, ocupado=False))
        self.assertFalse(lanza.activo)


class SoloEncolarTest(ConRaiz):
    def test_el_comando_deja_el_guion_en_la_cola(self):
        from tpi_videos import cli

        args = cli.construir_parser().parse_args(["lote", str(self.guion), "--solo-encolar"])
        self.assertEqual(cli.cmd_lote(args), 0)
        lote = cola.cargar()["lotes"][0]
        self.assertEqual([v["estado"] for v in lote["videos"]], ["en_cola"])
        self.assertFalse(cola.candado_tomado())

    def test_solo_encolar_sin_guiones_se_explica(self):
        from tpi_videos import cli
        from tpi_videos.errores import ErrorMotor

        args = cli.construir_parser().parse_args(["lote", "Porcentajes", "--solo-encolar"])
        with self.assertRaises(ErrorMotor):
            cli.cmd_lote(args)


if __name__ == "__main__":
    unittest.main()
