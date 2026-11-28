---
name: radar-geografias-liquidez
description: Guía por país para cubrir España, Portugal, Francia y Países Bajos en el Monitor de liquidez desde la óptica de cash management corporativo. Incluye fuentes primarias, prensa local, búsquedas en el idioma de cada país, temas de caja propios de cada mercado, calendario recurrente y rotación de las empresas del IBEX 35, PSI, CAC 40 y AEX. Úsala al rellenar la pestaña Europa (noticias_regionales, notas_bc y empresas) y siempre que haya que dar soporte a una de esas geografías.
---

# Radar de geografías para la mesa de liquidez

El objetivo es que el analista pueda apoyar a los equipos de cada país con lo que mueve la caja de sus empresas y la competencia por sus depósitos. Cada país se cubre con sus propias fuentes y en su idioma; la prensa internacional llega tarde y sin detalle local. Combínala con la skill noticias-cash-management, que fija el filtro, la puntuación y la redacción.

## 1. Rutina por país en cada actualización completa

1. **Fuentes oficiales** (tabla del país): notas de prensa de hoy y de ayer.
2. **Empresas**: búsquedas agrupadas por sector en el idioma local sobre las empresas de empresas.json de ese país, empezando por las que tienen la `date` más antigua.
3. **Bancos**: ofertas de cuentas y depósitos, resultados, ratings y sanciones de los bancos locales.
4. **Soberano y fiscal**: subastas, presupuesto, ratings y calendario fiscal.
5. **Cierre**: 5–8 noticias por país con al menos una de Banco o Regulador y una de Empresa; notas_bc con las publicaciones oficiales nuevas; empresas.json solo con información nueva y fechada.

Si un país no tiene noticias de hoy que pasen el filtro, usa las de los 2–3 días anteriores y no rellenes con noticias flojas.

## 2. España

**Oficiales**: Banco de España (notas de prensa, estadísticas de tipos MIR en be1903/be1905/be1907, datos de depósitos, Informe de Estabilidad Financiera) · Tesoro Público (calendario y resultados de Letras y Bonos) · CNMV (información privilegiada y otra información relevante: dividendos, emisiones, OPA) · INE (IPC adelantado y definitivo) · AEAT (calendario del contribuyente) · BOE (sanciones del Banco de España, decretos fiscales).
**Prensa**: Expansión, Cinco Días, El Economista, Europa Press, Bolsamanía, Invertia, Rankia/HelpMyCash para ofertas de depósito.
**Búsquedas**: «dividendo a cuenta fecha de pago», «coloca bonos millones demanda», «préstamo sindicado», «OPA en efectivo», «CNMV información privilegiada», «cuenta remunerada TAE empresas», «depósito a plazo tipo».
**Temas de caja propios**:
- Impuesto a la banca y su efecto en la capacidad de pagar el depósito.
- Letras del Tesoro como alternativa directa al depósito de empresas: compara el marginal con el Euríbor y con el depósito nuevo de empresas (dep_rate_nfc_es).
- Calendario fiscal de grandes empresas: pagos fraccionados del Impuesto sobre Sociedades (modelo 202, del 1 al 20 de abril, octubre y diciembre) e IVA. Comprueba las fechas exactas en el calendario de la AEAT de ese año.
- Pagas extra de junio y diciembre: salida de nóminas para empresas con mucha plantilla.
- Temporadas de dividendo: a cuenta entre diciembre y febrero y complementario entre junio y julio en muchas compañías del IBEX. Toma siempre la fecha de la CNMV o de la empresa.
- Competencia entre los grandes bancos (Santander, BBVA, CaixaBank, Sabadell, Bankinter, Unicaja) y entrantes digitales.

## 3. Portugal

**Oficiales**: Banco de Portugal (notas de prensa; BPstat, series 12533748 de préstamos nuevos a empresas y 12519736 de depósitos nuevos) · IGCP (Bilhetes do Tesouro, OT, Certificados de Aforro y del Tesoro) · CMVM (información privilegiada) · INE Portugal · Portal das Finanças (calendario fiscal; comprueba las fechas de los pagamentos por conta del IRC).
**Prensa**: ECO (eco.sapo.pt), Jornal de Negócios, Expresso, Público, Lusa vía Notícias ao Minuto, Dinheiro Vivo.
**Búsquedas**: «pagamento de dividendos data», «emissão de obrigações milhões», «empréstimo sindicado», «rating banco Moody's Fitch», «depósitos a prazo taxa», «Certificados de Aforro subscrições».
**Temas de caja propios**:
- Los Certificados de Aforro y del Tesoro compiten con el depósito de los hogares, y su tipo arrastra al resto del pasivo.
- Ratings del soberano y de CGD, BCP, Santander Totta, BPI y Novo Banco: una subida amplía las contrapartes elegibles para tesoreros con límites mínimos.
- El depósito nuevo portugués (dep_rate_pt) está muy por debajo del Euríbor: es una oportunidad de cash pooling ibérico para filiales de grupos españoles.
- Empresas clave del PSI: EDP, EDP Renováveis, Galp, Jerónimo Martins, BCP, NOS, Navigator, REN, Sonae, Mota-Engil.

## 4. Francia

**Oficiales**: Banque de France (estadísticas de depósitos y préstamos, ahorro regulado) · ACPR (supervisión, sanciones) · AFT (subastas semanales de BTF los lunes y de OAT) · AMF (información regulada) · INSEE · Assemblée nationale, Sénat y Public Sénat (presupuesto PLF y PLFSS) · agencias de rating sobre Francia, sus bancos y entidades públicas (CDC, AFL, SFIL, Bpifrance, EDF).
**Prensa**: Les Echos, L'Agefi, Boursorama, Le Figaro Économie, Zonebourse, Idéal Investisseur, La Tribune.
**Búsquedas**: «acompte sur dividende date de paiement», «émission obligataire milliards», «crédit syndiqué», «rachat d'actions programme», «note souveraine S&P Fitch Moody's», «Livret A collecte», «dépôts à terme entreprises taux».
**Temas de caja propios**:
- Riesgo de rating soberano y su contagio a bancos (BNP Paribas, Crédit Agricole, Société Générale, BPCE, Crédit Mutuel, La Banque Postale) y entidades públicas: es el principal motivo para que un tesorero mueva caja.
- Ahorro regulado (Livret A, LDDS) y sus flujos mensuales: es la competencia del depósito de hogares y fija la financiación de la CDC.
- Pagos a cuenta del Impuesto sobre Sociedades (acomptes de IS) del 15 de marzo, junio, septiembre y diciembre.
- Bloqueos presupuestarios: retrasos de pagos públicos a proveedores (sanidad, defensa, obra pública).

## 5. Países Bajos

**Oficiales**: DNB (estabilidad financiera, supervisión, fondos de pensiones, estadísticas) · DSTA (calendario trimestral de DSL y DTC) · AFM · CBS (IPC, PIB, paro) · agencias de rating sobre ING, ABN AMRO, Rabobank y de Volksbank.
**Prensa**: Het Financieele Dagblad (FD), NOS, banken.nl, IEX, BNR, BP Nieuws, NRC.
**Búsquedas**: «dividend uitkering betaaldatum», «obligatie-uitgifte miljard», «inkoopprogramma aandelen», «spaarrente zakelijk», «DNB toezicht bank», «pensioenfonds overstap nieuw stelsel».
**Temas de caja propios**:
- Transición de los fondos de pensiones al nuevo sistema (Wtp): las fechas de paso de los grandes fondos mueven mucha liquidez y coberturas.
- Muchos grupos multinacionales tienen en Países Bajos su centro de tesorería o banco interno: es el país natural de las cabeceras de cash pooling.
- Competencia de ING, ABN AMRO y Rabobank por el depósito de empresas: cuentas con preaviso y capital liberado.
- Empresas del AEX con grandes flujos: Shell, ASML, Prosus, Ahold Delhaize, Heineken, Philips, AkzoNobel, Wolters Kluwer, Adyen.

## 6. Rotación de empresas (empresas.json)

- En cada actualización completa, toma las 30 empresas con la `date` más antigua y búscalas en bloques de 4–6 por país y sector. En tres actualizaciones quedan cubiertas todas.
- Actualiza una empresa solo con información nueva y fechada: resultados con caja o deuda neta, dividendos con importe y fecha, emisiones, préstamos, M&A, ratings, guías, huelgas o incidentes que afecten a los cobros.
- `signal`: pos (más caja o liquidez más fuerte), neg (necesidad de caja, estrés o rebaja), vig (merece seguimiento). Una neg nueva dispara la alerta del monitor.
- `next_event`: siempre con fecha «YYYY-MM-DD: …» tomada de la empresa, la CNMV, la AMF, la AFM o la CMVM.
- Una vez por semana, comprueba la composición de los índices (BME para el IBEX 35 y Euronext para el CAC 40, el PSI y el AEX) y añade o quita miembros.

## 7. Soporte a la geografía: qué preguntas deben quedar respondidas

Para cada país, la pestaña Europa debe permitir contestar en un minuto:

1. ¿Qué empresas del país tienen flujos de caja fechados en las próximas cuatro semanas (dividendos, emisiones, pagos de compras, impuestos)?
2. ¿Qué bancos del país han cambiado su rating, su oferta de depósito o su comentario sobre depósitos de empresas?
3. ¿Cómo está el depósito nuevo de empresas del país frente al Euríbor, a las Letras o BT y a los otros tres países (dato para cash pooling)?
4. ¿Hay algún riesgo soberano, fiscal o político con fecha que pueda hacer que los tesoreros cambien de banco o acorten plazos?
5. ¿Qué publicó hoy el banco central, el Tesoro o el supervisor?

Si alguna pregunta queda sin respuesta por falta de noticias, dilo en «No actualizado» del mensaje final en lugar de rellenar.
