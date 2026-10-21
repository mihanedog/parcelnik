// ==UserScript==
// @name         Parcelnik → eZK redni izpis
// @namespace    https://github.com/mihanedog/parcelnik
// @version      1.0
// @description  Ko Parcelnik odpre eZK javne izpise s #parcelnik=KO:PARCELA, samodejno izpolni obrazec 03-001 (redni izpis) in zahteva PDF. Teče samo v tvojem brskalniku, s tvojo SI-PASS sejo.
// @author       Parcelnik
// @match        https://esodisce.si/evlozisce/javni_izpisi/list.html*
// @grant        none
// @run-at       document-idle
// ==/UserScript==
(function () {
  'use strict';
  const m = location.hash.match(/#parcelnik=(\d+):(.+)$/);
  if (!m) return;
  const ko = m[1], parcela = decodeURIComponent(m[2]);
  // obrazec 03-001 je prvi <form> z action .../03-001.html
  const form = [...document.forms].find(f => /03-001\.html$/.test(f.action));
  if (!form) return;
  const set = (name, val) => { const el = form.elements[name]; if (el) { el.value = val; el.dispatchEvent(new Event('change', { bubbles: true })); } };
  set('nacinList', 'IDZNAK'); set('nacinIskanja', 'IDZNAK');
  set('tipNepList.nobind', '1'); set('tipNep', '1');
  set('idZnakNep.katastrskaObcina.idsrcsifrant', ko);
  set('idZnakNep.parcelnaStevilkaNovo', parcela);
  history.replaceState(null, '', location.pathname); // da se ob osvežitvi ne sproži znova
  const btn = form.querySelector('#btn_pdf, button[name="_evendId_pdf"]');
  if (btn) btn.click(); else form.submit();
})();
