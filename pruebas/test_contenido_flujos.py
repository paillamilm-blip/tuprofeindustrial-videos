"""Qué enseña viaja intacto por ideas, CLI, lote, cobertura, ganchos y publicación."""

import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pruebas.datos_didacticos import datos_base, datos_concepto
from pruebas.test_ideas import idea
from tpi_videos import cli, publicar
from tpi_videos.errores import ErrorMotor
from tpi_videos.guion import Contenido, Guion, a_yaml
from tpi_videos.ideas import Idea, _limpiar

TANGENTE = {"intenciones": ["dato"], "objetivo": "Interpretar la pendiente local."}


class ContenidoFlujosTest(unittest.TestCase):
    def test_idea_json_retiene_intencion_y_objetivo(self):
        i = idea("Tangente", "pov", ["a", "b", "c"], contenido=TANGENTE)
        self.assertEqual(Idea.model_validate_json(i.model_dump_json()).contenido, i.contenido)

    def test_idea_guardada_antes_sigue_cargando(self):
        viejo = idea("Vieja", "pov", ["a", "b", "c"]).model_dump()
        viejo.pop("contenido", None)
        self.assertIsNone(Idea.model_validate(viejo).contenido)

    def test_idea_nueva_sin_contenido_se_descarta(self):
        ideas = [
            idea("A", "mito_realidad", ["a", "b", "c"], contenido=TANGENTE),
            idea("B", "reto", ["d", "e", "f"]),
        ]
        self.assertEqual([i.titulo for i in _limpiar(ideas, None, None, exigir_contenido=True)], ["A"])
        self.assertEqual(len(_limpiar(ideas, None, None)), 2)  # lo guardado no se exige

    def test_guion_encolado_no_vuelve_a_paso_a_paso_por_etiqueta(self):
        g = Guion.model_validate(datos_concepto())
        i = cli._idea_de_guion(g)
        self.assertEqual(i.contenido, g.contenido)

    def test_ideas_de_la_ia_falsa_traen_contenido(self):
        from tpi_videos.ideas import proponer_ideas

        from pruebas.ia_falsa import ClienteFalso

        with patch("tpi_videos.ia.cliente", return_value=ClienteFalso()):
            ideas = proponer_ideas(tema="Pitágoras")
        self.assertTrue(all(i.contenido is not None for i in ideas))


class ContenidoCliTest(unittest.TestCase):
    def _args(self, comando, *extra):
        return cli.construir_parser().parse_args([comando, *extra])

    def test_parser_acepta_contenido_json_en_los_tres_comandos(self):
        for comando in ("redactar", "producir", "ideas"):
            args = self._args(comando, "algo", "--contenido-json", json.dumps(TANGENTE))
            self.assertEqual(cli._contenido_de(args.contenido_json), Contenido(**TANGENTE))

    def test_contenido_desde_archivo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "c.json"
            ruta.write_text(json.dumps(TANGENTE), encoding="utf-8")
            self.assertEqual(cli._contenido_de(str(ruta)).intenciones, ["dato"])

    def test_vacio_es_automatico(self):
        self.assertIsNone(cli._contenido_de(None))
        self.assertIsNone(cli._contenido_de("  "))

    def test_json_invalido_avisa_sin_escribir_ni_llamar_a_la_ia(self):
        for malo in ('{"intenciones": ["curiosidad"], "objetivo": "x"}', "{no es json", "no/existe.json"):
            with self.subTest(malo=malo), tempfile.TemporaryDirectory() as carpeta:
                with (
                    patch.dict(os.environ, {"TPI_RAIZ": carpeta}),
                    patch("tpi_videos.redactor.redactar", side_effect=AssertionError("no debe redactar")),
                ):
                    args = self._args("redactar", "algo", "--contenido-json", malo)
                    with self.assertRaises(ErrorMotor):
                        cli.cmd_redactar(args)
                self.assertFalse(list(Path(carpeta).rglob("*.yaml")))

    def test_manual_gana_sobre_la_idea_y_llega_a_producir(self):
        vistos = {}

        def producir(valor, **kw):
            vistos.update(kw)
            raise ErrorMotor("alto acá")

        manual = {"intenciones": ["mito"], "objetivo": "Desarmar el mito."}
        args = argparse.Namespace(contenido_json=json.dumps(manual), progreso_json=False)
        with patch("tpi_videos.ideas.producir", side_effect=producir), self.assertRaises(ErrorMotor):
            cli._producir(args, "enunciado", contenido=Contenido(**TANGENTE))
        self.assertEqual(vistos["contenido"], Contenido(**manual))
        args = argparse.Namespace(contenido_json=None, progreso_json=False)
        with patch("tpi_videos.ideas.producir", side_effect=producir), self.assertRaises(ErrorMotor):
            cli._producir(args, "enunciado", contenido=Contenido(**TANGENTE))
        self.assertEqual(vistos["contenido"], Contenido(**TANGENTE))


class ContenidoRecorridosTest(unittest.TestCase):
    def test_producir_pasa_el_contenido_a_redactar(self):
        from tpi_videos import ideas

        vistos = {}

        def redactar(valor, **kw):
            vistos.update(kw)
            raise ErrorMotor("alto acá")

        with patch("tpi_videos.ideas.redactar", side_effect=redactar), self.assertRaises(ErrorMotor):
            ideas.producir("enunciado", contenido=Contenido(**TANGENTE))
        self.assertEqual(vistos["contenido"], Contenido(**TANGENTE))

    def test_reanudar_con_guion_escrito_no_llama_a_la_ia_y_conserva_su_contenido(self):
        from tpi_videos import ideas

        with tempfile.TemporaryDirectory() as carpeta, patch.dict(os.environ, {"TPI_RAIZ": carpeta}):
            ruta = Path(carpeta) / "guiones" / "c.yaml"
            ruta.parent.mkdir()
            ruta.write_text(a_yaml(datos_concepto()), encoding="utf-8")
            leidos = []

            def crear_video(r, **kw):
                from tpi_videos.guion import cargar_guion

                leidos.append(cargar_guion(r))
                raise ErrorMotor("alto acá")

            with (
                patch("tpi_videos.ideas.redactar", side_effect=AssertionError("no debe llamar a la IA")),
                patch("tpi_videos.render.crear_video", side_effect=crear_video),
                self.assertRaises(ErrorMotor),
            ):
                ideas.producir(
                    "x", contenido=Contenido(intenciones=["mito"], objetivo="Otro."),
                    reanudar={"guion": {"ruta": str(ruta)}},
                )  # fmt: skip
        self.assertEqual(leidos[0].contenido.intenciones, ["dato"])  # lo escrito no se reinfiere
        self.assertFalse(leidos[0].recursos.panel)

    def test_lote_pasa_el_contenido_de_cada_idea(self):
        from tpi_videos import lote

        vistos = []

        def producir(valor, **kw):
            vistos.append(kw.get("contenido"))
            raise ErrorMotor("alto acá")

        i = idea("Tangente", "pov", ["a", "b", "c"], contenido=TANGENTE)
        with patch("tpi_videos.lote.producir", side_effect=producir):
            items = lote.producir_lote([i], espera=0, reintentos=0)
        self.assertFalse(items[0].ok)
        self.assertEqual(vistos, [Contenido(**TANGENTE)])

    def test_completar_pasa_el_contenido_de_la_idea(self):
        from tpi_videos import completar

        vistos = {}

        def redactar(valor, **kw):
            vistos.update(kw)
            return type("R", (), {"ruta": Path("x.yaml")})()

        i = idea("Tangente", "pov", ["a", "b", "c"], contenido=TANGENTE)
        hueco = completar.Hueco("4° medio", "matematica", None, "Derivadas")
        with (
            patch("tpi_videos.ideas.proponer_ideas", return_value=[i]),
            patch("tpi_videos.redactor.redactar", side_effect=redactar),
        ):
            completar._escribir(hueco, lambda m: None)
        self.assertEqual(vistos["contenido"], Contenido(**TANGENTE))

    def test_gancho_conserva_contenido_y_ajustes_del_guion_base(self):
        from tpi_videos.ganchos import guion_de_vista_previa, idea_desde_guion

        datos = datos_concepto()
        datos["voz"] = "es-CL-LorenzoNeural"
        base = Guion.model_validate(datos)
        i = idea_desde_guion(base)
        self.assertEqual(i.contenido, base.contenido)
        vista = guion_de_vista_previa(i, i.ganchos[0], guion_base=base)
        self.assertEqual((vista.contenido, vista.recursos, vista.voz), (base.contenido, base.recursos, base.voz))
        solo = guion_de_vista_previa(i, i.ganchos[0])
        self.assertEqual(solo.contenido, base.contenido)


class KitPorContenidoTest(unittest.TestCase):
    def _kit(self, datos):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "g.yaml"
            ruta.write_text(a_yaml(datos), encoding="utf-8")
            salida = Path(carpeta) / "salida" / "g"
            salida.mkdir(parents=True)
            (salida / "linea_de_tiempo.json").write_text(json.dumps({"guion": str(ruta)}), encoding="utf-8")
            portada = salida / "portada.png"
            portada.write_bytes(b"x")
            with patch("tpi_videos.publicar.crear_portada", return_value=portada):
                kit = publicar.crear_kit(salida, con_ia=False)
            return kit.archivo.read_text(encoding="utf-8")

    def test_dato_sin_lenguaje_de_ejercicio(self):
        texto = self._kit(datos_concepto())
        for frase in ("ejerciciosresueltos", "Lo resolvemos", "lo resolviste", "ejercicios resueltos"):
            self.assertNotIn(frase.casefold(), texto.casefold())
        self.assertIn("Distinguir longitud y volumen", texto)

    def test_ejercicio_antiguo_conserva_su_copy(self):
        texto = self._kit(datos_base())
        self.assertIn("Lo resolvemos paso a paso", texto)
        self.assertIn("#ejerciciosresueltos", texto)
        self.assertIn("¿Lo resolviste igual? 👇", texto)

    def test_llamado_del_guion_se_respeta_en_un_dato(self):
        datos = datos_concepto()
        datos["llamado"] = "¿Tú también lo creías? Cuéntame 👇"
        texto = self._kit(datos)
        self.assertIn("¿Tú también lo creías? Cuéntame 👇", texto)


if __name__ == "__main__":
    unittest.main()
