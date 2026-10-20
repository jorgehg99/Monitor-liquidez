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
RESUMEN = (load("resumen.json", [{}]) or [{}])[0]
AGENDA = load("agenda.json", {"events": []})
AGENDA = AGENDA.get("events", []) if isinstance(AGENDA, dict) else AGENDA
WATCH = load("watchlist.json", {"items": []})
WATCH_URL = "https://docs.google.com/document/d/1W7OAssXSAwfdTeHtucsFwRjDHANj00QoOKrDtBFQqrs/edit"

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
            out.append(f'<line x1="{L:.1f}" x2="{w - R:.1f}" y1="{y:.1f}" y2="{y:.1f}" class="gl"/>')
            out.append(f'<text x="{L - 6:.1f}" y="{y + 3.5:.1f}" text-anchor="end" class="tk">{lb}</text>')
        out.append(f'<line x1="{L:.1f}" x2="{w - R:.1f}" y1="{h - B:.1f}" y2="{h - B:.1f}" class="ax"/>')
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
    return f'''<details class="card" id="c-{esc(r["id"])}" data-id="{esc(r["id"])}"><summary>
<div class="top"><span class="code">{esc(r.get("short") or r["id"])}</span><span class="date">{esc(fdate(r.get("date")))}<button type="button" class="star" data-fav="{esc(r["id"])}" aria-pressed="false" aria-label="Añadir a Mi vista">☆</button></span></div>
<div class="name">{esc(r.get("name"))}</div>
<div class="row"><span class="val">{fnum(v, dec)}</span><span class="unit">{esc(r.get("unit"))}</span><span class="chg {ccls(d1)}">{arrow}{fchg(d1, k) if d1 is not None else ""}</span></div>
{core}{extra}<div class="spark">{sp}</div></summary>
<div class="detail"><div class="stats">{stats_html}</div>
<div class="box"><div class="bh"><div class="cap">Histórico 3 años · {basis}; el último punto es el dato más reciente.</div>{zoom_btn(r.get("name"), [r["id"]] + ([r["core_id"]] if r.get("core_id") in BY else []), pool_for(r), r.get("group") == "policy")}</div>{big}{legend([(s[0], s[1]) for s in sers]) if len(sers) > 1 else ""}</div>
{read}<div class="meta">{meta}</div></div></details>'''

BANKP = {"ecb_dfr": "BCE", "fed_upper": "Fed", "boe_bank_rate": "BoE"}

def has_hist(i):
    return i in BY and len(HIST.get(i, {})) > 1

def pool_for(r):
    g, i = r.get("group"), r["id"]
    if g in ("infl", "infl_core"):
        ids = [x["id"] for x in U if x.get("group") in ("infl", "infl_core")]
    elif g in ("rate", "mm", "policy"):
        ids = [x["id"] for x in U if x.get("group") in ("rate", "mm", "policy")]
    elif g in ("oas", "credit", "cds_idx"):
        ids = [x["id"] for x in U if x.get("group") in ("oas", "credit", "cds_idx") and x.get("unit") == r.get("unit")]
    elif g == "reg":
        k = i.rsplit("_", 1)[0]
        ids = [x["id"] for x in U if x["id"].rsplit("_", 1)[0] == k]
    elif g in ("y10", "spread"):
        ids = [x["id"] for x in U if x.get("group") == g]
    else:
        ids = [x["id"] for x in U if x.get("group") == g]
    return [x for x in ids if has_hist(x)]

def zoom_btn(title, sel, pool, step=False):
    sel = [x for x in sel if has_hist(x)]
    pool = [x for x in dict.fromkeys(sel + pool) if has_hist(x)]
    if not sel:
        return ""
    cs = [BY[x].get("country") or "" for x in pool]
    lb = "c" if all(cs) and len(set(cs)) == len(cs) else "n"
    spec = json.dumps({"t": title, "s": sel, "p": pool, "st": bool(step), "lb": lb}, ensure_ascii=False)
    return f'<button type="button" class="zoom" data-zoom="{esc(spec)}">⤢ Ampliar y comparar</button>'

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

def multi(ids, title, sub, anchor, label=lambda r: r.get("country") or r.get("name"), step=False, dec=2, pool=None):
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
    sel = [i for i in ids if BY.get(i) and series(i)][:8]
    zb = zoom_btn(title, sel, (pool or []) + ids, step)
    return f'<div class="box" id="{anchor}"><div class="bh"><h3>{esc(title)}</h3>{zb}</div><p class="cap">{esc(sub)}</p>{svg}{legend([(s[0], s[1]) for s in sers])}</div>'

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

import statistics
def pct_rank(i):
    s = HIST.get(i, {})
    r = BY.get(i)
    if not r or num(r.get("value")) is None or len(s) < 12:
        return None
    m = str(r["date"])[:7]
    vals = [v for k, (v, _) in s.items() if k >= back(m, 36)]
    v = num(r["value"])
    return round(100 * sum(1 for x in vals if x <= v) / len(vals))

STRESS = [("euribor_estr_3m", "Euribor 3M − €STR"), ("spread_es_de_10y", "Prima España"), ("spread_it_de_10y", "Prima Italia"), ("spread_fr_de_10y", "Prima Francia"),
          ("oas_eur_hy", "High yield euro"), ("oas_us_hy", "High yield EE. UU."), ("oas_em", "Crédito emergente"), ("cp_spread_us", "Papel comercial − T-bill")]
def stress_box():
    comps = [(lab, pct_rank(i), i) for i, lab in STRESS]
    comps = [c for c in comps if c[1] is not None]
    if not comps:
        return ""
    sc = round(sum(c[1] for c in comps) / len(comps))
    lvl, cls = ("Calma", "ok") if sc < 40 else (("Vigilancia", "warn") if sc < 70 else ("Tensión", "bad"))
    rows = "".join(f'<div class="sr"><span>{esc(lab)}</span><span class="sb"><i style="width:{p}%"></i></span><b>{p}</b></div>' for lab, p, _ in comps)
    return (f'<section id="termometro"><div class="sh"><h2>Termómetro de liquidez y crédito</h2><p>Percentil del dato actual dentro de sus últimos 3 años (100 = el nivel más tenso del periodo). Media simple de {len(comps)} indicadores.</p></div>'
            f'<div class="gauge {cls}"><div class="gv"><span class="gn">{sc}</span><span class="gl2">{lvl}</span></div><div class="gbar"><i style="left:{sc}%"></i></div><div class="gs"><span>Calma</span><span>Vigilancia</span><span>Tensión</span></div></div>'
            f'<details class="more"><summary>Ver los componentes</summary><div class="srs">{rows}</div></details></section>')

def movers_box(n=8):
    dates = sorted(str(r.get("date")) for r in U if len(str(r.get("date") or "")) == 10)
    if not dates:
        return ""
    top = dates[-1]
    out = []
    for r in U:
        d = str(r.get("date") or "")
        v, pv = num(r.get("value")), num(r.get("prev_value"))
        if len(d) != 10 or v is None or pv is None or r.get("group") in ("policy",):
            continue
        if (datetime.date.fromisoformat(top) - datetime.date.fromisoformat(d)).days > 4:
            continue
        s = [x for _, (x, _) in sorted(HIST.get(r["id"], {}).items())]
        ch = [b - a for a, b in zip(s, s[1:])]
        if len(ch) < 6:
            continue
        sd = statistics.pstdev(ch)
        if not sd:
            continue
        z = (v - pv) / sd
        out.append((abs(z), z, r))
    out.sort(key=lambda x: -x[0])
    rows = []
    for az, z, r in out[:n]:
        st_ = stats(r)
        rows.append(f'<a class="mv" href="#c-{esc(r["id"])}" data-goto="{esc(r["id"])}"><span class="mn">{esc(r.get("name"))}</span><span class="mvv">{fnum(num(r["value"]), min(int(r.get("decimals") or 2), 3))} <em class="{ccls(st_["d1"])}">{fchg(st_["d1"], st_["kind"])}</em></span><span class="mz"><i style="width:{min(100, az / 1.5 * 100):.0f}%"></i></span></a>')
    if not rows:
        return ""
    return ('<section id="movers"><div class="sh"><h2>Lo que más se ha movido</h2><p>Movimiento del último dato frente a su variación mensual típica de los últimos 3 años. Toca para ir al cromo.</p></div>'
            f'<div class="mvs">{"".join(rows)}</div></section>')

def resumen_box():
    b = RESUMEN.get("bullets") or []
    if not b:
        return ""
    li = "".join(f"<li>{esc(x)}</li>" for x in b)
    return (f'<section id="hoy"><div class="sh"><h2>Hoy en 30 segundos</h2><p>Nota de {esc(fdate(str(RESUMEN.get("as_of", ""))[:10]))} {esc(str(RESUMEN.get("as_of", ""))[11:16])} · escrita por Claude con los datos de esta página.</p></div>'
            f'<div class="hoy"><ul>{li}</ul></div></section>')

P = [resumen_box(), stress_box(), movers_box()]
P.append(grid(["estr", "sofr", "fed_upper", "iorb", "sonia"], "Tipos overnight", "Variación frente al dato anterior. Toca un cromo para ver 3 años de histórico y la lectura de liquidez.", "tipos"))
P.append(grid(["ecb_dfr", "fed_upper", "boe_bank_rate"], "Bancos centrales", "Tipo oficial y probabilidades de mercado para las dos próximas reuniones.", "bc", extra=probs))
P.append(grid(["y10_de", "y10_es", "spread_es_de_10y", "y10_pt", "y10_fr", "spread_fr_de_10y", "y10_it", "spread_it_de_10y", "y10_nl", "y10_uk", "y10_pl", "y10_us", "y10_mx", "y10_br", "y10_co", "y10_cl", "y10_pe"], "Bonos soberanos 10 años", "Rentabilidad y primas de riesgo frente a Alemania.", "bonos"))
P.append(grid(["eurusd", "gbpeur", "gbpusd", "usdbrl", "usdmxn", "usdars", "usdclp"], "Divisas", "Variación diaria en %.", "fx"))
P.append(grid(["brent", "wti", "ttf", "henry_hub", "copper", "wheat", "corn", "fao_food", "gold"], "Materias primas ligadas a la inflación", "Energía, metales y alimentos.", "commodities"))
P.append(grid(["letra_es_3m", "letra_es_6m", "letra_es_12m", "btf_fr_3m", "btf_fr_12m", "bubill_de_6m", "bubill_de_12m", "tbill_us_3m", "tbill_us_6m", "tbill_us_1y"], "Alternativas al depósito a corto plazo", "Letras del Tesoro, BTF, Bubills y T-bills: lo que un tesorero compara con remunerar la caja en banco.", "letras"))
P.append(grid(["excess_liq_ecb", "dfr_recourse_ecb", "eurep_ecb", "euribor_estr_3m", "srf_fed", "tga_us", "rrp_us", "reserves_us", "fed_assets", "cp_spread_us"], "Liquidez del sistema", "Exceso de liquidez y facilidades del BCE, repo de la Fed, cuenta del Tesoro de EE. UU. y reservas bancarias.", "liquidez"))
P.append(grid(["itraxx_main_5y", "itraxx_xover_5y", "oas_us_ig", "oas_us_hy", "oas_eur_hy", "oas_em", "breakeven_10y_us"], "Crédito", "Índices CDS y diferenciales corporativos.", "credito"))
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
         + multi([r["id"] for r in oas], "Diferencial por rating · 3 años", "Cierre de cada mes, pb.", "ch-rating", label=lambda r: r.get("short"), dec=0, pool=[x["id"] for x in U if x.get("group") in ("oas", "credit") and x.get("unit") == "pb"])
         + '<div class="box">' + table(["Rating", "OAS (pb)", "Δ día", "Δ mes", "Δ 12 m", "Fecha"], [[(r["name"], ""), vcell(r), chg_cell(r, "d1"), chg_cell(r, "m1"), chg_cell(r, "y1"), (fdate(r.get("date")), "")] for r in oas]) + "</div></div></section>")
for g, t, s in (("cds_bank", "CDS bancos", "Senior a 5 años, pb."), ("cds_og", "CDS oil & gas", "Senior a 5 años, pb.")):
    M.append(f'<section id="{g}"><div class="sh"><h2>{t}</h2><p>{s}</p></div>' + table(["Entidad", "CDS 5A (pb)", "Δ día", "Fecha", "Fuente"], [[(r["name"], ""), vcell(r), chg_cell(r, "d1"), (fdate(r.get("date")), ""), (r.get("source", ""), "src")] for r in grp(g)]) + "</section>")
M.append('<section id="y10"><div class="sh"><h2>Bonos a 10 años · 3 años</h2><p>Media mensual; el último punto es el cierre diario más reciente.</p></div><div class="two">'
         + multi(["y10_de", "y10_es", "y10_it", "y10_fr", "y10_pt", "y10_nl", "y10_uk", "y10_us"], "Europa y EE. UU.", "% de rentabilidad.", "ch-y10-eu", pool=[x["id"] for x in U if x.get("group") == "y10"])
         + multi(["y10_mx", "y10_co", "y10_cl", "y10_pe", "y10_pl"], "Latinoamérica y Polonia", "% de rentabilidad.", "ch-y10-lat", pool=[x["id"] for x in U if x.get("group") == "y10"]) + "</div></section>")
M.append('<section id="tipos-oficiales"><div class="sh"><h2>Evolución de tipos oficiales · 3 años</h2><p>Tipo vigente al cierre de cada mes.</p></div><div class="two">'
         + multi(["ecb_dfr", "fed_upper", "boe_bank_rate"], "BCE, Fed y Banco de Inglaterra", "BCE: facilidad de depósito; Fed: techo del rango.", "ch-g3", label=lambda r: r.get("short"), step=True, pool=[x["id"] for x in U if x.get("group") == "policy"])
         + multi(["selic", "banrep", "banxico", "bcrp", "bcch", "nbp"], "Latinoamérica y Polonia", "Argentina (BCRA) no tiene tipo oficial desde julio de 2025.", "ch-lat", label=lambda r: r.get("short"), step=True, pool=[x["id"] for x in U if x.get("group") == "policy"]) + "</div>")
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
         + '<div class="two">' + multi(["cpi_ea", "cpi_es", "cpi_pt", "cpi_fr", "cpi_nl", "cpi_de", "cpi_uk", "cpi_pl"], "IPC general · Europa", "% interanual.", "ch-infl-eu", dec=1, pool=[x["id"] for x in U if x.get("group") in ("infl", "infl_core")])
         + multi(["cpi_us", "cpi_mx", "cpi_br", "cpi_cl", "cpi_co", "cpi_pe"], "IPC general · América", "% interanual. Argentina (33,4 %) fuera de escala: ver tabla.", "ch-infl-am", dec=1, pool=[x["id"] for x in U if x.get("group") in ("infl", "infl_core")]) + "</div></section>")
br = BY.get("brent")
if br:
    M.append('<section id="brent-3a"><div class="sh"><h2>Barril de Brent · 3 años</h2><p>Futuro ICE de primer vencimiento, USD por barril, cierre de cada mes.</p></div><div class="box"><div class="bh"><h3>Brent</h3>' + zoom_btn("Brent", ["brent"], [x["id"] for x in U if x.get("group") == "cmdty"]) + '</div>' + line_svg([("Brent", PAL[0], series("brent"))], w=760, h=280, unit="USD/bbl") + "</div></section>")
markets = "".join(M)

def agenda_page():
    ev = sorted(AGENDA, key=lambda e: (str(e.get("date")), str(e.get("time") or "99")))
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2))).date().isoformat()
    ev = [e for e in ev if str(e.get("date")) >= today]
    if not ev:
        return '<p class="empty">Sin eventos cargados.</p>'
    types = list(dict.fromkeys(e.get("type") or "Otros" for e in ev))
    chips = '<div class="fchips" id="ag-f"><button type="button" class="chip" aria-pressed="true" data-f="">Todos</button>' + "".join(f'<button type="button" class="chip" aria-pressed="false" data-f="{esc(x)}">{esc(x)}</button>' for x in types) + '<button type="button" class="chip" aria-pressed="false" data-f="alta">Solo relevancia alta</button></div>'
    out, cur = [chips], None
    for e in ev:
        d = str(e.get("date"))
        if d != cur:
            if cur:
                out.append("</div>")
            wd = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][datetime.date.fromisoformat(d).weekday()]
            out.append(f'<h3 class="sec">{wd} {esc(fdate(d))}</h3><div class="ag">')
            cur = d
        link = f' <a href="{esc(e["url"])}" target="_blank" rel="noopener">↗</a>' if str(e.get("url", "")).startswith("http") else ""
        out.append(f'<div class="ev {"hi" if e.get("relevance") == "alta" else ""}" data-t="{esc(e.get("type") or "Otros")}" data-r="{esc(e.get("relevance") or "")}"><span class="et">{esc(e.get("time") or "—")}</span><span class="ec">{esc(e.get("country") or "")}</span><span class="tag">{esc(e.get("type") or "")}</span><span class="ee">{esc(e.get("event"))}{link}</span></div>')
    out.append("</div>")
    return '<section id="agenda-l"><div class="sh"><h2>Próximos eventos</h2><p>Horas de Madrid. En rojo, relevancia alta para la mesa de liquidez.</p></div>' + "".join(out) + "</section>"

def watch_page():
    items = WATCH.get("items", []) if isinstance(WATCH, dict) else []
    head = (f'<section id="wl"><div class="sh"><h2>Mi watchlist</h2><p>Actualizada a {esc(fdate(str(WATCH.get("as_of", ""))[:10]) if isinstance(WATCH, dict) else "")} {esc(str(WATCH.get("as_of", ""))[11:16] if isinstance(WATCH, dict) else "")}. Se revisa en cada actualización.</p></div>'
            f'<p class="wlhelp">Para añadir o quitar algo, edita tu documento <a href="{WATCH_URL}" target="_blank" rel="noopener">Watchlist · Monitor de liquidez ↗</a> en Google Docs (una línea por empresa, índice o tema). Aparecerá aquí en la siguiente actualización.</p>')
    if not items:
        return head + '<p class="empty">Tu watchlist aún no tiene datos.</p></section>'
    cards = []
    for it in items:
        m = it.get("metric") or {}
        mv = ""
        if m.get("value") is not None:
            ch = ""
            if m.get("prev_value") not in (None, 0):
                u = m.get("unit") or ""
                if u in ("pb", "%"):
                    c = (m["value"] - m["prev_value"]) * (100 if u == "%" else 1)
                    ch = fchg(round(c, 1), "pb")
                else:
                    c = round((m["value"] / m["prev_value"] - 1) * 100, 2)
                    ch = fchg(c, "pct")
                ch = f' <em class="{ccls(c)}">{ch}</em>'
            src = f' · <a href="{esc(m["url"])}" target="_blank" rel="noopener">{esc(m.get("source") or "fuente")}</a>' if str(m.get("url", "")).startswith("http") else (f' · {esc(m.get("source"))}' if m.get("source") else "")
            mv = f'<div class="wm"><span class="wn">{esc(m.get("name") or "")}</span> <b>{fnum(num(m["value"]), 2)}</b> <span class="unit">{esc(m.get("unit") or "")}</span>{ch}<div class="wd">{esc(fdate(m.get("date")))}{src}</div></div>'
        news = "".join(f'<li><b>{esc(fdate(n.get("date")))}</b> {esc(n.get("headline"))}. {esc(n.get("summary") or "")} <span class="imp">{esc(n.get("implication") or "")}</span> ' + (f'<a href="{esc(n["url"])}" target="_blank" rel="noopener">{esc(n.get("source") or "Fuente")} ↗</a>' if str(n.get("url", "")).startswith("http") else "") + "</li>" for n in (it.get("news") or [])[:3])
        cards.append(f'<article class="wc"><div class="wh"><h3>{esc(it.get("item"))}</h3><span class="tag">{esc(it.get("type") or "")}</span></div>'
                     + (f'<p class="wnote">{esc(it.get("note"))}</p>' if it.get("note") else "") + mv
                     + (f'<p class="ws">{esc(it.get("summary_es"))}</p>' if it.get("summary_es") else "")
                     + (f'<p class="wnx">Próxima cita: {esc(it.get("next_event"))}</p>' if it.get("next_event") else "")
                     + (f'<ul class="wnews">{news}</ul>' if news else "") + "</article>")
    return head + f'<div class="wgrid">{"".join(cards)}</div></section>'

agenda = agenda_page()
watch = watch_page()
mivista = '<section id="mv-s"><div class="sh"><h2>Mi vista</h2><p>Toca la estrella ☆ de cualquier cromo para traerlo aquí. Se guarda en este móvil.</p></div><div class="grid" id="mv-grid"></div><p class="empty" id="mv-empty">Aún no has marcado ningún cromo.</p></section>'

curvas = grid(["estr", "euribor_1w", "euribor_1m", "euribor_3m", "euribor_6m", "euribor_12m"], "EUR · €STR y Euribor", "Toca cada plazo para ver su histórico.", "curva-eur") + grid(["sofr", "term_sofr_1m", "term_sofr_3m", "term_sofr_6m", "term_sofr_12m"], "USD · SOFR y Term SOFR", "Term SOFR de CME; histórico abierto desde octubre de 2025.", "curva-usd") + grid(["ecb_mro", "ecb_mlf", "fed_lower", "effr", "sofr_avg_30d", "sofr_avg_90d"], "Otros tipos de mercado monetario", "BCE, Fed y medias SOFR.", "curva-otros")

# Portugal, Francia, Holanda
R = []
for code, cname, bank in (("es", "España", "Banco de España"), ("pt", "Portugal", "Banco de Portugal"), ("fr", "Francia", "Banque de France"), ("nl", "Países Bajos", "De Nederlandsche Bank")):
    ids = [f"cpi_{code}", f"y10_{code}", f"spread_{code}_de_10y", f"gdp_{code}", f"unemp_{code}", f"loan_rate_nfc_{code}", f"dep_rate_{code}", f"dep_rate_nfc_{code}", f"dep_rate_hh_{code}", f"nfc_deposits_{code}", f"letra_{code}_3m", f"letra_{code}_12m"]
    cards = "".join(card(BY[i]).replace('id="c-', 'id="r-', 1) for i in ids if i in BY and num(BY[i].get("value")) is not None)
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
:root{--grid:#1c2939;--bg:#0b1119;--panel:#111a26;--panel2:#162231;--line:#233246;--line2:#2e4159;--fg:#dbe4ee;--muted:#8798ad;--faint:#5d6f86;--accent:#7cc4ff;--up:#3ddc97;--down:#ff7a7a;--warn:#f5c26b;
--mono:ui-monospace,"SF Mono",Menlo,Consolas,"Roboto Mono",monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color-scheme:dark}
:root[data-theme=light]{--bg:#f4f6f9;--panel:#ffffff;--panel2:#eef2f7;--line:#dde3eb;--line2:#c3ccd8;--fg:#14202e;--muted:#566578;--faint:#8592a3;--accent:#1f5f9e;--up:#147a4f;--down:#b42d2d;--warn:#8a5a00;--grid:#e6ebf1;color-scheme:light}
[hidden]{display:none!important}*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
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
.chart{display:block;width:100%;height:auto}.tk{font-family:var(--mono);font-size:10.5px;fill:var(--muted)}.el{font-family:var(--mono);font-size:10.5px;fill:var(--fg)}.gl{stroke:var(--grid)}.ax{stroke:var(--line2)}
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

# datos para el gráfico ampliado
DZ = {}
for r in U:
    s = HIST.get(r["id"], {})
    if len(s) > 1:
        DZ[r["id"]] = {"n": r.get("name"), "c": r.get("country") or "", "sh": r.get("short") or "", "u": r.get("unit") or "", "d": min(int(r.get("decimals") or 2), 3),
                       "p": [[k, round(v, 4)] for k, (v, _) in sorted(s.items())]}
DZJSON = json.dumps(DZ, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

ZCSS = """
nav button{flex:0 0 auto;font:inherit;background:transparent;color:var(--muted);font-size:12px;letter-spacing:.06em;text-transform:uppercase;padding:11px 10px;border:0;border-bottom:2px solid transparent;cursor:pointer}
nav button[aria-selected=true]{color:var(--fg);border-bottom-color:var(--accent)}
nav button:focus-visible,.zoom:focus-visible,.zm button:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.js .page{display:none}.js .page.on{display:block}
.endtab{margin:26px 0 8px;padding:14px;border:1px dashed var(--line2);border-radius:4px;text-align:center;color:var(--muted);font-size:12px}
.bh{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap}.bh .cap{margin:0}
.zoom{font:inherit;font-size:12px;color:var(--fg);background:var(--panel2);border:1px solid var(--line2);border-radius:4px;padding:6px 10px;cursor:pointer;white-space:nowrap}
.no-js .zoom{display:none}
.zm{position:fixed;inset:0;z-index:50;background:var(--bg);display:flex;flex-direction:column;gap:6px;padding:max(10px,env(safe-area-inset-top)) max(12px,env(safe-area-inset-right)) max(10px,env(safe-area-inset-bottom)) max(12px,env(safe-area-inset-left))}
.zm[hidden]{display:none}
.zm-h{display:flex;justify-content:space-between;align-items:center;gap:8px}.zm-h b{font-size:14px}
.zm button.x{font:inherit;font-size:13px;color:var(--fg);background:var(--panel2);border:1px solid var(--line2);border-radius:4px;padding:7px 12px}
.zm-ctl{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:11px;color:var(--muted)}
.seg{display:flex;border:1px solid var(--line2);border-radius:4px;overflow:hidden}.seg button{font:inherit;font-family:var(--mono);font-size:12px;background:transparent;color:var(--muted);border:0;border-right:1px solid var(--line2);padding:6px 12px}
.seg button:last-child{border-right:0}.seg button[aria-pressed=true]{background:var(--panel2);color:var(--fg)}
.zm-c{flex:1 1 auto;min-height:240px;position:relative;touch-action:none;background:var(--panel);border:1px solid var(--line);border-radius:4px}
.zm-c svg{position:absolute;inset:0;width:100%;height:100%}
.zm-r{min-height:40px;max-height:20vh;overflow-y:auto;font-family:var(--mono);font-size:12px;display:flex;flex-wrap:wrap;gap:2px 14px;align-items:center}.zm-r i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px}
.zm-r .k{color:var(--muted);width:100%}
.zm-chips{max-height:24vh;overflow-y:auto;display:flex;flex-wrap:wrap;gap:6px;padding-bottom:4px;-webkit-overflow-scrolling:touch}
.chip{font:inherit;font-size:12.5px;display:inline-flex;align-items:center;gap:6px;background:transparent;color:var(--muted);border:1px solid var(--line2);border-radius:16px;padding:6px 11px;cursor:pointer}
.chip[aria-pressed=true]{color:var(--fg);background:var(--panel2);border-color:var(--fg)}.chip i{width:9px;height:9px;border-radius:50%;background:var(--line2)}
.zm-hint{margin:0;font-size:11px;color:var(--faint)}
.thm{font:inherit;font-size:11px;color:var(--fg);background:var(--panel2);border:1px solid var(--line2);border-radius:4px;padding:3px 8px;margin-left:6px;cursor:pointer}
.star{font:inherit;font-size:15px;line-height:1;background:transparent;border:0;color:var(--faint);padding:0 0 0 8px;cursor:pointer;vertical-align:-1px}.star[aria-pressed=true]{color:var(--warn)}
.no-js .star{display:none}
.hoy{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:4px;padding:10px 14px}.hoy ul{margin:0;padding-left:18px;font-size:14px;line-height:1.55}.hoy li{margin:3px 0}
.gauge{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:12px 14px;display:flex;flex-direction:column;gap:8px}
.gv{display:flex;align-items:baseline;gap:10px}.gn{font-family:var(--mono);font-size:30px;font-weight:600}.gl2{font-size:13px;text-transform:uppercase;letter-spacing:.08em}
.gauge.ok .gl2{color:var(--up)}.gauge.warn .gl2{color:var(--warn)}.gauge.bad .gl2{color:var(--down)}
.gbar{position:relative;height:10px;border-radius:5px;background:linear-gradient(90deg,var(--up),var(--warn) 55%,var(--down))}.gbar i{position:absolute;top:-4px;width:4px;height:18px;margin-left:-2px;background:var(--fg);border-radius:2px}
.gs{display:flex;justify-content:space-between;font-size:10.5px;color:var(--muted)}
.srs{display:flex;flex-direction:column;gap:5px;margin-top:6px}.sr{display:grid;grid-template-columns:minmax(0,9rem) 1fr 2rem;gap:8px;align-items:center;font-size:12px}.sr b{font-family:var(--mono);text-align:right;font-weight:500}
.sb{height:8px;border-radius:4px;background:var(--line);overflow:hidden}.sb i{display:block;height:100%;background:var(--accent)}
.mvs{display:flex;flex-direction:column;gap:4px}.mv{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:8px 10px;text-decoration:none;color:var(--fg)}
.mn{font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.mvv{font-family:var(--mono);font-size:12.5px;text-align:right}.mvv em{font-style:normal}.mz{grid-column:1/-1;height:3px;background:var(--line);border-radius:2px;overflow:hidden}.mz i{display:block;height:100%;background:var(--accent)}
.fchips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.ag{display:flex;flex-direction:column;gap:4px}.ev{display:grid;grid-template-columns:3.4rem 2.6rem auto minmax(0,1fr);gap:4px 8px;align-items:baseline;background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:8px 10px;font-size:13px}
.ev.hi{border-left:3px solid var(--down)}.et,.ec{font-family:var(--mono);font-size:12px;color:var(--muted)}.ee{min-width:0}.ev .tag{font-size:9.5px}
@media (max-width:520px){.ev{grid-template-columns:3.2rem minmax(0,1fr)}.ev .ec,.ev .tag{grid-column:2}.ev .ee{grid-column:1/-1}}
.wlhelp{font-size:12.5px;color:var(--muted);margin:0 0 10px}
.wgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr));gap:8px}
.wc{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:10px 12px;display:flex;flex-direction:column;gap:6px;min-width:0}
.wh{display:flex;justify-content:space-between;align-items:center;gap:8px}.wh h3{margin:0;font-size:15px}.wnote{margin:0;font-size:12px;color:var(--muted)}
.wm{font-family:var(--mono);font-size:13px}.wm b{font-size:18px;font-weight:500}.wm em{font-style:normal}.wn{color:var(--muted);font-family:var(--sans);font-size:12px}.wd{font-size:11px;color:var(--faint);font-family:var(--sans)}
.ws{margin:0;font-size:13px;line-height:1.5}.wnx{margin:0;font-size:12px;color:var(--warn)}.wnews{margin:0;padding-left:16px;font-size:12.5px;line-height:1.5}.wnews li{margin-bottom:5px}.wnews .imp{color:var(--warn)}
@media (orientation:landscape) and (max-height:500px){.zm-chips{max-height:18vh}.zm-hint{display:none}.zm-r{max-height:12vh}.zm-c{min-height:150px}}
"""

ZJS = r"""
(function(){
document.documentElement.className = document.documentElement.className.replace('no-js','') + ' js';
var PAL=['#3987e5','#d95926','#199e70','#c98500','#d55181','#008300','#9085e9','#e66767'];
var MES=['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
var D=JSON.parse(document.getElementById('dz').textContent);
function fm(m){return MES[+m.slice(5,7)-1]+'-'+m.slice(2,4);}
function fn(v,d){if(v===null||v===undefined||isNaN(v))return '—';return v.toLocaleString('es-ES',{minimumFractionDigits:d,maximumFractionDigits:d});}
function back(m,k){var y=+m.slice(0,4),mo=+m.slice(5,7),t=y*12+mo-1-k;var mm=(t%12)+1;return Math.floor(t/12)+'-'+(mm<10?'0':'')+mm;}
function lbl(id){var x=D[id];if(!x)return id;return (S.spec&&S.spec.lb==='c'&&x.c)?x.c:x.n;}
/* pestañas */
var tabs=[].slice.call(document.querySelectorAll('nav [data-tab]'));
function show(id,scroll){tabs.forEach(function(b){var on=b.getAttribute('data-tab')===id;b.setAttribute('aria-selected',on?'true':'false');document.getElementById(id===b.getAttribute('data-tab')?id:b.getAttribute('data-tab')).className='page'+(on?' on':'');});
 try{history.replaceState(null,'','#'+id);}catch(e){} if(scroll)window.scrollTo(0,0);}
tabs.forEach(function(b){b.addEventListener('click',function(){show(b.getAttribute('data-tab'),true);});});
var h=location.hash.slice(1);show(tabs.some(function(b){return b.getAttribute('data-tab')===h;})?h:'pulso',false);
/* tema */
function ls(k,v){try{if(v===undefined)return localStorage.getItem(k);localStorage.setItem(k,v);}catch(e){return null;}}
var thb=document.getElementById('theme');function setTheme(m){if(m==='light')document.documentElement.setAttribute('data-theme','light');else document.documentElement.removeAttribute('data-theme');thb.textContent=m==='light'?'☾ Noche':'☀︎ Día';ls('mlv-theme',m);}
setTheme(ls('mlv-theme')==='light'?'light':'dark');thb.addEventListener('click',function(){setTheme(document.documentElement.getAttribute('data-theme')==='light'?'dark':'light');if(!zm.hidden)draw();});
/* Mi vista */
function favs(){try{return JSON.parse(ls('mlv-fav')||'[]');}catch(e){return [];}}
function renderFav(){var f=favs(),g=document.getElementById('mv-grid');g.innerHTML='';f.forEach(function(id){var c=document.querySelector('.page:not(#mivista) details[data-id="'+id+'"]');if(!c)return;var k=c.cloneNode(true);k.removeAttribute('id');k.open=false;g.appendChild(k);});
 document.getElementById('mv-empty').hidden=g.children.length>0;[].slice.call(document.querySelectorAll('[data-fav]')).forEach(function(b){var on=f.indexOf(b.getAttribute('data-fav'))>=0;b.setAttribute('aria-pressed',on?'true':'false');b.textContent=on?'★':'☆';});bindZoom(g);}
document.addEventListener('click',function(e){var b=e.target.closest?e.target.closest('[data-fav]'):null;if(!b)return;e.preventDefault();e.stopPropagation();var id=b.getAttribute('data-fav'),f=favs(),i=f.indexOf(id);if(i>=0)f.splice(i,1);else f.push(id);ls('mlv-fav',JSON.stringify(f));renderFav();},true);
/* ir a un cromo desde "lo que más se ha movido" */
[].slice.call(document.querySelectorAll('[data-goto]')).forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();var c=document.querySelector('#pulso details[data-id="'+a.getAttribute('data-goto')+'"]')||document.querySelector('details[data-id="'+a.getAttribute('data-goto')+'"]');if(!c)return;var pg=c.closest('.page');if(pg)show(pg.id,false);c.open=true;c.scrollIntoView({block:'start'});window.scrollBy(0,-56);});});
/* filtros de agenda */
[].slice.call(document.querySelectorAll('#ag-f .chip')).forEach(function(b){b.addEventListener('click',function(){var f=b.getAttribute('data-f');[].slice.call(document.querySelectorAll('#ag-f .chip')).forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});
 [].slice.call(document.querySelectorAll('.ev')).forEach(function(ev){ev.hidden=!(f===''||(f==='alta'?ev.getAttribute('data-r')==='alta':ev.getAttribute('data-t')===f));});});});
/* gráfico ampliado */
var zm=document.getElementById('zm'),host=document.getElementById('zm-c'),chips=document.getElementById('zm-chips'),ro=document.getElementById('zm-r'),note=document.getElementById('zm-n');
var S={spec:null,sel:[],col:{},range:36,last:null};
function colorFor(id){if(S.col[id])return S.col[id];var used={};S.sel.forEach(function(x){if(S.col[x])used[S.col[x]]=1;});for(var i=0;i<PAL.length;i++){if(!used[PAL[i]]){S.col[id]=PAL[i];return PAL[i];}}return PAL[0];}
function open(spec){S.spec=spec;S.sel=spec.s.slice(0,8);S.col={};S.sel.forEach(colorFor);document.getElementById('zm-t').textContent=spec.t;zm.hidden=false;document.body.style.overflow='hidden';drawChips();draw();}
function close(){zm.hidden=true;document.body.style.overflow='';}
document.getElementById('zm-x').addEventListener('click',close);
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!zm.hidden)close();});
[].slice.call(document.querySelectorAll('#zm-rg button')).forEach(function(b){b.addEventListener('click',function(){S.range=+b.getAttribute('data-r');[].slice.call(document.querySelectorAll('#zm-rg button')).forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});draw();});});
function drawChips(){chips.innerHTML='';S.spec.p.forEach(function(id){if(!D[id])return;var b=document.createElement('button');b.type='button';b.className='chip';var on=S.sel.indexOf(id)>=0;b.setAttribute('aria-pressed',on?'true':'false');var i=document.createElement('i');if(on)i.style.background=colorFor(id);b.appendChild(i);b.appendChild(document.createTextNode(lbl(id)));
 b.addEventListener('click',function(){var k=S.sel.indexOf(id);if(k>=0){if(S.sel.length===1)return;S.sel.splice(k,1);delete S.col[id];}else{if(S.sel.length>=8){note.textContent='Máximo 8 series a la vez: quita alguna para añadir otra.';return;}S.sel.push(id);colorFor(id);}drawChips();draw();});chips.appendChild(b);});}
function draw(){var sel=S.sel.filter(function(id){return D[id];});if(!sel.length){host.innerHTML='';return;}
 var lastM='';sel.forEach(function(id){var p=D[id].p;if(p.length&&p[p.length-1][0]>lastM)lastM=p[p.length-1][0];});var cut=back(lastM,S.range);
 var units={};sel.forEach(function(id){units[D[id].u]=1;});var rebase=Object.keys(units).length>1;
 note.textContent=rebase?'Unidades distintas: se muestran como índice base 100 al inicio del periodo.':'';
 var ser=sel.map(function(id){var pts=D[id].p.filter(function(q){return q[0]>=cut;});if(rebase&&pts.length){var b0=pts[0][1];pts=pts.map(function(q){return [q[0],b0?q[1]/b0*100:null,q[1]];});}else{pts=pts.map(function(q){return [q[0],q[1],q[1]];});}return {id:id,c:S.col[id],p:pts.filter(function(q){return q[1]!==null;})};});
 var ms={};ser.forEach(function(s){s.p.forEach(function(q){ms[q[0]]=1;});});var months=Object.keys(ms).sort();if(months.length<2){host.innerHTML='<p style="padding:12px;color:#8798ad">Sin histórico suficiente.</p>';return;}
 var lo=Infinity,hi=-Infinity;ser.forEach(function(s){s.p.forEach(function(q){if(q[1]<lo)lo=q[1];if(q[1]>hi)hi=q[1];});});if(lo===hi){lo-=1;hi+=1;}
 var W=host.clientWidth,H=host.clientHeight;var raw=(hi-lo)/5,mag=Math.pow(10,Math.floor(Math.log(raw)/Math.LN10)),st=[1,2,2.5,5,10].map(function(m){return m*mag;}).filter(function(x){return x>=raw;})[0]||raw;
 var a=Math.floor(lo/st)*st,b=Math.ceil(hi/st)*st,ticks=[];for(var t=a;t<=b+st/2;t+=st)ticks.push(+t.toFixed(10));
 var dec=rebase?0:Math.min(D[sel[0]].d,2);var L=12+Math.max.apply(null,ticks.map(function(x){return fn(x,dec).length;}))*7.2,R=14,T=12,B=26;
 var X=function(m){return L+(W-L-R)*months.indexOf(m)/(months.length-1);},Y=function(v){return T+(H-T-B)*(1-(v-ticks[0])/((ticks[ticks.length-1]-ticks[0])||1));};
 var o='<svg viewBox="0 0 '+W+' '+H+'" width="'+W+'" height="'+H+'">';
 ticks.forEach(function(x){var y=Y(x);o+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y+'" y2="'+y+'" style="stroke:var(--grid)"/><text x="'+(L-6)+'" y="'+(y+4)+'" text-anchor="end" font-size="11" style="fill:var(--muted)" font-family="ui-monospace,Menlo,monospace">'+fn(x,dec)+'</text>';});
 var stp=Math.max(1,Math.ceil(months.length/Math.max(2,Math.floor((W-L-R)/62))));months.forEach(function(m,i){if(i%stp===0)o+='<text x="'+X(m)+'" y="'+(H-8)+'" text-anchor="'+(X(m)>W-R-26?'end':(X(m)<L+26?'start':'middle'))+'" font-size="11" style="fill:var(--muted)" font-family="ui-monospace,Menlo,monospace">'+fm(m)+'</text>';});
 ser.forEach(function(s){if(!s.p.length)return;var d='';s.p.forEach(function(q,i){var x=X(q[0]).toFixed(1),y=Y(q[1]).toFixed(1);d+=(i?(S.spec.st&&!rebase?'H'+x+'V'+y:'L'+x+','+y):'M'+x+','+y);});var lq=s.p[s.p.length-1];
  o+='<path d="'+d+'" fill="none" stroke="'+s.c+'" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/><circle cx="'+X(lq[0])+'" cy="'+Y(lq[1])+'" r="4" fill="'+s.c+'"/>';});
 o+='<line id="zm-rule" x1="0" x2="0" y1="'+T+'" y2="'+(H-B)+'" style="stroke:var(--muted)" stroke-dasharray="3 3" opacity="0"/></svg>';host.innerHTML=o;
 S.last={months:months,ser:ser,X:X,L:L,R:R,W:W,rebase:rebase};readout(months[months.length-1]);}
function readout(m){var z=S.last;if(!z)return;var rule=document.getElementById('zm-rule');if(rule){var x=z.X(m);rule.setAttribute('x1',x);rule.setAttribute('x2',x);rule.setAttribute('opacity','1');}
 var h='<span class="k">'+fm(m)+(z.rebase?' · índice base 100 (valor original)':'')+'</span>';z.ser.forEach(function(s){var q=null;for(var i=0;i<s.p.length;i++)if(s.p[i][0]===m)q=s.p[i];var d=D[s.id].d;
 h+='<span><i style="background:'+s.c+'"></i>'+lbl(s.id).replace(/[<>&]/g,'')+': '+(q?(z.rebase?fn(q[1],1)+' ('+fn(q[2],d)+')':fn(q[1],d)+' '+D[s.id].u):'—')+'</span>';});ro.innerHTML=h;}
function pick(e){var z=S.last;if(!z)return;var r=host.getBoundingClientRect();var x=(e.touches?e.touches[0].clientX:e.clientX)-r.left;var f=(x-z.L)/(z.W-z.L-z.R);var i=Math.round(f*(z.months.length-1));i=Math.max(0,Math.min(z.months.length-1,i));readout(z.months[i]);if(e.cancelable)e.preventDefault();}
host.addEventListener('touchstart',pick,{passive:false});host.addEventListener('touchmove',pick,{passive:false});host.addEventListener('mousemove',pick);
window.addEventListener('resize',function(){if(!zm.hidden)draw();});
function bindZoom(root){[].slice.call(root.querySelectorAll('[data-zoom]')).forEach(function(b){if(b._z)return;b._z=1;b.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();open(JSON.parse(b.getAttribute('data-zoom')));});});}
bindZoom(document);renderFav();
})();
"""

TABS = [("pulso", "Pulso"), ("mivista", "Mi vista"), ("markets", "Markets information"), ("regional", "Europa"), ("curvas", "Curvas"), ("agenda", "Agenda"), ("watchlist", "Watchlist"), ("noticias", "Top 10 noticias")]
TITLES = {"pulso": "Pulso de mercado", "mivista": "Mi vista", "markets": "Markets information", "regional": "Europa · España, Portugal, Francia y Países Bajos", "curvas": "Curvas monetarias", "agenda": "Agenda", "watchlist": "Watchlist", "noticias": "Top 10 noticias"}
BODY = {"pulso": pulso, "mivista": mivista, "markets": markets, "regional": regional, "curvas": curvas, "agenda": agenda, "watchlist": watch, "noticias": noticias}
navh = "".join(f'<button type="button" role="tab" data-tab="{k}" aria-selected="false">{esc(v)}</button>' for k, v in TABS)
pages = "".join(f'<div class="page on" id="{k}" role="tabpanel"><h1>{esc(TITLES[k])}</h1>{BODY[k]}<div class="endtab">Fin de «{esc(TITLES[k])}». Cambia de pestaña arriba para seguir.</div></div>' for k, _ in TABS)
ZM = """<div id="zm" class="zm" hidden role="dialog" aria-modal="true" aria-labelledby="zm-t">
<div class="zm-h"><b id="zm-t"></b><button type="button" class="x" id="zm-x">Cerrar ✕</button></div>
<div class="zm-ctl"><div class="seg" id="zm-rg"><button type="button" data-r="12" aria-pressed="false">1A</button><button type="button" data-r="24" aria-pressed="false">2A</button><button type="button" data-r="36" aria-pressed="true">3A</button></div><span id="zm-n"></span></div>
<div class="zm-c" id="zm-c"></div>
<div class="zm-r" id="zm-r"></div>
<p class="zm-hint">Toca o desliza el dedo sobre el gráfico para ver los valores de cada fecha. Gira el móvil para verlo más grande.</p>
<div class="zm-chips" id="zm-chips"></div>
</div>"""

page = f"""<!doctype html><html lang="es" class="no-js"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Monitor de liquidez y mercados</title><meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#0b1119">
<style>{CSS}{ZCSS}</style></head><body>
<header><h1>Monitor de liquidez y mercados</h1><div class="asof">Datos a <b>{esc(asof)}</b> · generado {esc(built)} (hora de Madrid) <button type="button" id="theme" class="thm" aria-label="Cambiar a modo día">☀︎ Día</button></div></header>
<div class="tape">{"".join(tape)}</div>
<nav role="tablist" aria-label="Pestañas">{navh}</nav>
{pages}
<footer>Datos de fuentes públicas (bancos centrales, administradores de índices, institutos estadísticos y, donde no hay fuente oficial abierta, agregadores que se indican en cada indicador). Se actualiza los días laborables a las 7:45, 12:58 y 17:45 (Madrid). Lecturas y resúmenes de noticias redactados por Claude; no constituyen recomendación de inversión. Los CDS por emisor y las curvas por rating requieren datos con licencia (S&amp;P Global/Markit, LSEG, Bloomberg).</footer>
{ZM}
<script type="application/json" id="dz">{DZJSON}</script>
<script>{ZJS}</script>
</body></html>"""

(OUT / "index.html").write_text(page)
print(f"index.html: {len(page) / 1024:.0f} KB · {len(U)} indicadores · {len(NEWS)} noticias · {len(RNEWS)} noticias regionales")
