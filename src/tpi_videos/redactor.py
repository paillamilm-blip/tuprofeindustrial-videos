"""Redacta guiones con IA: enunciado (texto, foto o PDF) → guion YAML listo para revisar.

Flujo (con la persona siempre al final del ciclo):
1. Gemini resuelve el ejercicio y escribe el guion en un formato JSON fijo.
2. El motor lo valida: formato del guion, fórmulas LaTeX (se compilan de verdad) y las
   reglas de ``tpi revisar``.
3. Gemini, como profesor revisor y con contexto nuevo, rehace los cálculos.
4. Si hay problemas, se le pide corregirlos (hasta 2 rondas).
5. Se guarda ``guiones/<nombre>.yaml`` con los supuestos y advertencias como comentarios.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from . import ia
from .emojis import lista_para_ia, normalizar_para_ia, quitar_emojis
from .entorno import PLANTILLAS_DIR, raiz_proyecto
from .errores import ErrorMotor
from .guion import Gancho, Guion, a_yaml, cargar_guion, explicar_errores, sin_tildes
from .moldes import MOLDES, normalizar_molde, opciones_de_moldes

RONDAS_DE_CORRECCION = 2
MARGEN_DE_DURACION = 8.0  # s: «≈45 s» puede llegar a 53 s y sigue siendo lo prometido
TECHO_DE_LECTURA = 12.0  # s de lectura que se perdonan: 6 fórmulas pidieron 12,8 s en un render real
MAX_BYTES_ARCHIVO = 18 * 1024 * 1024  # límite práctico para enviar un archivo dentro de la petición
TIPOS_ARCHIVO = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".pdf": "application/pdf",
}
TEXTO = {".txt", ".md"}


# ------------------------------------------------------------------------------------------
# Formato que debe devolver Gemini (plano y explícito: más fácil de cumplir para el modelo)
# ------------------------------------------------------------------------------------------


class DatoIA(BaseModel):
    tex: str = Field(description="Dato en LaTeX, ej. h = 20\\ \\text{m}")
    voz: str = Field(description="El dato dicho en palabras, sin cifras ni símbolos")


class MapaIA(BaseModel):
    termino: str = Field(description="Término copiado EXACTAMENTE del tex del paso, ej. v_0")
    concepto: str = Field(description="Qué es ese término, de 1 a 3 palabras, ej. velocidad inicial")


class PasoIA(BaseModel):
    nota: str = Field(description="Qué se hace en este paso, máximo 5 palabras")
    tex: str = Field(description="Ecuación completa del paso en LaTeX, sin $")
    voz: str = Field(description="Por qué se hace este paso, en palabras, sin cifras ni símbolos")
    destacar: list[str] = Field(default_factory=list, description="0 o 1 fragmento copiado del tex")
    emoji: str = Field(default="", description="0 o 1 emoji de la lista permitida (vacío = ninguno)")
    error: bool = Field(
        default=False, description="true solo en el paso 'error típico': su tex es la forma EQUIVOCADA"
    )
    # Un paso puede pedirse con dibujo. Son campos planos para que el modelo los cumpla fácil;
    # a_guion() arma el bloque "visual:" anidado que lee el motor.
    dibujo: Literal[
        "",
        "grafico",
        "fuerzas",
        "circuito",
        "poligono",
        "proyectil",
        "circulo",
        "solido",
        "solido3d",
        "venn",
        "recta",
        "probabilidad",
        "torta",
        "barras",
        "onda",
        "energia",
        "optica",
        "pendulo",
        "resorte",
        "escala",
        "polea",
        "tanque",
        "viga",
        "cercha",
        "bloques",
        "engranaje",
        "mohr",
        "oscilador",
        "pendulo_doble",
        "tolva",
        "tuberia",
        "eje",
        "calor",
        "flujo",
    ] = Field(
        default="",
        description=(
            'Dibujo de este paso: "", "grafico", "fuerzas", "circuito", "poligono", "proyectil", '
            '"circulo", "solido", "solido3d", "venn", "recta", "probabilidad", "torta", "barras", "onda", '
            '"energia", "optica", "pendulo", "resorte", "escala", "polea", "tanque", "viga", "cercha", '
            '"bloques", '
            '"engranaje", "mohr", "oscilador", "pendulo_doble", "tolva", "tuberia", "eje", "calor" o '
            '"flujo" (máximo 1 en el guion)'
        ),
    )
    # Álgebra viva: lo que se ilumina en este paso.
    halo: list[str] = Field(
        default_factory=list,
        description='0 a 2 términos copiados EXACTAMENTE del tex que se siguen con un resplandor, ej. ["x^2"]',
    )
    mapa: list[MapaIA] = Field(
        default_factory=list,
        description=(
            "De 0 a 3 términos del tex de este paso, cada uno con su concepto en 1 a 3 palabras: el motor "
            "los pinta de un color y les pone una etiqueta con una flecha. Vacío en un paso con error = true"
        ),
    )
    resaltar_cambio: bool = Field(
        default=False,
        description="true si este paso despeja, cancela o agrupa: se tacha lo que se va y se ilumina lo nuevo",
    )
    funcion: str = Field(
        default="", description='Con dibujo="grafico": la fórmula en texto plano, ej. "-4.9t^2 + 20"'
    )
    eje_x: str = Field(default="", description='Nombre del eje horizontal con unidades, ej. "tiempo (s)"')
    eje_y: str = Field(default="", description='Nombre del eje vertical con unidades, ej. "altura (m)"')
    variable: str = Field(
        default="", description='Con dibujo="grafico": la variable, ej. "t" (vacío = la única)'
    )
    rango: list[float] = Field(
        default_factory=list,
        description='Con dibujo="grafico": [mínimo, máximo] del eje horizontal, ej. [0, 5]',
    )
    movimiento: Literal["", "tangente", "area"] = Field(
        default="",
        description=(
            'Con dibujo="grafico": "tangente" (una recta recorre la curva y muestra la pendiente) o '
            '"area" (el área bajo la curva se llena por tramos); vacío = gráfico quieto'
        ),
    )
    desde: float | None = Field(
        default=None, description="Con movimiento: el x donde empieza el recorrido (dentro del rango)"
    )
    hasta: float | None = Field(
        default=None, description="Con movimiento: el x donde termina el recorrido (dentro del rango)"
    )
    vectores: list[str] = Field(
        default_factory=list, description='Con dibujo="fuerzas": flechas entre "P", "N", "f", "v", "a", "T"'
    )
    cuerpo: Literal["", "bloque", "bola"] = Field(
        default="", description='Con dibujo="fuerzas": "bloque" (una caja) o "bola"'
    )
    angulo: float = Field(default=0.0, description="Grados del plano inclinado (0 = mesa), solo con bloque")
    descomponer: bool = Field(
        default=False,
        description='Con dibujo="fuerzas" y angulo: true para partir el peso en P sen θ y P cos θ',
    )
    fuente: str = Field(default="", description='Con dibujo="circuito": el voltaje, ej. "12 V"')
    resistencias: list[str] = Field(
        default_factory=list, description='Con dibujo="circuito": de 2 a 4 valores, ej. ["4 Ω", "6 Ω"]'
    )
    arreglo: Literal["", "serie", "paralelo"] = Field(
        default="", description='Con dibujo="circuito": "serie" o "paralelo"'
    )
    lados: int = Field(default=0, description='Con dibujo="poligono": cuántos lados tiene, de 3 a 8')
    lado: str = Field(
        default="",
        description=(
            'Con dibujo="poligono": cuánto mide un lado, con su unidad, ej. "12 cm"; '
            'con dibujo="solido" y figura="cubo": la arista, ej. "4 cm"; '
            'con dibujo="escala": el lado del original, ej. "4 cm"'
        ),
    )
    velocidad: str = Field(
        default="", description='Con dibujo="proyectil": la velocidad de lanzamiento, ej. "20 m/s"'
    )
    figura: str = Field(
        default="",
        description='Con dibujo="solido" o "solido3d": cuál cuerpo, entre "cubo", "cilindro", "cono" y "esfera"',
    )
    radio: str = Field(
        default="", description='Con dibujo="solido" o "solido3d": el radio con su unidad, ej. "3 cm"'
    )
    altura: str = Field(
        default="", description='Con dibujo="solido" o "solido3d": la altura con su unidad, ej. "5 cm"'
    )
    vista: Literal["", "frente", "piso", "ala", "axonometrica"] = Field(
        default="", description='Con dibujo="solido3d": "axonometrica" (relieve), "frente", "ala" o "piso"'
    )
    corte: Literal["", "sin_corte", "mitad"] = Field(
        default="",
        description='Con dibujo="solido3d": "mitad" parte el cuerpo; solo vale con figura="cubo"',
    )
    despiece: bool = Field(
        default=False,
        description=(
            'Con "solido3d", "tolva", "tuberia" o "eje": true para que el cuerpo se separe en sus piezas '
            "al final del giro (no vale con la esfera)"
        ),
    )
    radio_salida: str = Field(
        default="", description='Con dibujo="tolva": el radio de la boca de abajo, ej. "0,3 m"'
    )
    altura_cono: str = Field(default="", description='Con dibujo="tolva": la altura del cono, ej. "1,2 m"')
    espesor: str = Field(default="", description='Con dibujo="tuberia": el espesor de la pared, ej. "1 cm"')
    bridas: bool = Field(
        default=True, description='Con dibujo="tuberia": false para dibujar el tubo sin bridas'
    )
    radios: list[float] = Field(
        default_factory=list,
        description='Con dibujo="eje": el radio de cada tramo, de 2 a 5, ej. [20, 30, 25]',
    )
    largos: list[float] = Field(
        default_factory=list,
        description='Con dibujo="eje": el largo de cada tramo en el mismo orden, ej. [60, 120, 80]',
    )
    unidad: str = Field(default="", description='Con dibujo="eje": la unidad de radios y largos, ej. "mm"')
    temp_izquierda: float | None = Field(
        default=None, description='Con dibujo="calor": °C del borde izquierdo'
    )
    temp_derecha: float | None = Field(default=None, description='Con dibujo="calor": °C del borde derecho')
    temp_arriba: float | None = Field(default=None, description='Con dibujo="calor": °C del borde de arriba')
    temp_abajo: float | None = Field(default=None, description='Con dibujo="calor": °C del borde de abajo')
    flujo: Literal["", "couette", "poiseuille"] = Field(
        default="",
        description='Con dibujo="flujo": "couette" (la placa de arriba arrastra) o "poiseuille" (empuja la presión)',
    )
    separacion: str = Field(
        default="", description='Con dibujo="flujo": la distancia entre placas, ej. "1 cm"'
    )
    viscosidad: str = Field(
        default="", description='Con dibujo="flujo": ej. "0,001 Pa·s"; hace falta para anotar "esfuerzo"'
    )
    solo_a: int | None = Field(
        default=None, description='Con dibujo="venn": cuántos viven sólo en el conjunto A'
    )
    solo_b: int | None = Field(
        default=None, description='Con dibujo="venn": cuántos viven sólo en el conjunto B'
    )
    ambos: int | None = Field(default=None, description='Con dibujo="venn": cuántos viven en la intersección')
    fuera: int | None = Field(
        default=None, description='Con dibujo="venn": cuántos no están en ninguno (0 si no se menciona)'
    )
    extremo_a: float | None = Field(
        default=None,
        description='Con dibujo="recta": el extremo izquierdo del intervalo o el origen del rayo',
    )
    extremo_b: float | None = Field(
        default=None, description='Con dibujo="recta": el extremo derecho; sin él la recta marca un rayo'
    )
    incluye_a: bool = Field(
        default=True, description='Con dibujo="recta": true = punto lleno en extremo_a, false = abierto'
    )
    incluye_b: bool = Field(
        default=True, description='Con dibujo="recta": true = punto lleno en extremo_b, false = abierto'
    )
    derecha: bool = Field(
        default=True, description='Con dibujo="recta" sin extremo_b: hacia dónde apunta el rayo'
    )
    favorables: int | None = Field(
        default=None, description='Con dibujo="probabilidad": los casos favorables'
    )
    totales: int | None = Field(default=None, description='Con dibujo="probabilidad": los casos totales')
    categorias: list[str] = Field(
        default_factory=list,
        description=(
            'Con dibujo="torta", "barras" o "energia": de 2 a 6 categorías con el valor al final, '
            'ej. ["Fútbol 12", "Básquetbol 8", "Vóley 5", "Otros 5"] o ["Cinética 60", "Térmica 40"]'
        ),
    )
    amplitud: str = Field(default="", description='Con dibujo="onda": la amplitud con su unidad, ej. "0,5 m"')
    longitud_onda: str = Field(
        default="", description='Con dibujo="onda": la distancia entre crestas con su unidad, ej. "2 m"'
    )
    periodo: float | None = Field(
        default=None,
        description='Con dibujo="onda": segundos entre crestas; hace falta para anotar "velocidad"',
    )
    n1: float | None = Field(
        default=None, description='Con dibujo="optica": índice del medio que llega, ej. 1.0'
    )
    n2: float | None = Field(
        default=None, description='Con dibujo="optica": índice del medio al que pasa, ej. 1.33'
    )
    angulo_incidence: float | None = Field(
        default=None, description='Con dibujo="optica": grados desde la normal, ej. 30'
    )
    longitud: str = Field(
        default="", description='Con dibujo="pendulo": largo del hilo con su unidad, ej. "1 m"'
    )
    constante: str = Field(
        default="", description='Con dibujo="resorte": constante con unidad, ej. "200 N/m"'
    )
    extension: str = Field(default="", description='Con dibujo="resorte": cuánto se estira, ej. "10 cm"')
    factor: int = Field(default=0, description='Con dibujo="escala": cuántas veces crece el lado, 2 o 3')
    dimension: int = Field(
        default=0,
        description='Con dibujo="escala": 2 si se compara el área (cuadrados), 3 el volumen (cubos)'
    )
    masa_a: str = Field(default="", description='Con dibujo="polea": primera masa con su unidad, ej. "3 kg"')
    masa_b: str = Field(default="", description='Con dibujo="polea": segunda masa, distinta de la primera')
    capacidad: str = Field(default="", description='Con dibujo="tanque": cuánto entra, ej. "120 L"')
    entrada: str = Field(
        default="", description='Con dibujo="tanque": llave que llena, con "por", ej. "8 L/min"'
    )
    salida: str = Field(default="", description='Con dibujo="tanque": fisura que pierde, ej. "2 L/min"')
    carga: str = Field(
        default="",
        description='Con dibujo="viga" o "cercha": la carga con su unidad, ej. "200 N" o "50 N/m"',
    )
    repartida: bool = Field(
        default=False, description='Con dibujo="viga": true si la carga va repartida en "N/m"'
    )
    base: str = Field(default="", description='Con dibujo="cercha": la luz entre apoyos, ej. "6 m"')
    adelante: str = Field(
        default="", description='Con dibujo="bloques": la ganancia del bloque directo, sin unidad, ej. "10"'
    )
    retro: str = Field(
        default="", description='Con dibujo="bloques": la ganancia de la realimentación, ej. "0.2"'
    )
    negativa: bool = Field(
        default=True, description='Con dibujo="bloques": false sólo para mostrar un lazo que se descontrola'
    )
    dientes_a: str = Field(
        default="", description='Con dibujo="engranaje": cuántos dientes tiene la conductora, ej. "20"'
    )
    dientes_b: str = Field(
        default="", description='Con dibujo="engranaje": cuántos tiene la conducida, otro número, ej. "60"'
    )
    rpm: str = Field(
        default="", description='Con dibujo="engranaje": las vueltas del eje de entrada, ej. "1200 rpm"'
    )
    sigma_x: str = Field(default="", description='Con dibujo="mohr": el esfuerzo normal en X, ej. "80 MPa"')
    sigma_y: str = Field(default="", description='Con dibujo="mohr": el esfuerzo normal en Y, ej. "20 MPa"')
    cortante: str = Field(
        default="", description='Con dibujo="mohr": el esfuerzo cortante, ej. "30 MPa" (o "0 MPa")'
    )
    masa: str = Field(default="", description='Con dibujo="oscilador": la masa con su unidad, ej. "2 kg"')
    amortiguamiento: str = Field(
        default="",
        description='Con dibujo="oscilador": la resistencia del amortiguador, ej. "8 N·s/m" (vacío = sin roce)',
    )
    duracion: float | None = Field(
        default=None,
        description=(
            'Con dibujo="oscilador" o "pendulo_doble": segundos a simular (hasta 20); '
            "vacío = 6 el oscilador y 10 el péndulo"
        ),
    )
    masa_1: str = Field(
        default="", description='Con dibujo="pendulo_doble": la masa del brazo de arriba, ej. "1 kg"'
    )
    masa_2: str = Field(
        default="", description='Con dibujo="pendulo_doble": la masa del brazo de abajo, ej. "1 kg"'
    )
    longitud_1: str = Field(
        default="", description='Con dibujo="pendulo_doble": el largo del brazo de arriba, ej. "1 m"'
    )
    longitud_2: str = Field(
        default="", description='Con dibujo="pendulo_doble": el largo del brazo de abajo, ej. "1 m"'
    )
    angulo_1: float | None = Field(
        default=None,
        description='Con dibujo="pendulo_doble": grados desde la vertical donde se suelta el brazo de arriba, ej. 170',
    )
    angulo_2: float | None = Field(
        default=None,
        description='Con dibujo="pendulo_doble": grados desde la vertical donde se suelta el brazo de abajo, ej. 170',
    )
    anotar: list[str] = Field(
        default_factory=list,
        description=(
            'Hasta 2 marcas: con "poligono", de "apotema", "radio", "angulo_central", "angulo_interior"; '
            'con "proyectil", de "alcance", "altura_maxima", "componentes"; '
            'con "circulo", de "seno", "coseno", "tangente"; '
            'con "solido" o "solido3d", de "volumen", "area"; '
            'con "venn", "total"; con "probabilidad", "probabilidad"; con "onda", "velocidad"; '
            'con "pendulo", "periodo"; con "resorte", "fuerza"; con "escala", "contador" o "razon"; '
            'con "polea", "aceleracion" o "tension"; '
            'con "tanque", "llenado" o "vaciado"; con "viga", "reacciones" o "momento"; '
            'con "cercha", "esfuerzo" o "angulo"; con "bloques", "lazo_cerrado"; '
            'con "engranaje", "velocidad" o "relacion"; con "mohr", "principales" o "cortante"; '
            'con "oscilador", "regimen", "periodo" o "decaimiento"; '
            'con "pendulo_doble", "energia" o "angulos"; '
            'con "grafico" y movimiento="tangente", "pendiente"; con movimiento="area", "area"; '
            'con "tolva", "volumen" o "chapa"; con "tuberia", "seccion" o "material"; '
            'con "eje", "volumen" o "largo"; con "calor", "centro" o "isotermas"; con "flujo", "esfuerzo"; '
            'con "recta", "torta", "barras", "energia" u "optica" va vacío'
        ),
    )


class MetadatosIA(BaseModel):
    titulo: str = Field(
        description="Título para YouTube Shorts, Reels y TikTok: máximo 70 caracteres, con el gancho; sin revelar el resultado"
    )
    descripcion: str = Field(
        description="2 o 3 frases: qué se aprende y una pregunta que invite a comentar. Sin hashtags"
    )
    hashtags: list[str] = Field(description="De 8 a 12, en español, sin tildes ni espacios, cada uno con #")


class GuionIA(BaseModel):
    es_ejercicio: bool = Field(description="false si no es un ejercicio resoluble")
    motivo: str = Field(default="", description="Solo si es_ejercicio es false: por qué")
    # Se piensan ANTES que el resto del guion (por eso van primero): todo lo demás les sirve.
    idea_central: str = Field(
        default="", description="La UNA idea que el estudiante se lleva, en una frase sin fórmulas"
    )
    confusion_tipica: str = Field(
        default="", description="Qué confunde o qué cree mal el estudiante de ese nivel sobre esto"
    )
    titulo: str
    materia: Literal["matematica", "fisica", "ingenieria"]
    nivel: str
    gancho_texto: str
    gancho_voz: str
    gancho_emoji: str = Field(default="", description="1 emoji de la lista permitida (o vacío)")
    gancho_tex: str = Field(default="", description="Opcional: fórmula corta bajo el gancho, sin $")
    enunciado_texto: str
    enunciado_voz: str
    enunciado_destacar: list[str]
    datos: list[DatoIA]
    pasos: list[PasoIA]
    resultado_tex: str
    resultado_voz: str
    resultado_emoji: str = Field(default="", description="0 o 1 emoji de la lista permitida")
    resultado_destello: bool = Field(
        default=False, description="true para cerrar la respuesta final con un destello de confirmación"
    )
    verificacion_texto: str
    verificacion_voz: str
    reto_texto: str
    reto_voz: str
    reto_emoji: str = Field(default="", description="0 o 1 emoji de la lista permitida")
    supuestos: list[str] = Field(
        description="Supuestos o aclaraciones para el profesor (no salen en el video)"
    )
    metadatos: MetadatosIA = Field(description="Título, descripción y hashtags para publicar el video")


class RevisionIA(BaseModel):
    aprobado: bool
    problemas: list[str]


EJEMPLO = GuionIA(
    es_ejercicio=True,
    idea_central="El tiempo de caída no depende de la masa: solo de la altura y de la gravedad.",
    confusion_tipica="Creer que lo más pesado cae más rápido, o despejar t olvidando la raíz.",
    titulo="Caída libre: ¿cuánto tarda en caer?",
    materia="fisica",
    nivel="2° medio",
    gancho_texto="¿Cuánto tarda una piedra en caer 20 metros?",
    gancho_voz="¿Cuánto tarda una piedra en caer veinte metros? Menos de lo que crees.",
    gancho_emoji="🤔",
    enunciado_texto="Se deja caer una piedra desde 20 metros de altura. ¿Cuánto tarda en llegar al suelo? "
    "Usa g = 9,8 m/s².",
    enunciado_voz="Soltamos una piedra desde veinte metros de altura. ¿Cuánto demora en llegar al suelo?",
    enunciado_destacar=["20 metros", "g = 9,8 m/s²"],
    datos=[
        DatoIA(tex=r"h = 20\ \text{m}", voz="La altura es de veinte metros."),
        DatoIA(
            tex=r"g = 9,8\ \text{m/s}^2", voz="La gravedad, nueve coma ocho metros por segundo al cuadrado."
        ),
        DatoIA(tex="t = ?", voz="Y buscamos el tiempo."),
    ],
    pasos=[
        PasoIA(
            nota="Caída libre",
            tex=r"h = \frac{1}{2} g t^2",
            voz="Como la piedra parte del reposo, usamos la ecuación de caída libre.",
            mapa=[MapaIA(termino="h", concepto="altura"), MapaIA(termino="g", concepto="gravedad")],
            dibujo="grafico",
            funcion="-4.9t^2 + 20",
            eje_x="tiempo (s)",
            eje_y="altura (m)",
        ),
        PasoIA(
            nota="Despejamos t",
            tex=r"t = \sqrt{\frac{2h}{g}}",
            voz="Despejamos el tiempo. Queda la raíz de dos h sobre g.",
        ),
        PasoIA(
            nota="Reemplazamos",
            tex=r"t = \sqrt{\frac{2 \cdot 20}{9,8}}",
            voz="Reemplazamos la altura y la gravedad.",
        ),
        PasoIA(
            nota="Calculamos",
            tex=r"t = \sqrt{4,08}",
            voz="Dos por veinte es cuarenta. Dividido en nueve coma ocho, da cuatro coma cero ocho.",
        ),
    ],
    resultado_tex=r"t \approx 2,02\ \text{s}",
    resultado_voz="Sacamos la raíz: la piedra tarda unos dos segundos en caer.",
    resultado_emoji="⏱️",
    verificacion_texto="Con el doble de altura no tarda el doble: el tiempo crece con la raíz de la altura.",
    verificacion_voz="Ojo: con el doble de altura no tarda el doble. El tiempo crece con la raíz de la altura.",
    reto_texto="¿Cuánto tarda en caer desde 45 metros? Usa g = 10 m/s².",
    reto_voz="Ahora tú. ¿Cuánto tarda desde cuarenta y cinco metros, con g igual a diez?",
    reto_emoji="✍️",
    supuestos=[],
    metadatos=MetadatosIA(
        titulo="¿Cuánto tarda una piedra en caer 20 metros? 🤔",
        descripcion="Caída libre paso a paso: despejamos el tiempo de h = ½gt². ¿Te dio lo mismo?",
        hashtags=[
            "#tuprofeindustrial",
            "#fisica",
            "#caidalibre",
            "#cinematica",
            "#ejerciciosresueltos",
            "#paes",
            "#estudiantes",
            "#aprendeentiktok",
        ],
    ),
)


# Los tres ejemplos del motor vivo, uno por materia. Son guiones completos y válidos (las pruebas los
# pasan por el motor y por ``tpi revisar``); al modelo se le muestran solo los campos que no van por
# defecto de cada paso y del resultado, que es donde están los dibujos que se mueven.
EJEMPLOS_DINAMICOS: dict[str, GuionIA] = {
    "Ingeniería · tolva con despiece": GuionIA(
        es_ejercicio=True,
        titulo="Balance de masa en la tolva",
        materia="ingenieria",
        nivel="Técnico profesional",
        gancho_texto="¿En cuántas horas se llena esta tolva?",
        gancho_voz="¿En cuántas horas se llena esta tolva si sale menos de lo que entra?",
        gancho_emoji="⏱️",
        enunciado_texto=(
            "Una tolva de inyección tiene un cilindro de R = 0,5 m y H = 0,8 m, y un cono de 0,6 m que baja "
            "a una boca de 0,1 m. Entran 150 kg/h de pellets (600 kg/m³) y salen 30 kg/h. ¿Cuánto tarda en llenarse?"
        ),
        enunciado_voz=(
            "Una tolva de inyección: un cilindro y un cono que termina en una boca chica. "
            "Entran ciento cincuenta kilos por hora y salen treinta. ¿Cuándo se llena?"
        ),
        enunciado_destacar=["150 kg/h", "30 kg/h"],
        datos=[
            DatoIA(
                tex=r"\rho = 600\ \text{kg/m}^3", voz="Los pellets pesan seiscientos kilos por metro cúbico."
            ),
            DatoIA(tex="t = ?", voz="Y buscamos el tiempo de llenado."),
        ],
        pasos=[
            PasoIA(
                nota="Dos cuerpos",
                tex=r"V = V_{cil} + V_{cono}",
                voz='Mira cómo la tolva se abre en dos piezas. <break time="1.5s"/> Su volumen es el del cilindro más el del cono.',
                dibujo="tolva",
                radio="0,5 m",
                altura="0,8 m",
                radio_salida="0,1 m",
                altura_cono="0,6 m",
                vista="axonometrica",
                despiece=True,
                anotar=["volumen"],
            ),
            PasoIA(
                nota="Sumamos volúmenes",
                tex=r"V = 0,628 + 0,195 = 0,823\ \text{m}^3",
                voz="El cilindro aporta casi todo y el cono suma el resto.",
                halo=["0,823"],
            ),
            PasoIA(
                nota="Masa que cabe",
                tex=r"m = \rho V = 600 \cdot 0,823 \approx 494\ \text{kg}",
                voz="La masa es la densidad por el volumen.",
            ),
            PasoIA(
                nota="Balance de masa",
                tex=r"\frac{dm}{dt} = 150 - 30 = 120\ \text{kg/h}",
                voz="Lo que se acumula es lo que entra menos lo que sale.",
                resaltar_cambio=True,
            ),
        ],
        resultado_tex=r"t = \frac{494}{120} \approx 4,1\ \text{h}",
        resultado_voz="Dividimos la masa por la acumulación: se llena en un poco más de cuatro horas.",
        resultado_emoji="✅",
        resultado_destello=True,
        verificacion_texto="Si no saliera nada, tardaría 494/150 ≈ 3,3 h: menos, como debe ser.",
        verificacion_voz="Si no saliera nada, tardaría unas tres horas. Tiene sentido que ahora tarde más.",
        reto_texto="¿Y si salen 60 kg/h?",
        reto_voz="Ahora tú. ¿Cuánto tarda si salen sesenta kilos por hora?",
        reto_emoji="✍️",
        supuestos=["Se usa la densidad aparente de los pellets, no la del plástico macizo."],
        metadatos=MetadatosIA(
            titulo="¿En cuántas horas se llena esta tolva? ⏱️",
            descripcion="Balance de masa en una tolva de inyección: volumen, masa y lo que se acumula. ¿Cuánto te dio?",
            hashtags=[
                "#tuprofeindustrial",
                "#ingenieria",
                "#balancedemasa",
                "#tolva",
                "#procesos",
                "#tecnicoprofesional",
                "#ejerciciosresueltos",
                "#estudiantes",
            ],
        ),
    ),
    "Física · tiro parabólico con la tangente en movimiento": GuionIA(
        es_ejercicio=True,
        titulo="Tiro parabólico: la altura máxima",
        materia="fisica",
        nivel="3° medio",
        gancho_texto="¿Qué tan alto sube una pelota lanzada a 49 m/s?",
        gancho_voz="¿Qué tan alto sube una pelota lanzada a cuarenta y nueve metros por segundo?",
        gancho_emoji="🚀",
        enunciado_texto="Se lanza una pelota a 49 m/s con 30° sobre el suelo. ¿Cuál es su altura máxima? Usa g = 9,8 m/s².",
        enunciado_voz="Lanzamos una pelota a cuarenta y nueve metros por segundo, con treinta grados. ¿Cuánto sube?",
        enunciado_destacar=["49 m/s", "30°"],
        datos=[
            DatoIA(
                tex=r"v_0 = 49\ \text{m/s}", voz="La rapidez inicial es cuarenta y nueve metros por segundo."
            ),
            DatoIA(tex=r"\theta = 30^{\circ}", voz="El ángulo es de treinta grados."),
        ],
        pasos=[
            PasoIA(
                nota="La parte vertical",
                tex=r"v_{0y} = v_0 \sin\theta = 49 \cdot 0,5 = 24,5\ \text{m/s}",
                voz="Solo la parte vertical de la velocidad hace subir la pelota.",
            ),
            PasoIA(
                nota="Arriba no sube",
                tex=r"v_y = 0 \Rightarrow t = \frac{v_{0y}}{g} = 2,5\ \text{s}",
                voz='Mira la tangente recorrer la curva. <break time="1.5s"/> Se aplana justo arriba: ahí la velocidad vertical vale cero.',
                dibujo="grafico",
                funcion="24.5t - 4.9t^2",
                variable="t",
                rango=[0, 5],
                eje_x="tiempo (s)",
                eje_y="altura (m)",
                movimiento="tangente",
                desde=0,
                hasta=5,
                anotar=["pendiente"],
            ),
            PasoIA(
                nota="Altura máxima",
                tex=r"h_{max} = \frac{v_{0y}^2}{2g}",
                voz="Con ese dato usamos la altura máxima, sin necesitar el tiempo.",
                halo=[r"v_{0y}^2"],
            ),
            PasoIA(
                nota="Reemplazamos",
                tex=r"h_{max} = \frac{24,5^2}{2 \cdot 9,8} = \frac{600,25}{19,6}",
                voz="Reemplazamos la velocidad vertical y la gravedad.",
                resaltar_cambio=True,
            ),
        ],
        resultado_tex=r"h_{max} \approx 30,6\ \text{m}",
        resultado_voz="La pelota sube unos treinta metros.",
        resultado_emoji="🎯",
        resultado_destello=True,
        verificacion_texto="Sube 2,5 s y baja 2,5 s: el vuelo dura 5 s, lo que muestra el gráfico.",
        verificacion_voz="Sube dos segundos y medio y baja lo mismo. Justo lo que dibuja el gráfico.",
        reto_texto="¿Y si la lanzas a 60°?",
        reto_voz="Ahora tú. ¿Cuánto sube si la lanzas a sesenta grados?",
        reto_emoji="✍️",
        supuestos=[],
        metadatos=MetadatosIA(
            titulo="¿Qué tan alto sube una pelota a 49 m/s? 🚀",
            descripcion="Tiro parabólico: la altura máxima es donde la velocidad vertical se hace cero. ¿Lo sabías?",
            hashtags=[
                "#tuprofeindustrial",
                "#fisica",
                "#tiroparabolico",
                "#cinematica",
                "#paes",
                "#ejerciciosresueltos",
                "#estudiantes",
                "#aprendeentiktok",
            ],
        ),
    ),
    "Matemática · despeje con halo": GuionIA(
        es_ejercicio=True,
        titulo="Despejar x al cuadrado sin perder una raíz",
        materia="matematica",
        nivel="1° medio",
        gancho_texto="x² − 9 = 16 tiene dos respuestas",
        gancho_voz="Esta ecuación tiene dos respuestas, y casi todos encuentran una sola.",
        gancho_emoji="🤯",
        enunciado_texto="Resuelve x² − 9 = 16.",
        enunciado_voz="Resolvamos x al cuadrado menos nueve igual a dieciséis.",
        enunciado_destacar=["x² − 9 = 16"],
        datos=[],
        pasos=[
            PasoIA(
                nota="La ecuación",
                tex="x^2 - 9 = 16",
                voz="Seguimos a x al cuadrado, que es lo que queremos dejar solo.",
                halo=["x^2"],
            ),
            PasoIA(
                nota="El nueve cruza",
                tex="x^2 = 16 + 9",
                voz='El menos nueve pasa al otro lado sumando. <break time="1s"/>',
                halo=["x^2"],
                resaltar_cambio=True,
            ),
            PasoIA(
                nota="Sumamos",
                tex="x^2 = 25",
                voz="Dieciséis más nueve es veinticinco.",
                halo=["x^2"],
                resaltar_cambio=True,
            ),
            PasoIA(
                nota="Raíz con signo",
                tex=r"x = \pm \sqrt{25}",
                voz="Al sacar la raíz van los dos signos: positivo y negativo.",
                emoji="⚠️",
                resaltar_cambio=True,
            ),
        ],
        resultado_tex=r"x = 5 \quad \text{o} \quad x = -5",
        resultado_voz="Las soluciones son cinco y menos cinco.",
        resultado_emoji="✅",
        resultado_destello=True,
        verificacion_texto="(−5)² − 9 = 25 − 9 = 16: el negativo también sirve.",
        verificacion_voz="Prueba con menos cinco: al cuadrado da veinticinco. También funciona.",
        reto_texto="Resuelve x² + 4 = 40.",
        reto_voz="Ahora tú. Resuelve x al cuadrado más cuatro igual a cuarenta.",
        reto_emoji="✍️",
        supuestos=[],
        metadatos=MetadatosIA(
            titulo="x² − 9 = 16 tiene DOS respuestas 🤯",
            descripcion="Despejamos x al cuadrado sin perder la raíz negativa. ¿Cuál se te había olvidado?",
            hashtags=[
                "#tuprofeindustrial",
                "#matematica",
                "#algebra",
                "#ecuaciones",
                "#paes",
                "#ejerciciosresueltos",
                "#estudiantes",
                "#aprendeentiktok",
            ],
        ),
    ),
}


def _ejemplos_dinamicos() -> str:
    """Los ejemplos como los ve el modelo: solo los campos con valor en pasos y resultado."""
    bloques = []
    for titulo, g in EJEMPLOS_DINAMICOS.items():
        compacto = {
            "enunciado_texto": g.enunciado_texto,
            "pasos": [p.model_dump(exclude_defaults=True) for p in g.pasos],
            "resultado_tex": g.resultado_tex,
            "resultado_destello": g.resultado_destello,
            "metadatos": g.metadatos.model_dump(),
        }
        bloques.append(f"### {titulo}\n{json.dumps(compacto, ensure_ascii=False, indent=1)}")
    return "\n\n".join(bloques)


# ------------------------------------------------------------------------------------------
# Entrada: texto, foto o PDF
# ------------------------------------------------------------------------------------------


@dataclass
class Entrada:
    texto: str | None = None  # enunciado escrito
    datos: bytes | None = None  # foto o PDF
    tipo: str | None = None  # mime type del archivo
    origen: str = "texto"

    def partes(self) -> list[Any]:
        from google.genai import types

        if self.datos is not None:
            return [
                types.Part.from_bytes(data=self.datos, mime_type=self.tipo or "application/octet-stream"),
                "El ENUNCIADO está en el archivo adjunto. Transcríbelo fielmente en enunciado_texto.",
            ]
        return [f"ENUNCIADO:\n{self.texto}"]


def leer_entrada(valor: str) -> Entrada:
    """Interpreta el argumento: ruta a .txt/.md/.png/.jpg/.heic/.pdf, o el enunciado mismo."""
    ruta = Path(valor).expanduser()
    parece_archivo = bool(re.search(r"\.[A-Za-z0-9]{2,5}$", valor.strip())) and len(valor) < 300
    if ruta.is_file():
        sufijo = ruta.suffix.lower()
        if sufijo in TEXTO:
            texto = ruta.read_text(encoding="utf-8").strip()
            if not texto:
                raise ErrorMotor(f"{ruta.name} está vacío.")
            return Entrada(texto=texto, origen=ruta.name)
        if sufijo in TIPOS_ARCHIVO:
            datos = ruta.read_bytes()
            if len(datos) > MAX_BYTES_ARCHIVO:
                raise ErrorMotor(
                    f"{ruta.name} pesa {len(datos) // (1024 * 1024)} MB; el máximo es 18 MB.",
                    ayuda="Envía una captura de pantalla del ejercicio (Cmd+Shift+4 en el Mac).",
                )
            return Entrada(datos=datos, tipo=TIPOS_ARCHIVO[sufijo], origen=ruta.name)
        raise ErrorMotor(
            f"No sé leer archivos {sufijo}.", ayuda="Usa .txt, una foto (.jpg, .png, .heic) o un .pdf."
        )
    if parece_archivo and " " not in valor.strip():
        raise ErrorMotor(
            f"No encuentro el archivo «{valor}».",
            ayuda="Revisa la ruta o escribe el enunciado entre comillas.",
        )
    texto = " ".join(valor.split())
    if len(texto) < 15:
        raise ErrorMotor(
            "El enunciado es muy corto.",
            ayuda='Ejemplo: ./tpi redactar "Un auto acelera de 0 a 20 m/s en 5 s…"',
        )
    return Entrada(texto=texto, origen="texto")


# ------------------------------------------------------------------------------------------
# Limpieza de lo que devuelve el modelo
# ------------------------------------------------------------------------------------------

_UNICODE_A_LATEX = {
    "·": r" \cdot ", "×": r" \times ", "−": "-", "–": "-", "≈": r" \approx ", "≠": r" \neq ",
    "≤": r" \leq ", "≥": r" \geq ", "Ω": r"\Omega ", "π": r"\pi ", "Δ": r"\Delta ", "θ": r"\theta ",
    "α": r"\alpha ", "β": r"\beta ", "μ": r"\mu ", "λ": r"\lambda ", "ω": r"\omega ", "ρ": r"\rho ",
    "°": r"^{\circ}", "²": "^2", "³": "^3", "∞": r"\infty ",
}  # fmt: skip


def limpiar_tex(tex: str) -> str:
    tex = " ".join(tex.split())
    for inicio, fin in (("$$", "$$"), ("$", "$"), (r"\(", r"\)"), (r"\[", r"\]")):
        if tex.startswith(inicio) and tex.endswith(fin) and len(tex) > len(inicio) + len(fin):
            tex = tex[len(inicio) : -len(fin)].strip()
    tex = re.sub(r"\\\\(?=[A-Za-z])", r"\\", tex)  # "\\frac" (doble escape) → "\frac"
    for caracter, latex in _UNICODE_A_LATEX.items():
        tex = tex.replace(caracter, latex)
    return " ".join(tex.split())


def _texto(s: str) -> str:
    # Los emojis van en su propio campo: dentro de un texto no se dibujan y la voz los leería
    return quitar_emojis((s or "").replace("—", ", "))


def _emoji(valor: str) -> dict[str, str]:
    """{"emoji": …} si es un emoji permitido; si no, nada (la IA no puede inventar)."""
    emoji = normalizar_para_ia(valor)
    return {"emoji": emoji} if emoji else {}


_DIBUJOS = {
    "grafico": "grafico_funcion",
    "fuerzas": "diagrama_fuerzas",
    "circuito": "circuito",
    "poligono": "poligono_regular",
    "proyectil": "proyectil",
    "circulo": "circulo_trig",
    "solido": "solido",
    "solido3d": "solido_3d",
    "venn": "venn",
    "recta": "recta",
    "probabilidad": "probabilidad",
    "torta": "torta",
    "barras": "barras",
    "onda": "onda",
    "energia": "energia",
    "optica": "optica",
    "pendulo": "pendulo",
    "resorte": "resorte",
    "escala": "escala",
    "polea": "polea",
    "tanque": "tanque",
    "viga": "viga",
    "cercha": "cercha",
    "bloques": "bloques",
    "engranaje": "engranaje",
    "mohr": "mohr",
    "oscilador": "oscilador",
    "pendulo_doble": "pendulo_doble",
    "tolva": "tolva_3d",
    "tuberia": "tuberia_3d",
    "eje": "eje_3d",
    "calor": "gradiente_termico",
    "flujo": "perfil_flujo",
}


_ESPACIOS_DEL_TEX = re.compile(r"\\[,;:!]|\\quad|\\qquad|\\ |\s+")


def _mapa(p: PasoIA, tex: str) -> list[dict[str, str]]:
    """El mapa de color del paso, solo con términos que de verdad están en su fórmula.

    Mismo criterio que la validación del guion (sin espacios de LaTeX): un término inventado se
    descarta acá en vez de tirar el guion entero a otra ronda de corrección.
    """
    if p.error or not tex:
        return []
    formula = _ESPACIOS_DEL_TEX.sub("", tex)
    mapa: list[dict[str, str]] = []
    for m in p.mapa:
        termino, concepto = limpiar_tex(m.termino), " ".join(m.concepto.split())[:28]
        limpio = _ESPACIOS_DEL_TEX.sub("", termino)
        if limpio and concepto and limpio in formula and all(x["termino"] != termino for x in mapa):
            mapa.append({"termino": termino, "concepto": concepto})
    return mapa[:3]


def _visual(p: PasoIA) -> dict[str, Any] | None:
    """Los campos planos del paso, convertidos en el bloque "visual:" que valida el motor.

    Se copian solo los que corresponden al tipo pedido: así un "grafico" con angulo de sobra
    no tira el guion, y el mensaje de error que vuelve al modelo habla del dibujo que pidió.
    """
    tipo = _DIBUJOS.get(p.dibujo)
    if not tipo:
        return None
    visual: dict[str, Any] = {"tipo": tipo}
    marcas = [a.strip() for a in p.anotar if a.strip()]
    if tipo == "grafico_funcion":
        visual["funcion"] = _texto(p.funcion)
        visual |= {k: v for k, v in (("eje_x", _texto(p.eje_x)), ("eje_y", _texto(p.eje_y))) if v}
        if p.variable.strip():
            visual["variable"] = p.variable.strip()
        if len(p.rango) == 2:
            visual["rango"] = [float(v) for v in p.rango]
        if p.movimiento:
            visual["movimiento"] = p.movimiento
            for clave in ("desde", "hasta"):
                if getattr(p, clave) is not None:
                    visual[clave] = float(getattr(p, clave))
            if marcas:
                visual["anotar"] = marcas
    elif tipo == "diagrama_fuerzas":
        visual["vectores"] = [v.strip() for v in p.vectores if v.strip()]
        if p.cuerpo:
            visual["cuerpo"] = p.cuerpo
        if p.angulo:
            visual["angulo"] = float(p.angulo)
        if p.descomponer:
            visual["descomponer"] = True
    elif tipo == "proyectil":
        if p.velocidad:
            visual["velocidad"] = _texto(p.velocidad)
        if p.angulo:
            visual["angulo"] = float(p.angulo)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "circulo_trig":
        if p.angulo:
            visual["angulo"] = float(p.angulo)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo in ("solido", "solido_3d"):
        if p.figura:
            visual["figura"] = _texto(p.figura)
        for clave in ("lado", "radio", "altura"):
            valor = _texto(getattr(p, clave))
            if valor:
                visual[clave] = valor
        if tipo == "solido_3d":
            if p.vista:
                visual["vista"] = p.vista
            if p.corte:
                visual["corte"] = p.corte
            if p.despiece:
                visual["despiece"] = True
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "venn":
        for clave in ("solo_a", "solo_b", "ambos", "fuera"):
            valor = getattr(p, clave)
            if valor is not None:
                visual[clave] = int(valor)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "recta":
        if p.extremo_a is not None:
            visual["extremo_a"] = float(p.extremo_a)
        if p.extremo_b is not None:
            visual["extremo_b"] = float(p.extremo_b)
        for clave in ("incluye_a", "incluye_b", "derecha"):
            if getattr(p, clave) is False:
                visual[clave] = False
    elif tipo == "probabilidad":
        if p.favorables is not None:
            visual["favorables"] = int(p.favorables)
        if p.totales is not None:
            visual["totales"] = int(p.totales)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo in ("torta", "barras", "energia"):
        visual["categorias"] = [c.strip() for c in p.categorias if c.strip()]
    elif tipo == "onda":
        if p.amplitud:
            visual["amplitud"] = _texto(p.amplitud)
        if p.longitud_onda:
            visual["longitud_onda"] = _texto(p.longitud_onda)
        if p.periodo is not None:
            visual["periodo"] = float(p.periodo)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "optica":
        if p.n1 is not None:
            visual["n1"] = float(p.n1)
        if p.n2 is not None:
            visual["n2"] = float(p.n2)
        if p.angulo_incidence is not None:
            visual["angulo_incidence"] = float(p.angulo_incidence)
    elif tipo == "pendulo":
        if p.longitud:
            visual["longitud"] = _texto(p.longitud)
        if p.angulo:
            visual["angulo"] = float(p.angulo)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "resorte":
        if p.constante:
            visual["constante"] = _texto(p.constante)
        if p.extension:
            visual["extension"] = _texto(p.extension)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "escala":
        if _texto(p.lado):
            visual["lado"] = _texto(p.lado)
        visual["factor"] = p.factor if p.factor in (2, 3) else 2
        visual["dimension"] = p.dimension if p.dimension in (2, 3) else 3
        if marcas:
            visual["anotar"] = marcas
    elif tipo == "polea":
        if p.masa_a:
            visual["masa_a"] = _texto(p.masa_a)
        if p.masa_b:
            visual["masa_b"] = _texto(p.masa_b)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "tanque":
        for clave, valor in (
            ("capacidad", p.capacidad),
            ("entrada", p.entrada),
            ("salida", p.salida),
        ):
            if valor:
                visual[clave] = _texto(valor)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "viga":
        if p.longitud:
            visual["longitud"] = _texto(p.longitud)
        if p.carga:
            visual["carga"] = _texto(p.carga)
        if p.repartida:
            visual["repartida"] = True
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "cercha":
        for clave, valor in (("base", p.base), ("altura", p.altura), ("carga", p.carga)):
            if valor:
                visual[clave] = _texto(valor)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "bloques":
        for clave, valor in (("adelante", p.adelante), ("retro", p.retro)):
            if valor:
                visual[clave] = _texto(valor)
        if not p.negativa:
            visual["negativa"] = False
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "engranaje":
        for clave, valor in (("dientes_a", p.dientes_a), ("dientes_b", p.dientes_b), ("rpm", p.rpm)):
            if valor:
                visual[clave] = _texto(valor)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "mohr":
        for clave, valor in (("sigma_x", p.sigma_x), ("sigma_y", p.sigma_y), ("cortante", p.cortante)):
            if valor:
                visual[clave] = _texto(valor)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "poligono_regular":
        if p.lados:
            visual["lados"] = int(p.lados)
        if p.lado:
            visual["lado"] = _texto(p.lado)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "oscilador":
        for clave, valor in (("masa", p.masa), ("constante", p.constante), ("amplitud", p.amplitud)):
            if valor:
                visual[clave] = _texto(valor)
        if p.amortiguamiento:
            visual["amortiguamiento"] = _texto(p.amortiguamiento)
        if p.duracion is not None:
            visual["duracion"] = float(p.duracion)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo == "pendulo_doble":
        for clave, valor in (
            ("masa_1", p.masa_1),
            ("masa_2", p.masa_2),
            ("longitud_1", p.longitud_1),
            ("longitud_2", p.longitud_2),
        ):
            if valor:
                visual[clave] = _texto(valor)
        for clave in ("angulo_1", "angulo_2"):
            if getattr(p, clave) is not None:
                visual[clave] = float(getattr(p, clave))
        if p.duracion is not None:
            visual["duracion"] = float(p.duracion)
        if p.anotar:
            visual["anotar"] = [a.strip() for a in p.anotar if a.strip()]
    elif tipo in ("tolva_3d", "tuberia_3d", "eje_3d"):
        claves = {
            "tolva_3d": ("radio", "altura", "radio_salida", "altura_cono"),
            "tuberia_3d": ("radio", "espesor", "longitud"),
            "eje_3d": ("unidad",),
        }[tipo]
        for clave in claves:
            if valor := _texto(getattr(p, clave)):
                visual[clave] = valor
        if tipo == "eje_3d":
            visual["radios"] = [float(v) for v in p.radios]
            visual["largos"] = [float(v) for v in p.largos]
        if tipo == "tuberia_3d" and not p.bridas:
            visual["bridas"] = False
        if p.vista:
            visual["vista"] = p.vista
        if p.despiece:
            visual["despiece"] = True
        if marcas:
            visual["anotar"] = marcas
    elif tipo == "gradiente_termico":
        for clave in ("temp_izquierda", "temp_derecha", "temp_arriba", "temp_abajo"):
            if getattr(p, clave) is not None:
                visual[clave] = float(getattr(p, clave))
        for clave in ("base", "altura"):
            if valor := _texto(getattr(p, clave)):
                visual[clave] = valor
        if marcas:
            visual["anotar"] = marcas
    elif tipo == "perfil_flujo":
        if p.flujo:
            visual["flujo"] = p.flujo
        for clave in ("velocidad", "separacion", "viscosidad"):
            if valor := _texto(getattr(p, clave)):
                visual[clave] = valor
        if marcas:
            visual["anotar"] = marcas
    else:
        visual["fuente"] = _texto(p.fuente)
        visual["resistencias"] = [r.strip() for r in p.resistencias if r.strip()]
        if p.arreglo:
            visual["arreglo"] = p.arreglo
    return visual


def a_guion(g: GuionIA) -> dict[str, Any]:
    """Convierte la respuesta del modelo al formato de guion del motor."""
    enunciado = _texto(g.enunciado_texto)
    pasos = []
    for p in g.pasos:
        tex = limpiar_tex(p.tex)
        paso: dict[str, Any] = {"nota": _texto(p.nota) or None, "tex": tex, "voz": _texto(p.voz)}
        destacar = [d.strip() for d in p.destacar if d.strip() and d.strip() in tex][:1]
        if destacar:
            paso["destacar"] = destacar
        paso |= _emoji(p.emoji)
        if p.error and tex:
            paso["error"] = True
        # El halo solo vale con términos que de verdad están en la fórmula (como destacar).
        halo = [h.strip() for h in p.halo if h.strip() and limpiar_tex(h) in tex][:2]
        if halo and tex:
            paso["halo"] = [limpiar_tex(h) for h in halo]
        if mapa := _mapa(p, tex):
            paso["mapa"] = mapa
        if p.resaltar_cambio and tex and not p.error:
            paso["resaltar_cambio"] = True
        if (visual := _visual(p)) is not None:
            paso["visual"] = visual
        pasos.append(paso)
    gancho: dict[str, Any] = {"texto": _texto(g.gancho_texto), "voz": _texto(g.gancho_voz)}
    if limpiar_tex(g.gancho_tex or ""):
        gancho["tex"] = limpiar_tex(g.gancho_tex)
    gancho |= _emoji(g.gancho_emoji)
    guion: dict[str, Any] = {
        "titulo": _texto(g.titulo),
        "materia": g.materia,
        "nivel": _texto(g.nivel) or None,
        "gancho": gancho,
        "enunciado": {
            "texto": enunciado,
            "voz": _texto(g.enunciado_voz),
            "destacar": [d.strip() for d in g.enunciado_destacar if d.strip() and d.strip() in enunciado][:3],
        },
        "datos": [{"tex": limpiar_tex(d.tex), "voz": _texto(d.voz)} for d in g.datos],
        "pasos": pasos,
        "resultado": {"tex": limpiar_tex(g.resultado_tex), "voz": _texto(g.resultado_voz)}
        | _emoji(g.resultado_emoji)
        | ({"destello": True} if g.resultado_destello else {}),
    }
    if _texto(g.verificacion_texto):
        guion["verificacion"] = {
            "texto": _texto(g.verificacion_texto),
            "voz": _texto(g.verificacion_voz) or None,
        }
    if _texto(g.reto_texto):
        guion["reto"] = {"texto": _texto(g.reto_texto), "voz": _texto(g.reto_voz) or None} | _emoji(
            g.reto_emoji
        )
    m = g.metadatos
    if m is not None and (m.titulo.strip() or m.descripcion.strip() or m.hashtags):
        # Aquí sí van emojis (es texto para la red, no para el video). Los hashtags no se limpian:
        # si la IA inventa uno con espacios o signos, el motor se lo devuelve para que lo corrija.
        guion["metadatos"] = {
            "titulo": " ".join(m.titulo.replace("—", ", ").split()),
            "descripcion": m.descripcion.replace("—", ", ").strip(),
            "hashtags": [h.strip() for h in m.hashtags if h.strip()],
        }
    return guion


def _variante_limpia(v: dict[str, Any]) -> dict[str, Any] | None:
    # Las ideas y los clips del panel traen metadatos (estilo, archivo, segundos) que el guion no guarda.
    datos = {clave: v[clave] for clave in ("texto", "voz", "tex", "emoji", "destacar") if v.get(clave)}
    try:
        g = Gancho.model_validate(datos)
    except ValidationError:
        return None
    limpio: dict[str, Any] = {"texto": g.texto}
    if g.voz:
        limpio["voz"] = g.voz
    if g.tex:
        limpio["tex"] = g.tex
    if g.emoji:
        limpio["emoji"] = g.emoji
    if g.destacar:
        limpio["destacar"] = g.destacar
    return limpio


def _aplicar_eleccion(
    datos: dict[str, Any],
    molde: str | None,
    gancho_variante: dict[str, Any] | None,
    gancho_variantes: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """El gancho elegido manda sobre lo que escribió el modelo; las alternativas quedan sin repetirlo."""
    if molde:
        datos["molde"] = molde
    elegido = _variante_limpia(gancho_variante) if gancho_variante else None
    if elegido:
        gancho = datos.setdefault("gancho", {})
        gancho["texto"] = elegido["texto"]
        if elegido.get("voz"):
            gancho["voz"] = elegido["voz"]
        # La variante manda: si no trae fórmula ni emoji, no se heredan los del modelo para otro gancho.
        for clave in ("tex", "emoji", "destacar"):
            if elegido.get(clave):
                gancho[clave] = elegido[clave]
            else:
                gancho.pop(clave, None)
    texto_elegido = (elegido or datos.get("gancho") or {}).get("texto", "").strip()
    clave_elegida = sin_tildes(texto_elegido).casefold()
    alternativas: list[dict[str, Any]] = []
    for v in gancho_variantes or []:
        limpio = _variante_limpia(v)
        if limpio and sin_tildes(limpio["texto"]).casefold() != clave_elegida:
            alternativas.append(limpio)
    datos["gancho_variantes"] = alternativas[:5]
    return datos


# ------------------------------------------------------------------------------------------
# Revisiones automáticas
# ------------------------------------------------------------------------------------------


def _error_latex(excepcion: Exception) -> str:
    """El error útil del log de LaTeX, ej. «Undefined control sequence: \\sqrtt»."""
    m = re.search(r"log file: (\S+\.log)", str(excepcion))
    if m and Path(m.group(1)).exists():
        lineas = Path(m.group(1)).read_text(encoding="utf-8", errors="replace").splitlines()
        for i, linea in enumerate(lineas):
            if linea.startswith("! "):
                error = linea[2:].strip().rstrip(".")
                # TeX marca el punto del error cortando la línea: el último comando antes del corte
                siguiente = lineas[i + 1] if i + 1 < len(lineas) else ""
                culpable = re.findall(r"\\[A-Za-z]+", siguiente.replace("\\special", ""))
                return f"{error}: {culpable[-1]}" if culpable and "control sequence" in error else error
    return str(excepcion).splitlines()[0][:160]


class SinLatex(Exception):
    """LaTeX no está instalado: las fórmulas no se pudieron compilar."""


def errores_latex(guion: Guion) -> list[str]:
    """Compila cada fórmula con LaTeX (igual que al crear el video) y devuelve los errores."""
    from manim import MathTex, tempconfig

    from .entorno import latex_disponible, preparar
    from .tex import corregir_decimales, plantilla_tex

    preparar()
    if not all(latex_disponible()):  # sin LaTeX no se puede comprobar (y no es culpa de la IA)
        raise SinLatex
    formulas = [("gancho", guion.gancho.tex)] if guion.gancho.tex else []
    formulas += [(f"dato {i}", d.tex) for i, d in enumerate(guion.datos, 1)]
    formulas += [(f"paso {i}", p.tex) for i, p in enumerate(guion.pasos, 1) if p.tex]
    formulas.append(("resultado", guion.resultado.tex))
    problemas = []
    registro = logging.getLogger("manim")
    nivel = registro.level
    cache = Path(tempfile.gettempdir()) / "tpi-tex"
    with tempconfig({"media_dir": str(cache), "tex_template": plantilla_tex(), "verbosity": "CRITICAL"}):
        registro.setLevel(logging.CRITICAL)
        try:
            for donde, tex in formulas:
                try:
                    MathTex(corregir_decimales(tex))
                except Exception as e:
                    problemas.append(f"{donde}: la fórmula «{tex}» no compila en LaTeX ({_error_latex(e)}).")
        finally:
            registro.setLevel(nivel)
    return problemas


def promesa_incumplida(duracion: float, segundos_prometidos: int | None, lectura: float = 0.0) -> bool:
    """Si lo que duró el video pasa de lo que anunció la tarjeta de la idea.

    Es el único lugar donde vive ese umbral: lo usa el aviso del guion antes de renderizar y lo usan
    el comando y el panel después, para que nunca se contradigan con dos márgenes distintos.
    ``lectura`` son los segundos que el piso de lectura esperó para que la fórmula se pudiera leer:
    no son contenido de más, así que no cuentan como exceso. Se perdonan hasta TECHO_DE_LECTURA: un
    guion con doce fórmulas necesita otra promesa, no un ⚠️ que nunca salga.
    """
    if not segundos_prometidos:
        return False
    return duracion > segundos_prometidos + MARGEN_DE_DURACION + min(lectura, TECHO_DE_LECTURA)


def problemas_de_formato(guion: Guion, segundos_prometidos: int | None = None) -> list[str]:
    """Los avisos del revisor de guiones, que la IA debe corregir antes del render.

    Con ``segundos_prometidos`` (el ``≈45 s`` que muestra la tarjeta de la idea) la duración deja de
    ser una sugerencia: un guion más largo que lo prometido devuelve a Gemini a achicarse, porque el
    número que la persona vio al elegir es la única señal que tiene de cuánto va a durar el video.
    """
    from .config import cargar_marca
    from .revision import coma, revisar

    rev = revisar(guion, cargar_marca().cierre.voz)
    problemas = [f"{a.donde}: {a.mensaje}" for a in rev.avisos if a.nivel == "advertencia"]
    if promesa_incumplida(rev.segundos, segundos_prometidos):
        # La estimación es solo voz: el render todavía va a sumar el silencio que pide cada fórmula.
        # Decirlo acá evita que Gemini recorte pasos para compensar segundos que aún no existen.
        lectura = sum(f for _, f in rev.estirados)
        aparte = (
            ""
            if lectura <= 0.05
            else f" Los {coma(lectura)} s que las fórmulas necesitan para leerse quietas cuentan aparte:"
            " no los achiques borrando pasos."
        )
        problemas.append(
            f"duración: la idea se anunció en ≈{segundos_prometidos} s y este guion se estima en "
            f"~{rev.segundos:.0f} s de voz. Achícalo a ~{segundos_prometidos} s: quédate con los 3 o 4 "
            "pasos imprescindibles, quita la verificación o el reto y acorta las frases."
            + aparte
            + " No cambies los resultados ni los números del ejercicio."
        )
    return problemas


# ------------------------------------------------------------------------------------------
# Llamadas a Gemini
# ------------------------------------------------------------------------------------------


def _sistema() -> str:
    plantilla = (PLANTILLAS_DIR / "ia" / "sistema.md").read_text(encoding="utf-8")
    ejemplo = json.dumps(EJEMPLO.model_dump(), ensure_ascii=False, indent=1)
    return (
        plantilla.replace("{{EJEMPLO}}", ejemplo)
        .replace("{{EJEMPLOS_DINAMICOS}}", _ejemplos_dinamicos())
        .replace("{{EMOJIS}}", lista_para_ia())
    )


def pedir_json(
    cliente: Any,
    modelo: str,
    sistema: str,
    contenido: list[Any],
    esquema: type[BaseModel],
    pensar: str,
    avisar: Callable[..., None] | None = None,
):
    """Pide un JSON al modelo, y si ese modelo quedó sin cupo gratuito, prueba el siguiente.

    ``avisar(mensaje, modelo_usado)`` solo suena cuando hubo que cambiar de modelo.
    """
    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=sistema,
        response_mime_type="application/json",
        response_json_schema=esquema.model_json_schema(),
        thinking_config=types.ThinkingConfig(thinking_level=pensar),
        max_output_tokens=32768,  # incluye el razonamiento interno del modelo
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        ),  # no usamos herramientas
    )
    cadena = ia.cadena_desde(modelo)
    errores: list[Exception] = []
    respuesta = None
    for puesto, intento in enumerate(cadena):
        try:
            respuesta = cliente.models.generate_content(model=intento, contents=contenido, config=config)
        except ErrorMotor:
            raise
        except Exception as e:
            if not ia.vale_probar_otro_modelo(e):
                # Un 400 o una clave rechazada se repetirían en los cuatro modelos: mejor decirlo ya.
                raise ia.explicar_error(e, intento) from e
            errores.append(e)
            continue
        if puesto and avisar:
            motivo = "se quedó sin cupo" if ia.es_cuota_agotada(errores[-1]) else "está saturado"
            avisar(f"{modelo} {motivo}: sigo escribiendo con {intento}.", intento)
        break
    if respuesta is None:
        if all(ia.es_cuota_agotada(e) for e in errores):
            raise ErrorMotor(
                f"Se acabó el cupo gratuito de los {len(cadena)} modelos de respaldo.",
                ayuda=(
                    "El cupo se reinicia de madrugada (medianoche hora del Pacífico): mira cuánto "
                    "te queda con ./tpi cuota. Si apura, escribe el guion a mano y créalo igual: "
                    "./tpi crear guiones/<archivo>.yaml"
                ),
                transitorio=True,
            ) from errores[-1]
        raise ia.explicar_error(errores[0], cadena[-1]) from errores[0]
    texto = respuesta.text or ""
    if not texto.strip():
        candidato = (respuesta.candidates or [None])[0]
        motivo = getattr(getattr(candidato, "finish_reason", None), "value", None)
        bloqueo = getattr(getattr(respuesta, "prompt_feedback", None), "block_reason", None)
        raise ErrorMotor(
            f"Gemini no devolvió respuesta ({motivo or bloqueo or 'sin motivo'}).",
            ayuda="Repite el comando; si sigue pasando, prueba con el enunciado en texto.",
        )
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    try:
        return esquema.model_validate_json(texto)
    except ValidationError as e:
        raise ErrorMotor(
            "Gemini devolvió una respuesta con un formato inesperado.",
            ayuda="Repite el comando (a veces pasa). Detalle: " + "; ".join(explicar_errores(e))[:300],
        ) from e


def _contenido_base(
    entrada: Entrada, materia: str | None, nivel: str | None, pistas: list[str] | None = None
) -> list[Any]:
    contenido = entrada.partes()
    pistas_base = []
    if materia:
        pistas_base.append(f"Materia: {materia}.")
    pistas_base.append(f"Nivel de los estudiantes: {nivel or 'enseñanza media (Chile)'}.")
    contenido.append(" ".join(pistas_base))
    contenido.extend(pistas or [])
    return contenido


def _nombre_archivo(titulo: str, nombre: str | None, forzar: bool) -> Path:
    base = re.sub(r"[^a-z0-9]+", "_", sin_tildes((nombre or titulo).lower())).strip("_")[:50] or "guion"
    carpeta = raiz_proyecto() / "guiones"
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{base}.yaml"
    n = 2
    while destino.exists() and not forzar:
        destino = carpeta / f"{base}_{n}.yaml"
        n += 1
    return destino


# ------------------------------------------------------------------------------------------
# Orquestación
# ------------------------------------------------------------------------------------------


@dataclass
class ResultadoRedaccion:
    ruta: Path
    guion: Guion
    supuestos: list[str]
    pendientes: list[str]  # problemas que quedaron sin resolver (para que el profesor los vea)
    rondas: int
    modelo: str
    revisado_por_ia: bool
    historial: list[str] = field(default_factory=list)


def redactar(
    valor: str,
    materia: str | None = None,
    nivel: str | None = None,
    modelo: str = ia.MODELO_POR_DEFECTO,
    nombre: str | None = None,
    forzar: bool = False,
    revisar_con_ia: bool = True,
    pistas: list[str] | None = None,
    segundos_prometidos: int | None = None,
    molde: str | None = None,
    gancho_variante: dict[str, Any] | None = None,
    gancho_variantes: list[dict[str, Any]] | None = None,
    avisar=lambda mensaje: None,
    carrera: str | None = None,
) -> ResultadoRedaccion:
    from .malla import pista_para_la_ia
    from .niveles import normalizar

    entrada = leer_entrada(valor)
    nivel = normalizar(nivel) or nivel  # «segundo año de ingeniería» → «2° año ingeniería»
    cliente = ia.cliente()
    sistema = _sistema()
    clave_molde = normalizar_molde(molde) if molde else ""
    if molde and not clave_molde:
        raise ErrorMotor(
            f"El molde «{molde}» no existe.",
            ayuda=f"Opciones: {opciones_de_moldes()}.",
        )
    molde = clave_molde or None
    if segundos_prometidos:
        # La tarjeta de la idea ya le mostró esa duración a la persona: es un compromiso, no un deseo.
        pistas = [
            *(pistas or []),
            f"DURACIÓN PROMETIDA: este video se anunció con ≈{segundos_prometidos} s. La voz dice unos "
            f"15 caracteres por segundo, así que tienes ~{segundos_prometidos * 15} caracteres hablados "
            "para todo el guion (gancho, enunciado, pasos, resultado y cierre): 3 o 4 pasos cortos y "
            "frases de una línea.",
        ]
    pistas = list(pistas or [])
    if pista := pista_para_la_ia(nivel, materia, carrera):
        pistas.append(pista)
    if molde:
        m = MOLDES[molde]
        pistas.append(f"MOLDE «{m.nombre}»: {m.estructura}. {m.pista}")
    if gancho_variante:
        texto = str(gancho_variante.get("texto") or "").strip()
        if texto:
            emoji = str(gancho_variante.get("emoji") or "").strip()
            tex = str(gancho_variante.get("tex") or "").strip()
            pistas.append(
                "GANCHO ELEGIDO: usa tal cual el texto «"
                f"{texto}»"
                + (f", el emoji {emoji}" if emoji else "")
                + (f" y la fórmula {tex}" if tex else "")
                + ". Solo ajusta gancho_voz para que suene natural."
            )
    base = _contenido_base(entrada, materia, nivel, pistas)
    revisor = (PLANTILLAS_DIR / "ia" / "revisor.md").read_text(encoding="utf-8")
    historial: list[str] = []
    sin_latex = False
    en_uso = {"modelo": modelo}

    def al_cambiar_de_modelo(mensaje: str, nuevo: str) -> None:
        en_uso["modelo"] = nuevo  # el encabezado del guion debe decir quién lo escribió
        avisar(mensaje)

    avisar("Gemini está resolviendo el ejercicio y escribiendo el guion (30–90 s)…")
    respuesta = pedir_json(cliente, modelo, sistema, base, GuionIA, "high", avisar=al_cambiar_de_modelo)
    rondas = 0
    revisado = False
    while True:
        if not respuesta.es_ejercicio:
            raise ErrorMotor(
                f"Gemini dice que esto no es un ejercicio que pueda resolver: {respuesta.motivo or 'sin motivo'}",
                ayuda="Revisa el enunciado (¿está completo y se lee bien en la foto?).",
            )
        problemas: list[str] = []
        datos = _aplicar_eleccion(a_guion(respuesta), molde, gancho_variante, gancho_variantes)
        if materia:  # lo que pide la persona manda sobre lo que deduce la IA
            datos["materia"] = materia
        if nivel:
            datos["nivel"] = nivel
        if carrera:
            datos["carrera"] = carrera
        try:
            guion = Guion.model_validate(datos)
        except ValidationError as e:
            guion = None
            problemas += [f"formato: {linea}" for linea in explicar_errores(e)]
        if guion is not None:
            avisar("Compilando las fórmulas con LaTeX…")
            try:
                problemas += errores_latex(guion)
            except SinLatex:
                sin_latex = True
            problemas += problemas_de_formato(guion, segundos_prometidos)
            if revisar_con_ia and not problemas:
                avisar("Gemini revisa la matemática como profesor revisor…")
                guion_json = json.dumps(respuesta.model_dump(), ensure_ascii=False)
                revision = pedir_json(cliente, modelo, revisor, [*base, f"GUION A REVISAR (JSON):\n{guion_json}"],
                                  RevisionIA, "low", avisar=al_cambiar_de_modelo)  # fmt: skip
                revisado = True
                if not revision.aprobado:
                    problemas += [f"revisor: {p}" for p in revision.problemas] or [
                        "revisor: no aprobó el guion"
                    ]
        historial += [f"ronda {rondas}: {p}" for p in problemas]
        if not problemas or rondas >= RONDAS_DE_CORRECCION:
            break
        rondas += 1
        avisar(f"Corrigiendo {len(problemas)} detalle(s) (ronda {rondas} de {RONDAS_DE_CORRECCION})…")
        anterior = json.dumps(respuesta.model_dump(), ensure_ascii=False)
        pedido = "\n".join(
            [
                "Tu respuesta anterior tiene estos problemas. Corrígelos y devuelve el JSON completo corregido:",
                *[f"- {p}" for p in problemas],
                "",
                f"RESPUESTA ANTERIOR (JSON):\n{anterior}",
            ]
        )
        respuesta = pedir_json(
            cliente, modelo, sistema, [*base, pedido], GuionIA, "high", avisar=al_cambiar_de_modelo
        )

    if guion is None:
        detalle = "\n".join(f"  • {p}" for p in problemas[:8])
        raise ErrorMotor(f"No logré un guion válido tras {rondas + 1} intentos:\n{detalle}",
                         ayuda="Repite el comando o escribe el enunciado más claro.")  # fmt: skip

    destino = _nombre_archivo(guion.titulo, nombre, forzar)
    cabecera = [
        f"Guion redactado con IA ({en_uso['modelo']}) el {dt.date.today():%d-%m-%Y} a partir de: {entrada.origen}",
        "REVISA la matemática y los textos antes de publicar: la IA puede equivocarse.",
    ]
    if sin_latex:
        problemas.append(
            "no se compilaron las fórmulas porque falta LaTeX (ejecuta ./scripts/instalar_mac.sh)"
        )
    if respuesta.supuestos:
        cabecera += ["", "Supuestos de la IA:"] + [f"  - {s}" for s in respuesta.supuestos]
    if problemas:
        cabecera += ["", "Quedaron observaciones por revisar:"] + [f"  - {p}" for p in problemas]
    elif revisado:
        cabecera += [
            "",
            "Revisión automática: fórmulas compiladas y cálculos revisados por la IA (sin observaciones).",
        ]
    destino.write_text(a_yaml(datos, cabecera), encoding="utf-8")
    guion_final = cargar_guion(destino)  # comprueba que el archivo escrito se lee igual
    return ResultadoRedaccion(
        ruta=destino,
        guion=guion_final,
        supuestos=respuesta.supuestos,
        pendientes=problemas,
        rondas=rondas,
        modelo=modelo,
        revisado_por_ia=revisado,
        historial=historial,
    )
