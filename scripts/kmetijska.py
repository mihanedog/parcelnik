#!/usr/bin/env python3
"""Ponudbe za prodajo kmetijskih zemljišč, kmetij in gozdov (ZKZ, 20. člen) z oglasne
deske e-uprave → data/kmetijska.geojson za Parcelnik.

Vir: https://e-uprava.gov.si/si/e-uprava/oglasnadeska.html (vrsta objave PKZ).
Upravne enote objavljajo skenirane PDF-je, zato gre besedilo skozi OCR (tesseract, slv).
Iz besedila izluščimo k.o., parcele, ceno, površino; parcele geokodiramo prek javnega
WFS GURS (kataster nepremičnin). Vsa polja iz OCR so označena (ocr: true) in so informativna;
merodajen je PDF.
"""
import json, os, re, sys, time, subprocess, tempfile, html, unicodedata
import urllib.request, urllib.parse
from datetime import date, datetime, timedelta

BASE = "https://e-uprava.gov.si"
LIST = BASE + "/si/e-uprava/oglasnadeska.html?lang=si&type=PKZ&perioda=-&rijs=-1&is_ajax=1&offset={}"
DETAIL = BASE + "/si/e-uprava/oglasnadeska/podrobnosti-objave.html?id={}"
WFS = "https://ipi.eprostor.gov.si/wfs-si-gurs-kn/wfs"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "kmetijska.geojson")
CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "kmetijska_cache.json")
UA = {"User-Agent": "Parcelnik/1.0 (+https://github.com/mihanedog/parcelnik)"}
MAX_NEW = int(os.environ.get("MAX_NEW", "120"))   # največ novih PDF-jev na en zagon (OCR je počasen)

def get(url, binary=False, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read() if binary else r.read().decode("utf-8", "replace")
        except Exception as e:
            print("  retry", i, url[:100], e, file=sys.stderr); time.sleep(3 * (i + 1))
    return None

def strip(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def list_offers():
    """Vrne {id: {title, subtitle, ue, published}} za vse aktivne PKZ objave."""
    out, off = {}, 0
    while True:
        page = get(LIST.format(off))
        if not page: break
        items = re.findall(r'<a href="/si/e-uprava/oglasnadeska/podrobnosti-objave\.html\?id=(\d+)">(.*?)</a>(.*?)(?=<a href="/si/e-uprava/oglasnadeska/podrobnosti-objave|$)', page, re.S)
        if not items: break
        for oid, title, rest in items:
            txt = strip(rest)
            m_pub = re.search(r"Objavljeno:\s*(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})", txt)
            # institucija stoji pred naslovom; vzamemo iz širšega konteksta
            pre = page[: page.find(f"id={oid}")][-600:]
            m_ue = re.findall(r"Upravna enota [^<]+", strip(pre))
            out[oid] = {"title": strip(title), "sub": txt.split("Objavljeno")[0].strip()[:200],
                        "ue": m_ue[-1].strip() if m_ue else None,
                        "pub": m_pub[1].replace(" ", "") if m_pub else None}
        off += 50
        if off > 3000: break
    return out

def detail(oid):
    h = get(DETAIL.format(oid))
    if not h: return None
    m = re.search(r'href="(/\.download/oglasna/datoteka\?file=\d+[^"]*)"', h)
    txt = strip(h)
    dates = re.search(r"(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})\s*\(objava do\s*(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})", txt)
    doc = re.search(r"Št\. dokumenta\s*([\w\-/ ]+?)\s+Datum", txt)
    inst = re.search(r"Institucija\s*(.+?)\s+Št\. dokumenta", txt)
    return {"pdf": BASE + html.unescape(m[1]) if m else None,
            "pub": dates[1].replace(" ", "") if dates else None, "do": dates[2].replace(" ", "") if dates else None,
            "doc": doc[1].strip() if doc else None, "ue": inst[1].strip() if inst else None}

def ocr(pdf_bytes):
    with tempfile.TemporaryDirectory() as td:
        pdf = os.path.join(td, "p.pdf"); open(pdf, "wb").write(pdf_bytes)
        # najprej poskusi besedilo (nekateri PDF-ji ga imajo)
        try:
            t = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, timeout=60).stdout
            if len(re.sub(r"\s", "", t)) > 200: return t, False
        except Exception: pass
        subprocess.run(["pdftoppm", "-r", "200", "-gray", "-f", "1", "-l", "4", "-png", pdf, os.path.join(td, "pg")], timeout=180)
        txt = ""
        for f in sorted(os.listdir(td)):
            if f.endswith(".png"):
                r = subprocess.run(["tesseract", os.path.join(td, f), "-", "-l", "slv", "--psm", "6"], capture_output=True, text=True, timeout=180)
                txt += r.stdout + "\n"
        return txt, True

def norm(s): return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()

PARC_RE = re.compile(r"(?:parc(?:ela|\.|elna)?\s*(?:št\.?|st\.?|številka|stevilka)?\s*[:.]?\s*)((?:\*?\d{1,5}(?:/\d{1,4})?\s*[,;]?\s*(?:in|ter)?\s*){1,40})", re.I)

def parse(text, title, sub):
    t = text.replace(" ", " ")
    # k.o. – iz naslova/podnaslova ali besedila: "k.o. 1039 Rimske Toplice" / "k.o. DOBROVNIK"
    ko = None
    for src in (sub, title, t):
        m = re.search(r"k\.\s*o\.?\s*[:\-]?\s*(\d{1,4})?\s*[-–]?\s*([A-ZČŠŽĐĆa-zčšžđć][A-ZČŠŽĐĆa-zčšžđć .\-]{2,40}?)(?=[,;()\n]|\s+(?:parc|št|st\b|ID|id)|$)", src)
        if m:
            ko = {"id": int(m[1]) if m[1] else None, "name": m[2].strip(" .-")}; break
    # parcele
    parcels = []
    for m in PARC_RE.finditer(t):
        for p in re.findall(r"\d{1,5}(?:/\d{1,4})?", m[1]):
            if p not in parcels: parcels.append(p)
    parcels = parcels[:60]
    # cena
    cena = None
    for m in re.finditer(r"(\d{1,3}(?:[.\s]\d{3})+|\d{3,9})(?:[,.](\d{2}))?\s*(?:EUR|€|evr)", t, re.I):
        v = float(m[1].replace(".", "").replace(" ", "")) + (int(m[2]) / 100 if m[2] else 0)
        if 100 <= v <= 50_000_000 and (cena is None or v > cena): cena = v
    # površina
    pov = None
    for m in re.finditer(r"(\d{1,3}(?:[.\s]\d{3})+|\d{1,7})(?:[,.](\d{1,2}))?\s*m\s*[²2]", t):
        v = float(m[1].replace(".", "").replace(" ", "")) + (int(m[2]) / 100 if m[2] else 0)
        if 1 <= v <= 5_000_000: pov = (pov or 0) + v
    if pov is None:
        m = re.search(r"(\d{1,4}(?:[,.]\d{1,4})?)\s*ha\b", t)
        if m: pov = float(m[1].replace(",", ".")) * 10000
    vrsta = "gozd" if re.search(r"\bgozd", t, re.I) and not re.search(r"kmetij", t[:800], re.I) else ("kmetija" if re.search(r"\bkmetij[ae]\b", title + sub, re.I) else "kmetijsko zemljišče")
    return ko, parcels, cena, pov, vrsta

def wfs(cql, props):
    q = urllib.parse.urlencode({"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": "SI.GURS.KN:PARCELE",
                                "outputFormat": "application/json", "srsName": "EPSG:4326", "count": 80, "propertyName": props, "CQL_FILTER": cql})
    r = get(WFS + "?" + q)
    try: return json.loads(r)["features"]
    except Exception: return []

def geocode(ko, parcels):
    if not ko or not parcels: return [], None
    cql_ko = f"KO_ID={ko['id']}" if ko.get("id") else f"NAZIV ILIKE '%{norm(ko['name']).replace(chr(39), chr(39)*2)}%'"
    lst = ",".join("'" + p.replace("'", "''") + "'" for p in parcels[:60])
    feats = wfs(f"{cql_ko} AND ST_PARCELE IN ({lst})", "ST_PARCELE,KO_ID,NAZIV,POVRSINA,E_CEN,N_CEN")
    pts = [{"p": f["properties"]["ST_PARCELE"], "ko": f["properties"]["KO_ID"], "pov": f["properties"]["POVRSINA"],
            "e": f["properties"]["E_CEN"], "n": f["properties"]["N_CEN"]} for f in feats]
    ko_id = pts[0]["ko"] if pts else ko.get("id")
    return pts, ko_id

def d96_to_wgs(e, n):
    # izračun z proj (pyproj) – natančen
    from pyproj import Transformer
    tr = d96_to_wgs.tr = getattr(d96_to_wgs, "tr", None) or Transformer.from_crs("EPSG:3794", "EPSG:4326", always_xy=True)
    lon, lat = tr.transform(e, n); return round(lon, 6), round(lat, 6)

def main():
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    active = list_offers()
    print(f"{len(active)} aktivnih ponudb, {sum(1 for i in active if i in cache)} že obdelanih", flush=True)
    new_ids = [i for i in active if i not in cache]
    for k, oid in enumerate(new_ids[:MAX_NEW]):
        a = active[oid]; det = detail(oid) or {}
        rec = {"id": oid, "title": a["title"], "sub": a["sub"], "ue": det.get("ue") or a["ue"], "doc": det.get("doc"),
               "pub": det.get("pub") or a["pub"], "do": det.get("do"), "pdf": det.get("pdf"), "ocr": None, "ko": None,
               "parcels": [], "cena": None, "pov": None, "vrsta": None, "pts": [], "err": None}
        try:
            if det.get("pdf"):
                blob = get(det["pdf"], binary=True)
                if blob and len(blob) < 60_000_000:
                    text, used_ocr = ocr(blob)
                    rec["ocr"] = used_ocr
                    ko, parcels, cena, pov, vrsta = parse(text, a["title"], a["sub"])
                    rec.update({"ko": ko, "parcels": parcels, "cena": cena, "pov": pov, "vrsta": vrsta})
                else:
                    rec["err"] = "pdf prevelik ali nedosegljiv"
            else:
                # vsaj k.o. iz naslova
                ko, parcels, cena, pov, vrsta = parse("", a["title"], a["sub"]); rec.update({"ko": ko, "vrsta": vrsta})
            pts, ko_id = geocode(rec["ko"], rec["parcels"])
            rec["pts"] = pts
            if ko_id and rec["ko"]: rec["ko"]["id"] = ko_id
        except Exception as e:
            rec["err"] = str(e)[:200]
        cache[oid] = rec
        print(f"  [{k+1}/{min(len(new_ids), MAX_NEW)}] {oid} {rec['ue']} k.o.={rec['ko']} parcele={len(rec['parcels'])} geo={len(rec['pts'])} cena={rec['cena']}", flush=True)
        if (k + 1) % 10 == 0:
            json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    # počisti potekle (ni več na seznamu > 60 dni)
    today = date.today()
    for oid, rec in list(cache.items()):
        rec["active"] = oid in active
        if not rec["active"]:
            try:
                do = datetime.strptime(rec.get("do") or rec.get("pub") or "1.1.2000", "%d.%m.%Y").date()
                if today - do > timedelta(days=60): del cache[oid]
            except ValueError: pass
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    feats = []
    for oid, rec in cache.items():
        if not rec.get("active"): continue
        pts = rec.get("pts") or []
        if pts:
            lon, lat = d96_to_wgs(sum(p["e"] for p in pts) / len(pts), sum(p["n"] for p in pts) / len(pts))
            geom = {"type": "Point", "coordinates": [lon, lat]}
        else:
            geom = None
        props = {k: rec.get(k) for k in ("id", "title", "sub", "ue", "doc", "pub", "do", "pdf", "ocr", "ko", "parcels", "cena", "pov", "vrsta", "err")}
        props["geo_parcels"] = [{"p": p["p"], "ko": p["ko"], "pov": p["pov"]} for p in pts]
        props["m2"] = round(rec["cena"] / rec["pov"], 2) if rec.get("cena") and rec.get("pov") else None
        props["located"] = bool(pts)
        feats.append({"type": "Feature", "geometry": geom, "properties": props})
    gj = {"type": "FeatureCollection", "updated": today.isoformat(), "count": len(feats), "located": sum(1 for f in feats if f["geometry"]),
          "source": "e-uprava, oglasna deska (UE), vrsta objave PKZ; geokodiranje GURS WFS", "features": feats}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(gj, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"zapisano {len(feats)} ponudb, {gj['located']} z lokacijo", flush=True)

if __name__ == "__main__":
    main()
