#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  Instalador del motor de video · Tu Profe Industrial (macOS)
#  Uso (desde la carpeta del repo):   ./scripts/instalar_mac.sh
#  Se puede ejecutar todas las veces que quieras: lo que ya está instalado se salta.
#  Te pedirá tu contraseña del Mac un par de veces (al instalar LaTeX).
# ─────────────────────────────────────────────────────────────────────────────

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1

verde()    { printf "\033[32m✅ %s\033[0m\n" "$1"; }
amarillo() { printf "\033[33m➜  %s\033[0m\n" "$1"; }
rojo()     { printf "\033[31m❌ %s\033[0m\n" "$1"; }
titulo()   { printf "\n\033[1m%s\033[0m\n" "$1"; }

if [ "$(uname -s)" != "Darwin" ]; then
  rojo "Este instalador es para macOS. En Linux instala: cairo, pango, ffmpeg (con libass), texlive y uv."
  exit 1
fi

# ── 1. Herramientas de desarrollo de Apple (compilador) ──────────────────────
titulo "1/5 · Herramientas de Apple"
if xcode-select -p >/dev/null 2>&1; then
  verde "Herramientas de línea de comandos de Xcode presentes"
else
  amarillo "Se abrirá una ventana para instalar las 'Command Line Tools'. Acepta y espera a que termine."
  xcode-select --install
  amarillo "Cuando termine esa instalación, vuelve a ejecutar:  ./scripts/instalar_mac.sh"
  exit 0
fi

# ── 2. Homebrew ──────────────────────────────────────────────────────────────
titulo "2/5 · Homebrew (instalador de programas)"
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [ -x "$b" ]; then eval "$("$b" shellenv)"; fi
  done
fi
if ! command -v brew >/dev/null 2>&1; then
  amarillo "Homebrew no está instalado. Lo instalo ahora (te pedirá tu contraseña y presionar Enter)."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
    rojo "No se pudo instalar Homebrew. Revisa tu internet y vuelve a intentar."; exit 1; }
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [ -x "$b" ]; then eval "$("$b" shellenv)"; fi
  done
  # Para que la terminal encuentre brew la próxima vez
  if ! grep -qs "brew shellenv" "$HOME/.zprofile"; then
    echo "eval \"\$($(command -v brew) shellenv)\"" >> "$HOME/.zprofile"
  fi
fi
verde "Homebrew $(brew --version | head -1 | awk '{print $2}')"

# cairo + pkg-config: para la librería gráfica de Manim
# ffmpeg-full: la versión con libass (el ffmpeg normal de Homebrew ya no trae subtítulos)
# sox: evita avisos de manim-voiceover · uv: instala Python y las librerías del motor
titulo "3/5 · Programas del sistema (cairo, FFmpeg completo, uv…)"
for paquete in cairo pkg-config ffmpeg-full sox uv; do
  if brew list --formula "$paquete" >/dev/null 2>&1; then
    verde "$paquete ya instalado"
  else
    amarillo "Instalando $paquete…"
    brew install "$paquete" || { rojo "Falló la instalación de $paquete"; exit 1; }
  fi
done

# ── 4. LaTeX (fórmulas) ──────────────────────────────────────────────────────
titulo "4/5 · LaTeX para las fórmulas"
export PATH="/Library/TeX/texbin:$PATH"
if ! command -v latex >/dev/null 2>&1; then
  amarillo "Instalando BasicTeX (LaTeX liviano, ~100 MB). Te pedirá tu contraseña del Mac."
  brew install --cask basictex || { rojo "Falló la instalación de BasicTeX"; exit 1; }
  eval "$(/usr/libexec/path_helper)"
  export PATH="/Library/TeX/texbin:$PATH"
fi
if command -v latex >/dev/null 2>&1; then
  if kpsewhich standalone.cls >/dev/null 2>&1 && kpsewhich preview.sty >/dev/null 2>&1 \
     && command -v dvisvgm >/dev/null 2>&1; then
    verde "LaTeX listo ($(command -v latex))"
  else
    amarillo "Agregando a LaTeX los paquetes que usa Manim (contraseña del Mac)…"
    sudo tlmgr update --self
    sudo tlmgr install standalone preview dvisvgm || { rojo "Falló tlmgr. Prueba de nuevo más tarde."; exit 1; }
    verde "Paquetes LaTeX instalados"
  fi
else
  rojo "No encuentro LaTeX tras instalarlo. Cierra la terminal, ábrela de nuevo y repite este script."
  exit 1
fi

# ── 5. Python + librerías del motor ──────────────────────────────────────────
titulo "5/5 · Python 3.12 y librerías del motor (Manim, voz, Whisper, panel)"
PREFIJO_BREW="$(brew --prefix)"
PKG_CONFIG_PATH="$PREFIJO_BREW/lib/pkgconfig:$PREFIJO_BREW/opt/cairo/lib/pkgconfig:${PKG_CONFIG_PATH}"
export PKG_CONFIG_PATH
if [ ! -x ".venv/bin/python" ]; then
  uv venv --python 3.12 .venv || { rojo "No se pudo crear el entorno de Python"; exit 1; }
fi
# --only-binary av: usar siempre versiones precompiladas de PyAV (compatibles con tu macOS)
if uv pip install --python .venv/bin/python --only-binary av -e ".[whisper]"; then
  verde "Motor instalado con Whisper"
else
  amarillo "Whisper no se pudo instalar en este Mac; instalo el motor sin él (los subtítulos igual funcionan)."
  uv pip install --python .venv/bin/python --only-binary av -e . || {
    rojo "Falló la instalación de las librerías. Copia el mensaje de arriba y pídeme ayuda."; exit 1; }
  verde "Motor instalado (sin Whisper)"
fi
chmod +x "$REPO/tpi"

titulo "Revisión final"
"$REPO/tpi" doctor
estado=$?
echo
if [ $estado -eq 0 ]; then
  "$REPO/tpi" icono >/dev/null 2>&1 && verde "Ícono «Panel Tu Profe Industrial» listo en tu Escritorio"
  verde "¡Listo! Abre el panel de control con doble clic en ese ícono, o con:"
  echo "   ./tpi panel"
  echo "   (o crea un video desde la Terminal: ./tpi crear guiones/ejemplos/fisica_caida_libre.yaml --borrador --abrir)"
else
  amarillo "Casi listo: revisa los puntos marcados con ❌ arriba."
fi
exit $estado
