"""Guiones mínimos para las pruebas de contenido demostrativo (dato, mito, error, ejercicio).

Solo diccionarios: no importan modelos, para que sirvan también antes de que el esquema exista.
"""

from copy import deepcopy


def datos_base():
    return {
        "titulo": "Compara dos valores", "materia": "matematica",
        "gancho": {"texto": "¿Cambian de la misma manera?", "voz": "¿Cambian de la misma manera?"},
        "enunciado": {"texto": "Compara el doble de una longitud con el volumen del cubo."},
        "pasos": [
            {"voz": "Primero toma una arista.", "tex": "a = 1"},
            {"voz": "Después duplica la arista.", "tex": "a = 2"},
        ],
        "resultado": {"tex": "V = 8", "voz": "El volumen es ocho."},
    }  # fmt: skip


def datos_concepto():
    datos = deepcopy(datos_base())
    datos["contenido"] = {
        "intenciones": ["dato"],
        "objetivo": "Distinguir longitud y volumen sin confundir sus escalas.",
    }
    datos["recursos"] = {"panel": False, "micro": None}
    datos["resultado"] = {
        "texto": "Longitud y volumen crecen de distinta manera.",
        "voz": "La longitud y el volumen no crecen de la misma manera.",
    }
    return datos


def datos_mito_cubo():
    """El mito del cubo sobre los datos reales de guiones/caben_ocho_cubos.yaml (solo lectura).

    Mito + ejercicio: «duplicar la arista duplica el volumen». Variante consola_mito con el resumen
    de fórmulas encendido por elección (la variante sola no lo trae). La fórmula del guion real sigue
    siendo la pieza principal del cierre; la conclusión en texto la interpreta.
    """
    from pathlib import Path

    import yaml

    ruta = Path(__file__).resolve().parents[1] / "guiones" / "caben_ocho_cubos.yaml"
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    datos["titulo"] = "El mito del cubo: ¿doble arista, doble volumen?"
    datos["tema"] = "consola_mito"
    datos["contenido"] = {
        "intenciones": ["mito", "ejercicio"],
        "objetivo": "Demostrar que duplicar la arista multiplica el volumen por ocho, no por dos.",
    }
    datos["recursos"] = {"panel": True}
    datos["resultado"]["texto"] = "Duplicar la arista multiplica el volumen por ocho."
    return datos
