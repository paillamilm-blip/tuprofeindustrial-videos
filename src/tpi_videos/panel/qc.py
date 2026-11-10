"""La aprobación de guiones (QC): qué guion se revisó, con qué decisión, y su ficha de lectura.

Las decisiones viven en ``salida/.cola/qc.json`` (Git lo ignora, igual que la cola). Cada decisión
guarda la huella del archivo: si el guion se edita después de aprobarlo o rechazarlo, vuelve solo a
«por revisar». No depende de NiceGUI: se prueba sin abrir el panel.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import cargar_marca
from ..entorno import raiz_proyecto
from ..errores import ErrorMotor
from ..guion import Guion, cabecera_de, cargar_guion, fijar_tema
from ..pausas import sin_pausas, trozos
from ..temas import EstiloSugerido, estilo_del_guion, sugerir_tema_de_guion

POR_REVISAR, APROBADO, RECHAZADO = "por_revisar", "aprobado", "rechazado"
NOMBRES = {POR_REVISAR: "Por revisar", APROBADO: "Aprobado", RECHAZADO: "Rechazado"}


def _archivo() -> Path:
    return raiz_proyecto() / "salida" / ".cola" / "qc.json"


def _carpeta_guiones() -> Path:
    return raiz_proyecto() / "guiones"


def _clave(ruta: Path) -> str:
    return ruta.resolve().relative_to(_carpeta_guiones().resolve()).as_posix()


def huella(ruta: Path) -> str:
    return hashlib.sha1(ruta.read_bytes()).hexdigest()[:16]


def _leer() -> dict[str, Any]:
    try:
        datos = json.loads(_archivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "guiones": {}}
    if not isinstance(datos, dict) or not isinstance(datos.get("guiones"), dict):
        return {"version": 1, "guiones": {}}
    return datos


def _guardar(datos: dict[str, Any]) -> None:
    destino = _archivo()
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destino.parent, delete=False) as tmp:
        json.dump(datos, tmp, ensure_ascii=False, indent=1)
    os.replace(tmp.name, destino)


def guion_revisable(ruta: Path) -> bool:
    """Solo los guiones propios de guiones/ (no los ejemplos): son los que salen de ./tpi redactar."""
    try:
        ruta = ruta.resolve()
        relativa = ruta.relative_to(_carpeta_guiones().resolve())
    except ValueError:
        return False
    return ruta.is_file() and ruta.suffix in (".yaml", ".yml") and relativa.parts[0] != "ejemplos"


def estado(ruta: Path) -> str:
    decision = _leer()["guiones"].get(_clave(ruta))
    if not decision or decision.get("huella") != huella(ruta):
        return POR_REVISAR
    return str(decision.get("estado") or POR_REVISAR)


def decision(ruta: Path) -> dict[str, Any] | None:
    return _leer()["guiones"].get(_clave(ruta))


def _decidir(ruta: Path, nuevo: str, **extra: Any) -> None:
    if not guion_revisable(ruta):
        raise ErrorMotor("Ese archivo no es un guion de guiones/.", ayuda="Elige uno de la lista.")
    datos = _leer()
    datos["guiones"][_clave(ruta)] = {
        "estado": nuevo,
        "huella": huella(ruta),
        "fecha": dt.datetime.now().isoformat(timespec="seconds"),
        **extra,
    }
    _guardar(datos)


def aprobar(ruta: Path, cola_id: str | None) -> None:
    _decidir(ruta, APROBADO, cola_id=cola_id)


def rechazar(ruta: Path, nota: str = "") -> None:
    _decidir(ruta, RECHAZADO, nota=nota.strip())


def guiones(incluir_decididos: bool = False) -> list[Path]:
    """Los guiones propios, los más nuevos primero; por defecto solo los que esperan revisión."""
    carpeta = _carpeta_guiones()
    if not carpeta.exists():
        return []
    rutas = sorted(
        (r for r in [*carpeta.glob("*.yaml"), *carpeta.glob("*.yml")] if r.is_file()),
        key=lambda r: r.stat().st_mtime,
        reverse=True,
    )
    return rutas if incluir_decididos else [r for r in rutas if estado(r) == POR_REVISAR]


# ------------------------------------------------------------------------------------------
# La ficha de lectura: lo que una persona necesita para decidir, sin ver el YAML
# ------------------------------------------------------------------------------------------


@dataclass
class Voz:
    seccion: str
    texto: str  # sin las etiquetas de pausa
    pausas: list[float] = field(default_factory=list)  # los silencios de esta voz, en orden


@dataclass
class Ficha:
    ruta: Path
    titulo: str
    materia: str
    nivel: str
    estado: str
    metadatos: dict[str, Any] | None
    voces: list[Voz]
    observaciones: list[str]  # lo que la IA dejó sin resolver y los supuestos (comentarios del YAML)
    tecnico: list[str]  # una línea por dibujo, fórmula o ajuste visual
    yaml: str
    error: str | None = None  # si el YAML no valida: se puede rechazar, no aprobar
    estilo: EstiloSugerido | None = None  # con el que saldrá: el elegido acá o, si no, el sugerido
    sugerido: EstiloSugerido | None = None  # el que el motor le propone a este video

    @property
    def aprobable(self) -> bool:
        return self.error is None


def _observaciones(ruta: Path) -> list[str]:
    salida: list[str] = []
    for linea in cabecera_de(ruta):
        texto = linea.strip()
        if texto.startswith("- "):
            salida.append(texto[2:].strip())
    return salida


def _tecnico(guion: Guion) -> list[str]:
    lineas = []
    if guion.tema:
        lineas.append(f"Estilo: {guion.tema}")
    if guion.molde:
        lineas.append(f"Molde: {guion.molde}")
    for i, paso in enumerate(guion.pasos, 1):
        partes = []
        if paso.tex:
            partes.append(f"fórmula {paso.tex}")
        if paso.visual is not None:
            v = paso.visual
            extra = [
                nombre
                for nombre, activo in (
                    (f"movimiento {v.movimiento}", bool(v.movimiento)),
                    ("despiece", v.despiece),
                    (f"vista {v.vista}", v.tipo.endswith("_3d")),
                )
                if activo
            ]
            partes.append(f"dibujo {v.tipo}" + (f" ({', '.join(extra)})" if extra else ""))
        if paso.halo:
            partes.append(f"halo {', '.join(paso.halo)}")
        if paso.resaltar_cambio:
            partes.append("resalta el cambio")
        if paso.error:
            partes.append("error típico")
        if partes:
            lineas.append(f"Paso {i}: " + " · ".join(partes))
    if guion.resultado.destello:
        lineas.append("Resultado con destello")
    return lineas


def ficha(ruta: Path) -> Ficha:
    texto = ruta.read_text(encoding="utf-8")
    try:
        guion = cargar_guion(ruta)
    except ErrorMotor as e:
        return Ficha(
            ruta=ruta,
            titulo=ruta.stem.replace("_", " "),
            materia="",
            nivel="",
            estado=estado(ruta),
            metadatos=None,
            voces=[],
            observaciones=_observaciones(ruta),
            tecnico=[],
            yaml=texto,
            error=f"{e.mensaje} {e.ayuda or ''}".strip(),
        )
    voces = []
    for seccion, voz in guion.textos_de_voz(""):
        if not voz:
            continue
        voces.append(Voz(seccion, sin_pausas(voz), [p for _, p in trozos(voz) if p]))
    marca = cargar_marca()
    return Ficha(
        ruta=ruta,
        titulo=guion.titulo,
        materia=guion.etiqueta_materia,
        nivel=guion.nivel or "",
        estado=estado(ruta),
        metadatos=guion.metadatos.model_dump() if guion.metadatos else None,
        voces=voces,
        observaciones=_observaciones(ruta),
        tecnico=_tecnico(guion),
        yaml=texto,
        estilo=estilo_del_guion(guion, marca),
        sugerido=sugerir_tema_de_guion(guion, marca),
    )


# ------------------------------------------------------------------------------------------
# El estilo del video: el ÚNICO lugar del panel donde se elige
# ------------------------------------------------------------------------------------------


def cambiar_estilo(ruta: Path, clave: str) -> EstiloSugerido:
    """Deja el guion con ese estilo. Elegir el sugerido borra el ``tema:``: vuelve a lo automático.

    Cambiar el estilo no cambia lo que se dice ni lo que se calcula: si el guion ya estaba aprobado
    (o rechazado), la decisión se mantiene con la huella nueva. Así no vuelve a «por revisar» ni se
    puede mandar dos veces a la cola.
    """
    marca = cargar_marca()
    sugerido = sugerir_tema_de_guion(cargar_guion(ruta), marca)  # no mira el «tema:» actual
    previo = estado(ruta)
    guion = fijar_tema(ruta, None if clave == sugerido.clave else clave)
    if previo != POR_REVISAR and guion_revisable(ruta):
        datos = _leer()
        datos["guiones"][_clave(ruta)]["huella"] = huella(ruta)
        _guardar(datos)
    return estilo_del_guion(guion, marca)
