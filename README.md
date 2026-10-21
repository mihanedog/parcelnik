# Parcelnik

Odprt, brezplačen pregledovalnik prostora za vso Slovenijo. Ena sama statična datoteka (`index.html`) brez lastnega strežnika in baze: vse sloje in podatke bere neposredno iz javnih OGC storitev Geodetske uprave RS (GURS) in Prostorskega informacijskega sistema (MNVP), ki so objavljeni pod licenco CC BY 4.0.

**Kaj zna**

- klik na parcelo → številka, k.o., površina, urejenost meje, boniteta, javna last, omejitve
- namenska raba iz veljavnega OPN (oznaka, opis, EUP, predviden OPPN, akt in datum veljavnosti)
- dejanska raba, posebni režimi (VVO, gozdni rezervat …), služnosti in stavbna pravica, stavbe
- iskanje po k.o. + parceli (`850 430/17` ali `Slovenj Gradec 430/17`), po naslovu (`Gozdna pot 1, Slovenj Gradec`) in po kraju
- podlage: OSM, ortofoto DOF025, DTK50, lidar senčenje, TTN 5/10
- sloji: kataster, prostorski akti, raba in omejitve, gospodarska javna infrastruktura
- koordinate D96/TM in WGS84, merilo, deljiva povezava na parcelo (`#zoom/lat/lng?p=KO:parcela`)
- gumbi do uradnih virov: zemljiška knjiga (e-Sodstvo), javni vpogled GURS, trg nepremičnin (ETN), ponudbe kmetijskih zemljišč na UE

**Česa ne more (in zakaj)**

- *Lastniki* niso javen podatek: do njih prideš samo z brezplačno registracijo v e-Sodstvu (gumb v panelu te pelje tja, ID znak parcele skopiraš z enim klikom). Množičnega oziroma API dostopa do zemljiške knjige ni.
- *Cene prodanih nepremičnin (ETN)* GURS objavlja kot prosti prenos CSV (aplikacija JGP), ne kot WMS/WFS. Sloj s cenami bo prišel, ko bo pripravljen nočni skript, ki CSV pretvori v GeoJSON (glej »Načrt«).
- *Ponudbe za prodajo kmetijskih zemljišč* upravne enote objavljajo na oglasni deski e-uprave kot PDF, brez API-ja. Trenutno je povezava na zunanji agregator in oglasno desko.

## Gostovanje (0 €)

Statična datoteka, deluje kjerkoli:

- **GitHub Pages**: Settings → Pages → Source: `main` / root. Konec.
- **Domači strežnik / VPS**: skopiraj `index.html` v mapo spletnega strežnika (nginx, Caddy, Apache). Nič za nastaviti, strežnik ne dela nobenih poizvedb, vse teče v brskalniku.
- Lokalno: odpri `index.html` neposredno v brskalniku.

Strežniki GURS/MNVP pošiljajo `Access-Control-Allow-Origin: *`, zato ni potreben noben proxy.

## Viri podatkov

| Vsebina | Storitev | Licenca |
|---|---|---|
| Kataster nepremičnin (parcele, stavbe, bonitete, rabe, režimi) | `https://ipi.eprostor.gov.si/wms-si-gurs-kn/ows` (WMS), `…/wfs-si-gurs-kn/wfs` (WFS) | GURS, CC BY 4.0 |
| Register naslovov | `https://ipi.eprostor.gov.si/wfs-si-gurs-rn/wfs` | GURS, CC BY 4.0 |
| Ortofoto, DTK50, lidar, TTN | `https://ipi.eprostor.gov.si/wms-si-gurs-dts/ows` | GURS, CC BY 4.0 |
| Gospodarska javna infrastruktura | `https://ipi.eprostor.gov.si/wms-si-gurs-kgi/ows` | GURS, CC BY 4.0 |
| Prostorski akti (namenska raba, EUP, PEUP, regulacijske črte, DPN) | `https://ipi.eprostor.gov.si/wms-si-mnvp-pa/ows` | MNVP, PIS |
| Podlaga OSM, iskanje krajev (Nominatim) | OpenStreetMap | ODbL |

Metapodatki vseh storitev: [Slovenski INSPIRE metapodatkovni sistem](https://eprostor.gov.si/imps/). Pogoji uporabe geodetskih podatkov: [e-prostor.gov.si](https://www.e-prostor.gov.si/dostopi/javni-dostop/).

## Načrt

1. **ETN cene**: GitHub Action (tedensko) prenese CSV iz JGP, zgradi GeoJSON po k.o. in objavi sloj »prodane nepremičnine« s ceno, datumom in €/m².
2. **Kmetijska zemljišča**: skript, ki bere oglasno desko e-uprave in ponudbe UE prikaže kot točke s PDF povezavo in rokom za sprejem.
3. Merjenje razdalj in površin, tiskanje izseka, izvoz GeoJSON izbrane parcele.
4. Sloji ARSO (Natura 2000, vodovarstvena območja, poplavna ogroženost) in ZVKDS (kulturna dediščina) prek njihovih javnih WMS.

## Licenca

Koda: MIT. Podatki ostajajo pod licencami njihovih lastnikov (navedba vira je obvezna in je vgrajena v atribucijo zemljevida).
