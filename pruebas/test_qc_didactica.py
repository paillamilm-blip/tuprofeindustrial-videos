"""Ficha QC con qué enseña y sus herramientas, y un guardado seguro de las herramientas."""

from unittest.mock import patch

from pruebas.datos_didacticos import datos_base, datos_concepto
from pruebas.test_tablero import ConRaiz
from tpi_videos.errores import ErrorMotor
from tpi_videos.guion import RecursosDidacticos, a_yaml, cargar_guion
from tpi_videos.panel import qc


class QCDidacticaTest(ConRaiz):
    def _escribir(self, datos, cabecera=("Decisión del dueño",)):
        self.guion.write_text(a_yaml(datos, list(cabecera)), encoding="utf-8")

    def test_cambio_real_invalida_aprobacion_y_no_borra_comentarios(self):
        self._escribir(datos_concepto())
        qc.aprobar(self.guion, "lote-antiguo")
        qc.cambiar_recursos(self.guion, RecursosDidacticos(panel=True, micro=False))
        g = cargar_guion(self.guion)
        self.assertTrue(g.recursos.panel)
        self.assertFalse(g.recursos.micro)
        self.assertEqual(qc.estado(self.guion), qc.POR_REVISAR)
        self.assertIn("# Decisión del dueño", self.guion.read_text(encoding="utf-8"))
        self.assertEqual(qc.decision(self.guion)["cola_id"], "lote-antiguo")

    def test_sin_cambios_no_toca_bytes_ni_aprobacion(self):
        self._escribir(datos_concepto())
        qc.aprobar(self.guion, "lote-1")
        antes = self.guion.read_bytes()
        qc.cambiar_recursos(self.guion, RecursosDidacticos(panel=False))
        self.assertEqual(self.guion.read_bytes(), antes)
        self.assertEqual(qc.estado(self.guion), qc.APROBADO)

    def test_volver_al_sugerido_quita_las_elecciones(self):
        self._escribir(datos_concepto())
        qc.cambiar_recursos(self.guion, RecursosDidacticos())
        self.assertIsNone(cargar_guion(self.guion).recursos)
        self.assertNotIn("recursos:", self.guion.read_text(encoding="utf-8"))
        qc.cambiar_recursos(self.guion, RecursosDidacticos(tabs=True))
        qc.cambiar_recursos(self.guion, None)
        self.assertIsNone(cargar_guion(self.guion).recursos)

    def test_conserva_lo_demas_del_guion(self):
        datos = datos_concepto()
        datos |= {"voz": "es-CL-LorenzoNeural", "velocidad": "+5%", "tema": "consola_mito", "molde": "mito_realidad",
                  "llamado": "¿Tú también lo creías?"}  # fmt: skip
        datos["pasos"][0]["mapa"] = [{"termino": "a", "concepto": "arista"}]
        datos["gancho_variantes"] = [{"texto": "Otro gancho", "voz": "Otro gancho"}]
        self._escribir(datos)
        antes = cargar_guion(self.guion)
        qc.cambiar_recursos(self.guion, RecursosDidacticos(panel=True))
        despues = cargar_guion(self.guion)
        self.assertEqual(despues.model_copy(update={"recursos": antes.recursos}), antes)

    def test_rutas_externas_y_ejemplos_no_se_escriben(self):
        ejemplo = self.raiz / "guiones" / "ejemplos" / "e.yaml"
        ejemplo.write_text(a_yaml(datos_concepto()), encoding="utf-8")
        fuera = self.raiz / "fuera.yaml"
        fuera.write_text(a_yaml(datos_concepto()), encoding="utf-8")
        for ruta in (ejemplo, fuera, self.raiz / "guiones" / ".." / "fuera.yaml"):
            with self.subTest(ruta=ruta):
                antes = ruta.read_bytes()
                with self.assertRaises(ErrorMotor):
                    qc.cambiar_recursos(ruta, RecursosDidacticos(panel=True))
                self.assertEqual(ruta.read_bytes(), antes)

    def test_symlink_hacia_afuera_no_se_escribe(self):
        fuera = self.raiz / "fuera.yaml"
        fuera.write_text(a_yaml(datos_concepto()), encoding="utf-8")
        enlace = self.raiz / "guiones" / "enlace.yaml"
        enlace.symlink_to(fuera)
        antes = fuera.read_bytes()
        with self.assertRaises(ErrorMotor):
            qc.cambiar_recursos(enlace, RecursosDidacticos(panel=True))
        self.assertEqual(fuera.read_bytes(), antes)

    def test_fallo_al_reemplazar_deja_el_original_exacto(self):
        self._escribir(datos_concepto())
        antes = self.guion.read_bytes()
        with patch("tpi_videos.panel.qc.os.replace", side_effect=OSError("disco lleno")), self.assertRaises(OSError):
            qc.cambiar_recursos(self.guion, RecursosDidacticos(panel=True))
        self.assertEqual(self.guion.read_bytes(), antes)
        self.assertEqual(sorted(p.name for p in self.guion.parent.iterdir() if p.is_file()), ["motor_vivo.yaml"])

    def test_yaml_invalido_no_se_reescribe(self):
        self.guion.write_text("titulo: [roto\n", encoding="utf-8")
        antes = self.guion.read_bytes()
        with self.assertRaises(ErrorMotor):
            qc.cambiar_recursos(self.guion, RecursosDidacticos(panel=True))
        self.assertEqual(self.guion.read_bytes(), antes)
        self.assertFalse(qc.ficha(self.guion).aprobable)


class FichaDidacticaTest(ConRaiz):
    def test_ficha_trae_contenido_y_decisiones_con_motivo(self):
        self.guion.write_text(a_yaml(datos_concepto()), encoding="utf-8")
        f = qc.ficha(self.guion)
        self.assertEqual(f.contenido.intenciones, ["dato"])
        decisiones = {d.clave: d for d in f.recursos}
        self.assertEqual(list(decisiones), ["tabs", "panel", "mapa_color", "micro"])
        self.assertEqual((decisiones["panel"].activo, decisiones["panel"].origen), (False, "guion"))
        self.assertIn("fórmulas", decisiones["panel"].razon)
        self.assertTrue(any("Conclusión" in t for t in f.tecnico))
        self.assertTrue(any("Resumen de fórmulas: apagado" in t for t in f.tecnico))

    def test_ficha_de_guion_antiguo_hereda_del_estilo(self):
        self.guion.write_text(a_yaml(datos_base()), encoding="utf-8")
        f = qc.ficha(self.guion)
        self.assertIsNone(f.contenido)
        self.assertTrue(all(d.origen == "tema" for d in f.recursos))

    def test_dos_fichas_no_comparten_la_lista(self):
        a = qc.Ficha(self.guion, "a", "", "", qc.POR_REVISAR, None, [], [], [], "")
        b = qc.Ficha(self.guion, "b", "", "", qc.POR_REVISAR, None, [], [], [], "")
        a.recursos.append("x")
        self.assertEqual(b.recursos, [])
