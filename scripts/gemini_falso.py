"""Servidor de Gemini de mentira para probar ``tpi redactar`` sin clave ni internet.

Uso (en una Terminal aparte):
    .venv/bin/python scripts/gemini_falso.py 8765
y en otra:
    GOOGLE_GEMINI_BASE_URL=http://127.0.0.1:8765 GEMINI_API_KEY=falsa ./tpi redactar "Derivada de una cuadrática"

Responde con los ejemplos de ``pruebas/ia_falsa.py`` según el tema. Sirve para revisar que el
motor convierta bien lo que escribe la IA; no dice nada de lo que escribiría el Gemini de verdad.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pruebas.ia_falsa import respuesta  # noqa: E402


def _textos(bloque: object) -> list[str]:
    if isinstance(bloque, dict):
        return [p.get("text", "") for p in bloque.get("parts", []) if isinstance(p, dict)]
    return []


class _Gemini(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 (nombre que exige http.server)
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        sistema = "\n".join(_textos(cuerpo.get("systemInstruction") or cuerpo.get("system_instruction")))
        texto = "\n".join(t for c in cuerpo.get("contents", []) for t in _textos(c))
        salida = {
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": respuesta(sistema, texto)}]},
                    "finishReason": "STOP",
                }
            ]
        }
        datos = json.dumps(salida, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, formato: str, *args: object) -> None:
        sys.stderr.write("gemini falso: " + formato % args + "\n")


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"Gemini falso escuchando en http://127.0.0.1:{puerto}", flush=True)
    HTTPServer(("127.0.0.1", puerto), _Gemini).serve_forever()
