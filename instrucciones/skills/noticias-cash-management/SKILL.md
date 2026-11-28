---
name: noticias-cash-management
description: Selecciona, filtra y redacta las noticias del Monitor de liquidez (Top 10, noticias por país, eventos de caja, notas de bancos centrales) para una mesa de liquidez corporativa de GTB (cuentas operativas, depósitos, preaviso, cash pooling, LCR/NSFR). Úsala en cada actualización del monitor antes de escribir noticias.json, noticias_regionales.json, eventos_caja.json o notas_bc.json, y siempre que haya que decidir si una noticia sirve para cash management.
---

# Noticias que sirven a una mesa de cash management

El lector es un analista de la mesa de liquidez de GTB de un gran banco español. Su trabajo es captar, remunerar y retener la caja de empresas: cuentas operativas y remuneradas, depósitos a plazo, cuentas con preaviso, cash pooling y previsión de liquidez con los tesoreros, con la vista puesta en el valor LCR/NSFR de cada depósito. No opera repo, bonos ni derivados.

Una noticia solo entra si responde a esta pregunta: **¿cambia dónde, en qué moneda, durante cuánto tiempo o a qué precio mantiene una empresa su caja, o cómo compiten los bancos por ella?** Si la respuesta es «no» o «indirectamente», no entra, aunque sea un titular importante.

## 1. Filtro de entrada (las cuatro puertas)

Una noticia pasa si cumple al menos una puerta y tiene fecha y fuente verificables:

1. **Flujo de caja corporativo con importe o fecha**: dividendo (importe y fecha de pago), recompra, emisión de bonos o préstamo (importe), cobro por venta de activos o M&A, pago de una compra, capex extraordinario, vencimiento de deuda, pago de impuestos, multa, resultados con caja, deuda neta o flujo de caja libre.
2. **Precio del dinero para la caja**: decisiones y señales de BCE, Fed, BoE; €STR, Euríbor, SOFR, SONIA; subastas de Letras, BTF, BT, DTC; datos MIR y de depósitos de bancos centrales; fondos monetarios (rentabilidad, flujos).
3. **Contraparte y competencia por el depósito**: ratings de soberanos, bancos y entidades públicas; ofertas de depósito o cuentas de competidores; resultados de bancos con depósitos, beta, coste del pasivo, LCR/NSFR; supervisión y sanciones a bancos; incidentes operativos o de pagos.
4. **Regla o shock que mueve la caja**: LCR/NSFR y tratamiento de depósitos operativos, reservas mínimas, garantía de depósitos, pagos instantáneos, euro digital, stablecoins; presupuestos y crisis fiscales; shocks de energía o materias primas con efecto en el circulante; huelgas o apagones que retrasan cobros.

**Fuera siempre**: movimientos de bolsa sin flujo de caja, precios objetivo de analistas, rumores sin fuente, opinión, noticias de producto o marketing, operaciones de trading, repo, haircuts o posiciones en bonos, y cualquier dato interno o confidencial del banco.

## 2. Puntuación para ordenar (0–20)

Puntúa cada candidata y ordena por total; desempata con preferencias.json.

| Criterio | 0 | 2 | 4 |
|---|---|---|---|
| Impacto en caja | sin importe | importe o fecha | importe y fecha, > 500 M€ |
| Cliente típico | otra empresa | gran empresa europea, de EE. UU., del Reino Unido o de Latam | IBEX 35, CAC 40, PSI, AEX, Euro Stoxx 50 o los grupos no cotizados de empresas.json |
| Geografía | otra | zona euro, Reino Unido o EE. UU. | España, Portugal, Francia o Países Bajos |
| Acción posible | ninguna | vigilar | acción concreta con producto y fecha |
| Novedad y fuente | más de 3 días o fuente secundaria | 1–3 días | hoy, con fuente primaria (nota de prensa, regulador, agencia de rating, CNMV/AMF/AFM/CMVM) |

- Top 10: las 10 de mayor puntuación de cualquier geografía, con al menos 6 que toquen España, Portugal, Francia o Países Bajos.
- Por país: 5–8 noticias con 12 o más puntos; si un día no las hay, completa con las de 2–3 días antes y no rellenes con noticias de baja puntuación.

## 3. Plan de búsqueda en cada actualización

Busca por capas, en este orden, y anota qué capa cubrió cada noticia:

1. **Fuentes primarias** (radar-geografias-liquidez enumera las de cada país): notas de prensa de BCE, Banco de España, Banco de Portugal, Banque de France/ACPR, DNB; Tesoros (Tesoro Público, IGCP, AFT, DSTA); CNMV (información privilegiada y otra información relevante), AMF, AFM, CMVM; agencias de rating.
2. **Empresas del radar**: agrupa las búsquedas por país y sector («dividendo», «emisión», «préstamo», «adquisición», «rating», «resultados» y «caja» en el idioma local). Prioriza las de empresas.json con `date` más antigua, para rotar la cobertura.
3. **Bancos competidores**: ofertas de cuentas y depósitos, comentarios de la dirección sobre depósitos de empresas, resultados.
4. **Macro con efecto en la caja**: inflación, presupuestos, energía.

Consultas útiles: «dividendo a cuenta fecha de pago», «coloca bonos millones», «préstamo sindicado», «OPA en efectivo», «pagamento de dividendos», «emissão obrigações», «acompte sur dividende», «émission obligataire», «rachat d'actions», «uitkering dividend», «obligatie-uitgifte», «inkoopprogramma».

## 4. Una noticia, un sitio (sin duplicados)

Antes de escribir, construye una lista con el hecho clave de cada candidata (entidad + hecho + fecha) y asígnalo a una sola pestaña:

- **Top 10**: lo más importante del día y lo transversal (bancos centrales, soberanos, grandes eventos de caja).
- **Noticias por país**: el detalle local que no está en el Top 10. Solo repite una noticia del Top 10 si es imprescindible para el país; en ese caso aporta un ángulo distinto (otra cifra, la implicación local).
- **eventos_caja**: el flujo cuantificado (importe, dirección, fecha), en una frase. Puede coexistir con una noticia, pero el texto no se copia.
- **notas_bc**: solo publicaciones oficiales de bancos centrales, Tesoros, supervisores y agencias de rating, en una frase con su dato.

Si dos fuentes cuentan lo mismo, queda una sola entrada con la fuente más primaria. Al reemplazar el Top 10 de un día anterior, no vuelvas a meter una noticia ya publicada salvo que haya un dato nuevo, y en ese caso el titular empieza por ese dato nuevo.

## 5. Redacción

- **headline**: el hecho y su cifra clave, en menos de 110 caracteres. Correcto: «Iberdrola coloca 1.500 M€ en bonos verdes a 8 años con una demanda de 4.200 M€». Incorrecto: «Iberdrola refuerza su financiación».
- **summary**: 3–4 frases propias con quién, qué, cuánto, cuándo, y el contexto necesario para entenderlo sin abrir la fuente.
- **implication**: 1–2 frases que digan qué cambia para la caja: ¿hay excedente temporal hasta una fecha de pago?, ¿necesidad de caja?, ¿moneda?, ¿plazo?, ¿presión de precio?, ¿riesgo de contraparte?, ¿valor LCR del depósito?
- **action**: 1–2 frases con verbo, producto, destinatario y fecha. Correcto: «Proponer a la tesorería un depósito con vencimiento el 3-dic, un día antes del pago del dividendo, y mantener el saldo operativo en la cuenta pagadora». Incorrecto: «Seguir la evolución».
- Las acciones solo usan los productos de la mesa: cuenta operativa o remunerada (por ejemplo, referida al €STR), depósito a plazo, cuenta con preaviso, cash pooling físico o nocional, previsión de liquidez con el cliente, pricing frente a competidores y con ALM/precios de transferencia, captación de depósito operativo (LCR) y diversificación de contrapartidas del tesorero. Nunca repo, colateral, bonos, trading ni recomendaciones de compra o venta.
- Nunca afirmes que una empresa es o no es cliente.
- Cifras en formato español (1.500 M€, 2,45 %), fechas como «4-dic», como mucho una cita de menos de 15 palabras por fuente, y la URL real del artículo.

## 6. Tabla de implicaciones típicas

| Hecho | Implicación de caja | Acción tipo |
|---|---|---|
| Dividendo o recompra con fecha | excedente que se acumula y sale ese día | depósito con vencimiento justo antes del pago |
| Emisión de bonos o préstamo | entrada de caja antes del uso previsto | escalonar plazos hasta el uso; cuenta con preaviso |
| Cobro de una venta de activos o M&A | excedente grande y temporal | plazo corto y propuesta de cash pooling |
| Pago de una compra o vencimiento | necesidad de caja en una fecha | previsión de liquidez; asegurar el saldo operativo |
| Rebaja de un banco o soberano | límites de rating del tesorero | mapa de clientes afectados; diversificación |
| Oferta de depósito de un competidor | presión de precio | comparar tarifa; precio con ALM |
| Subida de tipos descontada | el cliente acorta plazos o pide más | plazo de 1–3 meses que cruce la reunión; €STR + margen |
| Energía al alza | más circulante en sectores intensivos | contactar a utilities, transporte y química |
| Regla de LCR, NSFR o reservas | cambia el valor del depósito | priorizar el depósito operativo y el preaviso de más de 30 días |

## 7. Control antes de guardar

- [ ] Cada noticia pasa una de las cuatro puertas y tiene 12 o más puntos (o está en el Top 10 por importancia evidente).
- [ ] Ningún hecho aparece dos veces entre el Top 10, las noticias por país, eventos_caja y notas_bc sin un ángulo distinto.
- [ ] Toda cifra está en la fuente enlazada y toda fecha es de este año.
- [ ] Cada acción nombra un producto de la mesa y una fecha o un disparador.
- [ ] España, Portugal, Francia y Países Bajos tienen 5–8 noticias cada uno, con al menos una de Banco o Regulador y una de Empresa.
- [ ] Ninguna noticia trata de trading o repo ni dice si una empresa es cliente.
