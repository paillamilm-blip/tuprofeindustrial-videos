"""Revisión del guion antes de renderizar (``tpi revisar``).

Aplica reglas de guion para video corto (gancho en los primeros segundos, frases cortas, una
idea por frase, duración ideal 30–75 s, un solo llamado a la acción) y de pedagogía (ejemplo
resuelto paso a paso, unidades en el resultado, práctica de recuperación con un "reto" final).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .guion import Guion
from .visuales import analizar_circuito

# Calibrado con la voz es-CL de edge-tts a +5 % de velocidad (~15 caracteres por segundo,
# contando espacios y signos) más una pequeña pausa al final de cada bloque.
CARACTERES_POR_SEGUNDO = 15.0
PAUSA_POR_BLOQUE = 0.35
SEGUNDOS_ANIMACION_EXTRA = 2.0  # transiciones que ocurren fuera de la voz

_INICIOS_DEBILES = ("hola", "en este video", "hoy vamos", "hoy veremos", "bienvenid", "en el video de hoy")
_SIMBOLOS_PROBLEMATICOS = {
    "\\": "una barra invertida (LaTeX)",
    "^": "el símbolo ^",
    "_": "el símbolo _",
    "/": "una barra /",
    "*": "un asterisco",
    "=": "el signo =",
    "²": "el símbolo ²",
    "³": "el símbolo ³",
    "√": "el símbolo √",
    "—": "un guion largo",
    "–": "un guion medio",
}


def estimar_segundos(texto: str) -> float:
    """Duración aproximada de un texto hablado por la voz sintética."""
    texto = " ".join(texto.split())
    return max(1.0, len(texto) / CARACTERES_POR_SEGUNDO + PAUSA_POR_BLOQUE)


@dataclass
class Aviso:
    nivel: str  # "advertencia" o "sugerencia"
    donde: str
    mensaje: str


@dataclass
class Revision:
    segundos: float
    palabras: int
    bloques: int
    avisos: list[Aviso]


def _frases(texto: str) -> list[str]:
    return [f.strip() for f in re.split(r"(?<=[.!?¿¡])\s+", texto) if f.strip()]


def _avisos_de_visuales(guion: Guion) -> list[Aviso]:
    """Que el dibujo se pueda trazar: el gráfico dice qué representa cada eje y la figura se ve en el celular."""
    avisos: list[Aviso] = []
    for i, paso in enumerate(guion.pasos, 1):
        v = paso.visual
        if v is None:
            continue
        donde = f"paso {i} (visual)"
        if v.tipo == "circuito":
            # Un rótulo sin número («cuatro ohmios») no revienta hasta el render: lo avisamos aquí.
            try:
                analizar_circuito(v.fuente, v.resistencias)
            except ValueError as e:
                avisos.append(Aviso("advertencia", donde, str(e)))
            continue
        if v.tipo == "poligono_regular":
            if not 3 <= (v.lados or 0) <= 8:
                avisos.append(
                    Aviso(
                        "advertencia",
                        donde,
                        f"con {v.lados} lados la figura ya se ve como una pelota en la pantalla del "
                        "celular; de 3 a 8 lados se dibuja bien (triángulo, cuadrado, pentágono, hexágono).",
                    )
                )
            if len(v.anotar) > 2:
                avisos.append(
                    Aviso(
                        "sugerencia",
                        donde,
                        f"{len(v.anotar)} marcas encima de una figura que apenas mide 3,3 de alta se "
                        "aprietan; deja 2 y lo demás lo dice la voz.",
                    )
                )
            continue
        if v.tipo != "grafico_funcion":
            continue
        try:
            f = v.funcion_analizada()
        except ValueError as e:
            avisos.append(Aviso("advertencia", donde, str(e)))
            continue
        if not (v.eje_x and v.eje_y):
            avisos.append(
                Aviso(
                    "sugerencia",
                    donde,
                    f"los ejes salen como «{f.variable}» y «y»; escribe eje_x y eje_y "
                    "(ej. 'tiempo (s)' y 'altura (m)').",
                )
            )
    return avisos


def revisar(guion: Guion, cierre_por_defecto: str) -> Revision:
    avisos: list[Aviso] = []
    voces = guion.textos_de_voz(cierre_por_defecto)
    segundos = sum(estimar_segundos(t) for _, t in voces) + SEGUNDOS_ANIMACION_EXTRA
    segundos += sum(p.visual.segundos for p in guion.pasos if p.visual)  # el dibujo se mira un rato más
    palabras = sum(len(t.split()) for _, t in voces)

    # Duración total
    if segundos > 90:
        avisos.append(
            Aviso(
                "advertencia",
                "duración",
                f"~{segundos:.0f} s es largo para un video corto; "
                "lo ideal es 30–75 s. Considera dividirlo en 'Parte 1' y 'Parte 2'.",
            )
        )
    elif segundos > 75:
        avisos.append(
            Aviso(
                "sugerencia", "duración", f"~{segundos:.0f} s está bien, pero bajo 75 s suele retener mejor."
            )
        )
    elif segundos < 25:
        avisos.append(Aviso("sugerencia", "duración", f"~{segundos:.0f} s es muy corto; ¿falta algún paso?"))

    # Gancho (primeros 3 segundos)
    gancho = guion.gancho.voz_final
    if gancho.lower().startswith(_INICIOS_DEBILES):
        avisos.append(
            Aviso(
                "advertencia",
                "gancho",
                "no empieces saludando ni con 'en este video…': "
                "abre con una pregunta o un dato sorprendente.",
            )
        )
    if len(gancho.split()) > 14:
        avisos.append(
            Aviso(
                "sugerencia",
                "gancho",
                f"tiene {len(gancho.split())} palabras; un gancho de 8–12 palabras se dice en ~3 segundos.",
            )
        )

    # Frases y símbolos en lo que se dice
    for seccion, texto in voces:
        for frase in _frases(texto):
            n = len(frase.split())
            if n > 22:
                avisos.append(Aviso("advertencia", seccion, f"frase de {n} palabras: divídela (ideal ≤ 15)."))
            elif n > 16:
                avisos.append(
                    Aviso("sugerencia", seccion, f"frase de {n} palabras; más corta se entiende mejor.")
                )
        for simbolo, nombre in _SIMBOLOS_PROBLEMATICOS.items():
            if simbolo in texto:
                avisos.append(
                    Aviso(
                        "advertencia",
                        seccion,
                        f"la voz contiene {nombre}; escríbelo en palabras "
                        "(ej.: 'metros por segundo', 'al cuadrado', 'igual a').",
                    )
                )

    # Pedagogía
    if len(guion.pasos) > 7:
        avisos.append(
            Aviso(
                "advertencia",
                "pasos",
                f"{len(guion.pasos)} pasos es mucha carga para un video "
                "corto; agrupa pasos o divide el ejercicio.",
            )
        )
    if len(guion.enunciado.texto) > 260:
        avisos.append(
            Aviso(
                "sugerencia",
                "enunciado",
                "el enunciado es largo para leerlo en un celular; "
                "deja solo lo esencial (los datos se muestran aparte).",
            )
        )
    if (
        guion.materia in ("fisica", "ingenieria")
        and "\\text" not in guion.resultado.tex
        and "\\mathrm" not in guion.resultado.tex
    ):
        avisos.append(Aviso("sugerencia", "resultado", "¿faltan las unidades? Ej.: '2{,}02\\ \\text{s}'."))
    if guion.reto is None:
        avisos.append(
            Aviso(
                "sugerencia",
                "reto",
                "agrega un 'reto' final: practicar recordando fija lo aprendido y genera comentarios.",
            )
        )
    for i, paso in enumerate(guion.pasos, 1):
        for parte in paso.destacar:
            if paso.tex and parte not in paso.tex:
                avisos.append(
                    Aviso("advertencia", f"paso {i}", f"destacar «{parte}» no aparece en la fórmula.")
                )

    # Estilo, emojis y error típico
    from .emojis import PATRON_EMOJI, es_valido
    from .guion import emojis_del_guion
    from .temas import existe_tema

    if guion.tema and not existe_tema(guion.tema):
        avisos.append(Aviso("advertencia", "tema", f"el tema «{guion.tema}» no existe: mira las opciones con "
                            "./tpi temas."))  # fmt: skip

    for donde, valor in emojis_del_guion(guion):
        if not es_valido(valor):
            avisos.append(Aviso("advertencia", donde, f"el emoji «{valor}» no existe: usa uno de ./tpi emojis "
                                "o guarda tu imagen en mis_ajustes/stickers/."))  # fmt: skip
    en_voz = [seccion for seccion, texto in voces if PATRON_EMOJI.search(texto)]
    for seccion in dict.fromkeys(en_voz):
        avisos.append(Aviso("advertencia", seccion, "la voz contiene un emoji o símbolo que se leería en "
                            "voz alta: ponlo en el campo «emoji»."))  # fmt: skip
    for seccion, texto in _textos_visibles(guion):
        if seccion not in en_voz and PATRON_EMOJI.search(texto):
            avisos.append(Aviso("advertencia", seccion, "hay un emoji dentro del texto y ahí no se dibuja "
                                "bien: ponlo en el campo «emoji»."))  # fmt: skip
    errores = [i for i, p in enumerate(guion.pasos, 1) if p.error]
    if errores and errores[-1] == len(guion.pasos):
        avisos.append(Aviso("advertencia", f"paso {errores[-1]}", "el último paso es un error típico: agrega "
                            "después la forma correcta."))  # fmt: skip
    if len(errores) > 1 and guion.molde != "tres_errores":
        avisos.append(Aviso("sugerencia", "pasos", f"hay {len(errores)} errores típicos; con uno basta para "
                            "llamar la atención."))  # fmt: skip

    from .guion import problemas_de_molde

    for problema in problemas_de_molde(guion):
        avisos.append(Aviso("advertencia", "molde", problema))

    return Revision(
        segundos=segundos, palabras=palabras, bloques=len(voces), avisos=avisos + _avisos_de_visuales(guion)
    )


def _textos_visibles(guion: Guion) -> list[tuple[str, str]]:
    """(sección, texto) de lo que se escribe en pantalla con letras."""
    textos = [("título", guion.titulo), ("gancho", guion.gancho.texto), ("enunciado", guion.enunciado.texto)]
    textos += [(f"paso {i}", p.nota) for i, p in enumerate(guion.pasos, 1) if p.nota]
    for campo, seccion in (("verificacion", "verificación"), ("reto", "reto"), ("cierre", "cierre")):
        bloque = getattr(guion, campo)
        if bloque is not None:
            textos.append((seccion, bloque.texto))
    return textos
