#!/usr/bin/env bash
# Genera la web desde una carpeta de datos y la cifra con contraseña (StatiCrypt, AES-256).
# Uso: STATICRYPT_PASSWORD='...' bash publish.sh <carpeta_datos>
# Los datos nunca se guardan en el repositorio: solo index.html cifrado.
set -euo pipefail
DATA="${1:?carpeta de datos}"
: "${STATICRYPT_PASSWORD:?falta STATICRYPT_PASSWORD}"
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
BUILD="$(TZ=Europe/Madrid date +%Y%m%d%H%M%S)"
MLV_BUILD="$BUILD" python3 -I "$HERE/build_site.py" "$DATA" "$TMP"
npx --yes staticrypt@3.5.4 "$TMP/index.html" -p "$STATICRYPT_PASSWORD" --short --remember 30 \
  --salt c638070ce5ca880e8485b0ff97fcde8c --config false -d "$TMP/enc" \
  --template-title "Monitor de liquidez y mercados by R‑ro" \
  --template-instructions "Introduce la contraseña para ver el monitor." \
  --template-button "Entrar" --template-placeholder "Contraseña" \
  --template-remember "Recordarme 30 días" --template-error "Contraseña incorrecta" \
  --template-toggle-show "Mostrar contraseña" --template-toggle-hide "Ocultar contraseña" \
  --template-color-primary "#2f6fb0" --template-color-secondary "#0b1119" >/dev/null
python3 -I - "$TMP/enc/index.html" "$HERE/index.html" "$BUILD" <<'PY'
import sys
src, dst, build = sys.argv[1], sys.argv[2], sys.argv[3]
h = open(src, encoding="utf-8").read()
tags = ('<link rel="apple-touch-icon" href="apple-touch-icon.png"><link rel="icon" href="apple-touch-icon.png">'
        '<meta name="apple-mobile-web-app-title" content="Monitor"><meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="theme-color" content="#0b1119"><meta name="mlv-build" content="' + build + '">'
        '<meta http-equiv="Cache-Control" content="no-cache">')
h = h.replace("<head>", "<head>" + tags, 1)
open(dst, "w", encoding="utf-8").write(h)
PY
rm -rf "$TMP"
echo "index.html cifrado: $(wc -c < "$HERE/index.html") bytes"
