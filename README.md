# Monitor de liquidez y mercados

Web privada protegida con contraseña: https://jorgehg99.github.io/Monitor-liquidez/

- `index.html` está cifrado (StatiCrypt, AES-256); sin la contraseña no se puede leer.
- `datos.enc` es una copia cifrada (AES-256, PBKDF2) de los datos de la web, con la misma contraseña. La usa GitHub Actions para reconstruir la página.
- `publish.sh` genera la página con `build_site.py` a partir de una carpeta de datos externa, la cifra y actualiza `datos.enc`.
- `fetch_market.py` (GitHub Actions, `.github/workflows/datos.yml`) descarga datos públicos de NY Fed, BCE y FRED en `mercado/auto.json`. `build_site.py` los fusiona cuando son más recientes y `actualiza_web.sh` vuelve a publicar la web.
- Secretos del repositorio: `STATICRYPT_PASSWORD` (contraseña de la web) y `FRED_API_KEY` (clave gratuita de FRED).
- `limpieza.yml` deja el repositorio con un solo commit el día 1 de cada mes para que no crezca sin límite.
- Claude actualiza noticias, análisis y el resto de datos los días laborables a las 8:20, 11:20, 15:20, 18:20 y 22:20 (Madrid).
- Control de calidad: `build_site.py --validate` (bloquea la publicación), `--check` (indicadores atrasados), `--alerts` (alertas por umbral de `instrucciones/umbrales.json`), `--nota` (cifras de la nota calculadas con los datos) y `--serie` (histórico diario de un indicador). La página muestra Pulso → «Calidad y cambios».
- `historico_diario.json`, `cambios.json` y `alertas_estado.json` viven solo dentro de `datos.enc`; `build_site.py` los recupera si tiene `STATICRYPT_PASSWORD`.
- Alertas por correo desde GitHub Actions (opcional): secretos `ALERT_EMAIL` (cuenta de Gmail) y `GMAIL_APP_PASSWORD` (contraseña de aplicación). Sin ellos, las alertas llegan solo con las actualizaciones de Claude.
