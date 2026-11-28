#!/usr/bin/env python3
"""Envía por correo (Gmail) las alertas nuevas que calcula `build_site.py --alerts`.

Uso: python3 alerta_correo.py <salida_de_--alerts.json>
Secretos de GitHub: ALERT_EMAIL (la cuenta de Gmail que envía y recibe) y GMAIL_APP_PASSWORD
(contraseña de aplicación de Google). Sale con 0 si no hay nada que enviar o si se ha enviado.
No escribe datos en la salida: los registros de GitHub Actions son públicos.
"""
import json, os, sys, smtplib, ssl
from email.message import EmailMessage

data = json.load(open(sys.argv[1], encoding="utf-8"))
new = data.get("nuevas") or []
if not new:
    print("Alertas: ninguna nueva")
    sys.exit(0)
to = os.environ["ALERT_EMAIL"]
alta = [a for a in new if a.get("nivel") == "alta"]
first = (alta or new)[0]["texto"]
msg = EmailMessage()
msg["Subject"] = f"ALERTA monitor de liquidez: {first[:110]}"
msg["From"] = to
msg["To"] = to
body = [f"Alertas por umbral del {data.get('now_madrid', '')} (hora de Madrid):", ""]
body += [f"- [{a.get('nivel', '').upper()}] {a['texto']}" for a in new]
body += ["", "Detalle y registro de cambios: https://jorgehg99.github.io/Monitor-liquidez/#pulso/calidad",
         "Umbrales: instrucciones/umbrales.json del repositorio."]
msg.set_content("\n".join(body))
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as s:
    s.login(to, os.environ["GMAIL_APP_PASSWORD"])
    s.send_message(msg)
print(f"Alertas: correo enviado ({len(new)})")
