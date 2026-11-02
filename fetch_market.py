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


def main():
    step("NY Fed tipos", nyfed_rates)
    step("NY Fed operaciones", nyfed_ops)
    step("BCE €STR", ecb_estr)
    step("BCE divisas", ecb_fx)
    step("BCE balance semanal", ecb_ilm)
    step("FRED", fred)
    out = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "log": LOG, "series": {}}
    for sid, s in sorted(SER.items()):
        obs = sorted(s["obs"].items())[-10:]
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
