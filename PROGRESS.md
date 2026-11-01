# PROGRESS.md

## Fase actual: Fase 2 shell terminada, esperando aprobación
## Hecho
- Entorno verificado: Python 3.12.4, Manim 0.20.0, MF_Tools 1.1.1 (ruta localizada).
- Leído `transforms.py` (127 líneas), `__init__.py`, `misc.py`, `manim index_labels`.
- Experimentos MathTex ejecutados: simple, frac, sqrt, sub, exp, groups, larga, multiarg + estructura profunda frac/groups.
- Creados `VERIFIED_FACTS.md`, `DECISIONS.md`, este archivo.
- Fase 1: `src/mf_core/extractor.py` + `glyph_worker.py` (subprocess JSON) + `src/mf_ui/inspector.py` (2 paneles, indices visibles, render async). QA paridad 7/7 + worker ok + UI offscreen ok + fix UI-thread (stdin + refs vivas) verificado.
- Fase 2: `src/mf_core/glyph_map_model.py` (N→M, reuso origen, undo/redo, serializable) + UI (clic/Ctrl, auto 1→1, boton N→M, lineas clicables, zoom/pan, Ctrl+Z/Y). Tests modelo 3/3 + test UI offscreen OK.
- Fase 3: `src/mf_core/validator.py` (7 codigos, replica restantes MF_Tools) + UI (fades explicitos, STALE, issues clicables que localizan glifos). Bateria 2/2 + modelo 3/3 + UI Fase2/3 OK, sin falsos positivos en mapas validos.
- Fase 4: `src/mf_core/exporter.py` (snippet `*glyph_map` + JSON) + dock exportar (preview, copiar, guardar .json+.py, abrir con re-render). Render real de escena minima OK (mp4, sin show_indices) + ida y vuelta identica + UI Fase4 OK.
- Fase 5: `src/mf_core/preview_worker.py` (render Manim + fotograma ffmpeg) + dock vista previa (reproductor, fotograma final, log de errores). Preview real OK en 8.5s + UI Fase5 OK.
- Fase 6 (DLC UI): `src/mf_ui/flow_windows.py` — Controlador + 3 ventanas dedicadas (Mapear espaciosa con splitter / Verificar+Exportar / Vista previa). Flow test OK. Tema oscuro `theme.qss` nativo (cero dependencias) aplicado en `app.py` e `inspector.py`.
- Fase 7 (V2.0): `src/mf_core/seq_extract.py` (AST: formulas, pares, fases) + `build_agent_bundle` + `src/mf_ui/seq_windows.py` (cargar .py, mapear por par, guardar mapa, exportar bundle). Verificado en tu `cinetica_orden_cuatro.py`: 21 formulas, 17 transiciones con BLOQUE, 0 avisos.
- Pulido grafico + `build_agent_instructions` (AGENTE.md junto al bundle). Test: relleno + 3 badges + barra dorada idx 1; md con ids, regla y prohibiciones.
- Fase 8 (estetica masiva): `icons.py` (14 SVG) + `onboarding.py` (bienvenida+?+tooltips) + `theme.qss` v2 + Inter empaquetada. Test 4 ventanas OK, suite intacta.
- Fix crash primer-clic (D17): workers cancelables, busy-guard, `closeEvent`, teardown `atexit`. Evidencia: clic+dobleclick en .py real + salida rc=0; suite verde.
- Fix dialogos modales (D17b): persistentes no modales + ruta directa + drag&drop en Secuencias.
- Fase 9a (web local backend): `web/server.py` stdlib (parse/render/validate/export/preview + estaticos). API verificada contra tu archivo (17 transiciones) y render real.
- Fase 9b (frontend): `web/static/` SPA — 5 pasos, lienzo SVG (misma regla grupos-de-4, verificada en node), informe de importación siempre visible, guardado con verificación, descargas bundle+AGENTE.md+snippet, previa con video. Stack en vivo: HTTP 200 + 17 transiciones. Arranque: `web_start.bat`.
## Falta
- Tu prueba en navegador + siguiente: pulido que pidas tras verla.
## En curso (01-nov-2026, agente A — asignados vs libres)
- Web aditiva sin tocar logica: `index.html` (+seccion #free-sec, pills #free-a/b-pill, v=4), `styles.css` (bloque FREE-STATUS al final), `app.js` (IIFE freeStatus al final + wrap de `redraw`, IDs `free-*`, `S._freeHi/_freeOnly`).
- Contrato para agente en paralelo: no editar `drawCanvas`/`redraw` por dentro; decorar via `refreshFree()` post-redraw; IDs reservados `free-*`; CSS prefijo `free-`/`is-free`/`is-used`. `window.__mf.free()` expone {freeA,freeB,usedA,usedB} para QA.
- Verificado: `node --check app.js` exit 0; `test_web.py` + `test_model.py` + `test_validator.py` verdes; logica libre 6v5 mock -> freeA [2,4,5], freeB [0,1,3,4] OK.
## En curso (01-nov-2026, agente A — tema claro + SVG/topbar)
- `tokens.css` v4: vars nuevas superficie/semanticos en A/B dark + light (lienzo siempre oscuro, D24); `styles.css` v5: `box-sizing`, `.tbtn` 30px centrado, `#stage/svg` block, hardcodes -> vars; `index.html` bump v5/v4.
- Verificado: `test_contrast.py` OK (9 pares base) + 8 pares light nuevos >=5.0 y dark-ok >=9.6; `test_web.py` verde; screenshots Playwright dark/light/map-tab sin `pageerror`; claro legible (inputs/report/listas) y ◐/? alineados.
## En curso (01-nov-2026, agente A — navbar/tipo 2026)
- `index.html`: logo SVG + chip v2.0 en `.brand` (mismo ids); `styles.css` v6: topbar 62px con linea accent, stepper pildoras con burbuja, base 15px/1.55, cards 24px/radio 16px/sombra.
- Verificado: `test_ids.py` (84 ids) + `test_contrast.py` + `test_web.py` verdes; screenshots Playwright dark/light sin `pageerror`.
## En curso (01-nov-2026, agente A — enlazado en claro D26)
- `tokens.css`: `--canvas` light `#f8fafc`; `styles.css` v8: lienzo claro, scroll por tab, switch, toast ✕, `.zbtn`; `index.html`: `#b-zin/#b-zout` + `zoom.js?v=1` (85→86 ids); `web/static/zoom.js` nuevo (wrap de `zoomAt`, cierre de toasts).
- Verificado: `test_ids` (86) + `test_contrast` + `test_web` verdes; Playwright D26 OK (stage claro rgb(248,250,252), scroll 1077>737, zoom in/out cambia y restaura viewBox, toast 1→0 con clic, switch 40px, 0 pageerrors).
## En curso (01-nov-2026, agente A — toolbar D27)
- `index.html`: `.actions` en 4 `.agroup` (MODO/CONECTAR/EDITAR/MAPA) con `data-label` y titles con atajos; `styles.css` v9: tarjeta, divisores, 11 iconos-mask.
- Verificado: `test_ids` (86) + `test_web` verdes; Playwright D27 OK (4 grupos, 11 máscaras, toggles intactos, 0 pageerrors dark+light).
## En curso (01-nov-2026, agente A — previa D28)
- `index.html`: `t-prev` en 3 tarjetas (cabecera + rejilla `figure.shot` + `details.logwrap`); `styles.css` v10.
- Verificado: `test_ids` (86) verde; Playwright D28 OK (cajas idénticas 559×314, 0 pageerrors dark+light).
## En curso (01-nov-2026, agente A — clic central D29)
- `zoom.js`: anti-autoscroll en captura + cursor grabbing; `styles.css` v11: glifos e insignias con más contraste.
- Verificado: `node --check`, `test_ids` (86); Playwright D29 OK (paneo central mueve viewBox, colores aplicados, 0 pageerrors).
## En curso (01-nov-2026, agente A — desplegable D30)
- `zoom.js?v=2`: envoltorio de `buildPairSel` que restaura la selección al par visible.
- Verificado: `node --check`, `test_ids` (86); Playwright D30 OK (navegar→sel "2", ✓ sin mover selección, limpiar+recargar→0 chulos, 0 pageerrors).
## En curso (01-nov-2026, agente A — barrido D31)
- `app.js` v9 (5 toques): guard anti-✓-fantasma en `autoSave`, status con cuenta real, limpieza en errores de render, `onclick` por `value`, fuera duplicados.
- Verificado: `node --check`, `test_ids` (87), `test_model`, `test_validator`, `test_web` verdes; Playwright D31 OK (hojear→0 ✓, recuperar→1+"1 mapeados", descartar→todo 0, 0 pageerrors). `test_canvas` funcional 3/3 OK; perf 60fps con varianza (pasa en rerun).
## En curso (01-nov-2026, agente A — exportar D32)
- `index.html`: `t-export` en 2 tarjetas numeradas + `figure.shot`; `styles.css` v12: `exp-head/exp-bar`, placeholder `#snip:empty`, 5 iconos-mask.
- Verificado: `test_ids` (87); Playwright D32 OK (snippet+bundle+2 descargas con contenido real, 5/5 máscaras, 0 pageerrors dark+light).
## En curso (01-nov-2026, agente A — verificar D33)
- `index.html`: `t-check` con cabecera numerada; `styles.css` v13: issues con píldora, stepper done/cur legibles, fix clases severidad.
- Verificado: `test_ids` (87); Playwright D33 OK (error+localizar+limpio, stepper tinta+burbuja, 0 pageerrors dark+light).
## En curso (01-nov-2026, agente A — cargar D34)
- `index.html`: `t-load` con cabeceras numeradas; `styles.css` v14: stats en informe, chulos-píldora, iconos upload/trash.
- Verificado: `test_ids` (87); Playwright D34 OK (informe ok, filtro 6→17, salto a par 4, inválido→err, descartar→0, 0 pageerrors dark+light).
## En curso (01-nov-2026, agente A — dock D35)
- `index.html`: dock como `figure.shot` + columna problemas; `styles.css` v15: píldoras vacías ocultas, placeholders.
- Verificado: `test_ids` (87); Playwright D35 OK (pre-carga sin líneas, dock en vivo, 0 pageerrors).
## En curso (01-nov-2026, agente A — sidebar D36)
- `styles.css` v16: scrollbars del tema, conteos y filas compactos.
- Verificado: `test_ids` (87); Playwright D36 OK (0 desbordes, listas y botones OK, 0 pageerrors dark+light).
## En curso (01-nov-2026, agente A — Ctrl+K D37)
- `app.js` (2 líneas): filtros aceptan `a->b`/`a → b`; versión la del otro agente (v21, sin bump propio).
- Verificado: `node --check`, `test_ids` (87); Playwright D37 OK (tab+foco, filtro flecha→1, no robo en inputs, 0 pageerrors).
## En curso (01-nov-2026, agente A — fotograma final D38)
- `src/mf_core/preview_worker.py`: `self.wait(0.5)` + ffmpeg `-sseof -0.1`.
- Verificado: `test_preview.py` verde; worker PNG idéntico al último frame (MAD 0.0 vs 0.284 mitad).
## En curso (01-nov-2026, agente A — flecha h3 + estabilidad)
- `index.html`: fuera la `→` sobre el lienzo; título ahora `EQ1 · EQ2` con tooltip "Par en edición: de A (origen) a B (destino)".
- Batería verde: `node --check` app.js+zoom.js, `test_ids` (86), `test_contrast`, `test_model`, `test_validator`, `test_exporter` (render real OK), `test_seq`, `test_web`; rutas servidas OK (/, /app.js, /styles.css, /static/zoom.js); sin `.tmp_` residuales.
## Bloqueos
- Ninguno.
## Patch Fase 3 (post-reporte, por QA usuario)
- glyph_path reescrito (grupos de 4 + moveTo en saltos; "=" ya con 2 subpaths, verificado).
- Regla consume-seleccion + `_suppress` en locate; MapView sin lambdas acumuladas.
- QShortcut a API valida (`activated.connect`, con refs).
- Worker con reintento backoff ante .dvi bloqueado (renders paralelos); defaults reales `x^2 + y=1` / `x^2 = 1-y` verificados en paralelo (6+6 glifos).
