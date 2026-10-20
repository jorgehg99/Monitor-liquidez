#!/usr/bin/env python3
"""Genera la web estática del Monitor de liquidez y mercados (index.html) a partir de los JSON de datos.

Uso: python3 build_site.py <carpeta_datos> <carpeta_salida> [url_publica]
La carpeta de datos contiene: ultimo.json, historico.json, eventos.json, probabilidades.json,
noticias.json, noticias_meta.json y, si existen, noticias_regionales.json y notas_bc.json.
Todo se dibuja en el servidor (SVG en línea) y se despliega con <details>: funciona sin JavaScript.
"""
import json, sys, html, pathlib, datetime, math

DATA = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data")
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "out")
OUT.mkdir(parents=True, exist_ok=True)

def load(name, default):
    p = DATA / name
    try:
        return json.loads(p.read_text())
    except Exception:
        return default

U = load("ultimo.json", [])
H = load("historico.json", [])
EV = load("eventos.json", [])
PR = load("probabilidades.json", [])
NEWS = load("noticias.json", [])
NMETA = (load("noticias_meta.json", [{}]) or [{}])[0]
RNEWS = load("noticias_regionales.json", [])
BNOTES = load("notas_bc.json", [])

BY = {r["id"]: r for r in U}
HIST = {}
for h in H:
    if h.get("value") is None:
        continue
    HIST.setdefault(h["id"], {})[str(h["month"])] = (float(h["value"]), str(h.get("date") or h["month"]))

MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
PAL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
UP, DOWN, FLAT = "#3ddc97", "#ff7a7a", "#8798ad"

esc = lambda s: html.escape(str(s if s is not None else ""), quote=True)

def num(x):
    try:
        return None if x is None or x == "" else float(x)
    except (TypeError, ValueError):
        return None

def fnum(v, d=2):
    if v is None:
        return "—"
    s = f"{abs(v):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if v < 0 else "") + s

def fdate(s):
    s = str(s or "")
    try:
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return f"{int(s[8:10])} {MES[int(s[5:7]) - 1]} {s[:4]}"
        if len(s) == 7 and s[4] == "-":
            return f"{MES[int(s[5:7]) - 1]} {s[:4]}"
    except (ValueError, IndexError):
        pass
    return s

def back(m, k):
    y, mo = map(int, m.split("-"))
    t = y * 12 + mo - 1 - k
    return f"{t // 12}-{t % 12 + 1:02d}"

def kind(r):
    u = r.get("unit")
    return "pb" if u in ("%", "pb") else ("pp" if u == "% a/a" or str(u).startswith("% de") else "pct")

def diff(a, b, u):
    if a is None or b is None:
        return None
    if u == "%":
        return round((a - b) * 100, 1)
    if u == "pb":
        return round(a - b, 1)
    if u == "% a/a" or str(u).startswith("% de"):
        return round(a - b, 2)
    return None if b == 0 else round((a / b - 1) * 100, 2)

def fchg(c, k):
    if c is None:
        return "—"
    s = "+" if c > 0 else ("−" if c < 0 else "±")
    if k == "pb":
        return f"{s}{fnum(abs(c), 1)} pb"
    if k == "pp":
        return f"{s}{fnum(abs(c), 2)} pp"
    return f"{s}{fnum(abs(c), 2)} %"

def ccls(c):
    return "flat" if not c else ("up" if c > 0 else "down")

def series(i, months=36):
    s = HIST.get(i, {})
    ks = sorted(s)
    if not ks:
        return []
    ks = ks[-(months + 1):]
    return [(k, s[k][0], s[k][1]) for k in ks]

def stats(r):
    v = num(r.get("value"))
    m = str(r.get("date", ""))[:7]
    s = {k: x for k, (x, _) in HIST.get(r["id"], {}).items()}
    u = r.get("unit")
    out = {"d1": diff(v, num(r.get("prev_value")), u), "kind": kind(r)}
    if len(m) == 7 and m[4] == "-":
        out["m1"] = diff(v, s.get(back(m, 1)), u)
        out["y1"] = diff(v, s.get(back(m, 12)), u)
        vals = [x for k, x in s.items() if k >= back(m, 36)]
        out["hi"] = max(vals) if vals else None
        out["lo"] = min(vals) if vals else None
    return out

# ------------------------------------------------------------------ SVG
def nice_ticks(lo, hi, n=5):
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=raw)
    a = math.floor(lo / step) * step
    b = math.ceil(hi / step) * step
    ticks, t = [], a
    while t <= b + step / 2:
        ticks.append(round(t, 10))
        t += step
    return ticks

def line_svg(sers, w=720, h=240, dec=2, unit="", spark=False, step=False, end_labels=None):
    """sers: list of (name, color, [(month, value, date)])"""
    sers = [s for s in sers if s[2]]
    if not sers:
        return '<p class="empty">Sin histórico disponible en fuentes abiertas.</p>'
    months = sorted({p[0] for s in sers for p in s[2]})
    idx = {m: i for i, m in enumerate(months)}
    vals = [p[1] for s in sers for p in s[2]]
    lo, hi = min(vals), max(vals)
    if spark:
        L, R, T, B = 2, 4, 4, 4
        ticks = None
        pad = (hi - lo) * 0.08 or 1
        ylo, yhi = lo - pad, hi + pad
    else:
        ticks = nice_ticks(lo, hi)
        ylo, yhi = ticks[0], ticks[-1]
        lab = [fnum(t, min(dec, 2)) for t in ticks]
        L = 10 + max(len(x) for x in lab) * 6.6
        R = 12 if not end_labels else 70
        T, B = 10, 26
    n = max(len(months) - 1, 1)
    X = lambda m: L + (w - L - R) * idx[m] / n
    Y = lambda v: T + (h - T - B) * (1 - (v - ylo) / ((yhi - ylo) or 1))
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" width="100%" role="img" preserveAspectRatio="none" aria-label="{esc(unit)}">' if spark else
           f'<svg class="chart" viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Gráfico {esc(unit)}">']
    if ticks:
        for t, lb in zip(ticks, lab):
            y = Y(t)
            out.append(f'<line x1="{L:.1f}" x2="{w - R:.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="#1c2939"/>')
            out.append(f'<text x="{L - 6:.1f}" y="{y + 3.5:.1f}" text-anchor="end" class="tk">{lb}</text>')
        out.append(f'<line x1="{L:.1f}" x2="{w - R:.1f}" y1="{h - B:.1f}" y2="{h - B:.1f}" stroke="#2e4159"/>')
        stepm = max(1, math.ceil(len(months) / max(2, int((w - L - R) / 70))))
        for i, m in enumerate(months):
            if i % stepm == 0 or i == len(months) - 1 and (len(months) - 1) % stepm > stepm / 2:
                out.append(f'<text x="{X(m):.1f}" y="{h - 8}" text-anchor="middle" class="tk">{MES[int(m[5:7]) - 1]}-{m[2:4]}</text>')
    labels = []
    for name, col, pts in sers:
        d = ""
        prev = None
        for m, v, _ in pts:
            x, y = X(m), Y(v)
            if not d:
                d = f"M{x:.1f},{y:.1f}"
            elif step:
                d += f"H{x:.1f}V{y:.1f}"
            else:
                d += f"L{x:.1f},{y:.1f}"
            prev = (x, y)
        if not spark and len(sers) == 1:
            first = pts[0][0]
            out.append(f'<path d="{d}L{X(pts[-1][0]):.1f},{h - B:.1f}L{X(first):.1f},{h - B:.1f}Z" fill="{col}" fill-opacity=".12"/>')
        out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{1.5 if spark else 2}" stroke-linejoin="round" stroke-linecap="round"/>')
        out.append(f'<circle cx="{prev[0]:.1f}" cy="{prev[1]:.1f}" r="{2.2 if spark else 3.2}" fill="{col}"/>')
        if not spark:
            labels.append([prev[1], name, col, pts[-1][1]])
    if labels and end_labels:
        labels.sort()
        for i in range(1, len(labels)):
            if labels[i][0] - labels[i - 1][0] < 12:
                labels[i][0] = labels[i - 1][0] + 12
        for y, name, col, v in labels:
            out.append(f'<text x="{w - R + 6:.1f}" y="{y + 3.5:.1f}" class="el"><tspan fill="{col}">■</tspan> {esc(name)} {fnum(v, min(dec, 2))}</text>')
    elif labels and not spark:
        y, name, col, v = labels[0]
        out.append(f'<text x="{w - R:.1f}" y="{max(y - 8, 10):.1f}" text-anchor="end" class="el">{fnum(v, dec)}</text>')
    out.append("</svg>")
    return "".join(out)

def legend(items):
    return '<div class="legend">' + "".join(f'<span><i style="background:{c}"></i>{esc(n)}</span>' for n, c in items) + "</div>"

# ------------------------------------------------------------------ cromos
def card(r, extra=""):
    st = stats(r)
    dec = int(r.get("decimals") or 2)
    v = num(r.get("value"))
    d1 = st.get("d1")
    arrow = "" if not d1 else ("▲ " if d1 > 0 else "▼ ")
    sp_col = UP if (d1 or 0) > 0 else (DOWN if (d1 or 0) < 0 else "#7cc4ff")
    sp = line_svg([("", sp_col, series(r["id"]))], w=240, h=34, spark=True, unit=r.get("name"))
    core = ""
    if r.get("core_id") and r["core_id"] in BY and num(BY[r["core_id"]].get("value")) is not None:
        core = f'<div class="sub">Subyacente {fnum(num(BY[r["core_id"]]["value"]), 1)} %</div>'
    infl = r.get("group") in ("infl", "reg") and r.get("unit") == "% a/a"
    lbl_prev = "Mes anterior" if infl else "Dato anterior"
    lbl_d1 = "Δ vs mes anterior" if infl else ("Δ vs día anterior" if len(str(r.get("date") or "")) == 10 else "Δ vs dato anterior")
    sers = [("General" if r.get("core_id") else r.get("name"), PAL[0], series(r["id"]))]
    if r.get("core_id") and r["core_id"] in BY:
        sers.append(("Subyacente", PAL[3], series(r["core_id"])))
    big = line_svg(sers, dec=min(dec, 3), unit=r.get("unit", ""), step=r.get("group") == "policy", end_labels=len(sers) > 1)
    k = st["kind"]
    stat_cells = [
        (lbl_prev + (f' ({fdate(r.get("prev_date"))})' if r.get("prev_date") else ""), fnum(num(r.get("prev_value")), dec), ""),
        (lbl_d1, fchg(d1, k), ccls(d1)),
        ("Δ vs cierre mes anterior", fchg(st.get("m1"), k), ccls(st.get("m1"))),
        ("Δ vs hace 12 meses", fchg(st.get("y1"), k), ccls(st.get("y1"))),
        ("Máximo 3 años", fnum(st.get("hi"), dec), ""),
        ("Mínimo 3 años", fnum(st.get("lo"), dec), ""),
    ]
    stats_html = "".join(f'<div><span>{esc(a)}</span><b class="{c}">{esc(b)}</b></div>' for a, b, c in stat_cells)
    src = esc(r.get("source") or "—")
    if str(r.get("source_url", "")).startswith("https://"):
        src = f'<a href="{esc(r["source_url"])}" target="_blank" rel="noopener">{src}</a>'
    meta = f"<div>Fuente: {src}</div>"
    if r.get("next_event"):
        meta += f'<div>{esc(r["next_event"])}</div>'
    if r.get("note"):
        meta += f'<div>{esc(r["note"])}</div>'
    read = ""
    if r.get("comment"):
        read = f'<div class="read"><h4>Lectura para liquidez y cash management</h4><p>{esc(r["comment"])}</p><small>Análisis generado por Claude con los datos de esta página; no es una recomendación.</small></div>'
    basis = {"monthly-average": "Media mensual", "y/y": "Tasa interanual de cada mes"}.get(r.get("basis"), "Cierre de cada mes")
    return f'''<details class="card" id="c-{esc(r["id"])}"><summary>
<div class="top"><span class="code">{esc(r.get("short") or r["id"])}</span><span class="date">{esc(fdate(r.get("date")))}</span></div>
<div class="name">{esc(r.get("name"))}</div>
<div class="row"><span class="val">{fnum(v, dec)}</span><span class="unit">{esc(r.get("unit"))}</span><span class="chg {ccls(d1)}">{arrow}{fchg(d1, k) if d1 is not None else ""}</span></div>
{core}{extra}<div class="spark">{sp}</div></summary>
<div class="detail"><div class="stats">{stats_html}</div>
<div class="box"><div class="cap">Histórico 3 años · {basis}; el último punto es el dato más reciente.</div>{big}{legend([(s[0], s[1]) for s in sers]) if len(sers) > 1 else ""}</div>
{read}<div class="meta">{meta}</div></div></details>'''

BANKP = {"ecb_dfr": "BCE", "fed_upper": "Fed", "boe_bank_rate": "BoE"}

def probs(r):
    rows = sorted([p for p in PR if p.get("bank") == BANKP.get(r["id"])], key=lambda p: str(p.get("meeting")))[:2]
    if not rows:
        return '<div class="probs"><div class="pl">Probabilidades no disponibles</div></div>'
    out = ['<div class="probs">']
    for p in rows:
        h, ho, c = num(p.get("hike")), num(p.get("hold")), num(p.get("cut"))
        bar = "".join(f'<i style="width:{x * 100:.0f}%;background:{col}"></i>' for x, col in ((c, DOWN), (ho, "#5d6f86"), (h, UP)) if x)
        if ho is None and h is not None:
            txt = f"Subida acumulada {fnum(h * 100, 0)} %"
        else:
            parts = []
            if c:
                parts.append(f"Baja {fnum(c * 100, 0)} %")
            if ho is not None:
                parts.append(f"Mant. {fnum(ho * 100, 0)} %")
            if h is not None:
                parts.append(f"Sube {fnum(h * 100, 0)} %")
            txt = " · ".join(parts)
        out.append(f'<div class="pr"><span>{esc(fdate(p.get("meeting")))}</span><span class="pb">{bar}</span></div><div class="pl">{esc(txt)}</div>')
    out.append("</div>")
    return "".join(out)

def grid(ids, title, sub, anchor, extra=None):
    cards = []
    for i in ids:
        r = BY.get(i)
        if r and num(r.get("value")) is not None:
            cards.append(card(r, extra(r) if extra else ""))
    if not cards:
        return ""
    return f'<section id="{anchor}"><div class="sh"><h2>{esc(title)}</h2><p>{esc(sub)}</p></div><div class="grid">{"".join(cards)}</div></section>'

# ------------------------------------------------------------------ tablas
def table(head, rows, cls=""):
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f'<td class="{c}">{esc(v)}</td>' for v, c in r) + "</tr>" for r in rows)
    if not rows:
        body = f'<tr><td class="na" colspan="{len(head)}">Sin datos en fuentes abiertas</td></tr>'
    return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'

def grp(g):
    return sorted([r for r in U if r.get("group") == g], key=lambda r: float(r.get("order") or 0))

def vcell(r):
    v = num(r.get("value"))
    return (fnum(v, int(r.get("decimals") or 1)) if v is not None else "N/D", "" if v is not None else "na")

def chg_cell(r, key):
    s = stats(r)
    c = s.get(key)
    return (fchg(c, s["kind"]), ccls(c))

def multi(ids, title, sub, anchor, label=lambda r: r.get("country") or r.get("name"), step=False, dec=2):
    sers = []
    for i in ids:
        r = BY.get(i)
        if r and series(i):
            sers.append((label(r), PAL[len(sers) % 8], series(i)))
        if len(sers) == 8:
            break
    if not sers:
        return ""
    svg = line_svg(sers, w=760, h=280, dec=dec, step=step, end_labels=len(sers) <= 8)
    return f'<div class="box" id="{anchor}"><h3>{esc(title)}</h3><p class="cap">{esc(sub)}</p>{svg}{legend([(s[0], s[1]) for s in sers])}</div>'

# ------------------------------------------------------------------ noticias
def news_items(items, show_rank=True):
    out = []
    for n, x in enumerate(items):
        link = ""
        if str(x.get("url", "")).startswith("http"):
            link = f'<a href="{esc(x["url"])}" target="_blank" rel="noopener">{esc(x.get("source") or "Fuente")} ↗</a>'
        rank = f'<div class="rk">{int(x.get("rank") or n + 1):02d}</div>' if show_rank else ""
        out.append(f'''<article class="nw">{rank}<div><div class="nt"><span class="tag">{esc(x.get("sector"))}</span> {esc(x.get("entities") or "")} · {esc(fdate(x.get("published")))}</div>
<h3>{esc(x.get("headline"))}</h3><p>{esc(x.get("summary"))}</p><p class="imp">Implicación: {esc(x.get("implication"))}</p>{link}</div></article>''')
    return "".join(out) or '<p class="empty">Sin noticias seleccionadas.</p>'

def by_sector(items):
    secs = {}
    for x in items:
        secs.setdefault(x.get("sector") or "Otros", []).append(x)
    return secs

# ------------------------------------------------------------------ página
ds = sorted(str(r.get("date")) for r in U if len(str(r.get("date") or "")) == 10)
asof = fdate(ds[-1]) if ds else "—"
built = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2))).strftime("%d/%m/%Y %H:%M")

tape_ids = ["estr", "sofr", "sonia", "euribor_3m", "eurusd", "y10_de", "y10_es", "spread_es_de_10y", "y10_us", "brent", "ttf", "gold"]
tape = []
for i in tape_ids:
    r = BY.get(i)
    if not r or num(r.get("value")) is None:
        continue
    s = stats(r)
    d1 = s.get("d1")
    tape.append(f'<span><b>{esc(r.get("short"))}</b> {fnum(num(r["value"]), min(int(r.get("decimals") or 2), 3))} <em class="{ccls(d1)}">{fchg(d1, s["kind"]) if d1 is not None else ""}</em></span>')

P = []
P.append(grid(["estr", "sofr", "fed_upper", "iorb", "sonia"], "Tipos overnight", "Variación frente al dato anterior. Toca un cromo para ver 3 años de histórico y la lectura de liquidez.", "tipos"))
P.append(grid(["ecb_dfr", "fed_upper", "boe_bank_rate"], "Bancos centrales", "Tipo oficial y probabilidades de mercado para las dos próximas reuniones.", "bc", extra=probs))
P.append(grid(["y10_de", "y10_es", "spread_es_de_10y", "y10_pt", "y10_fr", "spread_fr_de_10y", "y10_it", "spread_it_de_10y", "y10_nl", "y10_uk", "y10_pl", "y10_us", "y10_mx", "y10_br", "y10_co", "y10_cl", "y10_pe"], "Bonos soberanos 10 años", "Rentabilidad y primas de riesgo frente a Alemania.", "bonos"))
P.append(grid(["eurusd", "gbpeur", "gbpusd", "usdbrl", "usdmxn", "usdars", "usdclp"], "Divisas", "Variación diaria en %.", "fx"))
P.append(grid(["brent", "wti", "ttf", "henry_hub", "copper", "wheat", "corn", "fao_food", "gold"], "Materias primas ligadas a la inflación", "Energía, metales y alimentos.", "commodities"))
P.append(grid(["itraxx_main_5y", "itraxx_xover_5y", "oas_us_ig", "oas_us_hy", "oas_eur_hy", "oas_em", "cp_spread_us", "rrp_us", "reserves_us", "breakeven_10y_us"], "Crédito y financiación", "Índices CDS, diferenciales corporativos y termómetros de liquidez del sistema.", "credito"))
P.append(grid(["cpi_ea", "cpi_es", "cpi_pt", "cpi_fr", "cpi_nl", "cpi_de", "cpi_uk", "cpi_pl"], "Inflación en Europa", "IPC general y subyacente, tasa interanual; variación frente al mes anterior en pp.", "infl-eu"))
P.append(grid(["cpi_us", "cpi_mx", "cpi_br", "cpi_ar", "cpi_cl", "cpi_co", "cpi_pe"], "Inflación en América", "IPC general y subyacente, tasa interanual.", "infl-am"))
pulso = "".join(P)

# Markets information
M = []
M.append('<section id="cds"><div class="sh"><h2>Índices CDS</h2><p>iTraxx Europe y CDX a 5 años, en pb.</p></div>' + table(["Índice", "Nivel (pb)", "Δ día", "Fecha", "Fuente"], [[(r["name"], ""), vcell(r), chg_cell(r, "d1"), (fdate(r.get("date")), ""), (r.get("source", ""), "src")] for r in grp("cds_idx")]) + "</section>")
sov = {}
for r in grp("cds_sov"):
    o = sov.setdefault(r.get("country"), {"order": float(r.get("order") or 0), "rating": r.get("rating", ""), "1Y": None, "3Y": None, "5Y": None, "date": "", "d5": None})
    o[r.get("tenor")] = num(r.get("value"))
    if r.get("tenor") == "5Y":
        o["date"] = r.get("date")
        o["d5"] = stats(r)["d1"] if num(r.get("value")) is not None else None
srows = []
for c, o in sorted(sov.items(), key=lambda x: x[1]["order"]):
    srows.append([(c, "")] + [((fnum(o[t], 1) if o[t] is not None else "N/D"), "" if o[t] is not None else "na") for t in ("1Y", "3Y", "5Y")] + [(fchg(o["d5"], "pb"), ccls(o["d5"])), (fdate(o["date"]), ""), (o["rating"], "")])
M.append('<section id="cds-sov"><div class="sh"><h2>CDS soberanos</h2><p>1, 3 y 5 años, USD, pb. N/D: plazo sin cotización en fuentes abiertas.</p></div>' + table(["País", "1A", "3A", "5A", "Δ 5A día", "Fecha", "Rating"], srows) + "</section>")
oas = grp("oas")
M.append('<section id="rating"><div class="sh"><h2>Crédito corporativo por rating</h2><p>OAS ICE BofA, EE. UU., en pb. Los CDS por rating a 6M, 1A, 3A y 5A no se publican en abierto.</p></div><div class="two">'
         + multi([r["id"] for r in oas], "Diferencial por rating · 3 años", "Cierre de cada mes, pb.", "ch-rating", label=lambda r: r.get("short"), dec=0)
         + '<div class="box">' + table(["Rating", "OAS (pb)", "Δ día", "Δ mes", "Δ 12 m", "Fecha"], [[(r["name"], ""), vcell(r), chg_cell(r, "d1"), chg_cell(r, "m1"), chg_cell(r, "y1"), (fdate(r.get("date")), "")] for r in oas]) + "</div></div></section>")
for g, t, s in (("cds_bank", "CDS bancos", "Senior a 5 años, pb."), ("cds_og", "CDS oil & gas", "Senior a 5 años, pb.")):
    M.append(f'<section id="{g}"><div class="sh"><h2>{t}</h2><p>{s}</p></div>' + table(["Entidad", "CDS 5A (pb)", "Δ día", "Fecha", "Fuente"], [[(r["name"], ""), vcell(r), chg_cell(r, "d1"), (fdate(r.get("date")), ""), (r.get("source", ""), "src")] for r in grp(g)]) + "</section>")
M.append('<section id="y10"><div class="sh"><h2>Bonos a 10 años · 3 años</h2><p>Media mensual; el último punto es el cierre diario más reciente.</p></div><div class="two">'
         + multi(["y10_de", "y10_es", "y10_it", "y10_fr", "y10_pt", "y10_nl", "y10_uk", "y10_us"], "Europa y EE. UU.", "% de rentabilidad.", "ch-y10-eu")
         + multi(["y10_mx", "y10_co", "y10_cl", "y10_pe", "y10_pl"], "Latinoamérica y Polonia", "% de rentabilidad.", "ch-y10-lat") + "</div></section>")
M.append('<section id="tipos-oficiales"><div class="sh"><h2>Evolución de tipos oficiales · 3 años</h2><p>Tipo vigente al cierre de cada mes.</p></div><div class="two">'
         + multi(["ecb_dfr", "fed_upper", "boe_bank_rate"], "BCE, Fed y Banco de Inglaterra", "BCE: facilidad de depósito; Fed: techo del rango.", "ch-g3", label=lambda r: r.get("short"), step=True)
         + multi(["selic", "banrep", "banxico", "bcrp", "bcch", "nbp"], "Latinoamérica y Polonia", "Argentina (BCRA) no tiene tipo oficial desde julio de 2025.", "ch-lat", label=lambda r: r.get("short"), step=True) + "</div>")
evrows = [[(fdate(e.get("date")), ""), (e.get("bank"), ""), (e.get("decision"), "txt")] for e in sorted(EV, key=lambda e: str(e.get("date")), reverse=True)[:60]]
M.append('<details class="more"><summary>Ver las últimas 60 decisiones</summary>' + table(["Fecha", "Banco", "Decisión"], evrows) + "</details></section>")
irows = []
for r in sorted([r for r in U if r.get("group") in ("infl",) and str(r.get("id", "")).startswith("cpi_")], key=lambda r: float(r.get("order") or 0)) + [BY[i] for i in ("cpi_fr", "cpi_nl") if i in BY and BY[i].get("group") != "infl"]:
    m = str(r.get("date"))[:7]
    s = {k: x for k, (x, _) in HIST.get(r["id"], {}).items()}
    cr = BY.get(r.get("core_id") or ("core_" + r["id"][4:]))
    cs = {k: x for k, (x, _) in HIST.get(cr["id"], {}).items()} if cr else {}
    cm = str(cr.get("date"))[:7] if cr else m
    avg = lambda d: (round(sum(d[k] for k in d if k.startswith("2025-")) / 12, 2) if sum(1 for k in d if k.startswith("2025-")) == 12 else None)
    cell = lambda v, d=1: (fnum(v, d) if v is not None else "N/D", "" if v is not None else "na")
    irows.append([(r.get("country"), ""), (fdate(m), ""), cell(num(r.get("value"))), cell(s.get(back(m, 1))), cell(s.get(back(m, 12))), cell(avg(s), 2),
                  cell(num(cr.get("value")) if cr else None), cell(cs.get(back(cm, 1)) if cr else None), cell(cs.get(back(cm, 12)) if cr else None), cell(avg(cs) if cr else None, 2)])
M.append('<section id="inflacion"><div class="sh"><h2>Inflación por país</h2><p>Último dato frente al mes anterior, a hace 12 meses y a la media de 2025, en % interanual.</p></div>'
         + table(["País", "Mes", "IPC", "Mes ant.", "Hace 12 m", "Media 2025", "Subyac.", "Mes ant.", "Hace 12 m", "Media 2025"], irows)
         + '<div class="two">' + multi(["cpi_ea", "cpi_es", "cpi_pt", "cpi_fr", "cpi_nl", "cpi_de", "cpi_uk", "cpi_pl"], "IPC general · Europa", "% interanual.", "ch-infl-eu", dec=1)
         + multi(["cpi_us", "cpi_mx", "cpi_br", "cpi_cl", "cpi_co", "cpi_pe"], "IPC general · América", "% interanual. Argentina (33,4 %) fuera de escala: ver tabla.", "ch-infl-am", dec=1) + "</div></section>")
br = BY.get("brent")
if br:
    M.append('<section id="brent-3a"><div class="sh"><h2>Barril de Brent · 3 años</h2><p>Futuro ICE de primer vencimiento, USD por barril, cierre de cada mes.</p></div><div class="box">' + line_svg([("Brent", PAL[0], series("brent"))], w=760, h=280, unit="USD/bbl") + "</div></section>")
markets = "".join(M)

curvas = grid(["estr", "euribor_1w", "euribor_1m", "euribor_3m", "euribor_6m", "euribor_12m"], "EUR · €STR y Euribor", "Toca cada plazo para ver su histórico.", "curva-eur") + grid(["sofr", "term_sofr_1m", "term_sofr_3m", "term_sofr_6m", "term_sofr_12m"], "USD · SOFR y Term SOFR", "Term SOFR de CME; histórico abierto desde octubre de 2025.", "curva-usd") + grid(["ecb_mro", "ecb_mlf", "fed_lower", "effr", "sofr_avg_30d", "sofr_avg_90d"], "Otros tipos de mercado monetario", "BCE, Fed y medias SOFR.", "curva-otros")

# Portugal, Francia, Holanda
R = []
for code, cname, bank in (("pt", "Portugal", "Banco de Portugal"), ("fr", "Francia", "Banque de France"), ("nl", "Países Bajos", "De Nederlandsche Bank")):
    ids = [f"cpi_{code}", f"y10_{code}", f"spread_{code}_de_10y", f"gdp_{code}", f"unemp_{code}", f"loan_rate_nfc_{code}", f"dep_rate_{code}", f"nfc_deposits_{code}"]
    cards = "".join(card(BY[i]) for i in ids if i in BY and num(BY[i].get("value")) is not None)
    notes = [b for b in BNOTES if b.get("country") == cname]
    nhtml = "".join(f'<li><b>{esc(fdate(b.get("date")))}</b> {esc(b.get("text_es"))} ' + (f'<a href="{esc(b["url"])}" target="_blank" rel="noopener">{esc(b.get("source") or "Fuente")} ↗</a>' if str(b.get("url", "")).startswith("http") else "") + "</li>" for b in notes)
    rn = [x for x in RNEWS if x.get("country") == cname]
    R.append(f'<section id="reg-{code}"><div class="sh"><h2>{cname}</h2><p>Indicadores de macro, inflación y liquidez · {bank} · noticias de liquidez y cash de sus principales compañías.</p></div>'
             + (f'<div class="grid">{cards}</div>' if cards else "")
             + (f'<div class="box"><h3>{bank}</h3><ul class="notes">{nhtml}</ul></div>' if nhtml else "")
             + f'<div class="news">{news_items(rn, show_rank=False)}</div></section>')
regional = "".join(R)

secs = by_sector(NEWS)
chips = " · ".join(f'<a href="#ns-{i}">{esc(s)} ({len(v)})</a>' for i, (s, v) in enumerate(secs.items()))
noticias = (f'<section id="top10"><div class="sh"><h2>Top 10 del día para la mesa de liquidez</h2><p>Selección a {esc(fdate(str(NMETA.get("as_of", ""))[:10]))} · resúmenes propios con enlace a la fuente.</p></div><p class="chips">{chips}</p>'
            + "".join(f'<h3 class="sec" id="ns-{i}">{esc(s)}</h3><div class="news">{news_items(v)}</div>' for i, (s, v) in enumerate(secs.items())) + "</section>")

CSS = """
:root{--bg:#0b1119;--panel:#111a26;--panel2:#162231;--line:#233246;--line2:#2e4159;--fg:#dbe4ee;--muted:#8798ad;--faint:#5d6f86;--accent:#7cc4ff;--up:#3ddc97;--down:#ff7a7a;--warn:#f5c26b;
--mono:ui-monospace,"SF Mono",Menlo,Consolas,"Roboto Mono",monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color-scheme:dark}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--sans);font-size:14px;font-variant-numeric:tabular-nums;padding-left:max(12px,env(safe-area-inset-left));padding-right:max(12px,env(safe-area-inset-right));padding-bottom:40px}
a{color:var(--accent)}
header{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap;padding:14px 0 8px}
header h1{margin:0;font-size:15px;letter-spacing:.08em;text-transform:uppercase}
header .asof{font-family:var(--mono);font-size:11px;color:var(--muted)}header .asof b{color:var(--accent);font-weight:500}
.tape{display:flex;overflow-x:auto;border:1px solid var(--line);border-radius:4px;background:var(--panel);-webkit-overflow-scrolling:touch}
.tape span{flex:0 0 auto;padding:7px 12px;border-right:1px solid var(--line);font-family:var(--mono);font-size:12px;white-space:nowrap}.tape b{color:var(--muted);font-weight:500}.tape em{font-style:normal}
nav{position:sticky;top:0;z-index:5;background:var(--bg);display:flex;gap:2px;overflow-x:auto;border-bottom:1px solid var(--line);margin:10px 0 4px;-webkit-overflow-scrolling:touch;padding-top:env(safe-area-inset-top)}
nav a{flex:0 0 auto;color:var(--muted);text-decoration:none;font-size:12px;letter-spacing:.06em;text-transform:uppercase;padding:10px 10px;border-bottom:2px solid transparent}
nav a:hover,nav a:focus{color:var(--fg);border-bottom-color:var(--accent)}
.page{scroll-margin-top:48px}.page>h1{font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:var(--fg);margin:22px 0 4px;padding-top:10px;border-top:2px solid var(--line2)}
section{margin:14px 0 18px;scroll-margin-top:52px}
.sh{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:5px;margin-bottom:8px}
.sh h2{margin:0;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}.sh p{margin:0;font-size:11px;color:var(--muted);max-width:70ch}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,190px),1fr));gap:6px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:4px;min-width:0}
.card[open]{grid-column:1/-1;border-color:var(--line2)}
.card summary{list-style:none;cursor:pointer;padding:9px 10px 6px;display:block}.card summary::-webkit-details-marker{display:none}
.top{display:flex;justify-content:space-between;gap:6px}.code{font-family:var(--mono);font-size:10.5px;color:var(--accent);letter-spacing:.06em;text-transform:uppercase}.date{font-family:var(--mono);font-size:10.5px;color:var(--faint)}
.name{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:2px 0}
.row{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap}.val{font-family:var(--mono);font-size:20px;font-weight:500}.unit{font-family:var(--mono);font-size:10.5px;color:var(--faint)}
.chg{font-family:var(--mono);font-size:11.5px}.up{color:var(--up)}.down{color:var(--down)}.flat{color:var(--muted)}
.sub{font-family:var(--mono);font-size:11px;color:var(--muted)}.spark{height:34px;margin-top:3px}.spark svg{height:34px}
.probs{margin-top:4px}.pr{display:grid;grid-template-columns:5.2rem 1fr;gap:6px;align-items:center;font-family:var(--mono);font-size:10.5px;color:var(--muted)}
.pb{display:flex;height:8px;border-radius:2px;overflow:hidden;background:var(--line)}.pb i{display:block;height:100%}.pl{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin:1px 0 4px 5.6rem}
.detail{border-top:1px solid var(--line);padding:10px;display:flex;flex-direction:column;gap:10px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,130px),1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:4px;overflow:hidden}
.stats div{background:var(--panel);padding:7px 9px;display:flex;flex-direction:column;gap:2px}.stats span{font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}.stats b{font-family:var(--mono);font-size:14px;font-weight:500}
.box{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:10px;min-width:0}.box h3{margin:0 0 2px;font-size:12px;font-weight:600}
.cap{margin:0 0 6px;font-size:11px;color:var(--muted)}
.chart{display:block;width:100%;height:auto}.tk{font-family:var(--mono);font-size:10.5px;fill:#8798ad}.el{font-family:var(--mono);font-size:10.5px;fill:#dbe4ee}
.legend{display:flex;flex-wrap:wrap;gap:4px 10px;margin-top:6px;font-family:var(--mono);font-size:10.5px;color:var(--fg)}.legend i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:5px}
.read{border-left:2px solid var(--accent);background:var(--panel2);padding:9px 12px}.read h4{margin:0 0 4px;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}.read p{margin:0 0 4px;font-size:13.5px;line-height:1.55;max-width:80ch}.read small{font-size:10.5px;color:var(--faint)}
.meta{font-size:11px;color:var(--muted);display:flex;flex-direction:column;gap:3px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));gap:8px;align-items:start}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;background:var(--panel);border:1px solid var(--line);border-radius:4px}
table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:right;font-weight:500;font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);padding:6px 8px;border-bottom:1px solid var(--line2);white-space:nowrap}
td{text-align:right;font-family:var(--mono);padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}th:first-child,td:first-child{text-align:left;font-family:var(--sans)}
td.na{color:var(--faint)}td.txt{text-align:left;white-space:normal;font-family:var(--sans);min-width:18rem}td.src{font-family:var(--sans);color:var(--muted);font-size:11px}
details.more{margin-top:8px}details.more>summary{cursor:pointer;color:var(--accent);font-size:12px;padding:6px 0}
.news{display:flex;flex-direction:column;gap:6px}.nw{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:10px 12px;display:flex;gap:10px}
.rk{font-family:var(--mono);font-size:18px;color:var(--accent);min-width:1.8rem}.nt{font-family:var(--mono);font-size:10.5px;color:var(--muted)}
.tag{border:1px solid var(--line2);border-radius:3px;padding:1px 6px;color:var(--fg);text-transform:uppercase;letter-spacing:.05em}
.nw h3{margin:4px 0;font-size:14.5px;line-height:1.35}.nw p{margin:0 0 4px;font-size:13px;line-height:1.5;max-width:85ch}.nw .imp{color:var(--warn)}.nw a{font-size:11.5px}
h3.sec{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:14px 0 6px}.chips{font-size:12px;color:var(--muted);line-height:1.9}
ul.notes{margin:4px 0 0;padding-left:18px;font-size:13px;line-height:1.5}ul.notes li{margin-bottom:6px}
.empty{color:var(--faint);font-size:12px}
footer{margin-top:28px;font-size:11px;color:var(--faint);border-top:1px solid var(--line);padding-top:10px;line-height:1.6}
"""

page = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Monitor de liquidez y mercados</title><meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#0b1119">
<style>{CSS}</style></head><body>
<header><h1>Monitor de liquidez y mercados</h1><div class="asof">Datos a <b>{esc(asof)}</b> · generado {esc(built)} (hora de Madrid)</div></header>
<div class="tape">{"".join(tape)}</div>
<nav><a href="#pulso">Pulso</a><a href="#markets">Markets information</a><a href="#regional">Portugal · Francia · Holanda</a><a href="#curvas">Curvas</a><a href="#noticias">Top 10 noticias</a></nav>
<div class="page" id="pulso"><h1>Pulso de mercado</h1>{pulso}</div>
<div class="page" id="markets"><h1>Markets information</h1>{markets}</div>
<div class="page" id="regional"><h1>Portugal · Francia · Holanda</h1>{regional}</div>
<div class="page" id="curvas"><h1>Curvas monetarias</h1>{curvas}</div>
<div class="page" id="noticias"><h1>Top 10 noticias</h1>{noticias}</div>
<footer>Datos de fuentes públicas (bancos centrales, administradores de índices, institutos estadísticos y, donde no hay fuente oficial abierta, agregadores que se indican en cada indicador). Se actualiza los días laborables a las 7:45, 12:58 y 17:45 (Madrid). Lecturas y resúmenes de noticias redactados por Claude; no constituyen recomendación de inversión. Los CDS por emisor y las curvas por rating requieren datos con licencia (S&amp;P Global/Markit, LSEG, Bloomberg).</footer>
</body></html>"""

(OUT / "index.html").write_text(page)
print(f"index.html: {len(page) / 1024:.0f} KB · {len(U)} indicadores · {len(NEWS)} noticias · {len(RNEWS)} noticias regionales")
