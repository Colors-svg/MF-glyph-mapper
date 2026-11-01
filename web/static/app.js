/* Canvas unificado v3 — un SVG, dos bloques, zona de conexión. Regla de dibujo: grupos de 4 + moveTo. */
const $ = id => document.getElementById(id);
async function api(path, obj, timeoutMs = 200000) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"},
                                 body: JSON.stringify(obj), signal: ctl.signal});
    return await r.json();
  } finally { clearTimeout(t); }
}
const S = { file: null, formulas: [], transitions: [], warnings: [],
  tid: null, pairIdx: -1, latexA: "", latexB: "", gA: null, gB: null,
  selA: new Set(), selB: new Set(), conns: [], undo: [], redo: [],
  maps: {}, done: {}, sugg: [], view: null, issues: [], quick: true, hideConn: false,
  pre: {}, _preSeq: 0 };
const PAL = ["#e69f00","#56b4e9","#009e73","#f0e442","#0072b2","#d55e00","#cc79a7","#999999","#117733","#88ccee"];
const connColor = i => PAL[i % PAL.length];

/* tema */
try { if (localStorage.getItem("mf-theme") === "light") document.documentElement.dataset.theme = "light"; } catch (e) {}
$("tb-theme").onclick = () => {
  const h = document.documentElement;
  h.dataset.theme = h.dataset.theme === "light" ? "" : "light";
  try { localStorage.setItem("mf-theme", h.dataset.theme); } catch (e) {}
};
document.querySelectorAll(".stepper button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".stepper button").forEach(x => x.classList.remove("cur"));
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  b.classList.add("cur"); $(b.dataset.tab).classList.add("active");
});
function go(tab) { document.querySelector(`[data-tab="${tab}"]`).click(); }
$("tb-help").onclick = () => {
  toast("<b>Atajos</b> · clic A→clic B conecta · Ctrl suma individual · Shift rango · arrastre = rectángulo por zona · Espacio+arrastrar mueve · rueda zoom · doble clic encuadra · gris punteado = sugerencia (clic acepta) · Supr elimina · Ctrl+Z/Y · Esc limpia · <a href='#' onclick='startTour();return false'>ver tour</a>", 9000);
};
/* tour 4 pasos (primera visita; localStorage mf-tour) */
const TOUR = [
  {tab: "t-load", t: "1 · Carga tu escena", b: "Pega la ruta del .py (lee el código, no lo ejecuta) y pulsa Cargar. ¿Sin archivo a mano? «Probar demo» trae una escena de 3 pares incluida."},
  {tab: "t-map", t: "2 · Mapea glifos con índices reales", b: "Clic en A y luego clic en B conecta solo. Ctrl/Shift suma individual, arrastre captura por zona. Las sugerencias grises (forma única) se aceptan con un clic."},
  {tab: "t-check", t: "3 · Verifica sin show_indices", b: "El validador replica las reglas de MF_Tools: clic en un problema localiza los glifos. ✓ solo con cobertura total."},
  {tab: "t-export", t: "4 · Exporta y previsualiza", b: "Genera el snippet, el bundle para tu agente Manim y la vista previa real (mp4). El informe te dice exactamente qué mapa se renderizó."},
];
let _tourI = 0;
function startTour() {
  _tourI = 0; showTour();
  try { localStorage.setItem("mf-tour", "1"); } catch (e) {}
}
function showTour() {
  const s = TOUR[_tourI];
  go(s.tab);
  $("tour-title").textContent = s.t;
  $("tour-body").textContent = s.b;
  $("tour-step").textContent = `Paso ${_tourI + 1}/${TOUR.length}`;
  $("tour-back").disabled = _tourI === 0;
  $("tour-next").textContent = _tourI === TOUR.length - 1 ? "Terminar" : "Siguiente";
  $("tour-scrim").hidden = false;
}
function endTour() { $("tour-scrim").hidden = true; }
$("tour-next").onclick = () => { if (_tourI < TOUR.length - 1) { _tourI++; showTour(); } else endTour(); };
$("tour-back").onclick = () => { if (_tourI > 0) { _tourI--; showTour(); } };
$("tour-skip").onclick = endTour;
$("tour-scrim").onclick = e => { if (e.target.id === "tour-scrim") endTour(); };
try { if (!localStorage.getItem("mf-tour")) setTimeout(startTour, 600); } catch (e) {}
$("b-demo").onclick = async () => {
  let r;
  try { r = await api("/api/demo", {}, 15000); }
  catch (e) { toast("Servidor no responde.", 3500, true); return; }
  if (!r.exists) { toast("Demo no encontrada en el servidor.", 3500, true); return; }
  $("f-path").value = r.path;
  $("f-go").click();
};
function toast(html, ms = 3500, err = false) {
  const d = document.createElement("div");
  d.className = "toast" + (err ? " err" : ""); d.innerHTML = html;
  $("toasts").appendChild(d); setTimeout(() => d.remove(), ms);
}
function stepper() {
  const done = { "t-load": !!S.file, "t-map": Object.keys(S.maps).length > 0 || S.conns.length > 0,
    "t-check": S.gA !== null, "t-export": false, "t-prev": !!$("p-video").src };
  const errs = S.issues.filter(i => i.level === "error").length;
  document.querySelectorAll(".stepper button").forEach(b => {
    const t = b.dataset.tab;
    b.classList.toggle("done", !!done[t]);
    b.classList.toggle("blocked", (t === "t-export" || t === "t-prev") && errs > 0);
  });
  const v = $("tb-valid");
  if (!S.gA) { v.textContent = "—"; v.className = "vpill"; }
  else if (errs) { v.textContent = `✕ ${errs} err`; v.className = "vpill err"; }
  else { const w = S.issues.filter(i => i.level === "warning").length;
    v.textContent = w ? `⚠ ${w} avis` : "✓ válido"; v.className = "vpill " + (w ? "warn" : "ok"); }
  $("tb-file").textContent = S.file ? S.file.split(/[\\/]/).pop() : "sin archivo";
  $("tb-pair").textContent = S.pairIdx >= 0 ? S.transitions[S.pairIdx].from_var + "→" + S.transitions[S.pairIdx].to_var : "sin par";
  $("st-pairs").textContent = `${S.transitions.length} pares`;
  $("st-mapped").textContent = `${Object.keys(S.done).length} ✓`;
  $("st-err").textContent = `${errs} errores`;
  $("st-warn").textContent = `${S.issues.filter(i => i.level === "warning").length} avisos`;
}
function status(m) { $("st-msg").textContent = m; }

/* geometría */
const NS = "http://www.w3.org/2000/svg";
const GAP = 2.4; // unidades Manim entre bloques
function glyphD(pts, s) {
  let d = "", cx = null;
  for (let i = 0; i + 3 < pts.length; i += 4) {
    const sx = pts[i][0]*s, sy = -pts[i][1]*s;
    if (cx === null || Math.hypot(sx-cx[0], sy-cx[1]) > 1e-4) d += `M${sx.toFixed(1)},${sy.toFixed(1)}`;
    d += `C${(pts[i+1][0]*s).toFixed(1)},${(-pts[i+1][1]*s).toFixed(1)} ${(pts[i+2][0]*s).toFixed(1)},${(-pts[i+2][1]*s).toFixed(1)} ${(pts[i+3][0]*s).toFixed(1)},${(-pts[i+3][1]*s).toFixed(1)}`;
    cx = [pts[i+3][0]*s, -pts[i+3][1]*s];
  }
  return d;
}
function el(n, at) { const e = document.createElementNS(NS, n); for (const k in at) e.setAttribute(k, at[k]); return e; }
function layout() {
  // Todo se mide en unidades Manim (s=1); s escala para altura objetivo ~380u.
  const ga = [], gb = [];
  const push = (arr, g, dx) => { arr.push({g, cx: g.center[0] + dx, cy: -g.center[1]}); };
  (S.gA ? S.gA.glyphs : []).forEach(g => push(ga, g, 0));
  (S.gB ? S.gB.glyphs : []).forEach(g => push(gb, g, 0));
  const boxU = items => {
    const xs = [], ys = [];
    items.forEach(o => { const w = o.g.width / 2, h = o.g.height / 2;
      xs.push(o.cx - w, o.cx + w); ys.push(o.cy - h, o.cy + h); });
    return xs.length ? [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)] : [0, 1, 0, 1];
  };
  const bb = boxU(ga), bb2 = boxU(gb);
  const h = Math.max(bb[3] - bb[2], bb2[3] - bb2[2], 0.5);
  const s = 380 / h;
  const dx = (bb[1] - bb2[0]) + GAP; // hueco en unidades Manim
  gb.forEach(o => o.cx += dx);
  return {s, ga, gb, dx, midU: bb[1] + GAP / 2,
          topU: Math.min(bb[2], bb2[2]), botU: Math.max(bb[3], bb2[3])};
}
function viewBoxTransform(elm) {
  // preserveAspectRatio por defecto (xMidYMid meet): hay bandas si el aspecto difiere.
  const r = elm.getBoundingClientRect(), vb = elm.viewBox.baseVal;
  const k = Math.min(r.width / vb.width, r.height / vb.height);
  return {k, ox: r.left + (r.width - vb.width * k) / 2, oy: r.top + (r.height - vb.height * k) / 2, vb};
}
function toScene(svg, evt) {
  const t = viewBoxTransform(svg);
  return {x: t.vb.x + (evt.clientX - t.ox) / t.k,
          y: t.vb.y + (evt.clientY - t.oy) / t.k};
}
function setView(v) { S.view = v; $("stage").setAttribute("viewBox", `${v.x} ${v.y} ${v.w} ${v.h}`); drawMini(); }
function fitView() {
  const L = layout(); if (!L.ga.length && !L.gb.length) return;
  const xs = [], ys = [];
  [...L.ga, ...L.gb].forEach(o => { const w = o.g.width*L.s/2 + 60, h = o.g.height*L.s/2 + 60;
    xs.push(o.cx*L.s - w, o.cx*L.s + w); ys.push(o.cy*L.s - h, o.cy*L.s + h); });
  let x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (S.conns.length && isFinite(S._laneTop)) y0 = Math.min(y0, S._laneTop);
  setView({x: x0, y: y0, w: x1 - x0, h: y1 - y0});
}
function zoomAt(mx, my, k) {
  const v = S.view; if (!v) return;
  // Tope dinámico: nunca más cerrado que el contenido (pares largos superan 4000u).
  let need = 4000;
  try {
    const L = layout();
    if (L.ga.length || L.gb.length) {
      const xs = [...L.ga, ...L.gb].map(o => o.cx * L.s);
      need = Math.max(4000, (Math.max(...xs) - Math.min(...xs)) * 1.25);
    }
  } catch (e) {}
  const nw = Math.min(Math.max(v.w*k, 40), need), nh = nw * v.h / v.w;
  setView({x: mx - (mx - v.x)*(nw/v.w), y: my - (my - v.y)*(nh/v.h), w: nw, h: nh});
}
$("b-fit").onclick = fitView;
$("t-badges").onchange = e => $("stage").classList.toggle("no-badge", !e.target.checked);

function connKind(c) { return c.f.length && c.t.length ? "transform" : c.f.length ? "fade-out" : "fade-in"; }
function glyphConns(side, idx) {
  const out = [];
  S.conns.forEach((c, i) => {
    if ((side === "A" ? c.f : c.t).includes(idx)) out.push(i);
  });
  return out;
}
function drawCanvas() {
  const svg = $("stage"); svg.innerHTML = "";
  if (!S.gA || !S.gB) return;
  const L = layout(), s = L.s;
  S._layoutS = s;
  const world = el("g", {id: "world"}); svg.appendChild(world);
  // Divisoria A|B en el medio del hueco (fondo, no intercepta clics).
  const divX = L.midU * s;
  world.appendChild(el("path", {d: `M${divX},${L.topU * s - 30} L${divX},${L.botU * s + 30}`, class: "divider"}));
  const blockA = el("g", {id: "blockA"}), blockB = el("g", {id: "blockB"});
  blockB.setAttribute("transform", `translate(${L.dx * s},0)`);
  world.appendChild(blockA); world.appendChild(blockB);
  const map = {A: {}, B: {}};
  [["A", L.ga], ["B", L.gb]].forEach(([side, items]) => {
    items.forEach(o => {
      const g = o.g, bar = g.type_name === "Rectangle";
      const cc = glyphConns(side, g.index);
      const p = el("path", {d: glyphD(g.points, s), class: "g" + (bar ? " bar" : "") +
        ((side === "A" ? S.selA : S.selB).has(g.index) ? " sel" : "") +
        (cc.length ? "" : (S.conns.length ? " dim" : ""))});
      p.dataset.side = side; p.dataset.idx = g.index;
      const x = o.cx*s, y = o.cy*s;
      p._box = {x0: x - g.width*s/2, x1: x + g.width*s/2, y0: y - g.height*s/2, y1: y + g.height*s/2};
      if (cc.length) { const col = connColor(cc[0]); p.setAttribute("stroke", col); }
      if (S._errIdx && S._errIdx[side] && S._errIdx[side].has(g.index)) p.classList.add("err");
      // Halo de clic: mismo trazo, grueso e invisible — agranda la zona sin cambiar el índice.
      const halo = el("path", {d: p.getAttribute("d"), class: "hit"});
      halo.dataset.side = side; halo.dataset.idx = g.index;
      (side === "A" ? blockA : blockB).appendChild(halo);
      (side === "A" ? blockA : blockB).appendChild(p);
      map[side][g.index] = {el: p, x, y, top: y - g.height*s/2, bar, cc};
    });
  });
  S._map = map;
  // insignias con anti-solape
  const badges = el("g", {id: "badges"}); world.appendChild(badges);
  ["A", "B"].forEach(side => {
    const items = Object.entries(map[side]).map(([idx, o]) => ({idx: +idx, ...o}))
      .sort((a, b) => a.top - b.top);
    let prev = -1e9;
    items.forEach(o => {
      let y = Math.min(o.top - 14, prev + 24);
      y = Math.max(y, o.top - 14);
      if (y < prev + 24) y = prev + 24;
      prev = y;
      const col = o.cc.length ? connColor(o.cc[0]) : (o.bar ? "#f0a832" : "#4c8dff");
      const grp = el("g", {class: "bdg"});
      grp.dataset.side = side; grp.dataset.idx = o.idx;
      const w = String(o.idx).length*7 + 16;
      grp.appendChild(el("rect", {x: -w/2, y: y-11, width: w, height: 22, rx: 11, stroke: col}));
      const t = el("text", {x: 0, y: y+4}); t.textContent = o.idx; grp.appendChild(t);
      grp.setAttribute("transform", `translate(${o.x},0)`);
      if (Math.abs(y - (o.top - 14)) > 2) {
        const ln = el("path", {d: `M${o.x},${o.top} L${o.x},${y+11}`, class: "leader"});
        badges.appendChild(ln);
      }
      badges.appendChild(grp);
    });
  });
  // curvas
  const layer = el("g", {id: "curves"}); world.appendChild(layer);
  // Arcos en abanico por ENCIMA: cada conexión su arco, altura escalonada por índice.
  const topY = Math.min(...Object.values(map.A).map(o => o.top),
                        ...Object.values(map.B).map(o => o.top));
  const laneY = i => topY - 46 - (i % 12) * 17;
  S._laneTop = topY - 46 - (Math.min(S.conns.length, 12) - 1) * 17 - 30;
  S.conns.forEach((c, i) => {
    const col = connColor(i);
    const peak = laneY(i);
    const emitLane = (x1, y1, x2, y2, cls, extra, e, nE) => {
      // Arco suave: sube al carril y baja al destino (pico escalonado = abanico).
      // Varias aristas del mismo N→M: picos desfasados en X para no encimarse.
      const off = (nE > 1 ? (e - (nE - 1) / 2) * 22 : 0);
      const p = el("path", {d: `M${x1},${y1} Q${(x1 + x2) / 2 + off},${peak} ${x2},${y2}`, class: "conn " + cls, stroke: col, ...extra});
      p.dataset.c = i; layer.appendChild(p);
    };
    const emit = (x1, y1, x2, y2, cls, extra) => {
      const mx = (x1 + x2) / 2;
      const p = el("path", {d: `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`, class: "conn " + cls, stroke: col, ...extra});
      p.dataset.c = i; layer.appendChild(p);
    };
    if (c.f.length && c.t.length) {
      const nE = c.f.length * c.t.length; let e = 0;
      c.f.forEach(f => c.t.forEach(t => {
        const a = map.A[f], b = map.B[t];
        if (a && b) emitLane(a.x + S.gA.glyphs.find(g => g.index === f).width*s/2, a.y,
                             b.x - S.gB.glyphs.find(g => g.index === t).width*s/2, b.y, "", {}, e++, nE);
      }));
    } else if (c.f.length) {
      c.f.forEach(f => { const a = map.A[f]; if (!a) return;
        const w = S.gA.glyphs.find(g => g.index === f).width*s/2;
        emit(a.x + w, a.y, a.x + w + 46, a.y, "stub fade", {}); });
    } else {
      c.t.forEach(t => { const b = map.B[t]; if (!b) return;
        const w = S.gB.glyphs.find(g => g.index === t).width*s/2;
        emit(b.x - w - 46, b.y, b.x - w, b.y, "stub fade", {}); });
    }
  });
  // Sugerencias (grises, punteadas): abanico propio por encima de los carriles reales. Clic las acepta.
  pruneSugg();
  const suggBase = (isFinite(S._laneTop) ? S._laneTop : topY) - 24;
  (S.sugg || []).forEach((sg, k) => {
    const a = map.A[sg.f[0]], b = map.B[sg.t[0]];
    if (!a || !b) return;
    const gwA = S.gA.glyphs.find(g => g.index === sg.f[0]).width*s/2;
    const gwB = S.gB.glyphs.find(g => g.index === sg.t[0]).width*s/2;
    const p = el("path", {d: `M${a.x + gwA},${a.y} Q${(a.x + gwA + b.x - gwB) / 2},${suggBase - k * 14} ${b.x - gwB},${b.y}`,
      class: "conn sugg", stroke: "#8b93a5"});
    p.dataset.s = k; layer.appendChild(p);
  });
  if ((S.sugg || []).length) S._laneTop = Math.min(S._laneTop, suggBase - ((S.sugg || []).length - 1) * 14 - 20);
  updateSuggBtn();
  const rb = el("rect", {id: "rubber", class: "rubber", visibility: "hidden"}); world.appendChild(rb);
  if (S.hideConn) svg.classList.add("hide-conn"); else svg.classList.remove("hide-conn");
  if (!S.view) fitView(); else setView(S.view);
  drawMini();
  // hover: glifo <-> conexiones
  svg.onmouseover = ev => {
    const ch = ev.target.closest("path.conn");
    if (ch && ch.dataset.c !== undefined) {
      const i = +ch.dataset.c;
      svg.querySelectorAll("path.conn").forEach(p => p.classList.toggle("hl", +p.dataset.c === i));
      document.querySelectorAll("#c-list .tr").forEach((row, j) => row.style.borderColor = j === i ? connColor(i) : "");
      return;
    }
    const t = ev.target.closest("[data-idx]"); if (!t) return;
    const side = t.dataset.side, idx = +t.dataset.idx;
    const cc = side ? glyphConns(side, idx) : [];
    const cs = t.dataset.c !== undefined ? [+t.dataset.c] : cc;
    svg.querySelectorAll("path.conn").forEach(p => p.classList.toggle("hl", cs.includes(+p.dataset.c)));
    document.querySelectorAll("#c-list .tr").forEach((row, i) => row.style.borderColor = cs.includes(i) ? connColor(i) : "");
  };
  svg.onmouseout = () => {
    svg.querySelectorAll("path.conn.hl").forEach(p => p.classList.remove("hl"));
    document.querySelectorAll("#c-list .tr").forEach(row => row.style.borderColor = "");
  };
}
/* minimapa: los puntos se construyen 1 vez por par; por frame solo se mueve el rect del viewport */
function drawMini() {
  const mm = $("minimap");
  if (!S.gA || !S._map) { mm.innerHTML = ""; S._miniKey = null; return; }
  const all = [...Object.values(S._map.A), ...Object.values(S._map.B)];
  const xs = all.flatMap(o => [o.x - 20, o.x + 20]), ys = all.flatMap(o => [o.y - 20, o.y + 20]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const key = [x0, y0, x1, y1, all.length].join(",");
  if (S._miniKey !== key) {
    // Reconstrucción completa (solo al cambiar de par o de conexiones).
    mm.innerHTML = "";
    mm.setAttribute("viewBox", `${x0} ${y0} ${x1-x0} ${y1-y0}`);
    const dots = el("g", {id: "mini-dots"});
    all.forEach(o => dots.appendChild(el("rect", {x: o.x-8, y: o.y-8, width: 16, height: 16, fill: "#4c8dff", opacity: .7})));
    mm.appendChild(dots);
    S._miniKey = key;
    S._miniSpan = x1 - x0;
  }
  let vr = mm.querySelector("#mini-view");
  if (!vr) {
    vr = el("rect", {id: "mini-view", fill: "none", stroke: "#ff7b00",
      "stroke-width": Math.max((S._miniSpan || 100) / 150, 2)});
    mm.appendChild(vr);
  }
  if (S.view) {
    vr.setAttribute("visibility", "visible");
    vr.setAttribute("x", S.view.x); vr.setAttribute("y", S.view.y);
    vr.setAttribute("width", S.view.w); vr.setAttribute("height", S.view.h);
  } else vr.setAttribute("visibility", "hidden");
  mm.onmousedown = ev => {
    const t = viewBoxTransform(mm);
    const mx = t.vb.x + (ev.clientX - t.ox)/t.k, my = t.vb.y + (ev.clientY - t.oy)/t.k;
    if (S.view) setView({x: mx - S.view.w/2, y: my - S.view.h/2, w: S.view.w, h: S.view.h});
  };
}
/* interaccion: clic / rectangulo / pan / zoom */
(function wireStage() {
  const svg = $("stage");
  let mode = null, sx = 0, sy = 0, moved = false, space = false;
  document.addEventListener("keydown", e => { if (e.code === "Space" && !e.target.matches("input,select,textarea")) { space = true; svg.style.cursor = "grab"; e.preventDefault(); } });
  document.addEventListener("keyup", e => { if (e.code === "Space") { space = false; svg.style.cursor = "default"; } });
  const rb = () => svg.querySelector("#rubber");
  svg.addEventListener("pointerdown", ev => {
    if (ev.button === 1 || space) { mode = "pan"; sx = ev.clientX; sy = ev.clientY; svg.setPointerCapture(ev.pointerId); return; }
    if (ev.button !== 0) return;
    if (ev.target.closest("[data-idx]")) return; // lo gestiona click
    mode = "rubber"; moved = false;
    const p = toScene(svg, ev); sx = p.x; sy = p.y;
    svg.setPointerCapture(ev.pointerId);
  });
  svg.addEventListener("pointermove", ev => {
    if (!mode) return;
    if (mode === "pan") {
      const dx = (ev.clientX - sx), dy = (ev.clientY - sy);
      const v = S.view, k = 1 / viewBoxTransform(svg).k;
      setView({x: v.x - dx*k, y: v.y - dy*k, w: v.w, h: v.h});
      sx = ev.clientX; sy = ev.clientY; moved = true; return;
    }
    const p = toScene(svg, ev);
    if (Math.hypot(p.x - sx, p.y - sy) > 4 / viewBoxTransform(svg).k) moved = true;
    if (!moved) return;
    const r = rb(); if (!r) return;
    r.setAttribute("visibility", "visible");
    r.setAttribute("x", Math.min(sx, p.x)); r.setAttribute("y", Math.min(sy, p.y));
    r.setAttribute("width", Math.abs(p.x - sx)); r.setAttribute("height", Math.abs(p.y - sy));
  });
  function up(ev) {
    if (mode === "rubber" && moved) {
      const r = rb();
      const x = +r.getAttribute("x"), y = +r.getAttribute("y"), w = +r.getAttribute("width"), h = +r.getAttribute("height");
      r.setAttribute("visibility", "hidden");
      if (!ev.shiftKey && !ev.ctrlKey && !ev.metaKey) { S.selA.clear(); S.selB.clear(); }
      [["A", S.gA, S.selA], ["B", S.gB, S.selB]].forEach(([side, pay, sel]) => {
        if (!pay) return;
        pay.glyphs.forEach(g => {
          const o = S._map[side][g.index]; if (!o) return;
          const gw = g.width*layoutScale()/2, gh = g.height*layoutScale()/2;
          if (o.x + gw >= x && o.x - gw <= x + w && o.y + gh >= y && o.y - gh <= y + h) sel.add(g.index);
        });
      });
      S._justRubbered = true;
      redraw(); inspectSel();
    }
    mode = null;
  }
  svg.addEventListener("pointerup", up);
  // Trazo visible más cercano al clic (los halos se solapan en sub/super pegados;
  // el de arriba ganaría aunque toques el otro). Solo paths.g: la precisión no cambia.
  function nearestGlyph(ev) {
    try {
      const svg = $("stage");
      if (!S._map) return null;
      const paths = svg.querySelectorAll("path.g");
      if (!paths.length) return null;
      let best = null;
      for (const p of paths) {
        const ctm = p.getScreenCTM(); if (!ctm) continue;
        const L = p.getTotalLength(); if (!isFinite(L) || L <= 0) continue;
        const n = Math.max(8, Math.min(40, Math.round(L / 10)));
        for (let k = 0; k <= n; k++) {
          const sp = p.getPointAtLength(L * k / n).matrixTransform(ctm);
          const d = Math.hypot(sp.x - ev.clientX, sp.y - ev.clientY);
          if (!best || d < best.d) best = {d, side: p.dataset.side, idx: +p.dataset.idx};
        }
      }
      if (!best) return null;
      const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
      const haloPx = 10 * (r.width / vb.width) + 4;
      return best.d <= haloPx ? {side: best.side, idx: best.idx} : null;
    } catch (e) { return null; }
  }
  svg.addEventListener("click", ev => {
    if (S._justRubbered) { S._justRubbered = false; return; }
    const sg0 = ev.target.closest("path.conn.sugg");
    if (sg0 && sg0.dataset.s !== undefined) { acceptSugg(+sg0.dataset.s); return; }
    const cc0 = ev.target.closest("path.conn");
    if (cc0 && cc0.dataset.c !== undefined) {
      const i = +cc0.dataset.c;
      S._delIdx = (S._delIdx === i ? undefined : i);
      inspectConn(i); redraw(); return;
    }
    const t = ev.target.closest("[data-idx]"); if (!t) {
      if (!ev.shiftKey && !ev.ctrlKey && !ev.metaKey) { S.selA.clear(); S.selB.clear(); redraw(); inspectSel(); }
      return;
    }
    const hit = nearestGlyph(ev); // sub/super pegados: decide el trazo, no el halo de arriba
    const side = hit ? hit.side : t.dataset.side, idx = hit ? hit.idx : +t.dataset.idx;
    const s = side === "A" ? S.selA : S.selB;
    const plain = !ev.ctrlKey && !ev.metaKey && !ev.shiftKey;
    if (ev.shiftKey) {
      // Shift: rango continuo lo..hi en su lado (para barrer sub/superscripts contiguos).
      const cur = [...s];
      if (cur.length) { const lo = Math.min(...cur, idx), hi = Math.max(...cur, idx);
        for (let i = lo; i <= hi; i++) s.add(i); }
      else s.add(idx);
    } else if (plain) {
      // Clic simple: limpia SOLO su lado (conserva el opuesto) → permite A y luego B.
      s.clear(); s.add(idx);
    } else s.has(idx) ? s.delete(idx) : s.add(idx); // Ctrl: suma/resta individual
    // Modo rápido: 1 en A + 1 en B con clic simple → conecta solo sin botón.
    if (S.quick && plain && S.selA.size === 1 && S.selB.size === 1) {
      addConn([...S.selA], [...S.selB]);
      toast(`Rápido: <b>A${[...S.conns[S.conns.length-1].f]} → B${[...S.conns[S.conns.length-1].t]}</b> conectada.`, 2200);
      inspectConn(S.conns.length - 1);
      return;
    }
    redraw(); inspectSel();
  });
  // Clic directo en una LÍNEA de conexión = marcarla para Eliminar.
  svg.addEventListener("dblclick", ev => {
    const cc = ev.target.closest("path.conn");
    if (cc && cc.dataset.c !== undefined) {
      const i = +cc.dataset.c;
      S._delIdx = i; inspectConn(i); redraw();
    } else fitView(); // doble clic en vacío = encuadrar todo (rescate del zoom)
  });
  // Hover: atenúa el resto para que las líneas no invadan.
  svg.addEventListener("mouseover", ev => {
    const t = ev.target.closest("[data-idx],path.conn");
    svg.classList.toggle("focusing", !!t);
  });
  svg.addEventListener("wheel", ev => {
    ev.preventDefault();
    const p = toScene(svg, ev);
    zoomAt(p.x, p.y, ev.deltaY < 0 ? 1/1.15 : 1.15);
  }, {passive: false});
})();
function layoutScale() { return S._layoutS || 120; }
function redraw() {
  drawCanvas();
  const sel = [...S.selA].sort((a,b)=>a-b).map(i => "A"+i).concat([...S.selB].sort((a,b)=>a-b).map(i => "B"+i));
  $("selinfo").textContent = sel.length ? "sel=[" + sel.join(" ") + "]" : "clic: selecciona · arrastre: rectángulo · Espacio+arrastrar: mover";
  $("gm-prev").textContent = S.conns.length
    ? "glyph_map = [\n" + S.conns.map(c => `  ([${c.f}], [${c.t}]),  # ${connKind(c)}`).join("\n") + "\n]"
    : "glyph_map = [\n  # vacío: clic A → clic B conecta solo;\n  # Ctrl/Shift suma N→M y pulsa Conectar;\n  # o acepta las sugerencias grises.\n]";
  const cl = $("c-list"); cl.innerHTML = "";
  $("c-count").textContent = S.conns.length ? `${S.conns.length}` : "";
  S.conns.forEach((c, i) => {
    const d = document.createElement("div");
    d.className = "tr" + (S._delIdx === i ? " cur" : "");
    d.style.borderLeft = `4px solid ${connColor(i)}`;
    d.innerHTML = `<span class="badge">[${i}]</span><span>[${c.f}] → [${c.t}]</span><span class="hint">${connKind(c)}</span>`;
    d.title = "Clic: inspeccionar · marca y pulsa Eliminar";
    d.onmouseenter = () => document.querySelectorAll("#stage path.conn").forEach(p => p.classList.toggle("hl", +p.dataset.c === i));
    d.onmouseleave = () => document.querySelectorAll("#stage path.conn.hl").forEach(p => p.classList.remove("hl"));
    d.onclick = () => { S._delIdx = (S._delIdx === i ? undefined : i); inspectConn(i); redraw(); };
    cl.appendChild(d);
  });
  (S.sugg || []).forEach((sg, k) => {
    const d = document.createElement("div");
    d.className = "tr sugg";
    d.innerHTML = `<span class="badge">◌</span><span>[${sg.f}] → [${sg.t}]</span><span class="hint">sugerida · clic acepta</span>`;
    d.title = "Sugerencia única por forma: clic para aceptarla";
    d.onclick = () => acceptSugg(k);
    cl.appendChild(d);
  });
  $("dock-sum").textContent = `${S.conns.length} conexiones`;
  refreshIssues();
}
function inspectConn(i) {
  const c = S.conns[i]; if (!c) return;
  $("inspector").innerHTML = `<b style="color:${connColor(i)}">● Conexión ${i} — ${connKind(c)}</b><br><code>[${c.f}] → [${c.t}]</code><br><span class="hint">Marca y pulsa Eliminar para quitarla.</span>`;
}
function inspectSel() {
  const all = [...S.selA].map(i => ["A", i]).concat([...S.selB].map(i => ["B", i]));
  if (!all.length) { $("inspector").innerHTML = "<p class='muted'>Selecciona un glifo o una conexión.</p>"; return; }
  const pay = all[0][0] === "A" ? S.gA : S.gB;
  const g = pay.glyphs.find(g => g.index === all[0][1]);
  const cc = glyphConns(all[0][0], all[0][1]);
  $("inspector").innerHTML = `<b>Glifo ${all[0][1]}</b> <span class="hint">${all[0][0] === "A" ? "origen" : "destino"}</span><br>` +
    `tipo <code>${g.type_name}</code> · <code>${g.width.toFixed(2)}×${g.height.toFixed(2)}</code> · ${g.points.length} pts<br>` +
    (cc.length ? `<span class="hint">en conexiones ${cc.map(i => `<b style="color:${connColor(i)}">${i}</b>`).join(", ")}</span>` : `<span class="hint">sin correspondencia explícita</span>`) +
    (all.length > 1 ? `<br><span class="hint">+${all.length - 1} seleccionados</span>` : "");
}
function snap() { S.undo.push(JSON.stringify(S.conns)); S.redo = []; }

/* Paso 1 */
$("f-go").onclick = async () => {
  const path = $("f-path").value.trim();
  const btn = $("f-go"); btn.disabled = true;
  const rep = $("report");
  status(`Leyendo ${path} …`);
  rep.className = "report";
  rep.innerHTML = "<p class='muted'>Leyendo y analizando…</p>";
  let r;
  try { r = await api("/api/parse", {path}, 60000); }
  catch (e) {
    rep.className = "report err";
    rep.innerHTML = `<b>El servidor no responde.</b><br><span class="hint">¿Abriste la app con <code>web_start.bat</code> (http://127.0.0.1:8765/)? Si abriste el .html como archivo, la API no existe. Detalle: ${e}</span>`;
    status("Servidor no responde."); btn.disabled = false; return;
  }
  if (!r.transitions) {
    rep.className = "report err";
    rep.innerHTML = `<b>No se pudo leer el .py.</b><br><span class="hint">${r.error || "?"}</span>`;
    status("Error: " + (r.error || "?")); toast("No se pudo leer el .py", 4000, true);
    btn.disabled = false; return;
  }
  S.file = path; S.formulas = r.formulas; S.transitions = r.transitions; S.warnings = r.warnings; S.maps = {}; S.done = {}; S.pre = {}; S._preSeq = (S._preSeq || 0) + 1;
  // Importar empieza LIMPIO. Si hay trabajo anterior, se ofrece recuperarlo (no en silencio).
  let hadPrev = false, nPrev = 0;
  try {
    const raw = localStorage.getItem("mf-maps::" + path);
    if (raw) { const o = JSON.parse(raw); nPrev = Object.keys(o || {}).length; hadPrev = nPrev > 0; }
  } catch (e) {}
  if (hadPrev) {
    if (confirm(`Hay ${nPrev} mapa(s) guardados de una sesión anterior. ¿Recuperarlos?\nAceptar = recuperar · Cancelar = empezar limpio.`)) restoreMaps();
    else { try { localStorage.removeItem("mf-maps::" + path); } catch (e) {} }
  }
  S.pairIdx = -1; S.gA = S.gB = null; S.view = null;
  $("report").className = "report " + (r.warnings.length ? "warn" : "ok");
  $("report").innerHTML = `<b>${r.formulas.length}</b> fórmulas · <b>${r.transitions.length}</b> transiciones · <b>${r.warnings.length}</b> avisos` +
    (r.warnings.length ? "<ul>" + r.warnings.map(w => `<li>${w}</li>`).join("") : "<p>0 avisos: extracción limpia.</p>");
  $("t-count").textContent = `${r.transitions.length} pares`;
  buildPairSel(""); renderTList("");
  if (r.transitions.length) { $("pair-sel").selectedIndex = 0; await loadPair(0); go("t-map"); preloadRest(); }
  stepper(); status(`Cargado: ${r.transitions.length} pares, ${Object.keys(S.done).length} completos ✓.`);
  btn.disabled = false;
};
$("t-filter").oninput = e => renderTList(e.target.value.toLowerCase());
$("b-wipemaps").onclick = () => {
  const n = Object.keys(S.maps).length;
  if (!n && !S.conns.length) return toast("No hay mapas que descartar.", 2500);
  if (!confirm(`¿Descartar los ${n} mapa(s) guardados + conexiones actuales? Se pierde el trabajo de este archivo.`)) return;
  S.maps = {}; S.done = {}; S.conns = []; S.undo = []; S.redo = [];
  try { localStorage.removeItem("mf-maps::" + S.file); } catch (e) {}
  renderTList($("t-filter").value.toLowerCase()); buildPairSel($("pair-filter").value.toLowerCase());
  redraw(); stepper(); status("Mapas descartados: todo limpio.");
};
/* Sugerencias: solo coincidencia ÚNICA 1:1 por forma (si hay varias, manual). Nunca se guardan solas. */
function shapeSig(g) {
  const pts = g.points;
  if (!pts || !pts.length) return g.type_name + "|vacio";
  let cx = 0, cy = 0;
  pts.forEach(p => { cx += p[0]; cy += p[1]; });
  cx /= pts.length; cy /= pts.length;
  const sc = Math.max(g.width, g.height, 1e-6), q = v => Math.round(v * 200) / 200;
  let h = g.type_name + "|" + q(g.width / sc) + "x" + q(g.height / sc) + "|";
  const step = Math.max(1, Math.floor(pts.length / 48));
  for (let i = 0; i < pts.length; i += step) h += q((pts[i][0] - cx) / sc) + "," + q((pts[i][1] - cy) / sc) + ";";
  return h;
}
function computeSugg() {
  S.sugg = [];
  if (!S.gA || !S.gB) { updateSuggBtn(); return; }
  const keyA = {}, keyB = {};
  S.gA.glyphs.forEach(g => { const k = shapeSig(g); (keyA[k] = keyA[k] || []).push(g.index); });
  S.gB.glyphs.forEach(g => { const k = shapeSig(g); (keyB[k] = keyB[k] || []).push(g.index); });
  Object.keys(keyA).forEach(k => {
    if (keyA[k].length === 1 && keyB[k] && keyB[k].length === 1)
      S.sugg.push({f: [keyA[k][0]], t: [keyB[k][0]]});
  });
  pruneSugg(); updateSuggBtn();
}
function pruneSugg() {
  // Fuera sugerencias que pisen conexiones reales (recién aceptadas o mapeadas).
  const ua = new Set(), ub = new Set();
  S.conns.forEach(c => { c.f.forEach(i => ua.add(i)); c.t.forEach(i => ub.add(i)); });
  S.sugg = (S.sugg || []).filter(sg => !sg.f.some(i => ua.has(i)) && !sg.t.some(i => ub.has(i)));
}
function updateSuggBtn() {
  const n = (S.sugg || []).length, b = $("b-sugg"), x = $("b-suggno");
  if (b) { b.textContent = n ? `Aceptar ${n} sugerencia${n > 1 ? "s" : ""} ✓` : "Sin sugerencias"; b.disabled = !n; }
  if (x) x.style.display = n ? "" : "none";
}
function acceptSugg(k) {
  const list = (k === undefined ? [...(S.sugg || []).keys()] : [k])
    .map(i => (S.sugg || [])[i]).filter(Boolean);
  if (!list.length) return;
  snap();
  list.forEach(sg => {
    if (S.conns.some(c => JSON.stringify(c.f) === JSON.stringify(sg.f) && JSON.stringify(c.t) === JSON.stringify(sg.t))) return;
    S.conns.push({f: [...sg.f], t: [...sg.t]});
  });
  const ids = new Set(list.map(sg => sg.f[0] + ":" + sg.t[0]));
  S.sugg = (S.sugg || []).filter(sg => !ids.has(sg.f[0] + ":" + sg.t[0]));
  pruneSugg(); S.selA.clear(); S.selB.clear();
  redraw(); autoSave(); updateSuggBtn();
  toast(`<b>${list.length}</b> sugerencia${list.length > 1 ? "s" : ""} aceptada${list.length > 1 ? "s" : ""}.`, 2500);
}
/* Cobertura: ✓ solo si TODO glifo de A y B está en alguna conexión. Una sola fuente para lista + selector. */
function pairCoverage(conns, nA, nB) {
  const a = new Set(), b = new Set();
  (conns || []).forEach(c => {
    const f = c.f !== undefined ? c.f : c[0], t = c.t !== undefined ? c.t : c[1];
    (f || []).forEach(i => a.add(i)); (t || []).forEach(i => b.add(i));
  });
  const missA = [], missB = [];
  for (let i = 0; i < nA; i++) if (!a.has(i)) missA.push(i);
  for (let i = 0; i < nB; i++) if (!b.has(i)) missB.push(i);
  return {ok: (conns || []).length > 0 && !missA.length && !missB.length, missA, missB};
}
function markFor(tid) {
  // done / partial / none — idéntico en lista y selector, sin falsos ✓.
  if (S.done[tid]) return {mark: "✓", cls: "done", bcls: "ok"};
  if (S.maps[tid] && S.maps[tid].length) return {mark: "◐", cls: "partial", bcls: ""};
  return {mark: "·", cls: "todo", bcls: ""};
}
function refreshMarks() {
  renderTList($("t-filter").value.toLowerCase()); buildPairSel($("pair-filter").value.toLowerCase());
  stepper();
}
function computeDone(tid) {
  // Solo fiable con conteos reales (par cargado). Sin ellos: sin ✓, como mucho ◐.
  const saved = S.maps[tid];
  if (saved && saved.length && S.gA && S.gB) {
    const cov = pairCoverage(saved.map(([f, t]) => ({f, t})), S.gA.resolved_len, S.gB.resolved_len);
    if (cov.ok) S.done[tid] = true; else delete S.done[tid];
    return cov;
  }
  delete S.done[tid];
  return null;
}
function renderTList(f = "") {
  const L = $("t-list"); L.innerHTML = "";
  S.transitions.forEach((t, i) => {
    const hay = `${t.from_var} ${t.to_var} ${t.from_var}->${t.to_var} ${t.from_var} → ${t.to_var} ${t.fase}`.toLowerCase();
    if (f && !hay.includes(f)) return;
    const tid = `${t.from_var}->${t.to_var}`;
    const d = document.createElement("div");
    d.className = "tr" + (i === S.pairIdx ? " cur" : "");
    const mk = markFor(tid);
    d.innerHTML = `<span class="${mk.cls}">${mk.mark}</span><span class="badge ${mk.bcls}">${tid}</span><span>${t.fase}</span>`;
    d.title = (t.latex_a + " → " + t.latex_b).slice(0, 160);
    d.onclick = async () => { const sel = $("pair-sel"), want = String(i);
      let has = false; for (const o of sel.options) { if (o.value === want) { has = true; break; } }
      if (has) sel.value = want; await loadPair(i); go("t-map"); };
    L.appendChild(d);
  });
  if (!L.children.length) L.innerHTML = '<p class="muted">Sin coincidencias: ajusta el filtro o carga un .py con TransformMatchingTex (o prueba la demo).</p>';
}
function buildPairSel(f = "") {
  const sel = $("pair-sel"); sel.innerHTML = "";
  const groups = {};
  S.transitions.forEach((t, i) => {
    if (f && !`${t.from_var} ${t.to_var} ${t.from_var}->${t.to_var} ${t.from_var} → ${t.to_var} ${t.fase}`.toLowerCase().includes(f)) return;
    (groups[t.fase] = groups[t.fase] || []).push(i);
  });
  Object.entries(groups).forEach(([fase, idxs]) => {
    const og = document.createElement("optgroup"); og.label = fase;
    idxs.forEach(i => {
      const t = S.transitions[i], tid = `${t.from_var}->${t.to_var}`;
      og.appendChild(new Option(`${markFor(tid).mark} ${t.from_var} → ${t.to_var}`, i));
    });
    sel.appendChild(og);
  });
}
$("pair-filter").oninput = e => buildPairSel(e.target.value.toLowerCase());
$("side-toggle").onclick = () => {
  if (window.innerWidth <= 1100) document.body.classList.toggle("side-open");
  else document.body.classList.toggle("side-collapsed");
};
$("scrim").onclick = () => document.body.classList.remove("side-open");
$("dock-toggle").onclick = () => $("dock").classList.toggle("closed");

/* Paso 2 */
$("pair-sel").onchange = e => loadPair(+e.target.value);
$("m-render").onclick = () => loadPair(S.pairIdx < 0 ? 0 : S.pairIdx);
async function loadPair(i) {
  if (i < 0 || i >= S.transitions.length) return;
  // No perder trabajo: vuelca el par actual antes de cambiar (autosave ya lo hace en cada mutación).
  try { autoSave(); } catch (e) {}
  const seq = (S._renderSeq = (S._renderSeq || 0) + 1); // si cambias de par a mitad, el render viejo se descarta
  S.pairIdx = i;
  const t = S.transitions[i], tid = `${t.from_var}->${t.to_var}`;
  S.latexA = t.latex_a; S.latexB = t.latex_b;
  S.selA.clear(); S.selB.clear(); S.undo = []; S.redo = []; S._delIdx = undefined; S.view = null;
  // Aviso + lienzo vacío INMEDIATO: nada de glifos viejos con nombre de par nuevo.
  S.gA = S.gB = null; S.conns = []; S._map = null; S.sugg = []; updateSuggBtn();
  $("la-show").textContent = t.from_var; $("lb-show").textContent = t.to_var;
  $("m-info").textContent = `⏳ Renderizando ${t.from_var}→${t.to_var} con Manim (~15s): lienzo vacío hasta terminar…`;
  status(`Renderizando ${tid}…`);
  redraw(); refreshMarks();
  let a, b;
  if (S.pre[i]) {
    // Pre-render de fondo: instantáneo.
    a = S.pre[i].gA; b = S.pre[i].gB;
  } else {
  try { [a, b] = await Promise.all([
    api("/api/render", {latex: S.latexA, path: [0]}),
    api("/api/render", {latex: S.latexB, path: [0]})]); }
  catch (e) { S.gA = S.gB = null; S.conns = []; redraw(); $("m-info").textContent = "Servidor no responde."; return; }
  if (seq !== S._renderSeq) return; // cambiaste de par mientras renderizaba: este resultado ya no vale
  if (a.ok && b.ok) S.pre[i] = {gA: a, gB: b};
  }
  if (!a.ok) { S.gA = S.gB = null; S.conns = []; redraw(); $("m-info").textContent = "ERROR inicial: " + a.error; return; }
  if (!b.ok) { S.gA = S.gB = null; S.conns = []; redraw(); $("m-info").textContent = "ERROR final: " + b.error; return; }
  S.gA = a; S.gB = b;
  const saved = S.maps[tid];
  S.conns = saved ? saved.map(([f, t2]) => ({f: [...f], t: [...t2]})) : [];
  computeDone(tid); computeSugg();
  $("m-info").textContent = `✓ ${a.resolved_len} vs ${b.resolved_len} glifos` +
    (a.warnings.concat(b.warnings).length ? " · AVISO ruta" : "") + (saved ? " · mapa restaurado" : " · par limpio, a mapear");
  status(`Par ${tid} listo: ${a.resolved_len} vs ${b.resolved_len} glifos.`);
  if ((S.sugg || []).length) toast(`<b>${S.sugg.length}</b> sugerencia${S.sugg.length > 1 ? "s únicas" : " única"} por forma — revísalas en gris y acepta.`, 5000);
  refreshMarks();
  redraw(); stepper();
}
/* Pre-render progresivo: cola de a un par por vez, sin bloquear. loadPair usa la caché. */
async function preloadRest() {
  const seq = ++S._preSeq;
  S.pre = S.pre || {};
  const idxs = S.transitions.map((_, i) => i).filter(i => i !== S.pairIdx);
  let done = 0;
  for (const i of idxs) {
    if (seq !== S._preSeq) return; // otro archivo tomó el turno
    if (S.pre[i]) { done++; continue; }
    if (i === S.pairIdx) { done++; continue; } // el usuario lo abrió: ya está en curso
    const t = S.transitions[i]; if (!t) { done++; continue; }
    $("st-pre").textContent = `fondo ${done + 1}/${idxs.length} · ${t.from_var}→${t.to_var}…`;
    try {
      const [a, b] = await Promise.all([
        api("/api/render", {latex: t.latex_a, path: [0]}, 300000),
        api("/api/render", {latex: t.latex_b, path: [0]}, 300000)]);
      if (seq !== S._preSeq) return;
      if (a.ok && b.ok) S.pre[i] = {gA: a, gB: b};
    } catch (e) { /* reintentable al abrir el par */ }
    done++;
    await new Promise(r => setTimeout(r, 400)); // respiro al servidor
  }
  if (seq === S._preSeq) $("st-pre").textContent = `fondo completo · ${Object.keys(S.pre).length}/${S.transitions.length} listos`;
}
function addConn(f, t) {
  if (!f.length && !t.length) { toast("Selecciona al menos 1 glifo en algún panel (Ctrl suma).", 3000, true); return; }
  f = [...new Set(f)].sort((a,b)=>a-b); t = [...new Set(t)].sort((a,b)=>a-b);
  if (S.conns.some(c => JSON.stringify(c.f) === JSON.stringify(f) && JSON.stringify(c.t) === JSON.stringify(t))) {
    toast("Conexión duplicada, ignorada.", 2500, true); return;
  }
  const nA = S.gA.resolved_len, nB = S.gB.resolved_len;
  if (f.some(x => x < 0 || x >= nA) || t.some(x => x < 0 || x >= nB)) { toast("Índice fuera de rango.", 2500, true); return; }
  snap(); S.conns.push({f, t});
  S.selA.clear(); S.selB.clear(); redraw(); stepper(); autoSave();
}
$("b-conn").onclick = () => addConn([...S.selA], [...S.selB]);
$("b-sugg").onclick = () => acceptSugg();
$("b-suggno").onclick = () => { S.sugg = []; updateSuggBtn(); redraw(); status("Sugerencias descartadas: mapeo manual."); };
$("b-quick").onclick = () => {
  S.quick = !S.quick;
  $("b-quick").textContent = S.quick ? "Rápido: ON" : "Rápido: OFF";
  $("b-quick").classList.toggle("primary", S.quick);
  toast(S.quick ? "Clic A → clic B conecta solo (1→1). Ctrl para N→M." : "Modo rápido OFF: usa Conectar N→M.", 3500);
};
$("b-curves").onclick = () => {
  S.hideConn = !S.hideConn;
  $("stage").classList.toggle("hide-conn", S.hideConn);
  $("b-curves").textContent = S.hideConn ? "Líneas: OFF" : "Líneas: ON";
};
$("b-fout").onclick = () => { if (!S.selA.size) return toast("Selecciona origen.", 2500, true); addConn([...S.selA], []); };
$("b-fin").onclick = () => { if (!S.selB.size) return toast("Selecciona destino.", 2500, true); addConn([], [...S.selB]); };
$("b-del").onclick = () => {
  if (S._delIdx === undefined || S._delIdx < 0 || S._delIdx >= S.conns.length) return toast("Marca una conexión en el panel.", 2500, true);
  snap(); S.conns.splice(S._delIdx, 1); S._delIdx = undefined; redraw(); autoSave();
};
$("b-undo").onclick = () => { if (S.undo.length) { S.redo.push(JSON.stringify(S.conns)); S.conns = JSON.parse(S.undo.pop()); redraw(); autoSave(); } };
$("b-redo").onclick = () => { if (S.redo.length) { S.undo.push(JSON.stringify(S.conns)); S.conns = JSON.parse(S.redo.pop()); redraw(); autoSave(); } };
$("b-clear").onclick = () => {
  if (!S.conns.length || !confirm("¿Borrar todas las conexiones? Se puede deshacer.")) return;
  snap(); S.conns = []; redraw();
  // Limpiar también retira el mapa guardado: si no, el ◐/✓ fantasma sobreviviría.
  if (S.pairIdx >= 0 && S.transitions[S.pairIdx]) {
    const t = S.transitions[S.pairIdx], tid = `${t.from_var}->${t.to_var}`;
    delete S.maps[tid]; delete S.done[tid];
    try { persistMaps(); } catch (e) {}
    refreshMarks();
  }
};
$("b-savemap").onclick = async () => {
  if (S.pairIdx < 0) return;
  const t = S.transitions[S.pairIdx], tid = `${t.from_var}->${t.to_var}`;
  // Guardado de borrador: NUNCA bloquea. Solo avisa si hay errores (el bloqueo real queda en Exportar).
  let v = null;
  try { v = await api("/api/validate", curVal()); } catch (e) { v = null; }
  const errs = v ? v.issues.filter(i => i.level === "error").length : 0;
  const nDone = Object.keys(S.done).length;
  if (!S.conns.length) {
    // Guardar vacío = quitar el mapa: sin conexiones no hay ✓ ni ◐.
    delete S.maps[tid]; delete S.done[tid];
    try { persistMaps(); } catch (e) {}
    refreshMarks();
    toast(`Mapa <b>${tid}</b> vaciado (sin ✓).`); status(`Mapa ${tid} vaciado.`);
    return;
  }
  S.maps[tid] = S.conns.map(c => [[...c.f], [...c.t]]);
  const cov = computeDone(tid);
  try { persistMaps(); } catch (e) {}
  refreshMarks();
  const state = cov && cov.ok ? `completo ✓` :
    `parcial ◐ (faltan A:[${cov ? cov.missA.join(",") : "?"}] B:[${cov ? cov.missB.join(",") : "?"}])`;
  if (errs) toast(`Borrador guardado <b>${tid}</b> (${S.conns.length}) — ${state} — con <b>${errs} error(es)</b>, revísalos en Verificar.`, 5000);
  else toast(`Mapa guardado <b>${tid}</b> (${S.conns.length}) — ${state} · ${nDone}/${S.transitions.length} completos`);
  status(`Mapa guardado ${tid} (${state}). Completos: ${Object.keys(S.done).length}/${S.transitions.length}.`);
};
function persistMaps() {
  if (!S.file) return;
  try { localStorage.setItem("mf-maps::" + S.file, JSON.stringify({v: 1, maps: S.maps, done: S.done})); } catch (e) {}
}
function restoreMaps() {
  if (!S.file) return;
  try {
    const raw = localStorage.getItem("mf-maps::" + S.file);
    if (!raw) return;
    const o = JSON.parse(raw);
    if (o && typeof o === "object") {
      if (o.v === 1 && o.maps) { S.maps = o.maps; S.done = o.done || {}; }
      else { S.maps = o; S.done = {}; } // legado: sin ✓ hasta revisitar cada par
    }
  } catch (e) {}
}
function autoSave() {
  if (S.pairIdx < 0) return;
  const t = S.transitions[S.pairIdx]; if (!t) return;
  // D31: sin conexiones no hay borrador. Vacío = retirar mapa y ✓ (si no, el ◐/✓ fantasma sobreviviría).
  const tid = `${t.from_var}->${t.to_var}`;
  if (!S.conns.length) {
    delete S.maps[tid]; delete S.done[tid];
    try { persistMaps(); } catch (e) {}
    refreshMarks();
    return;
  }
  S.maps[tid] = S.conns.map(c => [[...c.f], [...c.t]]);
  computeDone(tid);
  try { persistMaps(); } catch (e) {}
  refreshMarks();
}
function curVal() {
  return {n_from: S.gA ? S.gA.resolved_len : 0, n_to: S.gB ? S.gB.resolved_len : 0,
    glyph_map: S.conns.map(c => [c.f, c.t]),
    top_from: S.gA ? S.gA.top_len : 1, top_to: S.gB ? S.gB.top_len : 1, stale: false};
}

/* Paso 3 */
async function refreshIssues() {
  const render = (box, interactive) => {
    box.innerHTML = "";
    if (!S.gA) { box.innerHTML = '<p class="muted">Sin mapa todavía.</p>'; return; }
    if (!S.issues.length) box.innerHTML = '<p class="muted">Limpio: sin errores ni avisos.</p>';
    S.issues.forEach((iss, i) => {
      const d = document.createElement("div");
      d.className = "issue " + iss.level;
      d.innerHTML = `<span class="lv">${iss.level.toUpperCase()}</span><b>${iss.code}</b>: ${iss.message}`;
      if (interactive) d.onclick = () => locate(i);
      box.appendChild(d);
    });
  };
  if (!S.gA) { render($("issues"), true); render($("issues-dock"), false); return; }
  let v;
  try { v = await api("/api/validate", curVal()); }
  catch (e) {
    $("issues").innerHTML = '<p class="muted">Servidor no responde.</p>';
    $("issues-dock").innerHTML = $("issues").innerHTML; return;
  }
  S.issues = v.issues || [];
  render($("issues"), true); render($("issues-dock"), false);
  stepper();
}
function locate(i) {
  const iss = S.issues[i]; if (!iss) return;
  S._errIdx = {A: new Set(), B: new Set()};
  if (iss.side === "both" || iss.side === "") {
    ["A", "B"].forEach(s => (iss.indices.length ? iss.indices : allIdx(s)).forEach(x => S._errIdx[s].add(x)));
  } else if (iss.side === "from" || iss.side === "to") {
    const s = iss.side === "from" ? "A" : "B";
    (iss.indices.length ? iss.indices : allIdx(s)).forEach(x => S._errIdx[s].add(x));
  }
  const keepA = new Set(S.selA), keepB = new Set(S.selB);
  S.selA.clear(); S.selB.clear();
  redraw();
  S.selA = keepA; S.selB = keepB;
  document.querySelectorAll("#stage g.bdg").forEach(g => {
    if (S._errIdx[g.dataset.side] && S._errIdx[g.dataset.side].has(+g.dataset.idx)) g.classList.add("hl");
  });
  go("t-map");
  setTimeout(() => { S._errIdx = null; redraw(); }, 1600);
}
function allIdx(side) {
  const pay = side === "A" ? S.gA : S.gB;
  return pay ? pay.glyphs.map(g => g.index) : [];
}

/* Paso 4 */
let lastSnippet = "", lastBundle = null, lastAGENTE = "";
$("e-snip").onclick = async () => {
  const r = await api("/api/export", {mode: "snippet", glyph_map: S.conns.map(c => [c.f, c.t])});
  lastSnippet = r.snippet || ""; $("snip").textContent = lastSnippet;
};
function dl(name, text, type = "text/plain") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], {type})); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}
$("e-snipdl").onclick = () => lastSnippet ? dl("glyph_map.py", lastSnippet) : toast("Genera el snippet primero.", 3000, true);
$("e-bundle").onclick = async () => {
  const meta = {};
  S.transitions.forEach(t => {
    const tid = `${t.from_var}->${t.to_var}`;
    if (S.maps[tid]) meta[tid] = {fase: t.fase, latex_a: t.latex_a, latex_b: t.latex_b};
  });
  const r = await api("/api/export", {mode: "bundle", maps: S.maps, meta});
  lastBundle = r.bundle; lastAGENTE = r.instructions || "";
  let msg, ok = true;
  try {
    const back = JSON.parse(JSON.stringify(lastBundle));
    msg = `<b>Verificación:</b> JSON válido · <b>${back.transitions.length}/${S.transitions.length}</b> transiciones · ids: ${back.transitions.map(t => t.id).join(", ")}`;
  } catch (e) { ok = false; msg = "JSON INVÁLIDO: " + e; }
  const elx = $("bundle-report");
  elx.className = "report " + (ok ? "ok" : "err");
  elx.innerHTML = msg + `<br><b>AGENTE.md:</b> ${lastAGENTE.length} caracteres` +
    (lastAGENTE.includes("TransformByGlyphMap") ? ", con regla de reemplazo." : ", SIN regla — revisar.");
  if (ok) toast(`Bundle verificado: <b>${lastBundle.transitions.length}</b> transiciones.`);
};
$("e-bdl").onclick = () => lastBundle ? dl("agent_bundle.json", JSON.stringify(lastBundle, null, 2), "application/json") : toast("Genera el bundle primero.", 3000, true);
$("e-adl").onclick = () => lastAGENTE ? dl("AGENTE.md", lastAGENTE) : toast("Genera el bundle primero.", 3000, true);

/* Paso 5 */
$("p-gen").onclick = async () => {
  $("p-info").textContent = "Renderizando en el servidor (~10s)…";
  let r;
  try {
    r = await api("/api/preview", {latex_a: S.latexA, latex_b: S.latexB,
      glyph_map: S.conns.map(c => [c.f, c.t]), quality: "l"}, 320000);
  } catch (e) { $("p-info").textContent = "Servidor no responde."; return; }
  if (!r.ok) { $("p-info").textContent = "ERROR: " + r.error; $("p-log").textContent = (r.log || "").slice(-1500); return; }
  const bust = "?t=" + Date.now();
  $("p-video").src = r.mp4 + bust; $("p-video").play().catch(() => {});
  $("p-frame").src = r.png + bust;
  const sent = S.conns.map(c => `[${c.f}]→[${c.t}]`).join(" ");
  $("p-info").textContent = `Vista previa OK en ${r.seconds}s · ${S.conns.length} conexiones · ${new Date().toLocaleTimeString()} · ${sent}`;
  $("p-log").textContent = (r.log || "").slice(-500);
};

/* atajos */
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k" && !e.target.matches("input,select,textarea")) {
    e.preventDefault(); go("t-map");
    const f = $("pair-filter"); f.focus(); f.select();
    toast("Buscar par: escribe para filtrar el desplegable (p. ej. <code>eq5</code>).", 3000);
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.target.matches("input,select,textarea")) {
    e.preventDefault(); $("b-undo").click();
  }
  if (e.key === "?" && !e.target.matches("input,select,textarea")) $("tb-help").click();
  if ((e.key === "Delete" || e.key === "Backspace") && document.activeElement === $("stage")) $("b-del").click();
  if (e.key === "Escape" && !e.target.matches("input,select,textarea")) {
    S.selA.clear(); S.selB.clear(); S._delIdx = undefined; redraw(); inspectSel(); status("Selección limpiada.");
  }
  if ((e.key === "f" || e.key === "F") && !e.target.matches("input,select,textarea")) fitView();
});
$("f-path").value = "D:\\manim\\ejercicios\\cinetica_orden_cuatro.py";
stepper();
/* Requisitos: la app abre igual sin ellos, pero avisa claro en vez de fallar raro. */
(async () => {
  try {
    const h = await (await fetch("/api/health")).json();
    if (!h.ok) {
      const faltan = h.checks.filter(c => !c.ok).map(c => c.name).join(", ");
      toast(`<b>Faltan requisitos:</b> ${faltan}. Sin ellos no hay renders ni previas. Detalle en README (requirements.txt).`, 15000, true);
      status(`Faltan requisitos: ${faltan}. La app abre igual, pero sin renders.`);
    } else {
      status(`Requisitos OK: manim ${h.checks[0].detail} · MF_Tools + LaTeX presentes.`);
    }
  } catch (e) { /* sin servidor no hay chequeo */ }
})();

/* FREE-STATUS (aditivo): asignados vs libres. No edita drawCanvas/redraw por dentro;
   decora el DOM tras cada redraw y expone window.__mf.free() para QA. */
(function freeStatus() {
  if (typeof S !== "undefined") { if (S._freeHi === undefined) S._freeHi = true; if (S._freeOnly === undefined) S._freeOnly = false; }
  function assignedSets() {
    const a = new Set(), b = new Set();
    (S.conns || []).forEach(c => { (c.f || []).forEach(i => a.add(i)); (c.t || []).forEach(i => b.add(i)); });
    return {a, b};
  }
  function freeLists() {
    const out = {freeA: [], freeB: [], usedA: [], usedB: []};
    if (!S.gA || !S.gB) return out;
    const {a, b} = assignedSets();
    for (let i = 0; i < S.gA.resolved_len; i++) ((a.has(i) ? out.usedA : out.freeA).push(i));
    for (let i = 0; i < S.gB.resolved_len; i++) ((b.has(i) ? out.usedB : out.freeB).push(i));
    return out;
  }
  window.refreshFree = function refreshFree() {
    const svg = $("stage"); if (!svg) return {freeA: [], freeB: [], usedA: [], usedB: []};
    const st = freeLists();
    svg.classList.toggle("free-off", !S._freeHi);
    svg.classList.toggle("free-only", !!S._freeOnly);
    svg.querySelectorAll("path.g").forEach(p => {
      const side = p.dataset.side, idx = +p.dataset.idx;
      const used = side === "A" ? assignedSetsCache.a.has(idx) : assignedSetsCache.b.has(idx);
      p.classList.toggle("is-free", !used); p.classList.toggle("is-used", used);
    });
    svg.querySelectorAll("g.bdg").forEach(g => {
      const side = g.dataset.side, idx = +g.dataset.idx;
      const used = side === "A" ? assignedSetsCache.a.has(idx) : assignedSetsCache.b.has(idx);
      g.classList.toggle("free", !used); g.classList.toggle("used", used);
    });
    const setTxt = (id, txt, hasFree) => { const e = $(id); if (!e) return;
      e.textContent = txt; e.classList.toggle("has-free", !!hasFree); };
    setTxt("free-count-a", `A libres (${st.freeA.length}): ${st.freeA.join(", ") || "—"}`, st.freeA.length);
    setTxt("free-count-b", `B libres (${st.freeB.length}): ${st.freeB.join(", ") || "—"}`, st.freeB.length);
    setTxt("free-a-pill", S.gA ? `A libres ${st.freeA.length}/${S.gA.resolved_len}` : "", st.freeA.length);
    setTxt("free-b-pill", S.gB ? `B libres ${st.freeB.length}/${S.gB.resolved_len}` : "", st.freeB.length);
    const sum = $("free-sum"); if (sum) sum.textContent = S.gA ? `${st.freeA.length + st.freeB.length} libres` : "";
    const fill = (id, side, arr) => { const box = $(id); if (!box) return; box.innerHTML = "";
      if (!S.gA) { box.innerHTML = '<p class="muted">Sin par.</p>'; return; }
      if (!arr.length) { box.innerHTML = '<p class="muted">Ninguno: todo asignado ✓</p>'; return; }
      arr.forEach(idx => { const d = document.createElement("div"); d.className = "tr";
        d.innerHTML = `<span class="badge">${side}${idx}</span><span>libre — clic para seleccionar</span>`;
        d.onclick = ev => { const sel = side === "A" ? S.selA : S.selB;
          if (!ev.ctrlKey && !ev.metaKey) sel.clear(); sel.add(idx); redraw(); inspectSel(); };
        box.appendChild(d); }); };
    fill("free-a-list", "A", st.freeA); fill("free-b-list", "B", st.freeB);
    const ft = $("free-toggle"); if (ft) ft.textContent = `Resaltar libres: ${S._freeHi ? "ON" : "OFF"}`;
    const fo = $("free-only"); if (fo) fo.textContent = S._freeOnly ? "Ver todos" : "Solo libres";
    return st;
  };
  // caché por frame para no recalcular por nodo
  let assignedSetsCache = {a: new Set(), b: new Set()};
  const _refreshFreeInner = window.refreshFree;
  window.refreshFree = function () { assignedSetsCache = assignedSets(); return _refreshFreeInner(); };
  function wire(id, fn) { const e = $(id); if (e && !e._freeWired) { e._freeWired = true; e.onclick = fn; } }
  wire("free-toggle", () => { S._freeHi = !S._freeHi; refreshFree(); });
  wire("free-only", () => { S._freeOnly = !S._freeOnly; refreshFree(); });
  wire("free-sel-a", () => { const st = freeLists(); S.selA = new Set(st.freeA); redraw(); inspectSel(); });
  wire("free-sel-b", () => { const st = freeLists(); S.selB = new Set(st.freeB); redraw(); inspectSel(); });
  // gancho: tras cada redraw original, refrescar estado libre (1 sola llamada, sin tocar redraw)
  if (typeof redraw !== "undefined" && !redraw._freeWrapped) {
    const orig = redraw;
    redraw = function () { const r = orig.apply(this, arguments); try { refreshFree(); } catch (e) {} return r; };
    redraw._freeWrapped = true;
  }
  try { refreshFree(); } catch (e) {}
  if (window.__mf) window.__mf.free = () => (window.refreshFree ? window.refreshFree() : {freeA: [], freeB: []});
})();
/* gancho de test (solo QA local): dibujo sintético, lectura de insignias, paneo medido */
window.__mf = Object.assign(window.__mf || {}, {
  badges() {
    const out = {A: [], B: []};
    document.querySelectorAll("#stage g.bdg").forEach(g => {
      (g.dataset.side === "A" ? out.A : out.B).push(+g.querySelector("text").textContent);
    });
    return out;
  },
  badgeBoxes() {
    const r = [];
    document.querySelectorAll("#stage g.bdg").forEach(g => {
      const b = g.getBoundingClientRect();
      r.push({side: g.dataset.side, idx: +g.dataset.idx, x0: b.x, y0: b.y, x1: b.right, y1: b.bottom});
    });
    return r;
  },
  async setPair(i) { await loadPair(i); },
  async measurePan(frames) {
    // Coste JS dentro de UN frame (sin esperar al siguiente rAF: en headless
    // el cuanto de frame falsea la medida). Detecta regresiones reales
    // (p. ej. reconstruir el minimapa entero por frame).
    const xs = [];
    await new Promise(r => requestAnimationFrame(() => {
      for (let f = 0; f < frames; f++) {
        const t0 = performance.now();
        const v = S.view;
        setView({x: v.x + v.w * 0.01, y: v.y, w: v.w, h: v.h});
        xs.push(performance.now() - t0);
      }
      r();
    }));
    xs.sort((a, b) => a - b);
    return {avg: xs.reduce((a, b) => a + b, 0) / xs.length, p95: xs[Math.floor(xs.length * 0.95)], n: xs.length};
  }
});
