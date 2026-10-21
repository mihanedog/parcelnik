// ==UserScript==
// @name         Parcelnik → eZK redni izpis
// @namespace    https://github.com/mihanedog/parcelnik
// @version      1.1
// @description  Parcelnik odpre eZK z #parcelnik=KO:PARCELA. Skript si parcelo zapomni, po prijavi SI-PASS sam preklika vmesne korake varnostne sheme (zunanji uporabnik → fizična oseba z EMŠO → Nadaljuj → Prijavi se), odpre javne izpise in zahteva redni izpis (03-001) kot PDF. Teče samo v tvojem brskalniku, s tvojo sejo; gesel ne vidi in ne hrani.
// @author       Parcelnik
// @match        https://esodisce.si/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==
(function () {
  'use strict';
  const KEY = 'parcelnik.pending';
  const LIST = 'https://esodisce.si/evlozisce/javni_izpisi/list.html';

  // 1) nova zahteva iz Parcelnika → zapomni si jo (hash se med prijavo izgubi, localStorage ne)
  const m = location.hash.match(/#parcelnik=(\d+):(.+)$/);
  if (m) {
    try { localStorage.setItem(KEY, JSON.stringify({ ko: m[1], p: decodeURIComponent(m[2]), t: Date.now() })); } catch (e) {}
    history.replaceState(null, '', location.pathname + location.search);
  }
  let pending = null;
  try { pending = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) {}
  if (!pending || Date.now() - pending.t > 15 * 60 * 1000) return; // zahteva velja 15 min

  const byText = (sel, re) => [...document.querySelectorAll(sel)].find(el => re.test((el.textContent || el.value || '').trim()));
  const clickLabel = re => { const l = [...document.querySelectorAll('label')].find(l => re.test(l.textContent.trim())); if (!l) return false; const i = l.control || document.getElementById(l.htmlFor) || l.querySelector('input'); if (i) { i.click(); i.checked = true; i.dispatchEvent(new Event('change', { bubbles: true })); } else l.click(); return true; };

  // 2) stran z obrazci za izpise → izpolni 03-001 in zahtevaj PDF
  if (location.pathname.startsWith('/evlozisce/javni_izpisi/')) {
    const form = [...document.forms].find(f => /03-001\.html$/.test(f.action));
    if (!form) return;
    const set = (n, v) => { const el = form.elements[n]; if (el) { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); } };
    set('nacinList', 'IDZNAK'); set('nacinIskanja', 'IDZNAK'); set('tipNepList.nobind', '1'); set('tipNep', '1');
    set('idZnakNep.katastrskaObcina.idsrcsifrant', pending.ko);
    set('idZnakNep.parcelnaStevilkaNovo', pending.p);
    try { localStorage.removeItem(KEY); } catch (e) {}
    const btn = form.querySelector('#btn_pdf, button[name="_evendId_pdf"]');
    if (btn) btn.click(); else form.submit();
    return;
  }

  // 3) vmesne strani varnostne sheme po SI-PASS (iskanje po besedilu, best-effort)
  if (location.pathname.startsWith('/vash')) {
    if (clickLabel(/fizi[čc]na oseba z EM[ŠS]O/i)) { /* izbrano; nadaljuj spodaj */ }
    const b = byText('button, input[type=submit], input[type=button], a.btn, a',
      /^(Prijavi se kot zunanji uporabnik.*|Prijavi se in nadaljuj s postopki|Nadaljuj)$/i);
    if (b) { setTimeout(() => b.click(), 300); return; }
  }

  // 4) domača stran portala po prijavi → pojdi na javne izpise
  if (/^\/(spa\/?)?$/.test(location.pathname) || location.pathname === '/spa') {
    if (document.body.textContent.includes('Prijavljeni ste') || byText('a', /^Zemlji[šs]ka knjiga$/i)) {
      location.href = LIST; return;
    }
  }
})();
