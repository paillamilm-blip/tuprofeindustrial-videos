"""La pantalla única no puede prometer lo que el motor no cumple.

Estas pruebas no abren navegador: revisan la lógica que arma la tarjeta «Así está armado» y el
comando que sale de ahí. Cada pieza mostrada tiene que existir como bandera de `tpi producir`, y
cada razón tiene que decir de dónde vino el valor.
"""

import tempfile
import unittest
from pathlib import Path

from tpi_videos.formatos import formato
from tpi_videos.guion import MATERIAS
from tpi_videos.ideas import DIFICULTADES
from tpi_videos.moldes import MOLDES
from tpi_videos.panel.sugerencia import (
    BANDERAS,
    Preferencias,
    anotaciones,
    armar,
    dividir_variantes,
    nombre_compilacion,
    opciones,
)
from tpi_videos.rodaje import RECETA_LIBRE, rodaje_para

PREF = Preferencias(tema="hoja_de_desarrollo", voz="es-CL-LorenzoNeural", voces={"es-CL-LorenzoNeural": "Lorenzo (Chile)"})
SIN_IDEA = ""  # fmt: skip


def claves(s) -> set[str]:
    return {p.clave for p in s.piezas}


class SugerenciaTest(unittest.TestCase):
    def test_sin_idea_no_deja_crearse_pero_no_esconde_nada(self):
        """La tarjeta se muestra entera desde el principio; sólo falta la frase."""
        s = armar(SIN_IDEA, {}, PREF)
        self.assertEqual(s.bloqueada(), "Escribe el tema o pega el enunciado.")
        self.assertEqual(
            claves(s),
            {
                "familia", "molde", "materia", "nivel", "dificultad",
                "tema", "voz", "segundos", "lectura", "gancho", "rodaje",
            },
        )  # fmt: skip

    def test_la_frase_delata_la_familia_y_lo_dice(self):
        """«dato» es de la familia Datos: la razón tiene que nombrar la palabra que la delató."""
        s = armar("un dato curioso con porcentajes", {}, PREF)
        self.assertEqual(s.familia, "datos")
        self.assertIn("«dato»", s.pieza("familia").razon)
        self.assertEqual(s.pieza("familia").valor, formato("datos").nombre)

    def test_una_frase_neutral_no_inventa_una_familia(self):
        s = armar("x + 3 = 7", {}, PREF)
        self.assertIsNone(s.familia)
        self.assertIn("No reconocí", s.pieza("familia").razon)
        self.assertIsNone(s.pieza("molde").codigo)  # lo decide la IA, y eso se dice tal cual

    def test_cada_chip_de_la_pantalla_arranca_con_su_familia(self):
        """Los temas sugeridos están para no tener que escribir: ninguno puede caer en «No reconocí»."""
        from tpi_videos.panel.paginas.crear import TEMAS_SUGERIDOS

        self.assertTrue(TEMAS_SUGERIDOS)
        for tema in TEMAS_SUGERIDOS:
            s = armar(tema, {}, PREF)
            self.assertIsNotNone(s.familia, tema)
            self.assertNotIn("No reconocí", s.pieza("familia").razon, tema)

    def test_lo_que_cambia_ella_gana_y_queda_marcado(self):
        s = armar("un dato curioso con porcentajes", {"materia": "fisica"}, PREF)
        molde_familia = s.pieza("molde")
        self.assertFalse(molde_familia.tocada)  # ése lo trajo la familia
        materia = s.pieza("materia")
        self.assertTrue(materia.tocada)
        self.assertEqual(materia.codigo, "fisica")
        self.assertEqual(materia.razon, "Cambiado por ti.")

    def test_la_propuesta_de_la_ia_deja_de_ser_un_secreto(self):
        """Si la idea trajo molde, gancho y duración, la tarjeta lo dice: no «lo decidió la IA»."""
        propuesta = {"molde": "mito_realidad", "gancho": "¿Adivinaste?", "segundos": 42, "titulo": "El dato"}
        s = armar("un dato curioso con porcentajes", {}, PREF, propuesta)
        self.assertEqual(s.pieza("molde").razon, "Lo trajo la idea que elegiste.")
        self.assertEqual(s.pieza("gancho").valor, "«¿Adivinaste?»")
        self.assertEqual(s.pieza("segundos").valor, "≈42 s")

    def test_la_promesa_de_duracion_dice_lo_que_va_aparte(self):
        """El ≈42 s de la tarjeta es la voz: quien elige tiene que saber que la lectura se suma."""
        s = armar("porcentajes", {}, PREF, {"segundos": 42, "titulo": "El dato"})
        self.assertIn("hasta 12 s de lectura", s.pieza("segundos").razon)
        s_ia = armar("porcentajes", {}, PREF)
        self.assertIn("lectura", s_ia.pieza("segundos").razon)

    def test_el_gancho_escrito_por_vas_reemplaza_al_de_la_idea(self):
        propuesta = {"gancho": "¿Adivinaste?", "gancho_elegido": {"texto": "¿Adivinaste?"}}
        s = armar("un dato curioso", {"gancho": "Lo mío"}, PREF, propuesta)
        self.assertIn("--gancho", list(s.args))
        self.assertNotIn("--gancho-json", list(s.args))
        self.assertTrue(s.pieza("gancho").tocada)

    def test_el_molde_de_la_propuesta_le_gana_a_la_familia(self):
        """La idea ya eligió molde: la familia no lo atropella."""
        s = armar("un dato curioso", {}, PREF, {"molde": "tres_errores"})
        self.assertEqual(s.pieza("molde").codigo, "tres_errores")
        self.assertEqual(s.rodaje, rodaje_para("tres_errores"))


class ArgsTest(unittest.TestCase):
    def test_el_enunciado_viaja_detras_de_doble_guion(self):
        """Un tema que empieza con «-» no puede leerse como una bandera."""
        s = armar("-3 + 5 = ", {}, PREF)
        args = list(s.args)
        self.assertEqual(args[-2:], ["--", "-3 + 5 ="])

    def test_sin_kit_su_bandera(self):
        self.assertIn("--sin-kit", list(armar("porcentajes", {}, PREF, kit=False).args))
        self.assertNotIn("--sin-kit", list(armar("porcentajes", {}, PREF).args))

    def test_no_hay_banderas_inventadas(self):
        """Cada --bandera del comando existe en `tpi producir` (si no, el motor la rechaza)."""
        import subprocess
        import sys

        salida = subprocess.run(
            [sys.executable, "-m", "tpi_videos", "producir", "--help"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        for s in (
            armar("porcentajes", {"molde": "reto", "materia": "fisica"}, PREF),
            armar("porcentajes", {}, PREF, {"molde": "mito_realidad", "segundos": 42, "gancho": "Mirá"}),
        ):
            for bandera in [a for a in s.args if a.startswith("--") and a != "--"]:
                self.assertIn(bandera, salida, f"{bandera} no es una bandera de `tpi producir`")

    def test_el_orden_del_comando(self):
        args = list(armar("porcentajes", {}, PREF).args)
        self.assertEqual(args[0], "producir")
        self.assertEqual(args.index("--") > args.index("--molde"), True)
        self.assertNotIn("--estilo", args)  # el estilo no viaja desde la tarjeta: se elige en QC


class PiezasTest(unittest.TestCase):
    def test_el_rodaje_no_promete_una_bandera(self):
        """El rodaje no es del comando: se cambia en Ajustes, y la tarjeta lo dice con su destino."""
        s = armar("porcentajes", {}, PREF)
        rodaje = s.pieza("rodaje")
        self.assertIsNone(rodaje.codigo)
        self.assertEqual(rodaje.destino, "/ajustes")
        self.assertNotIn("--rodaje", list(s.args))

    def test_las_opciones_salen_de_las_listas_del_motor(self):
        """Nada de listas copiadas a mano: si aparece un molde, aparece en «cambiar»."""
        self.assertEqual(set(opciones("molde")), set(MOLDES))
        self.assertIn("datos", opciones("familia"))
        self.assertIn("pizarra_nocturna", opciones("tema"))

    def test_solo_se_muestran_las_banderas_reales(self):
        self.assertEqual(
            set(BANDERAS),
            {
                "molde", "materia", "nivel", "dificultad",
                "tema", "voz", "segundos", "lectura", "gancho",
            },
        )  # fmt: skip

    def test_el_piso_de_lectura_viaja_aunque_no_se_toque(self):
        """Lo que muestra la tarjeta y lo que recibe el motor tienen que ser el mismo comando."""
        from tpi_videos.revision import PISO_LECTURA

        s = armar("porcentajes", {}, PREF)
        args = list(s.args)
        self.assertEqual(args[args.index("--piso-lectura") + 1], f"{PISO_LECTURA:g}")

    def test_la_lectura_muestra_su_valor_aunque_nadie_la_toque(self) -> None:
        """El piso de lectura no es un secreto del motor: se ve, y trae su bandera real."""
        s = armar("porcentajes", {}, PREF)
        lectura = s.pieza("lectura")
        self.assertIsNotNone(lectura)
        self.assertFalse(lectura.tocada)
        self.assertIn("--piso-lectura", list(s.args))

    def test_el_piso_bajado_a_cero_viaja_en_el_comando(self) -> None:
        """«Como hoy» es una opción de verdad: el 0 tiene que llegar al motor, no perderse."""
        s = armar("porcentajes", {"lectura": "0"}, PREF)
        args = list(s.args)
        self.assertEqual(args[args.index("--piso-lectura") + 1], "0")
        self.assertTrue(s.pieza("lectura").tocada)

    def test_las_opciones_de_lectura_son_seconds_elegibles(self) -> None:
        self.assertEqual(set(opciones("lectura")), {"0", "2", "2.5", "3"})

    def test_anotaciones_de_la_receta_libre(self):
        """La portada de la pantalla escribe cuatro cosas, todas salidas de la receta."""
        textos = anotaciones(rodaje_para(RECETA_LIBRE))
        self.assertEqual(len(textos), 4)
        self.assertTrue(all(t for t in textos))


class EstiloPorMoldeTest(unittest.TestCase):
    """El estilo visual también se recomienda: cada molde se ve mejor en un tema distinto."""

    def test_un_reto_se_recomienda_en_neon(self) -> None:
        s = armar("apotema de un hexágono", {}, PREF, {"molde": "reto", "titulo": "El reto"})
        estilo = s.pieza("tema")
        self.assertEqual(estilo.codigo, "neon_reja")
        self.assertFalse(estilo.tocada)
        self.assertIn("reto", estilo.razon.lower())

    def test_los_cinco_moldes_tienen_estilo_y_ninguno_se_repite(self) -> None:
        """Las 3 ideas de un lote traen moldes distintos: los estilos salen distintos solos."""
        codigos = {
            armar("porcentajes", {}, PREF, {"molde": clave, "titulo": "La idea"}).pieza("tema").codigo
            for clave in MOLDES
        }
        self.assertEqual(len(codigos), len(MOLDES))
        from tpi_videos.temas import listar_temas

        validos = {ident for ident, _tema, _propio in listar_temas()}
        self.assertTrue(codigos <= validos, "no puedo recomendar un estilo que el motor no tiene")

    def test_el_estilo_solo_se_muestra_y_se_cambia_en_qc(self) -> None:
        """La tarjeta dice qué estilo saldrá, pero no lo manda: se elige en un solo lugar (QC)."""
        s = armar("porcentajes", {"tema": "pizarra_nocturna"}, PREF, {"molde": "reto", "titulo": "La idea"})
        estilo = s.pieza("tema")
        self.assertEqual(estilo.codigo, "neon_reja")  # un cambio viejo guardado ya no manda
        self.assertFalse(estilo.tocada)
        self.assertEqual(estilo.destino, "/qc")
        self.assertNotIn("--estilo", s.args)

    def test_sin_molde_el_estilo_sale_de_la_materia(self) -> None:
        s = armar("una frase que no delata nada", {"materia": "fisica"}, PREF)
        self.assertEqual(s.pieza("tema").codigo, "neon_cian")
        self.assertIn("Física", s.pieza("tema").razon)

    def test_sin_molde_ni_materia_queda_el_de_siempre(self) -> None:
        s = armar("una frase que no delata nada", {}, PREF)
        self.assertEqual(s.pieza("tema").codigo, PREF.tema)
        self.assertIn("Tu estilo de siempre", s.pieza("tema").razon)


class PublicoTest(unittest.TestCase):
    """Materia, nivel y dificultad: la tarjeta existe, su valor viene de una lista real y nada bloquea."""

    def test_el_predeterminado_de_ajustes_manda_cuando_no_hay_idea(self) -> None:
        pref = Preferencias(
            tema="hoja_de_desarrollo", voz="es-CL-LorenzoNeural", voces={},
            materia="matematica", nivel="2° medio", dificultad="media",
        )  # fmt: skip
        s = armar("porcentajes", {}, pref)
        self.assertEqual(s.pieza("materia").codigo, "matematica")
        self.assertEqual(s.pieza("materia").valor, "Matemática")
        self.assertEqual(s.pieza("materia").razon, "Tu predeterminado (Ajustes).")
        self.assertEqual(s.pieza("nivel").valor, "2° medio")
        self.assertEqual(s.pieza("dificultad").valor, "Media")

    def test_la_idea_le_gana_al_predeterminado(self) -> None:
        pref = Preferencias(tema="hoja_de_desarrollo", voz="es-CL-LorenzoNeural", voces={}, materia="matematica")
        s = armar("porcentajes", {}, pref, {"materia": "fisica", "dificultad": "facil"})
        self.assertEqual(s.pieza("materia").codigo, "fisica")
        self.assertEqual(s.pieza("materia").razon, "Lo trajo la idea que elegiste.")
        self.assertEqual(s.pieza("dificultad").codigo, "facil")

    def test_su_cambio_gana_y_viaja_una_sola_bandera(self) -> None:
        """La idea también trajo materia: el cambio de ella manda y la bandera no se repite."""
        s = armar("porcentajes", {"materia": "ingenieria"}, PREF, {"materia": "fisica"})
        self.assertEqual(s.pieza("materia").codigo, "ingenieria")
        self.assertTrue(s.pieza("materia").tocada)
        args = list(s.args)
        self.assertEqual(args.count("--materia"), 1, "la bandera no puede viajar dos veces")
        self.assertEqual(args[args.index("--materia") + 1], "ingenieria")

    def test_sin_predeterminado_no_inventa_nada_y_no_viaja_la_bandera(self) -> None:
        s = armar("una frase que no delata nada", {}, PREF)
        for clave in ("materia", "nivel", "dificultad"):
            self.assertIsNone(s.pieza(clave).codigo, f"{clave} no puede mandarle un valor a la IA")
            self.assertIn("la IA", s.pieza(clave).valor)
            self.assertNotIn(f"--{clave}", list(s.args))

    def test_el_nivel_es_texto_libre_porque_el_motor_lo_acepta(self) -> None:
        pref = Preferencias(
            tema="hoja_de_desarrollo", voz="es-CL-LorenzoNeural", voces={}, nivel="técnico en electricidad"
        )
        s = armar("poleas", {}, pref)
        args = list(s.args)
        self.assertEqual(args[args.index("--nivel") + 1], "técnico en electricidad")

    def test_las_listas_salen_del_motor_no_de_una_copia(self) -> None:
        """El «cambiar» usa las materias y dificultades del motor: si el motor agrega una, aparece."""
        self.assertEqual(set(opciones("materia")), set(MATERIAS))
        self.assertEqual(opciones("dificultad"), DIFICULTADES)

    def test_ninguna_tarjeta_de_publico_bloquea_el_paso(self) -> None:
        """Sin idea y sin predeterminado las 3 tarjetas se muestran igual: nada le corta «Crear»."""
        s = armar("", {}, PREF)
        self.assertTrue({"materia", "nivel", "dificultad"} <= claves(s))


class CompilarTest(unittest.TestCase):
    """Lo que la pestaña pinta cuando se compilaron varias variantes de una."""

    def test_una_variante_se_nombra_en_singular(self) -> None:
        self.assertEqual(nombre_compilacion(1), "Compilar 1 variante")
        self.assertEqual(nombre_compilacion(3), "Compilar 3 variantes")

    def test_solo_es_lista_si_el_mp4_existe(self) -> None:
        with tempfile.TemporaryDirectory() as caja:
            video = Path(caja) / "uno.mp4"
            video.write_bytes(b"mp4")
            partidos = dividir_variantes(
                [
                    {"titulo": "con archivo", "ok": True, "video": str(video)},
                    {"titulo": "dice ok pero no está", "ok": True, "video": str(Path(caja) / "roto.mp4")},
                    {"titulo": "esperando a la IA", "ok": False, "pendiente": True},
                    {"titulo": "falló", "ok": False, "error": "no cerró la animación"},
                ]
            )

        self.assertEqual([i["titulo"] for i in partidos["listas"]], ["con archivo"])
        self.assertEqual([i["titulo"] for i in partidos["esperando"]], ["esperando a la IA"])
        self.assertEqual([i["titulo"] for i in partidos["fallas"]], ["dice ok pero no está", "falló"])


if __name__ == "__main__":
    unittest.main()
