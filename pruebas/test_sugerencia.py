"""La pantalla única no puede prometer lo que el motor no cumple.

Estas pruebas no abren navegador: revisan la lógica que arma la tarjeta «Así está armado» y el
comando que sale de ahí. Cada pieza mostrada tiene que existir como bandera de `tpi producir`, y
cada razón tiene que decir de dónde vino el valor.
"""

import unittest

from tpi_videos.formatos import formato
from tpi_videos.moldes import MOLDES
from tpi_videos.panel.sugerencia import BANDERAS, Preferencias, anotaciones, armar, opciones
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
            claves(s), {"familia", "molde", "tema", "voz", "segundos", "gancho", "rodaje"}
        )

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

    def test_lo_que_cambia_ella_gana_y_queda_marcado(self):
        s = armar("un dato curioso con porcentajes", {"tema": "pizarra_nocturna"}, PREF)
        molde_familia = s.pieza("molde")
        self.assertFalse(molde_familia.tocada)  # ése lo trajo la familia
        estilo = s.pieza("tema")
        self.assertTrue(estilo.tocada)
        self.assertEqual(estilo.codigo, "pizarra_nocturna")
        self.assertEqual(estilo.razon, "Cambiado por ti.")

    def test_la_propuesta_de_la_ia_deja_de_ser_un_secreto(self):
        """Si la idea trajo molde, gancho y duración, la tarjeta lo dice: no «lo decidió la IA»."""
        propuesta = {"molde": "mito_realidad", "gancho": "¿Adivinaste?", "segundos": 42, "titulo": "El dato"}
        s = armar("un dato curioso con porcentajes", {}, PREF, propuesta)
        self.assertEqual(s.pieza("molde").razon, "Lo trajo la idea que elegiste.")
        self.assertEqual(s.pieza("gancho").valor, "«¿Adivinaste?»")
        self.assertEqual(s.pieza("segundos").valor, "≈42 s")

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
            armar("porcentajes", {"molde": "reto", "tema": "pizarra_nocturna"}, PREF),
            armar("porcentajes", {}, PREF, {"molde": "mito_realidad", "segundos": 42, "gancho": "Mirá"}),
        ):
            for bandera in [a for a in s.args if a.startswith("--") and a != "--"]:
                self.assertIn(bandera, salida, f"{bandera} no es una bandera de `tpi producir`")

    def test_el_orden_del_comando(self):
        args = list(armar("porcentajes", {}, PREF).args)
        self.assertEqual(args[0], "producir")
        self.assertEqual(args.index("--") > args.index("--estilo"), True)


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
        self.assertEqual(set(BANDERAS), {"molde", "tema", "voz", "segundos", "gancho"})

    def test_anotaciones_de_la_receta_libre(self):
        """La portada de la pantalla escribe cuatro cosas, todas salidas de la receta."""
        textos = anotaciones(rodaje_para(RECETA_LIBRE))
        self.assertEqual(len(textos), 4)
        self.assertTrue(all(t for t in textos))


if __name__ == "__main__":
    unittest.main()
