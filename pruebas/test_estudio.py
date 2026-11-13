"""El Estudio (la pantalla única): la lógica que no necesita navegador.

Cada tipo de contenido lleva al molde correcto, los comandos que se lanzan existen en el CLI, los
cambios del guion se validan antes de escribir (un clic no deja un guion roto), los atajos aguantan un
archivo dañado, la URL no puede abrir un archivo fuera de guiones/ y el llamado a la acción elegido
llega al texto de la publicación.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from tpi_videos.cli import construir_parser
from tpi_videos.errores import ErrorMotor
from tpi_videos.guion import Guion, cargar_guion
from tpi_videos.moldes import MOLDES
from tpi_videos.niveles import NIVELES
from tpi_videos.panel import estudio
from tpi_videos.publicar import LLAMADOS_DE_SIEMPRE, aplicar_llamado, textos_de_plantilla
from tpi_videos.redactor import DIBUJOS, GanchoAltIA, GuionIA, _aplicar_eleccion, dibujo_de_tipo

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "guiones" / "caben_ocho_cubos.yaml"


class _ConRaiz(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        (self.raiz / "guiones").mkdir()
        self.ruta = self.raiz / "guiones" / "cubos.yaml"
        shutil.copy(GUION, self.ruta)
        entorno = patch.dict(os.environ, {"TPI_RAIZ": str(self.raiz)})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.addCleanup(self.tmp.cleanup)


class TiposTest(unittest.TestCase):
    def test_cada_tipo_lleva_a_un_molde_que_existe(self) -> None:
        for tipo in estudio.TIPOS.values():
            if tipo.molde:
                self.assertIn(tipo.molde, MOLDES, tipo.clave)
            self.assertEqual(len(tipo.cierres), 3, tipo.clave)
            self.assertEqual(len(tipo.llamados), 3, tipo.clave)
            for c in tipo.cierres:
                self.assertLessEqual(len(c), estudio.LARGO_CIERRE)
            for llamado in tipo.llamados:
                self.assertLessEqual(len(llamado), estudio.LARGO_LLAMADO)

    def test_el_molde_vuelve_a_su_tipo(self) -> None:
        self.assertEqual(estudio.tipo_de_molde("mito_realidad"), "mito")
        self.assertEqual(estudio.tipo_de_molde("tres_errores"), "error")
        self.assertEqual(estudio.tipo_de_molde(None), "pasos")
        self.assertEqual(estudio.tipo_de_molde("pov"), "pasos")  # sin chip propio


class ComandosTest(unittest.TestCase):
    def test_redactar_con_molde_y_nivel_lo_entiende_el_cli(self) -> None:
        args = estudio.args_redactar("-3 + x = 2, ¿cuánto vale x?", "1° medio", "mito")
        leidos = construir_parser().parse_args(args)
        self.assertEqual(leidos.molde, "mito_realidad")
        self.assertEqual(leidos.nivel, "1° medio")
        self.assertEqual(" ".join(leidos.enunciado), "-3 + x = 2, ¿cuánto vale x?")

    def test_paso_a_paso_no_pide_molde(self) -> None:
        args = estudio.args_redactar("Una escalera de 5 m se apoya en una pared", None, "pasos")
        self.assertNotIn("--molde", args)
        self.assertNotIn("--nivel", args)

    def test_una_idea_vacia_o_corta_no_sale(self) -> None:
        for idea in ("", "   ", "x=2"):
            with self.assertRaises(ErrorMotor):
                estudio.args_redactar(idea, None, "pasos")

    def test_un_nivel_inventado_no_sale(self) -> None:
        with self.assertRaises(ErrorMotor):
            estudio.args_redactar("Una escalera de 5 m se apoya en una pared", "9° medio", "pasos")

    def test_el_video_final_trae_kit_y_el_borrador_no(self) -> None:
        parser = construir_parser()
        final = parser.parse_args(estudio.args_video(Path("g.yaml")))
        borrador = parser.parse_args(estudio.args_video(Path("g.yaml"), borrador=True))
        self.assertTrue(final.kit)
        self.assertFalse(final.borrador)
        self.assertTrue(borrador.borrador)
        self.assertFalse(borrador.kit)

    def test_si_el_kit_falla_el_video_no_se_pierde(self) -> None:
        from tpi_videos.cli import _kit_tras_crear

        with patch("tpi_videos.publicar.crear_kit", side_effect=ErrorMotor("sin internet")):
            archivo, aviso = _kit_tras_crear(Path("salida/x/x.mp4"), json_activo=False)
            self.assertIsNone(archivo)
            self.assertIn("sin internet", aviso)
        with patch("tpi_videos.publicar.crear_kit", side_effect=RuntimeError("raro")):
            self.assertIsNone(_kit_tras_crear(Path("salida/x/x.mp4"), json_activo=False)[0])

    def test_redibujar_lo_entiende_el_cli(self) -> None:
        leidos = construir_parser().parse_args(estudio.args_redibujar(Path("g.yaml"), 2, "escala"))
        self.assertEqual((leidos.paso, leidos.tipo), (2, "escala"))


class AtajosTest(_ConRaiz):
    def test_sin_archivo_parte_de_cero(self) -> None:
        self.assertEqual(estudio.cargar_atajos()["recientes"], [])
        self.assertEqual(estudio.cargar_atajos()["tipo"], "pasos")

    def test_un_archivo_roto_no_bota_la_pantalla(self) -> None:
        archivo = self.raiz / "mis_ajustes" / "estudio.json"
        archivo.parent.mkdir()
        archivo.write_text("{ no es json", encoding="utf-8")
        self.assertEqual(estudio.cargar_atajos()["recientes"], [])
        archivo.write_text(
            json.dumps({"tipo": "inventado", "recientes": [{"idea": 3}, "x"]}), encoding="utf-8"
        )
        self.assertEqual(estudio.cargar_atajos(), {"nivel": "", "tipo": "pasos", "recientes": []})

    def test_recuerda_lo_ultimo_sin_repetir_y_con_tope(self) -> None:
        for n in range(8):
            estudio.recordar(f"Ejercicio número {n}", NIVELES[0], "reto")
        estudio.recordar("ejercicio NÚMERO 3", NIVELES[1], "mito")  # la misma idea sube al inicio
        atajos = estudio.cargar_atajos()
        self.assertEqual(len(atajos["recientes"]), estudio.MAX_ATAJOS)
        self.assertEqual(atajos["recientes"][0]["idea"], "ejercicio NÚMERO 3")
        self.assertEqual(sum("3" in r["idea"] for r in atajos["recientes"]), 1)
        self.assertEqual((atajos["nivel"], atajos["tipo"]), (NIVELES[1], "mito"))

    def test_el_resumen_de_un_atajo_se_acorta(self) -> None:
        texto = estudio.resumen_atajo({"idea": "a" * 200, "nivel": "1° medio", "tipo": "mito"})
        self.assertTrue(texto.startswith("Mito · 1° medio · "))
        self.assertTrue(texto.endswith("…"))


class RutaTest(_ConRaiz):
    def test_abre_un_guion_de_la_carpeta(self) -> None:
        self.assertEqual(estudio.ruta_de_guion(str(self.ruta)), self.ruta.resolve())
        self.assertEqual(estudio.ruta_de_guion("guiones/cubos.yaml"), self.ruta.resolve())

    def test_no_abre_nada_fuera_de_guiones(self) -> None:
        afuera = self.raiz / "marca.yaml"
        afuera.write_text("nombre: x\n", encoding="utf-8")
        for valor in (str(afuera), "guiones/../marca.yaml", "/etc/passwd", str(self.raiz / "guiones")):
            with self.assertRaises(ErrorMotor, msg=valor):
                estudio.ruta_de_guion(valor)

    def test_un_guion_que_no_existe_se_explica(self) -> None:
        with self.assertRaises(ErrorMotor):
            estudio.ruta_de_guion("guiones/no_existe.yaml")


class CambiosTest(_ConRaiz):
    def test_escribir_un_gancho_guarda_el_anterior_como_alternativa(self) -> None:
        antes = cargar_guion(self.ruta).gancho.texto
        g = estudio.escribir_gancho(self.ruta, "¿Caben 8 cubos en uno solo?")
        self.assertEqual(g.gancho.texto, "¿Caben 8 cubos en uno solo?")
        self.assertIsNone(g.gancho.tex)
        self.assertEqual(g.gancho_variantes[0].texto, antes)
        # y se puede volver con un clic
        g = estudio.usar_gancho(self.ruta, 2)
        self.assertEqual(g.gancho.texto, antes)
        self.assertIn("¿Caben 8 cubos en uno solo?", [v.texto for v in g.gancho_variantes])

    def test_un_gancho_vacio_o_largo_no_toca_el_archivo(self) -> None:
        original = self.ruta.read_text(encoding="utf-8")
        for texto in ("", "x" * (estudio.LARGO_GANCHO + 1)):
            with self.assertRaises(ErrorMotor):
                estudio.escribir_gancho(self.ruta, texto)
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), original)

    def test_cierre_y_llamado(self) -> None:
        g = estudio.cambiar_cierre(self.ruta, "Mito derribado")
        self.assertEqual((g.cierre.texto, g.cierre.voz), ("Mito derribado", "Mito derribado"))
        g = estudio.cambiar_llamado(self.ruta, "¿Tú también lo creías? Cuéntame 👇")
        self.assertEqual(g.llamado, "¿Tú también lo creías? Cuéntame 👇")
        self.assertIn("llamado:", self.ruta.read_text(encoding="utf-8"))
        g = estudio.cambiar_llamado(self.ruta, "  ")
        self.assertIsNone(g.llamado)
        self.assertNotIn("llamado:", self.ruta.read_text(encoding="utf-8"))

    def test_quitar_el_dibujo_y_editar_un_paso(self) -> None:
        g = cargar_guion(self.ruta)
        con_dibujo = next(n for n, p in enumerate(g.pasos, 1) if p.visual is not None)
        g = estudio.quitar_dibujo(self.ruta, con_dibujo)
        self.assertIsNone(g.pasos[con_dibujo - 1].visual)
        g = estudio.cambiar_paso(self.ruta, 1, nota="Mira el lado", voz="Primero miramos el lado del cubo.")
        self.assertEqual(
            (g.pasos[0].nota, g.pasos[0].voz), ("Mira el lado", "Primero miramos el lado del cubo.")
        )
        with self.assertRaises(ErrorMotor):
            estudio.cambiar_paso(self.ruta, 99, nota="x")
        with self.assertRaises(ErrorMotor):
            estudio.cambiar_paso(self.ruta, 1, voz="   ")

    def test_lo_guardado_conserva_la_cabecera_del_guion(self) -> None:
        cabecera = self.ruta.read_text(encoding="utf-8").splitlines()[0]
        estudio.cambiar_cierre(self.ruta, "Ahora lo sabes")
        if cabecera.startswith("#"):
            self.assertEqual(self.ruta.read_text(encoding="utf-8").splitlines()[0], cabecera)


class AnimacionesTest(_ConRaiz):
    def test_ofrece_dibujos_que_la_ia_sabe_armar_y_no_el_que_ya_esta(self) -> None:
        g = cargar_guion(self.ruta)
        for n, paso in enumerate(g.pasos, 1):
            opciones = estudio.animaciones_sugeridas(g, n)
            self.assertTrue(opciones)
            self.assertLessEqual(len(opciones), 8)
            for o in opciones:
                self.assertIn(o.dibujo, DIBUJOS)
            if paso.visual is not None:
                self.assertNotIn(dibujo_de_tipo(paso.visual.tipo), [o.dibujo for o in opciones])

    def test_el_nombre_del_dibujo(self) -> None:
        self.assertEqual(estudio.nombre_dibujo(None), "Sin dibujo")
        self.assertEqual(dibujo_de_tipo("tolva_3d"), "tolva")
        with self.assertRaises(ErrorMotor):
            dibujo_de_tipo("dinosaurio")


class RedibujarTest(_ConRaiz):
    """«Cambiar animación»: la IA llena el dibujo; el resto del paso y del guion no se toca."""

    def _con_ia(self, *respuestas):
        from tpi_videos.redactor import PasoIA

        pasos = [PasoIA(nota="x", tex="x", voz="otra voz", **r) for r in respuestas]
        return (
            patch("tpi_videos.redactor.ia.cliente", return_value=object()),
            patch("tpi_videos.redactor.pedir_json", side_effect=pasos),
        )

    def test_solo_cambia_el_dibujo_del_paso(self) -> None:
        from tpi_videos.redactor import redibujar_paso

        antes = cargar_guion(self.ruta)
        cliente, pedir = self._con_ia({"dibujo": "grafico", "funcion": "x^3", "rango": [0, 3]})
        with cliente, pedir as llamado:
            redibujar_paso(self.ruta, 1, "grafico")
        despues = cargar_guion(self.ruta)
        self.assertEqual(despues.pasos[0].visual.tipo, "grafico_funcion")
        self.assertEqual(despues.pasos[0].voz, antes.pasos[0].voz)  # la voz de la IA no entra
        self.assertEqual(despues.pasos[1:], antes.pasos[1:])
        self.assertEqual(llamado.call_count, 1)

    def test_si_el_primer_intento_no_vale_pide_otra_vez(self) -> None:
        from tpi_videos.redactor import redibujar_paso

        cliente, pedir = self._con_ia(
            {"dibujo": "grafico", "funcion": ""},  # sin función: no pasa la validación
            {"dibujo": "grafico", "funcion": "2x + 1", "rango": [0, 4]},
        )
        with cliente, pedir as llamado:
            redibujar_paso(self.ruta, 2, "grafico")
        self.assertEqual(llamado.call_count, 2)
        self.assertEqual(cargar_guion(self.ruta).pasos[1].visual.tipo, "grafico_funcion")

    def test_dos_intentos_malos_no_tocan_el_archivo(self) -> None:
        from tpi_videos.redactor import redibujar_paso

        original = self.ruta.read_text(encoding="utf-8")
        cliente, pedir = self._con_ia(
            {"dibujo": "grafico", "funcion": ""}, {"dibujo": "grafico", "funcion": ""}
        )
        with cliente, pedir, self.assertRaises(ErrorMotor):
            redibujar_paso(self.ruta, 1, "grafico")
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), original)

    def test_un_paso_que_no_existe(self) -> None:
        from tpi_videos.redactor import redibujar_paso

        with self.assertRaises(ErrorMotor):
            redibujar_paso(self.ruta, 99, "grafico")


class GanchosAlternativosTest(unittest.TestCase):
    def test_las_alternativas_del_guionista_quedan_sin_repetir_el_gancho(self) -> None:
        datos = {"gancho": {"texto": "¿Caben 8 cubos?"}}
        propias = [
            GanchoAltIA(texto="¿Caben 8 cubos?").model_dump(),  # repite el principal: fuera
            GanchoAltIA(
                texto="El doble de lado no es el doble de cubos", voz="El doble de lado…"
            ).model_dump(),
        ]
        resultado = _aplicar_eleccion(datos, None, None, propias)
        self.assertEqual(
            [v["texto"] for v in resultado["gancho_variantes"]], ["El doble de lado no es el doble de cubos"]
        )

    def test_el_esquema_de_la_ia_pide_las_alternativas(self) -> None:
        self.assertIn("ganchos_alternativos", GuionIA.model_json_schema()["properties"])


class LlamadoEnLaPublicacionTest(_ConRaiz):
    def _textos(self, llamado: str | None):
        g = cargar_guion(self.ruta)
        return aplicar_llamado(textos_de_plantilla(g), llamado)

    def test_sin_llamado_queda_el_de_siempre(self) -> None:
        t = self._textos(None)
        self.assertIn(LLAMADOS_DE_SIEMPRE[0], t.texto_tiktok)
        self.assertIn(LLAMADOS_DE_SIEMPRE[1], t.texto_instagram)

    def test_el_llamado_reemplaza_al_de_siempre_en_los_tres_textos(self) -> None:
        llamado = "¿Te atreves? Escribe tu respuesta 👇"
        t = self._textos(llamado)
        for texto in (t.texto_tiktok, t.texto_instagram, t.descripcion_youtube):
            self.assertEqual(texto.count(llamado), 1)
            for viejo in LLAMADOS_DE_SIEMPRE:
                self.assertNotIn(viejo, texto)
        self.assertLessEqual(len(t.texto_tiktok), 150)
        self.assertTrue(t.descripcion_youtube.rstrip().endswith("Suscríbete para más ejercicios resueltos."))

    def test_tiktok_largo_acorta_el_resto_y_no_el_llamado(self) -> None:
        g = cargar_guion(self.ruta)
        textos = textos_de_plantilla(g).model_copy(update={"texto_tiktok": "palabra " * 30})
        llamado = "Guárdalo para tu próxima prueba 📌"
        t = aplicar_llamado(textos, llamado)
        self.assertLessEqual(len(t.texto_tiktok), 150)
        self.assertTrue(t.texto_tiktok.endswith(llamado))

    def test_si_la_ia_ya_lo_puso_no_se_repite(self) -> None:
        llamado = "¿Lo sabías? Cuéntame 👇"
        g = cargar_guion(self.ruta)
        textos = textos_de_plantilla(g).model_copy(update={"texto_instagram": f"Hola. {llamado}"})
        self.assertEqual(aplicar_llamado(textos, llamado).texto_instagram, f"Hola. {llamado}")

    def test_el_guion_acepta_y_limita_el_llamado(self) -> None:
        datos = cargar_guion(self.ruta).model_dump()
        datos["llamado"] = "x" * 151
        with self.assertRaises(ValidationError):
            Guion.model_validate(datos)


if __name__ == "__main__":
    unittest.main()
