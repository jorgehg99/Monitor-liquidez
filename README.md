# Monitor de liquidez y mercados

Web privada protegida con contraseña: https://jorgehg99.github.io/Monitor-liquidez/

- `index.html` está cifrado (StatiCrypt, AES-256); sin la contraseña no se puede leer.
- `publish.sh` genera la página con `build_site.py` a partir de una carpeta de datos externa y la cifra. Los datos no se guardan en el repositorio.
- Se actualiza los días laborables a las 7:45, 12:58 y 17:45 (Madrid).
