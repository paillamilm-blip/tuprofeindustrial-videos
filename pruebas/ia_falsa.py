"""Un Gemini de mentira para probar ``tpi redactar`` de punta a punta sin clave ni internet.

Contesta con los ejemplos del motor vivo según el tema del ENUNCIADO, y como revisor siempre aprueba.
Lo usan las pruebas (cliente en memoria) y el servidor HTTP de ``scripts/gemini_falso.py``.
No reemplaza una redacción real: comprueba que lo que escribe la IA llegue intacto al YAML.
"""

from __future__ import annotations

import json
from typing import Any

from tpi_videos.redactor import EJEMPLOS_DINAMICOS, DatoIA, GuionIA, MetadatosIA, PasoIA

DERIVADA = GuionIA(
    es_ejercicio=True,
    titulo="La derivada de una cuadrática",
    materia="matematica",
    nivel="4° medio",
    gancho_texto="¿Dónde deja de bajar f(x) = x² − 4x + 3?",
    gancho_voz="¿En qué punto exacto esta parábola deja de bajar y empieza a subir?",
    gancho_emoji="🎯",
    enunciado_texto="Deriva f(x) = x² − 4x + 3 y encuentra dónde su pendiente vale cero.",
    enunciado_voz="Derivemos f de x igual a x al cuadrado menos cuatro x más tres. ¿Dónde se aplana?",
    enunciado_destacar=["f(x) = x² − 4x + 3"],
    datos=[],
    pasos=[
        PasoIA(
            nota="La función",
            tex="f(x) = x^2 - 4x + 3",
            voz='Mira la tangente recorrer la curva. <break time="1.5s"/> Baja, se aplana y después sube.',
            dibujo="grafico",
            funcion="x^2 - 4x + 3",
            rango=[-1, 5],
            movimiento="tangente",
            desde=-1,
            hasta=5,
            anotar=["pendiente"],
        ),
        PasoIA(
            nota="Derivamos",
            tex="f'(x) = 2x - 4",
            voz="La derivada de x al cuadrado es dos x, y la de menos cuatro x es menos cuatro.",
            halo=["2x"],
            resaltar_cambio=True,
        ),
        PasoIA(
            nota="Pendiente cero",
            tex="2x - 4 = 0",
            voz="Donde la tangente se aplana, la pendiente vale cero.",
            halo=["2x"],
        ),
        PasoIA(
            nota="Despejamos",
            tex="2x = 4",
            voz="El menos cuatro pasa al otro lado sumando.",
            halo=["2x"],
            resaltar_cambio=True,
        ),
    ],
    resultado_tex="x = 2",
    resultado_voz="La parábola deja de bajar en x igual a dos: ahí está su vértice.",
    resultado_emoji="✅",
    resultado_destello=True,
    verificacion_texto="f'(1) = −2 baja y f'(3) = 2 sube: el cambio está justo en x = 2.",
    verificacion_voz="Antes de dos la pendiente es negativa y después es positiva. Cuadra.",
    reto_texto="Deriva g(x) = x² − 6x y encuentra dónde se aplana.",
    reto_voz="Ahora tú. ¿Dónde se aplana x al cuadrado menos seis x?",
    reto_emoji="✍️",
    supuestos=[],
    metadatos=MetadatosIA(
        titulo="¿Dónde deja de bajar esta parábola? 🎯",
        descripcion="Derivada de una cuadrática paso a paso: la pendiente se hace cero en el vértice. ¿Te dio x = 2?",
        hashtags=[
            "#tuprofeindustrial",
            "#matematica",
            "#derivadas",
            "#calculo",
            "#ejerciciosresueltos",
            "#estudiantes",
            "#paes",
            "#aprendeentiktok",
        ],
    ),
)


TUBERIA = GuionIA(
    es_ejercicio=True,
    titulo="¿Laminar o turbulento en la tubería?",
    materia="ingenieria",
    nivel="Técnico profesional",
    gancho_texto="¿El agua en este tubo va ordenada o revuelta?",
    gancho_voz="¿El agua dentro de este tubo avanza ordenada o completamente revuelta?",
    gancho_emoji="💧",
    enunciado_texto=(
        "Por una tubería de radio exterior 10 cm y pared de 1 cm circula agua a 2 m/s "
        "(ρ = 1000 kg/m³, μ = 0,001 Pa·s). ¿El flujo es laminar o turbulento?"
    ),
    enunciado_voz="Circula agua a dos metros por segundo por una tubería. ¿Va ordenada o turbulenta?",
    enunciado_destacar=["2 m/s"],
    datos=[
        DatoIA(tex=r"v = 2\ \text{m/s}", voz="El agua va a dos metros por segundo."),
        DatoIA(
            tex=r"\mu = 0,001\ \text{Pa} \cdot \text{s}",
            voz="Su viscosidad es de un milésimo de pascal segundo.",
        ),
    ],
    pasos=[
        PasoIA(
            nota="El diámetro de adentro",
            tex=r"D = 2 r_i = 2 \cdot 9 = 18\ \text{cm}",
            voz='Abrimos la tubería para ver por dónde pasa el agua. <break time="1.5s"/> Cuenta el diámetro de adentro.',
            dibujo="tuberia",
            radio="10 cm",
            espesor="1 cm",
            longitud="80 cm",
            vista="axonometrica",
            despiece=True,
            anotar=["seccion"],
        ),
        PasoIA(
            nota="Número de Reynolds",
            tex=r"Re = \frac{\rho v D}{\mu}",
            voz="El número de Reynolds compara la inercia del agua con su viscosidad.",
            halo=["Re"],
        ),
        PasoIA(
            nota="Reemplazamos",
            tex=r"Re = \frac{1000 \cdot 2 \cdot 0,18}{0,001}",
            voz="Reemplazamos la densidad, la velocidad, el diámetro y la viscosidad.",
            halo=["Re"],
            resaltar_cambio=True,
        ),
        PasoIA(
            nota="Comparamos",
            tex=r"Re = 360000 > 4000",
            voz='Da trescientos sesenta mil, mucho más que cuatro mil. <break time="1s"/>',
            halo=["Re"],
            resaltar_cambio=True,
        ),
    ],
    resultado_tex=r"Re \approx 3,6 \cdot 10^5 \Rightarrow \text{turbulento}",
    resultado_voz="El flujo es turbulento: el agua avanza revuelta, con remolinos.",
    resultado_emoji="✅",
    resultado_destello=True,
    verificacion_texto="Sobre 4000 el flujo en tuberías es turbulento; bajo 2300, laminar.",
    verificacion_voz="Sobre cuatro mil siempre es turbulento. Con trescientos sesenta mil no hay duda.",
    reto_texto="¿Y si fuera aceite con μ = 0,3 Pa·s y ρ = 900 kg/m³?",
    reto_voz="Ahora tú. ¿Qué pasa si por la tubería circula aceite, mucho más viscoso?",
    reto_emoji="✍️",
    supuestos=["Se usa el diámetro interior: el fluido no pasa por la pared."],
    metadatos=MetadatosIA(
        titulo="¿El agua en este tubo va ordenada o revuelta? 💧",
        descripcion="Número de Reynolds en una tubería con bridas: laminar o turbulento en cuatro pasos. ¿Qué te dio?",
        hashtags=[
            "#tuprofeindustrial",
            "#ingenieria",
            "#mecanicadefluidos",
            "#reynolds",
            "#tuberias",
            "#tecnicoprofesional",
            "#ejerciciosresueltos",
            "#estudiantes",
        ],
    ),
)


def _ejemplo(clave: str) -> GuionIA:
    return next(g for titulo, g in EJEMPLOS_DINAMICOS.items() if titulo.startswith(clave))


def respuesta(sistema: str, texto: str) -> str:
    """El JSON que devolvería Gemini para esta petición."""
    if sistema.startswith("Eres un profesor revisor"):
        return json.dumps({"aprobado": True, "problemas": []})
    bajo = texto.lower()
    if "tuber" in bajo or "turbul" in bajo:
        guion = TUBERIA
    elif "tolva" in bajo:
        guion = _ejemplo("Ingeniería")
    elif "parab" in bajo or "proyectil" in bajo:
        guion = _ejemplo("Física")
    elif "deriv" in bajo:
        guion = DERIVADA
    else:
        guion = _ejemplo("Matemática")
    return guion.model_dump_json()


class _Respuesta:
    def __init__(self, texto: str):
        self.text = texto
        self.candidates = []
        self.prompt_feedback = None


class ClienteFalso:
    """Lo mínimo de ``genai.Client`` que usa ``redactor.pedir_json``."""

    def __init__(self) -> None:
        self.pedidos: list[str] = []
        self.models = self

    def generate_content(self, model: str, contents: list[Any], config: Any) -> _Respuesta:
        texto = "\n".join(c for c in contents if isinstance(c, str))
        self.pedidos.append(texto)
        return _Respuesta(respuesta(config.system_instruction or "", texto))
