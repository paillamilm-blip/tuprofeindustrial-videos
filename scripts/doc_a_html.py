"""Convierte un documento de docs/ (Markdown) en su versión HTML autocontenida, con la piel de la casa.

Uso:
    python3 scripts/doc_a_html.py docs/ANALISIS_TECNICO.md docs/ANALISIS_TECNICO.html

Sin dependencias (solo la biblioteca estándar). Toma el ``<style>`` del HTML de destino si ya existe, así el
diseño se conserva y solo cambia el contenido. Entiende lo que usan los documentos del repo: títulos, párrafos,
listas, tablas, bloques de código, citas y enlaces. Las celdas ``ALTO`` / ``MEDIO`` / ``BAJO`` salen como chips.

Opcional, en el Markdown (invisible en GitHub):
    <!-- sobretitulo: Documento técnico · Sistema 2 -->
    <!-- cifras: 48 | guiones YAML ; 885 | pruebas automáticas -->
    <!-- pie: Motor de video Tu Profe Industrial · Análisis técnico -->
"""

from __future__ import annotations

import html
import re
import sys
import unicodedata
from pathlib import Path

ESTILO_MINIMO = """<style>
  body{font-family:system-ui,sans-serif;max-width:980px;margin:40px auto;padding:0 20px;line-height:1.55;color:#1B2430}
  table{border-collapse:collapse;width:100%} th,td{border:1px solid #DCDCD7;padding:6px 8px;text-align:left}
  pre{background:#EEF1F5;padding:12px;overflow:auto} code{background:#EEF1F5;padding:0 3px}
</style>"""

_CHIP = re.compile(r"^(ALTO|MEDIO|BAJO)\b:?\s*(.*)$")


def _ancla(texto: str) -> str:
    sin = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", sin).strip("-") or "seccion"


def _en_linea(texto: str) -> str:
    """Código, negritas, cursivas y enlaces. Lo demás se escapa."""
    partes = re.split(r"(`[^`]+`)", texto)
    salida = []
    for parte in partes:
        if parte.startswith("`") and parte.endswith("`") and len(parte) > 1:
            salida.append(f"<code>{html.escape(parte[1:-1])}</code>")
            continue
        t = html.escape(parte, quote=False)
        t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<em>\1</em>", t)
        salida.append(t)
    return "".join(salida)


def _celda(texto: str) -> str:
    texto = texto.strip()
    if m := _CHIP.match(texto):
        nivel, resto = m.groups()
        chip = f'<span class="chip {nivel.lower()}">{nivel}</span>'
        return chip + (" " + _en_linea(resto) if resto else "")
    return _en_linea(texto)


def _tabla(filas: list[str]) -> str:
    def partir(linea: str) -> list[str]:
        return [c for c in linea.strip().strip("|").split("|")]

    cabecera = partir(filas[0])
    cuerpo = [partir(f) for f in filas[2:]]
    th = "".join(f"<th>{_en_linea(c.strip())}</th>" for c in cabecera)
    trs = "\n".join("        <tr>" + "".join(f"<td>{_celda(c)}</td>" for c in fila) + "</tr>" for fila in cuerpo)
    return (
        '  <div class="tabla-envoltura">\n    <table>\n'
        f"      <thead><tr>{th}</tr></thead>\n      <tbody>\n{trs}\n      </tbody>\n    </table>\n  </div>"
    )


def _codigo(lineas: list[str]) -> str:
    salida = []
    for linea in lineas:
        if linea.lstrip().startswith(("#", "//")):
            salida.append(f'<span class="c">{html.escape(linea)}</span>')
        else:
            salida.append(html.escape(linea))
    return '<pre class="flujo">' + "\n".join(salida) + "</pre>"


def _bloques(lineas: list[str]) -> str:
    """El cuerpo de una sección: párrafos, listas, tablas, código, citas y subtítulos."""
    salida: list[str] = []
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        if not linea.strip() or linea.strip() == "---" or linea.strip().startswith("<!--"):
            i += 1
            continue
        if linea.startswith("```"):
            j = i + 1
            while j < len(lineas) and not lineas[j].startswith("```"):
                j += 1
            salida.append(_codigo(lineas[i + 1 : j]))
            i = j + 1
            continue
        if linea.startswith("#### "):
            salida.append(f"  <h4>{_en_linea(linea[5:])}</h4>")
            i += 1
            continue
        if linea.startswith("### "):
            salida.append(f"  <h3>{_en_linea(linea[4:])}</h3>")
            i += 1
            continue
        if linea.startswith("|"):
            j = i
            while j < len(lineas) and lineas[j].startswith("|"):
                j += 1
            salida.append(_tabla(lineas[i:j]))
            i = j
            continue
        if linea.startswith(">"):
            j = i
            texto = []
            while j < len(lineas) and lineas[j].startswith(">"):
                texto.append(lineas[j].lstrip("> ").rstrip())
                j += 1
            salida.append(f'  <div class="nota">{_en_linea(" ".join(texto))}</div>')
            i = j
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s", linea):
            ordenada = bool(re.match(r"^\s*\d+\.\s", linea))
            items: list[str] = []
            j = i
            while j < len(lineas) and lineas[j].strip():
                if re.match(r"^\s*([-*]|\d+\.)\s", lineas[j]) and not lineas[j].startswith("    "):
                    items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lineas[j]))
                else:
                    items[-1] += " " + lineas[j].strip()
                j += 1
            etiqueta = "ol" if ordenada else "ul"
            lis = "\n".join(f"    <li>{_en_linea(t)}</li>" for t in items)
            salida.append(f"  <{etiqueta}>\n{lis}\n  </{etiqueta}>")
            i = j
            continue
        j = i
        texto = []
        while j < len(lineas) and lineas[j].strip() and not re.match(r"^(#|\||```|>|\s*([-*]|\d+\.)\s)", lineas[j]):
            texto.append(lineas[j].strip())
            j += 1
        salida.append(f"  <p>{_en_linea(' '.join(texto))}</p>")
        i = j
    return "\n\n".join(salida)


def convertir(md: str, estilo: str) -> str:
    lineas = md.splitlines()
    titulo = next((l[2:].strip() for l in lineas if l.startswith("# ")), "Documento")
    principal, _, bajada = titulo.partition(" — ")
    comentarios = dict(re.findall(r"<!--\s*([a-z]+):\s*(.*?)\s*-->", md))
    meta = re.findall(r"^\*\*([^*]+):\*\*\s*(.+)$", md, re.MULTILINE)

    # Secciones: todo lo que va bajo cada «## ».
    secciones: list[tuple[str, list[str]]] = []
    for linea in lineas:
        if linea.startswith("## "):
            secciones.append((linea[3:].strip(), []))
        elif secciones:
            secciones[-1][1].append(linea)

    cifras = ""
    if comentarios.get("cifras"):
        celdas = []
        for par in comentarios["cifras"].split(";"):
            numero, _, rotulo = par.partition("|")
            celdas.append(f'  <div class="cifra"><b>{html.escape(numero.strip())}</b><small>{_en_linea(rotulo.strip())}</small></div>')
        cifras = '<div class="cifras">\n' + "\n".join(celdas) + "\n</div>\n"

    indice, cuerpo = [], []
    for nombre, contenido in secciones:
        m = re.match(r"^(\d+)\.\s+(.*)$", nombre)
        numero, texto = (m.group(1), m.group(2)) if m else ("", nombre)
        ancla = _ancla(texto)
        indice.append(f'    <li><a href="#{ancla}">{_en_linea(texto)}</a></li>')
        num = f'<span class="num">{numero}</span>' if numero else ""
        cuerpo.append(f'<section id="{ancla}">\n  <h2>{num}{_en_linea(texto)}</h2>\n{_bloques(contenido)}\n</section>')

    spans = "\n".join(f"    <span><b>{html.escape(k)}:</b> {_en_linea(v)}</span>" for k, v in meta if k.lower() != "para")
    sobretitulo = html.escape(comentarios.get("sobretitulo", "Documento · Tu Profe Industrial"))
    pie = html.escape(comentarios.get("pie", principal))
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(principal)}</title>
{estilo}
</head>
<body>
<div class="lienzo">

<!-- Generado con scripts/doc_a_html.py a partir del .md del mismo nombre: no editar a mano. -->
<header class="tapa">
  <p class="sobretitulo">{sobretitulo}</p>
  <h1>{_en_linea(principal)}</h1>
  {f"<p>{_en_linea(bajada)}</p>" if bajada else ""}
  <div class="meta">
{spans}
  </div>
</header>

{cifras}
<nav class="indice">
  <h2>Contenido</h2>
  <ol>
{chr(10).join(indice)}
  </ol>
</nav>

{chr(10).join(cuerpo)}

<footer>{pie}</footer>
</div>
</body>
</html>
"""


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    origen, destino = Path(argv[1]), Path(argv[2])
    estilo = ESTILO_MINIMO
    if destino.exists():
        previo = destino.read_text(encoding="utf-8")
        if m := re.search(r"<style>.*?</style>", previo, re.DOTALL):
            estilo = m.group(0)
    destino.write_text(convertir(origen.read_text(encoding="utf-8"), estilo), encoding="utf-8")
    print(f"Listo: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
