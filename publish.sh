#!/usr/bin/env bash
# Genera la web desde una carpeta de datos y la cifra con contraseña (StatiCrypt, AES-256).
# Uso: STATICRYPT_PASSWORD='...' bash publish.sh <carpeta_datos>
# Los datos nunca se guardan en el repositorio: solo index.html cifrado.
set -euo pipefail
DATA="${1:?carpeta de datos}"
: "${STATICRYPT_PASSWORD:?falta STATICRYPT_PASSWORD}"
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
python3 -I "$HERE/build_site.py" "$DATA" "$TMP"
npx --yes staticrypt@3.5.4 "$TMP/index.html" -p "$STATICRYPT_PASSWORD" --short --remember 30 \
  --salt c638070ce5ca880e8485b0ff97fcde8c --config false -d "$TMP/enc" \
  --template-title "Monitor de liquidez y mercados" \
  --template-instructions "Introduce la contraseña para ver el monitor." \
  --template-button "Entrar" --template-placeholder "Contraseña" \
  --template-remember "Recordarme 30 días" --template-error "Contraseña incorrecta" \
  --template-toggle-show "Mostrar contraseña" --template-toggle-hide "Ocultar contraseña" \
  --template-color-primary "#2f6fb0" --template-color-secondary "#0b1119" >/dev/null
cp "$TMP/enc/index.html" "$HERE/index.html"
rm -rf "$TMP"
echo "index.html cifrado: $(wc -c < "$HERE/index.html") bytes"
