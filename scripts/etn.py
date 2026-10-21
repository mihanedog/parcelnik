#!/usr/bin/env python3
"""ETN (Evidenca trga nepremičnin) → ploščice JSON za Parcelnik.

Vir: GURS, aplikacija Javni geodetski podatki (JGP), »Kupoprodajni posli za območje
Slovenije po letih« (CC BY 4.0). Prenos gre prek dveh javnih GET klicev JGP API-ja,
ki vrneta podpisan URL do ZIP-a s CSV-ji (POSLI, DELISTAVB, ZEMLJISCA, sifranti).

Izhod:  data/etn/{leto}/{cx}_{cy}.json   (mreža CELL m v D96/TM, EPSG:3794)
        data/etn/index.json               (leta, celice, datum, šifranti)
"""
import csv, io, json, os, re, sys, time, zipfile, urllib.request, urllib.parse
from collections import defaultdict
from datetime import date

API = "https://ipi.eprostor.gov.si/jgp-service-api"
GROUP, PRODUCT = 127, 321            # Kupoprodajni posli za območje Slovenije po letih
CELL = 10000                          # 10 km mreža
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "etn")
UA = {"User-Agent": "Parcelnik/1.0 (+https://github.com/mihanedog/parcelnik)"}

def get(url, binary=False, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read() if binary else r.read().decode("utf-8")
        except Exception as e:
            print("  retry", i, url[:120], e, file=sys.stderr); time.sleep(5 * (i + 1))
    raise RuntimeError("download failed: " + url)

def fetch_year(year):
    q = f"filterParam=DRZAVA&filterValue=1&filterYear={year}"
    meta = json.loads(get(f"{API}/display-views/groups/{GROUP}/composite-products/{PRODUCT}/result?{q}"))
    if meta.get("statusId") != 1:
        print(f"{year}: status {meta.get('statusText')}", file=sys.stderr); return None, None
    link = json.loads(get(f"{API}/display-views/groups/{GROUP}/composite-products/{PRODUCT}/file?{q}"))
    url = link["url"].replace("https://ipi.eprostor.gov.si:443", "https://ipi.eprostor.gov.si")
    return get(url, binary=True), meta["file"]["name"]

def read_csv(z, part):
    name = next(n for n in z.namelist() if part in n)
    txt = z.read(name).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(txt)))

def num(s):
    try: return float(s) if s not in ("", None) else None
    except ValueError: return None

def d(s):  # 15.02.2026 -> 2026-02-15
    m = re.match(r"(\d\d)\.(\d\d)\.(\d{4})", s or ""); return f"{m[3]}-{m[2]}-{m[1]}" if m else None

def build(year, blob, sifranti_out):
    z = zipfile.ZipFile(io.BytesIO(blob))
    posli = {r["ID_POSLA"]: r for r in read_csv(z, "_POSLI_")}
    deli = read_csv(z, "_DELISTAVB_")
    zem = read_csv(z, "_ZEMLJISCA_")
    sif = read_csv(z, "_sifranti_")
    for r in sif:
        sifranti_out.setdefault(r["SIFRANT"], {})[r["NUMERICNA_VREDNOST"]] = r["OPIS"]
    vz = {r["NUMERICNA_VREDNOST"]: r["OPIS"] for r in sif if r["SIFRANT"] == "Vrsta zemljišča"}

    # koliko nepremičnin ima posel (za €/m² in oznako »paket«)
    cnt = defaultdict(int); area = defaultdict(float)
    for r in deli:
        cnt[r["ID_POSLA"]] += 1; area[r["ID_POSLA"]] += num(r["PRODANA_POVRSINA"]) or 0
    for r in zem:
        cnt[r["ID_POSLA"]] += 1; area[r["ID_POSLA"]] += num(r["POVRSINA_PARCELE"]) or 0

    cells = defaultdict(list)
    def put(e, n, rec):
        if e is None or n is None: return
        cells[(int(e // CELL), int(n // CELL))].append(rec)

    for r in deli:
        p = posli.get(r["ID_POSLA"]);
        if not p: continue
        cena_posla = num(p["POGODBENA_CENA_ODSKODNINA"]); cena_dela = num(r["POGODBENA_CENA_DELA_STAVBE"])
        pov = num(r["PRODANA_POVRSINA"]) or num(r["POVRSINA_DELA_STAVBE"])
        n = cnt[r["ID_POSLA"]]
        cena = cena_dela if cena_dela else (cena_posla if n == 1 else None)
        m2 = round(cena / pov) if cena and pov else None
        raba = (r["DEJANSKA_RABA_DELA_STAVBE"] or "").strip()
        put(num(r["E_CENTROID"]), num(r["N_CENTROID"]), {
            "t": "s", "id": int(r["ID_POSLA"]), "ko": r["SIFRA_KO"], "kon": r["IME_KO"], "ob": r["OBCINA"],
            "st": r["STEVILKA_STAVBE"], "ds": r["STEVILKA_DELA_STAVBE"],
            "nas": " ".join(x for x in [r["ULICA"] or r["NASELJE"], (r["HISNA_STEVILKA"] or "") + (r["DODATEK_HS"] or "")] if x).strip(),
            "raba": raba, "leto_i": r["LETO_IZGRADNJE_DELA_STAVBE"] or None, "nad": r["NADSTROPJE_DELA_STAVBE"] or None,
            "sobe": r["STEVILO_SOB"] or None, "pov": pov, "upov": num(r["PRODANA_UPORABNA_POVRSINA_DELA_STAVBE"]) or num(r["UPORABNA_POVRSINA"]),
            "novo": r["NOVOGRADNJA"] == "1", "delez": r["PRODANI_DELEZ_DELA_STAVBE"] or None,
            "cena": cena, "cena_posla": cena_posla, "m2": m2, "n": n, "pov_posla": round(area[r["ID_POSLA"]]) if n > 1 else None,
            "dat": d(p["DATUM_SKLENITVE_POGODBE"]), "vp": p["VRSTA_KUPOPRODAJNEGA_POSLA"], "trz": p["TRZNOST_POSLA"],
            "ddv": p["VKLJUCENOST_DDV"] == "1", "ag": p["POSREDOVANJE_NEPREMICNINSKE_AGENCIJE"] == "1",
            "op": (p["OPOMBE_O_PRAVNEM_POSLU"] or r["OPOMBE_O_NEPREMICNINI"] or "")[:200] or None,
            "e": num(r["E_CENTROID"]), "nn": num(r["N_CENTROID"]),
        })
    for r in zem:
        p = posli.get(r["ID_POSLA"]);
        if not p: continue
        cena_posla = num(p["POGODBENA_CENA_ODSKODNINA"]); cena_p = num(r["POGODBENA_CENA_PARCELE"])
        pov = num(r["POVRSINA_PARCELE"]); n = cnt[r["ID_POSLA"]]
        cena = cena_p if cena_p else (cena_posla if n == 1 else None)
        m2 = round(cena / pov, 2) if cena and pov else None
        put(num(r["E_CENTROID"]), num(r["N_CENTROID"]), {
            "t": "z", "id": int(r["ID_POSLA"]), "ko": r["SIFRA_KO"], "kon": r["IME_KO"], "ob": r["OBCINA"],
            "parc": r["PARCELNA_STEVILKA"], "vz": r["VRSTA_ZEMLJISCA"], "vzn": vz.get(r["VRSTA_ZEMLJISCA"], ""),
            "nasad": r["VRSTA_TRAJNEGA_NASADA"] or None, "pov": pov, "delez": r["PRODANI_DELEZ_PARCELE"] or None,
            "cena": cena, "cena_posla": cena_posla, "m2": m2, "n": n, "pov_posla": round(area[r["ID_POSLA"]]) if n > 1 else None,
            "dat": d(p["DATUM_SKLENITVE_POGODBE"]), "vp": p["VRSTA_KUPOPRODAJNEGA_POSLA"], "trz": p["TRZNOST_POSLA"],
            "ddv": p["VKLJUCENOST_DDV"] == "1", "ag": p["POSREDOVANJE_NEPREMICNINSKE_AGENCIJE"] == "1",
            "op": (p["OPOMBE_O_PRAVNEM_POSLU"] or r["OPOMBE_O_NEPREMICNINI"] or "")[:200] or None,
            "e": num(r["E_CENTROID"]), "nn": num(r["N_CENTROID"]),
        })
    return cells, len(posli), len(deli), len(zem)

def main():
    years = [int(y) for y in sys.argv[1:]] or list(range(date.today().year - 4, date.today().year + 1))
    os.makedirs(OUT, exist_ok=True)
    idx_path = os.path.join(OUT, "index.json")
    index = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {"years": {}, "sifranti": {}, "cell": CELL}
    sifranti = index.get("sifranti", {})
    for y in years:
        print("ETN", y, "…", flush=True)
        blob, fname = fetch_year(y)
        if not blob: continue
        cells, np_, nd, nz = build(y, blob, sifranti)
        ydir = os.path.join(OUT, str(y))
        os.makedirs(ydir, exist_ok=True)
        for f in os.listdir(ydir): os.remove(os.path.join(ydir, f))
        for (cx, cy), recs in cells.items():
            with open(os.path.join(ydir, f"{cx}_{cy}.json"), "w", encoding="utf-8") as f:
                json.dump(recs, f, ensure_ascii=False, separators=(",", ":"))
        index["years"][str(y)] = {"file": fname, "posli": np_, "deli_stavb": nd, "zemljisca": nz, "cells": sorted(f"{cx}_{cy}" for cx, cy in cells)}
        print(f"  {np_} poslov, {nd} delov stavb, {nz} zemljišč, {len(cells)} celic", flush=True)
    index["sifranti"] = sifranti; index["cell"] = CELL; index["updated"] = date.today().isoformat()
    index["source"] = "GURS – Evidenca trga nepremičnin (JGP), CC BY 4.0"
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

if __name__ == "__main__":
    main()
