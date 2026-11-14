"""Lista los guiones donde el dibujo no acompaña la explicación (pasos con fórmula y sin dibujo).

Uso, desde la carpeta del proyecto:  python3 scripts/dibujos_que_faltan.py [guiones/x.yaml ...]
Sin argumentos revisa todos los de guiones/. Usa la misma regla que ``./tpi revisar``
(``tpi_videos.acompanar``), pero lee el YAML con PyYAML para no necesitar el motor completo.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import yaml  # noqa: E402

from tpi_videos.acompanar import PasoParaRevisar, faltas_de_acompanamiento  # noqa: E402


def revisar(ruta: Path) -> list:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    intenciones = (datos.get("contenido") or {}).get("intenciones") or ["ejercicio"]
    pasos = [
        PasoParaRevisar(tex=str(p.get("tex") or ""), error=bool(p.get("error")), visual=p.get("visual"))
        for p in datos.get("pasos") or []
    ]
    return faltas_de_acompanamiento(pasos, ejercicio="ejercicio" in intenciones)


def main() -> int:
    rutas = [Path(a) for a in sys.argv[1:]] or sorted((RAIZ / "guiones").glob("*.yaml"))
    con_faltas = 0
    for ruta in rutas:
        faltas = revisar(ruta)
        if faltas:
            con_faltas += 1
            print(f"✗ {ruta.name}")
            for f in faltas:
                print(f"    {f.donde}: {f.mensaje}")
        else:
            print(f"✓ {ruta.name}")
    print(f"\n{con_faltas} de {len(rutas)} guiones tienen pasos sin su dibujo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
