#!/usr/bin/env python3
"""Descarga datos de mercado de fuentes oficiales con API pública y los deja en mercado/auto.json.

Lo ejecuta GitHub Actions (.github/workflows/datos.yml). Solo datos públicos: NY Fed, BCE y FRED.
FRED necesita la clave gratuita en la variable FRED_API_KEY; sin ella se omite.
build_site.py fusiona mercado/auto.json con los datos de la web (solo valores más recientes).
"""
import csv, io, json, os, sys, urllib.request, urllib.parse, datetime, pathlib

OUT = pathlib.Path(__file__).resolve().parent / "mercado" / "auto.json"
UA = {"User-Agent": "monitor-liquidez/1.0 (GitHub Actions)", "Accept": "*/*"}
LOG = []


def get(url, params=None, timeout=40):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


SER = {}


def put(sid, date, value, source, url, nd=None):
    if value is None:
        return
    v = float(value)
    if nd is not None:
        v = round(v, nd)
    SER.setdefault(sid, {"source": source, "source_url": url, "obs": {}})["obs"][str(date)[:10]] = v


def step(name, fn):
    try:
        n0 = sum(len(s["obs"]) for s in SER.values())
        fn()
        LOG.append(f"{name}: ok (+{sum(len(s['obs']) for s in SER.values()) - n0})")
    except Exception as e:  # una fuente caída no detiene las demás
        LOG.append(f"{name}: ERROR {type(e).__name__}: {e}")


# ---------- New York Fed ----------
NYF = "https://markets.newyorkfed.org"


def nyfed_rates():
    for kind in ("sofr", "effr", "sofrai"):
        grp = "secured" if kind in ("sofr", "sofrai") else "unsecured"
        d = json.loads(get(f"{NYF}/api/rates/{grp}/{kind}/last/10.json"))
        for r in d.get("refRates", []):
            dt = r.get("effectiveDate")
            if kind == "sofr":
                put("sofr", dt, r.get("percentRate"), "Federal Reserve Bank of New York (API)", "https://www.newyorkfed.org/markets/reference-rates/sofr", 2)
            elif kind == "effr":
                put("effr", dt, r.get("percentRate"), "Federal Reserve Bank of New York (API)", "https://www.newyorkfed.org/markets/reference-rates/effr", 2)
            else:
                put("sofr_avg_30d", dt, r.get("average30day"), "Federal Reserve Bank of New York (API)", "https://www.newyorkfed.org/markets/reference-rates/sofr-averages-and-index", 5)
                put("sofr_avg_90d", dt, r.get("average90day"), "Federal Reserve Bank of New York (API)", "https://www.newyorkfed.org/markets/reference-rates/sofr-averages-and-index", 5)


def nyfed_ops():
    d = json.loads(get(f"{NYF}/api/rp/all/all/results/last/12.json"))
    tot = {}
    for op in d.get("repo", {}).get("operations", []):
        t = (op.get("operationType") or "").lower()
        sid = "rrp_us" if "reverse" in t else ("srf_fed" if "repo" in t else None)
        if not sid:
            continue
        k = (sid, op.get("operationDate"))
        tot[k] = tot.get(k, 0.0) + float(op.get("totalAmtAccepted") or 0)
    for (sid, dt), amt in tot.items():
        put(sid, dt, amt / 1e9, "Federal Reserve Bank of New York (API de operaciones)", "https://www.newyorkfed.org/markets/desk-operations/" + ("reverse-repo" if sid == "rrp_us" else "repo"), 3)


# ---------- BCE (ECB Data Portal) ----------
ECB = "https://data-api.ecb.europa.eu/service/data/"


def ecb_csv(flow_key, n=15):
    t = get(ECB + flow_key, {"lastNObservations": n, "format": "csvdata"})
    return list(csv.DictReader(io.StringIO(t)))


def ecb_estr():
    for r in ecb_csv("EST/B.EU000A2X2A25.WT"):
        put("estr", r["TIME_PERIOD"], r["OBS_VALUE"], "BCE (ECB Data Portal)", "https://data.ecb.europa.eu/data/datasets/EST/EST.B.EU000A2X2A25.WT", 3)


def ecb_fx():
    rows = ecb_csv("EXR/D.USD+GBP+BRL+MXN.EUR.SP00.A")
    by = {}
    for r in rows:
        if r.get("OBS_VALUE"):
            by.setdefault(r["TIME_PERIOD"], {})[r["CURRENCY"]] = float(r["OBS_VALUE"])
    src, url = "BCE, tipos de referencia", "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"
    for dt, x in by.items():
        if "USD" in x:
            put("eurusd", dt, x["USD"], src, url, 4)
            if "GBP" in x:
                put("gbpeur", dt, 1 / x["GBP"], src + " (inverso de EUR/GBP)", url, 4)
                put("gbpusd", dt, x["USD"] / x["GBP"], src + " (cruce EUR/USD ÷ EUR/GBP)", url, 4)
            if "BRL" in x:
                put("usdbrl", dt, x["BRL"] / x["USD"], src + " (cruce EUR/BRL ÷ EUR/USD)", url, 4)
            if "MXN" in x:
                put("usdmxn", dt, x["MXN"] / x["USD"], src + " (cruce EUR/MXN ÷ EUR/USD)", url, 4)


def ecb_ilm():
    src, url = "BCE, estado financiero semanal (ECB Data Portal)", "https://data.ecb.europa.eu/data/datasets/ILM"
    for sid, key in (("dfr_recourse_ecb", "ILM/W.U2.C.L020200.U2.EUR"), ("mro_ecb", "ILM/W.U2.C.A050100.U2.EUR"), ("ltro_ecb", "ILM/W.U2.C.A050200.U2.EUR")):
        for r in ecb_csv(key, 6):
            tp = r["TIME_PERIOD"]
            if "-W" in tp:  # semana ISO → viernes de esa semana (fecha del estado financiero)
                y, w = tp.split("-W")
                tp = datetime.date.fromisocalendar(int(y), int(w), 5).isoformat()
            put(sid, tp, float(r["OBS_VALUE"]) / 1000, src, url, 3)


# ---------- FRED ----------
FRED = {
    # id: (serie, factor, decimales)
    "y10_us": ("DGS10", 1, 3), "tbill_us_3m": ("DTB3", 1, 2), "tbill_us_6m": ("DTB6", 1, 2), "tbill_us_1y": ("DTB1YR", 1, 2),
    "breakeven_10y_us": ("T10YIE", 1, 2), "brent_spot": ("DCOILBRENTEU", 1, 2),
    "oas_us_aa": ("BAMLC0A2CAA", 100, 0), "oas_us_a": ("BAMLC0A3CA", 100, 0), "oas_us_bbb": ("BAMLC0A4CBBB", 100, 0),
    "oas_us_bb": ("BAMLH0A1HYBB", 100, 0), "oas_us_b": ("BAMLH0A2HYB", 100, 0), "oas_us_ig": ("BAMLC0A0CM", 100, 0),
    "oas_us_hy": ("BAMLH0A0HYM2", 100, 0), "oas_eur_hy": ("BAMLHE00EHYIOAS", 100, 0), "oas_em": ("BAMLEMCBPIOAS", 100, 0),
    "oas_em_hg": ("BAMLEMIBHGCRPIOAS", 100, 0), "oas_em_hy": ("BAMLEMHBHYCRPIOAS", 100, 0),
    "reserves_us": ("WRESBAL", 0.001, 2), "tga_us": ("WTREGEN", 0.001, 3), "fed_assets": ("WALCL", 0.001, 3),
}


def fed_policy():
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise RuntimeError("falta FRED_API_KEY")
    for sid, ser in (("fed_upper", "DFEDTARU"), ("fed_lower", "DFEDTARL"), ("iorb", "IORB")):
        d = json.loads(get("https://api.stlouisfed.org/fred/series/observations", {"series_id": ser, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 5}))
        for o in d.get("observations", []):
            if o.get("value") not in (None, "", "."):
                put(sid, o["date"], o["value"], f"Federal Reserve vía FRED ({ser})", f"https://fred.stlouisfed.org/series/{ser}", 2)


def fred():
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise RuntimeError("falta FRED_API_KEY (secreto de GitHub); se omite FRED")
    for sid, (s, f, nd) in FRED.items():
        try:
            d = json.loads(get("https://api.stlouisfed.org/fred/series/observations", {"series_id": s, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 10}))
            for o in d.get("observations", []):
                if o.get("value") not in (None, "", "."):
                    put(sid, o["date"], float(o["value"]) * f, f"FRED ({s})", f"https://fred.stlouisfed.org/series/{s}", nd)
        except Exception as e:
            LOG.append(f"  FRED {s}: ERROR {e}")


# ---------- Eurostat (IPCA, PIB, paro) ----------
EST = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"


def eurostat(dataset, params):
    q = dict(params)
    q.update({"format": "JSON", "lang": "EN"})
    d = json.loads(get(EST + dataset, q))
    tdim = d["dimension"]["time"]["category"]["index"]
    pos = {v: k for k, v in tdim.items()}
    out = []
    for k, v in d.get("value", {}).items():
        t = pos.get(int(k))
        if t is not None and v is not None:
            if "-Q" in t:  # trimestre → último mes del trimestre
                y, q_ = t.split("-Q")
                t = f"{y}-{int(q_) * 3:02d}"
            out.append((t, v))
    return sorted(out)


def eurostat_all():
    since = (datetime.date.today() - datetime.timedelta(days=500)).strftime("%Y-%m")
    hicp = [("cpi_ea", "EA", "TOTAL"), ("core_ea", "EA", "TOT_X_NRG_FOOD"), ("cpi_pt", "PT", "TOTAL"), ("core_pt", "PT", "TOT_X_NRG_FOOD"),
            ("cpi_fr", "FR", "TOTAL"), ("core_fr", "FR", "TOT_X_NRG_FOOD"), ("cpi_nl", "NL", "TOTAL"), ("core_nl", "NL", "TOT_X_NRG_FOOD"),
            ("core_de", "DE", "TOT_X_NRG_FOOD")]
    for sid, geo, c in hicp:
        try:
            for t, v in eurostat("prc_hicp_minr", {"geo": geo, "unit": "RCH_A", "coicop18": c, "sinceTimePeriod": since}):
                put(sid, t, v, "Eurostat (IPCA)", f"{EST}prc_hicp_minr?geo={geo}&unit=RCH_A&coicop18={c}&lang=EN", 1)
        except Exception as e:
            LOG.append(f"  Eurostat {sid}: ERROR {e}")
    for sid, geo in (("gdp_fr", "FR"), ("gdp_pt", "PT"), ("gdp_nl", "NL")):
        try:
            for t, v in eurostat("namq_10_gdp", {"geo": geo, "unit": "CLV_PCH_SM", "s_adj": "SCA", "na_item": "B1GQ", "sinceTimePeriod": "2024-Q1"}):
                put(sid, t, v, "Eurostat (PIB trimestral, tasa interanual)", f"{EST}namq_10_gdp?geo={geo}&unit=CLV_PCH_SM&s_adj=SCA&na_item=B1GQ&lang=EN", 1)
        except Exception as e:
            LOG.append(f"  Eurostat {sid}: ERROR {e}")
    for sid, geo in (("unemp_pt", "PT"), ("unemp_nl", "NL")):
        try:
            for t, v in eurostat("une_rt_m", {"geo": geo, "unit": "PC_ACT", "s_adj": "SA", "age": "TOTAL", "sex": "T", "sinceTimePeriod": since}):
                put(sid, t, v, "Eurostat (paro desestacionalizado)", f"{EST}une_rt_m?geo={geo}&unit=PC_ACT&s_adj=SA&age=TOTAL&sex=T&lang=EN", 1)
        except Exception as e:
            LOG.append(f"  Eurostat {sid}: ERROR {e}")


# ---------- BCE: tipos bancarios (MIR), depósitos de empresas (BSI) y tipos oficiales ----------
def ecb_mir():
    keys = [
        ("loan_rate_nfc_nl", "MIR/M.NL.B.A2I.AM.R.A.2240.EUR.N", "BCE MIR (préstamos nuevos a empresas, coste compuesto)"),
        ("dep_rate_nl", "MIR/M.NL.B.L22.F.R.A.2240.EUR.N", "BCE MIR (depósitos a plazo nuevos de empresas, hasta 1 año)"),
    ]
    for sid, key, src in keys:
        try:
            for r in ecb_csv(key, 14):
                if r.get("OBS_VALUE"):
                    put(sid, r["TIME_PERIOD"], r["OBS_VALUE"], src, "https://data.ecb.europa.eu/data/datasets/MIR/" + key.replace("/", "."), 2)
        except Exception as e:
            LOG.append(f"  BCE {key}: ERROR {e}")
    for sid, cc in (("nfc_deposits_nl", "NL"), ("nfc_deposits_fr", "FR"), ("nfc_deposits_pt", "PT")):
        for key in (f"BSI/M.{cc}.N.A.L20.A.I.{cc}.2240.Z01.A", f"BSI/M.{cc}.N.A.L20.A.I.U2.2240.Z01.A"):
            try:
                rows = [r for r in ecb_csv(key, 14) if r.get("OBS_VALUE")]
                if rows:
                    for r in rows:
                        put(sid, r["TIME_PERIOD"], r["OBS_VALUE"], "BCE BSI (depósitos de empresas, tasa interanual)", "https://data.ecb.europa.eu/data/datasets/BSI/" + key.replace("BSI/", "BSI."), 1)
                    break
            except Exception as e:
                LOG.append(f"  BCE {key}: ERROR {e}")


def ecb_key_rates():
    for sid, key in (("ecb_dfr", "FM/B.U2.EUR.4F.KR.DFR.LEV"), ("ecb_mro", "FM/B.U2.EUR.4F.KR.MRR_FR.LEV"), ("ecb_mlf", "FM/B.U2.EUR.4F.KR.MLFR.LEV")):
        for r in ecb_csv(key, 5):
            if r.get("OBS_VALUE"):
                put(sid, r["TIME_PERIOD"], r["OBS_VALUE"], "BCE (ECB Data Portal)", "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/key_ecb_interest_rates/html/index.en.html", 2)


# ---------- Banco de Portugal (BPstat) ----------
def bpstat():
    for sid, ds, ser in (("loan_rate_nfc_pt", "9ab0b6dd481ff9d0a79aeca89363b9ec", "12533748"), ("dep_rate_pt", "ec7b2a0f066656833f1013b3a2f9f189", "12519736")):
        url = f"https://bpstat.bportugal.pt/data/v1/domains/21/datasets/{ds}"
        try:
            d = json.loads(get(url, {"lang": "EN", "series_ids": ser, "obs_since": "2024-06-01"}))
            dims = d.get("dimension", {})
            tkey = next((k for k in d.get("id", []) if "date" in k.lower() or "time" in k.lower()), None)
            if not tkey:
                raise RuntimeError(f"estructura no reconocida: id={d.get('id')}")
            cats = dims[tkey]["category"]["index"]
            order = sorted(cats, key=lambda c: cats[c]) if isinstance(cats, dict) else cats
            vals = d.get("value", [])
            if isinstance(vals, dict):
                vals = [vals.get(str(i)) for i in range(len(order))]
            for t, v in zip(order, vals):
                if v is not None:
                    put(sid, str(t)[:7], v, "Banco de Portugal (BPstat)", f"{url}?lang=EN&series_ids={ser}", 2)
        except Exception as e:
            LOG.append(f"  BPstat {sid}: ERROR {e}")


# ---------- Banco de España (Boletín Estadístico, cap. 19) ----------
BDE = "https://www.bde.es/webbe/es/estadisticas/compartido/datos/csv/"
MESES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}


def bde_csv(name):
    raw = urllib.request.urlopen(urllib.request.Request(BDE + name, headers=UA), timeout=40).read()
    try:
        t = raw.decode("utf-8")
    except UnicodeDecodeError:
        t = raw.decode("latin-1")
    rows = list(csv.reader(io.StringIO(t)))
    head = [r for r in rows[:8]]
    data = []
    for r in rows:
        if not r:
            continue
        m = r[0].strip().upper().replace('"', "")
        parts = m.split()
        if len(parts) == 2 and parts[0][:3] in MESES and parts[1].isdigit():
            data.append((f"{parts[1]}-{MESES[parts[0][:3]]:02d}", r))
    return head, data


def bde():
    targets = {
        # id: (csv, palabras que deben estar en la descripción de la columna)
        "loan_rate_nfc_es": ("be1903.csv", ["sociedades no financieras"]),
        "dep_rate_nfc_es": ("be1907.csv", ["sociedades no financieras", "plazo"]),
        "dep_rate_hh_es": ("be1907.csv", ["hogares", "plazo"]),
    }
    cache = {}
    for sid, (f, words) in targets.items():
        try:
            if f not in cache:
                cache[f] = bde_csv(f)
            head, data = cache[f]
            ncol = max(len(r) for r in head)
            desc = [" ".join((h[c] if c < len(h) else "") for h in head).lower() for c in range(ncol)]
            cols = [c for c in range(1, ncol) if all(w in desc[c] for w in words)]
            if not cols:
                LOG.append(f"  BdE {sid}: columna no encontrada; cabeceras: " + " || ".join(d[:120] for d in desc[:12]))
                continue
            c = cols[0]
            LOG.append(f"  BdE {sid}: columna {c} «{desc[c][:160]}»")
            for t, r in data[-14:]:
                v = r[c].strip().replace(",", ".") if c < len(r) else ""
                try:
                    put(sid, t, float(v), "Banco de España (Boletín Estadístico, cap. 19)", BDE + f, 3)
                except ValueError:
                    pass
        except Exception as e:
            LOG.append(f"  BdE {sid}: ERROR {e}")


# ---------- Bank of England (SONIA y Bank Rate) ----------
def boe():
    start = (datetime.date.today() - datetime.timedelta(days=20)).strftime("%d/%b/%Y")
    t = get("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp",
            {"csv.x": "yes", "Datefrom": start, "Dateto": "now", "SeriesCodes": "IUDSOIA,IUDBEDR", "CSVF": "TN", "UsingCodes": "Y", "VPD": "Y", "VFD": "N"})
    rows = list(csv.reader(io.StringIO(t)))
    if not rows or "DATE" not in rows[0][0].upper():
        raise RuntimeError("respuesta inesperada: " + t[:120].replace("\n", " "))
    hdr = [h.strip().upper() for h in rows[0]]
    for r in rows[1:]:
        if len(r) < len(hdr):
            continue
        dt = datetime.datetime.strptime(r[0].strip(), "%d %b %Y").date().isoformat()
        for code, sid, nd in (("IUDSOIA", "sonia", 4), ("IUDBEDR", "boe_bank_rate", 2)):
            if code in hdr and r[hdr.index(code)].strip():
                put(sid, dt, r[hdr.index(code)], "Bank of England (base de datos)", "https://www.bankofengland.co.uk/boeapps/database/", nd)


# ---------- IPC de EE. UU. (tasa interanual desde el índice de FRED) ----------
def us_cpi():
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise RuntimeError("falta FRED_API_KEY")
    for sid, s in (("cpi_us", "CPIAUCNS"), ("core_us", "CPILFENS")):
        d = json.loads(get("https://api.stlouisfed.org/fred/series/observations", {"series_id": s, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 30}))
        idx = {o["date"][:7]: float(o["value"]) for o in d.get("observations", []) if o.get("value") not in (None, "", ".")}
        for m, v in idx.items():
            y, mo = m.split("-")
            prev = idx.get(f"{int(y) - 1}-{mo}")
            if prev:
                put(sid, m, (v / prev - 1) * 100, f"BLS vía FRED ({s}), tasa interanual", f"https://fred.stlouisfed.org/series/{s}", 1)


def main():
    step("NY Fed tipos", nyfed_rates)
    step("NY Fed operaciones", nyfed_ops)
    step("BCE €STR", ecb_estr)
    step("BCE divisas", ecb_fx)
    step("BCE balance semanal", ecb_ilm)
    step("FRED", fred)
    step("FRED tipos oficiales de la Fed", fed_policy)
    step("IPC EE. UU.", us_cpi)
    step("BCE tipos oficiales", ecb_key_rates)
    step("BCE tipos bancarios y depósitos", ecb_mir)
    step("Eurostat", eurostat_all)
    step("Banco de Portugal", bpstat)
    step("Banco de España", bde)
    step("Bank of England", boe)
    out = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "log": LOG, "series": {}}
    for sid, s in sorted(SER.items()):
        obs = sorted(s["obs"].items())[-14:]
        out["series"][sid] = {"source": s["source"], "source_url": s["source_url"], "obs": [{"date": d, "value": v} for d, v in obs]}
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text())
        except Exception:
            pass
    # Conserva series que hoy no se hayan podido descargar
    for sid, s in old.get("series", {}).items():
        if all(len(str(o.get("date", ""))) == 10 for o in s.get("obs", [])):
            out["series"].setdefault(sid, s)
    OUT.parent.mkdir(exist_ok=True)
    changed = json.dumps(old.get("series"), sort_keys=True) != json.dumps(out["series"], sort_keys=True)
    if changed:
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print("\n".join(LOG))
    print(f"{len(out['series'])} series · {'cambios' if changed else 'sin cambios'}")


if __name__ == "__main__":
    main()
