/* D26 — controles aditivos sin tocar app.js: zoom +/- , toasts cerrables.
   Vive en archivo propio para no colisionar con ediciones paralelas de app.js. */
(function () {
  "use strict";
  function view() { try { return S.view; } catch (e) { return null; } }
  function zin() {
    const v = view(); if (!v || typeof zoomAt !== "function") return;
    zoomAt(v.x + v.w / 2, v.y + v.h / 2, 1 / 1.25);
  }
  function zout() {
    const v = view(); if (!v || typeof zoomAt !== "function") return;
    zoomAt(v.x + v.w / 2, v.y + v.h / 2, 1.25);
  }
  function wire(id, fn) {
    const b = document.getElementById(id);
    if (b && !b._zdone) { b._zdone = true; b.addEventListener("click", fn); }
  }
  function init() {
    wire("b-zin", zin);
    wire("b-zout", zout);
    const fit = document.getElementById("b-fit");
    if (fit && !fit._ztitle) { fit._ztitle = true; fit.title = "Ajustar vista (encuadrar todo)"; }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  // Reintento tardío por si app.js aún no definió zoomAt al cargar este archivo.
  setTimeout(init, 500);
  // Toasts cerrables con clic (incluye la ayuda "?": ya no hay que esperar 7s).
  document.addEventListener("click", function (ev) {
    const t = ev.target && ev.target.closest ? ev.target.closest(".toast") : null;
    if (t) t.remove();
  });
  // D29 — clic central sin autoscroll: se cancela el gesto del navegador en
  // captura (sin stopPropagation: el paneo de app.js sigue funcionando).
  let midPanning = false;
  function stageBox() { return document.getElementById("stage"); }
  document.addEventListener("pointerdown", function (ev) {
    if (ev.button === 1 && ev.target && ev.target.closest &&
        ev.target.closest("#stage")) {
      ev.preventDefault();
      midPanning = true;
      const st = stageBox(); if (st) st.style.cursor = "grabbing";
    }
  }, true);
  ["pointerup", "pointercancel"].forEach(function (tn) {
    document.addEventListener(tn, function () {
      if (midPanning) { midPanning = false; const st = stageBox(); if (st) st.style.cursor = ""; }
    }, true);
  });
  // Rueda sobre el minimapa no debe mover la página.
  document.addEventListener("wheel", function (ev) {
    if (ev.target && ev.target.closest && ev.target.closest("#minimap-box")) ev.preventDefault();
  }, {capture: true, passive: false});
  // D30 — el desplegable debe seguir al par en edición (sin tocar app.js).
  // buildPairSel() reconstruye las <option> y el <select> vuelve al índice 0:
  // mostraba otro par (y su ✓) distinto del que se está viendo. El envoltorio
  // restaura la selección a S.pairIdx tras cada reconstrucción, así el ✓
  // siempre corresponde al par visible y no hay falsos positivos.
  if (typeof buildPairSel === "function" && !buildPairSel._selkeep) {
    const origBPS = buildPairSel;
    buildPairSel = function () {
      const r = origBPS.apply(this, arguments);
      try {
        const sel = document.getElementById("pair-sel");
        if (sel && typeof S !== "undefined" && S && S.pairIdx >= 0) {
          const want = String(S.pairIdx);
          let has = false;
          for (const o of sel.options) { if (o.value === want) { has = true; break; } }
          if (has) sel.value = want;
        }
      } catch (e) { /* decoración: nunca romper el flujo */ }
      return r;
    };
    buildPairSel._selkeep = true;
  }
})();
