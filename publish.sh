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
# Control de calidad: si hay datos rotos (fechas futuras, valores no numéricos…) no se publica
if ! python3 -I "$HERE/build_site.py" --validate "$DATA" > "$TMP/validacion.json"; then
  echo "ERROR: control de calidad no superado; no se publica. Detalle:"; cat "$TMP/validacion.json"; rm -rf "$TMP"; exit 2
fi
python3 -I -c "import json,sys;w=json.load(open(sys.argv[1]))['avisos'];[print('AVISO:',x) for x in w]" "$TMP/validacion.json"
MLV_BUILD="$BUILD" python3 -I "$HERE/build_site.py" "$DATA" "$TMP"
# Comprime la página antes de cifrar (lo cifrado ya no se puede comprimir): ~4 veces menos que descargar
python3 -I - "$TMP/index.html" <<'PY2'
import sys, gzip, base64
p = sys.argv[1]
raw = open(p, "rb").read()
b64 = base64.b64encode(gzip.compress(raw, 9)).decode()
loader = ("<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
          "<title>Monitor de liquidez y mercados</title><style>body{background:#0b1119;color:#dbe4ee;font:15px system-ui;margin:0;padding:40px 16px;text-align:center}</style></head>"
          "<body><p id=\"mlv-l\">Cargando el monitor…</p><script>(function(){var b=\"" + b64 + "\";"
          "function fail(){document.getElementById('mlv-l').textContent='Tu navegador es demasiado antiguo para abrir el monitor. Actualiza Safari o Chrome.';}"
          "if(!window.DecompressionStream){fail();return;}"
          "try{var bin=atob(b),u=new Uint8Array(bin.length);for(var i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);"
          "new Response(new Blob([u]).stream().pipeThrough(new DecompressionStream('gzip'))).text().then(function(h){document.open();document.write(h);document.close();}).catch(fail);}catch(e){fail();}})();</script></body></html>")
open(p, "w", encoding="utf-8").write(loader)
print(f"página: {len(raw) // 1024} KB → comprimida {len(loader) // 1024} KB")
PY2
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
        '<meta http-equiv="Cache-Control" content="no-cache"><link rel="manifest" href="manifest.webmanifest">'
        '<script>if("serviceWorker" in navigator)window.addEventListener("load",function(){navigator.serviceWorker.register("sw.js").catch(function(){})});</script>')
h = h.replace("<head>", "<head>" + tags, 1)
open(dst, "w", encoding="utf-8").write(h)
PY
rm -rf "$TMP"
# Copia cifrada de los datos (mismo cifrado fuerte que la web) para que GitHub Actions pueda
# reconstruir la página con datos de mercado nuevos sin intervención de Claude.
(cd "$DATA" && ls *.json >/dev/null 2>&1) && \
  tar -C "$DATA" -czf - $(cd "$DATA" && ls *.json) | \
  openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:STATICRYPT_PASSWORD -out "$HERE/datos.enc" && \
  git -C "$HERE" add datos.enc 2>/dev/null || true
echo "index.html cifrado: $(wc -c < "$HERE/index.html") bytes"
