#!/usr/bin/env bash
# GitHub Actions: reconstruye la web cuando fetch_market.py ha traído datos nuevos.
# Necesita el secreto STATICRYPT_PASSWORD (la misma contraseña de la web).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
if [ -z "${STATICRYPT_PASSWORD:-}" ]; then echo "Sin STATICRYPT_PASSWORD: solo se guardan los datos"; exit 0; fi
if [ ! -f datos.enc ]; then echo "Aún no hay datos.enc: la próxima actualización de Claude lo crea"; exit 0; fi
if git ls-files --error-unmatch mercado/auto.json >/dev/null 2>&1 && git diff --quiet -- mercado/auto.json; then
  echo "Sin datos nuevos: no se reconstruye la web"; exit 0
fi
D="$(mktemp -d)"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:STATICRYPT_PASSWORD -in datos.enc | tar -C "$D" -xzf -
bash publish.sh "$D"
rm -rf "$D"
