#!/usr/bin/env bash
# Convierte el report_*.md de una sesión a PDF con plantilla eisvogel.
#
# Uso:
#   ./make_pdf.sh [session_dir]   # default: sesión más reciente
#
# Salida: reporte_<session>.pdf en la carpeta de la sesión.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$HERE/templates/eisvogel.latex"

if [ -n "${1:-}" ]; then
    SDIR="$1"
else
    SDIR=$(ls -dt "$HERE"/sessions/*/ 2>/dev/null | head -1)
    SDIR="${SDIR%/}"
fi
[ -d "$SDIR" ] || { echo "no session dir: $SDIR"; exit 2; }

REPORT_MD=$(ls "$SDIR"/report_*.md 2>/dev/null | head -1 || true)
[ -f "$REPORT_MD" ] || { echo "no report_*.md in $SDIR — corre el notebook primero"; exit 2; }

NAME=$(basename "$SDIR")
# Escape underscores for LaTeX title (they break in math mode otherwise).
NAME_TEX="${NAME//_/\\_}"
PDF="$SDIR/reporte_${NAME}.pdf"

echo "[pdf] $REPORT_MD -> $PDF"
pandoc "$REPORT_MD" \
    --from=markdown+pipe_tables+raw_tex \
    --to=pdf \
    --pdf-engine=xelatex \
    --template="$TEMPLATE" \
    --resource-path="$SDIR" \
    --variable title:"Reporte de sesión — $NAME_TEX" \
    --variable subtitle:"Tesis CEC-EPN · harness de métricas" \
    --variable author:"Jean Poll Cardoso Chiriboga" \
    --variable date:"$(date '+%Y-%m-%d')" \
    --variable titlepage:true \
    --variable titlepage-color:"097479" \
    --variable titlepage-text-color:"FFFFFF" \
    --variable titlepage-rule-color:"FFFFFF" \
    --variable book:false \
    --variable toc:true \
    --variable toc-own-page:true \
    --variable lang:"es" \
    --variable mainfont:"DejaVu Serif" \
    --variable sansfont:"DejaVu Sans" \
    --variable monofont:"DejaVu Sans Mono" \
    --variable colorlinks:true \
    --output "$PDF"

echo "[pdf] OK -> $PDF ($(du -h "$PDF" | cut -f1))"
