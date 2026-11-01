# DECISIONS.md

## D1 — Fuente de verdad = código instalado
Motivo: `TransformByGlyphMap` cambia entre versiones. Alternativa descartada: documentar desde GitHub o docs públicas.

## D2 — Target Manim 0.20.0 (no 0.19.0)
Motivo: es la versión instalada y verificada. Todo test se corre contra 0.20.0.

## D3 — V1 input = pegar 2 LaTeX single-string
Motivo: respeta Regla de Oro sin resolver extracción de `.py`. Usuario lo aprobó.
Alternativa (V2): ingresar `.py` y extraer `MathTex` literales. Pospuesta a V2.

## D4 — Índices = nivel `mob[0]` por defecto
Motivo: `transforms.py:25-30`. La UI deberá instanciar `MathTex` real y usar `m[0]`.
Si `len(m)!=1` (caso `{{...}}`/multi-arg), default `[0]` es incorrecto: el validador lo marcará (ruta incorrecta) en vez de adivinar.

## D5 — Reutilización de origen permitida, destino advertida
Motivo: `transforms.py:81` soporta origen repetido con `.copy()`; destino repetido no está validado en el código. El validador pedirá confirmación explícita.

## D6 — Dibujo UI desde `VMobject.points` (Fase 1, corregido Fase 3)
Motivo: posiciones deben salir de Manim, no de reconstrucción. Cada grupo de 4 puntos es un bezier independiente; si el inicio no coincide con el punto actual es salto de subpath (ej. "=" con 2 moveTos) y se hace moveTo. Avanzar de 3 en 3 trataba el ancla duplicada como handle y colgaba curvas falsas. Alternativas descartadas: re-render PNG + overlay, parsear SVG de disco.

## D7 — Worker por stdin + refs vivas en UI (fix Fase 1)
Motivo: pasar JSON por argv rompe en PowerShell (quita comillas) y el `RenderWorker` local era devorado por GC (botones quedaban en "renderizando" para siempre). Señal simplificada a `finished(dict)`, refs `self._worker/_thread`, subprocess con `input=req`. Verificado con test threadeado offscreen.

## D8 — Fase 2: auto-conexion solo 1→1, N→M con boton (endurecido Fase 3)
Motivo: `selectionChanged` dispara en cada Ctrl+clic parcial; auto-crear ahi generaria conexiones basura. Clic simple 1+1 conecta al instante; N→M y reutilizar origen usan "Conectar sel.". Regla "toda accion exitosa consume ambas selecciones": evita pares rancios que disparaban auto-transforms espurios y falsos "duplicada" (caso fade-in con origen viejo seleccionado). Lineas: conexion unica en `__init__`, no una por refresh. Pen via `itemChange`, no en `paint`. `_locate_issue` con `_suppress`.

## D9 — Fase 3: validador replica transforms.py:99-106, fades explicitos, STALE
Motivo: predecir `show_indices` antes de renderizar exige la misma aritmetica de restantes que MF_Tools. Sin correspondencia se cubre con botones fade out/in (entradas `([a],[])`/`([],[b])`), no con olvidos. STALE via `_rendered` vs texto actual; re-render poda fuera de rango y lo reporta. Instalado 1.1.1 no tiene `auto_fade`/`auto_morph`: no se validan esos modos, se documenta ausencia.

## D10 — Fase 4: snippet `*glyph_map` + proyecto JSON reabrible
Motivo: la forma `TransformByGlyphMap(A, B, *glyph_map)` acepta 2-tuplas y 3-tuplas con kwargs (transforms.py:43); el modelo no guarda kwargs, exporta 2-tuplas. Export bloqueado con errores (STALE incluido), permitido con warnings. Reabrir fija LaTeX, re-renderiza y aplica pendientes solo con ambos tamanos >0 (si no, se perderian). Test renderiza escena minima real en dir dentro del proyecto (%TEMP% rompe el pipeline tex de Manim).

## D11 — Fase 5: vista previa = mp4 Manim real + reproductor + fotograma ffmpeg
Motivo: criterio pide clip o fotograma; se entregan ambos (reproductor QtMultimedia + PNG final extraido con `-sseof -0.3`). Worker en proceso aparte con timeout 300s; errores de Manim/ffmpeg visibles en panel (status + log + dialogo). Artefactos en `previews/` con timestamp.

## D12 — Fase 6: tres ventanas (Mapear / Verificar+Exportar / Previa) con Controlador
Motivo: todo en una ventana apeñusca, peor con formulas grandes. Sin dependencias nuevas: Qt nativo. Controlador QObject comparte modelo/tamanos/STALE/issues/pending y avisa con `updated`; localizar viaja con senal `locate`. `inspector.py` intacto (compat + tests viejos); el flujo nuevo vive en `flow_windows.py` con entrada `app.py`.

## D13 — Tema oscuro QSS nativo (sin dependencias)
Motivo: salir del gris default del 2000 sin meter carga: QSS es parte de Qt, un archivo leido una vez al arrancar. Accion primaria en azul para guiar el flujo (Siguiente/Generar). `load_theme()` compartido en `app.py` e `inspector.py`.

## D14 — Fase 7: AST estatico + bundle por nombres reales (V2.0)
Motivo: no ejecutar la escena (importarla correria codigo del usuario). AST extrae `MathTex`/`Tex` literales (desenvolviendo `.shift()` etc.), pares de `TransformMatchingTex` y fases de comentarios `BLOQUE`. Lo no-literal se avisa, no se inventa. El bundle se clavea por variables reales (`eq1->eq2` + latex de verificacion) para que el agente reemplace sin adivinar; snippets "pegar y listo" descartados por decision del usuario.

## D15 — Grafico jerarquico + AGENTE.md
Motivo: el trazo azul plano no jerarquizaba. Relleno semitransparente + color por tipo (azul contenido, dorado barras `Rectangle`) + badges numerados; leyenda en panel. El `AGENTE.md` se genera junto al bundle (esquema, regla unica de reemplazo con ejemplo, 5 prohibiciones, contexto 1.1.1, verificacion por render).

## D16 — Estetica masiva sin dependencias (Fase 8)
Motivo: mismo formato en las 4 ventanas sin riesgo: QSS global + iconos SVG inline (QtSvg nativo) + Inter empaquetada (`assets/fonts/`, OFL, QFontDatabase). Onboarding una vez (QSettings) + boton ? + tooltips en cada accion. Regla: nada que toque logica; la suite verde es el detector de danos.

## D17 — Hilos render: anti-reentrancia + cancelables + teardown (fix crash 0xC0000409)
Motivo: re-render con hilo vivo reemplazaba el QThread en marcha y salir con renders vivos corrompia la pila al destruir. Ahora: segundo render rebota ("en curso"), workers Popen cancelables (`cancel()` mata el subprocess), `closeEvent` cancela+espera, `_track/_untrack` + `atexit` como red. Caza via QTest+faulthandler: clic+dobleclick en .py real, salida rc=0.
Nota: dialogos de archivo NO modales persistentes en los 6 puntos (el estatico modal podia dejar la app como "No responde"); ruta directa + drag&drop en Secuencias.

## D18 — Fase 9 web local con stdlib (cero dependencias)
Motivo: FastAPI no instalado y pip innecesario: `http.server` Threading + JSON basta para herramienta local. Reusa `mf_core` intacto (seq_extract, validator, exporter, workers). Frontend dibujara SVG desde `points` (misma regla de grupos de 4 + moveTo). `previews/` se sirve en `/previews/`.

## D19 — Fase 1 rediseño: tokens + styleguides + ruta /static/
Motivo: `tokens.css` centraliza color/tipo/espacio/radio/motion (dark A/B + light); las guías son autocontenidas (inline) para no depender del shell. Ruta genérica `/static/**` con guarda anti-traversal: necesaria para servir guías y el futuro shell con tokens. Contraste AA verificado por script (WCAG 2.1, 9 pares).

## D21 — Puertos efímeros en tests web + caza de servidores huérfanos
Motivo: un script de prueba que muere antes de `terminate()` deja el puerto squateado y el siguiente test habla en silencio con un servidor viejo (falsos fallos "imposibles": DOM sin #report, getScreenCTM undefined en fixtures fantasma). `test_canvas.py` usa `--port 0` y lee el puerto real del log; limpieza puntual de 8766–8777. No tocar el 8765 del usuario sin avisar.

## D22 — Canvas unificado: trasladar trazos + id único (fix "clic borra la app")
Motivo: los `points` de Manim vienen en coordenadas absolutas; se desplazaban insignias y curvas pero no los trazos de B (se dibujaba encima de A). Además `id="stage"` duplicado (main + svg) hacía que `getElementById` devolviera el contenedor e `innerHTML=""` vaciara la app. Fix: grupos `<g id="blockA/blockB">` con `translate(dx)`, `main id="workspace"`, test `test_ids.py` anti-regressión, `pointer-events:none` en badges/líderes para no robar clics.

## D24 — Guardar nunca bloquea; autosave + localStorage (fix "mapa no se guarda")
Motivo: `b-savemap` bloqueaba el guardado si había cualquier error (p. ej. COUNT_MISMATCH en un mapa parcial, que es el estado normal a mitad de trabajo) → el usuario mapeaba, intentaba guardar, se rechazaba en silencio relativo y al cambiar de par `loadPair` vaciaba `S.conns`. Fix: Guardar persiste siempre el borrador (avisa pero no bloquea; el bloqueo real queda en Exportar); autosave en cada mutación (conectar/eliminar/deshacer/rehacer/limpiar) + volcado al cambiar de par + `localStorage["mf-maps::<file>"]` restaurado al Cargar.

## D25 — Clic rápido A→B, líneas sutiles, clic en línea para eliminar (UX mapa)
Motivo: el ✓ se marcaba con solo existir `S.maps[tid]` (incluso `[]` o parcial) y cada vista lo calculaba por su cuenta. Ahora una sola fuente: `markFor()` (✓ completo / ◐ parcial / · vacío) usada por lista y selector; `pairCoverage()` exige todo glifo de A y B en alguna conexión; `computeDone()` solo valida con conteos reales del par cargado; `st-mapped` y toasts cuentan completos; vacío/Limpiar retiran mapa y ✓; persistencia con sobre `{v,maps,done}` (legado sin ✓ hasta revisitar).
Motivo: el flujo solo-botón obligaba a Ctrl+clic para todo; el clic simple limpiaba ambos lados (imposible A y luego B). Ahora el clic simple limpia solo su lado y con Rápido:ON (defecto) 1+1 conecta solo; Ctrl acumula N→M con Conectar. Líneas: grosor 1.2/opacidad .22, resto atenuado al enfocar (`focusing`), toggle Líneas ON/OFF; clic en línea marca la conexión para Eliminar. Sidebar en tarjetas con cabeceras fijas.

## D20 — Fase 2 shell banco de trabajo (variante B)
Motivo: layout 100dvh sin scroll de página (topbar/stepper/stage/statusbar); canvas dominante + sidebar colapsable + dock colapsable; stepper con done/current/blocked; selector agrupado por BLOQUE con filtro; UNA primaria por zona (Conectar/Guardar/Generar); destructivas diferenciadas con undo; sidebar→drawer <1100px. Sin tocar API ni lógica.

## D23 — Estado asignado/libre aditivo y paralelizable (web)
Motivo: saber que glifos ya estan asignados sin reescribir el canvas que otro agente puede estar tocando. Solo anade: seccion `#free-sec`, pills, CSS `FREE-STATUS`, IIFE `freeStatus` que decora `path.g`/`g.bdg` con `is-free`/`is-used` tras cada `redraw` (wrap, no edicion interna). Filtros `Resaltar libres` / `Solo libres` + `Sel. libres A/B` + listas clicables. Regla de asignado = aparece en algun `S.conns` (coherente con `mentioned_from/to` del modelo y `UNMENTIONED` del validador).

## D24 — Tema claro legible + botones/SVG arriba fijos (sin tocar logica)
Motivo: el claro tenia cajas negras con texto ilegible (inputs, report, listas con `#10141b/#0a0d13` quemados) y los botones ◐/? deformados (`button{padding}` vs `.tbtn{width/height}` sin `box-sizing` ni `padding:0`). El `svg{display:flex}` en `#stage` y el `svg` inline con `width:100%` desplazaban los SVG (hueco de linea base). Fix: variables nuevas en `tokens.css` (`--surface/--surface-2/--input-bg/--badge-bg/--row-hover/--row-cur/--row-line`, semanticos `--ok/--warn/--sel/--err`, `--canvas`) en A/B dark + light; `styles.css` usa esas vars en vez de hex quemados; lienzo `var(--canvas)` siempre oscuro para no rehacer colores de glifo; `*{box-sizing}`, `.tbtn` centrado 30px, `#stage/svg{display:block}`. Contraste light verificado AA (>=5.0 en los 8 pares nuevos).

## D25 — Navbar y tipografia 2026 (solo visual, IDs intactos)
Motivo: pagina con pinta prehistorica (13.5px, navbar de 6px, sin logo). Logo SVG inline en `.brand` (nodos A→B con curvas, gradiente accent, #mf-lg), chip `v2.0`, contexto (`#tb-file/#tb-pair`) como chips, `.tbtn` redondos 36px; stepper como pildoras segmentadas con burbuja `.n` (se conservan `data-tab` y clases `.cur/.done/.blocked` que usa `app.js`); escala base 15px/1.55, h2 17px, botones 12.5px/600, cards 24px + radio 16px + sombra, tabs 26px. Sin tocar JS ni IDs: `test_ids.py` y API intactos.

## D26 — Enlazado usable en claro: lienzo claro, scroll, zoom, ayuda cerrable, switch (sin tocar app.js)

## D27 — Barra de acciones agrupada con iconos (cero JS, convive con toggles)
Motivo: 12 botones en fila eran un muro ilegible. Grupos `MODO/CONECTAR/EDITAR/MAPA` con sobre-etiqueta y divisores en `.actions` (tarjeta). Iconos vía máscara CSS (`::before` + `mask-image` data-URI) con la geometría de `src/mf_ui/icons.py` (link/out/in/trash/undo/redo/clear/save + zap/curva/panel): heredan `currentColor`, funcionan en dark+light y sobreviven a los `textContent` de Rápido/Líneas (el texto sigue intacto). Sin tocar `app.js`: solo `index.html` (estructura) + `styles.css` v9. Verificado en Playwright: 4 grupos, 11 máscaras activas, toggles no rompen iconos, 0 pageerrors dark+light.

## D28 — Previa pareja: rejilla 16:9 + log plegable (sin tocar JS)
Motivo: video y fotograma a distintos tamaños + log crudo siempre visible. `t-prev` en 3 tarjetas: cabecera (botón + `#p-info` como píldora que se oculta vacía con `:empty`), rejilla 2×1 con `figure.shot` numeradas (`01 VIDEO`/`02 FOTOGRAMA`) en `aspect-ratio:16/9` idéntico y fondo negro (el mp4 es negro: a propósito), y `details.logwrap` para el registro. Mismos IDs: `app.js` intacto. `styles.css` v10. Verificado: cajas 559×314.44 idénticas, 0 pageerrors dark+light.

## D29 — Clic central sin autoscroll + visor con más contraste (sin tocar app.js)
Motivo: el botón central abría el autoscroll del navegador y peleaba con el paneo. `zoom.js`: `pointerdown` en captura con `button===1` hace `preventDefault()` (sin `stopPropagation`: el paneo de `app.js` sigue vivo), cursor `grabbing` mientras dura + restauración en `pointerup/cancel`; rueda sobre el minimapa con `preventDefault`. Colores: glifo `#58a6ff→#6ea8ff` con relleno .16→.20, trazo 1.3→1.4; insignias `#0f172a→#162032` y texto 11→11.5px; en claro relleno .10→.14. `styles.css` v11. Verificado en Playwright: viewBox se mueve con arrastre central, cursor grabbing→normal, trazos rgb(110,168,255)/rgb(31,111,235), 0 pageerrors.

## D30 — Desplegable sincronizado con el par visible (sin tocar app.js)

## D31 — Barrido de estabilidad: 4 bugs reales + duplicados (toques mínimos en app.js, v9)

## D32 — Exportar parejo con Previa + verificación punta a punta (sin tocar JS)
Motivo: snippet y bundle a distintos tamaños, log/informe crudo, botones sin iconos. `t-export` en 2 tarjetas `exp-head` numeradas (`01 Snippet`/`02 Bundle`) con `exp-bar` + `figure.shot` para el código (`#snip` con placeholder `:empty`) y el informe de verificación como `report` con borde de estado; 5 iconos-mask (code/download/package). Mismos IDs: `app.js` intacto. `styles.css` v12. Verificado en Playwright con 2 conexiones reales: snippet con TransformByGlyphMap, descarga `glyph_map.py`, bundle report ok 1/17 eq1→eq2, descargas `agent_bundle.json` (parseado, con la transición) y `AGENTE.md` (2273 c., con regla), 5/5 máscaras, 0 pageerrors dark+light.

## D33 — Verificar moderno + stepper legible + bug de severidad (CSS only, v13)
Motivo: `t-check` era una tarjeta plana y el stepper `done` en verde fino no pasaba contraste. `t-check` con cabecera numerada `exp-head`; issues aireados con píldora de severidad rellena (texto `var(--bg0)`, AA en ambos temas) y hover. Stepper: `done` en tinta con burbuja sólida verde+glifo oscuro (antes `color:var(--ok)` 12px, ilegible); `cur` con burbuja oscura+blanco. Bug cazado por el QA: `app.js` emite clases `error/warning/info` pero el CSS esperaba `err/warn` → ninguna severidad se pintaba nunca; renombrado solo en CSS (cero JS). Verificado: error detectado + clic localiza en Mapear (23 badges), mapa completo→0 errores, stepper done tinta+burbuja verde, 0 pageerrors dark+light.

## D34 — Cargar moderno + verificación funcional completa (HTML+CSS only, v14)
Motivo: `t-load` era el único paso sin numerar ni iconos. Cabeceras `exp-head` (`1 Cargar escena`/`2 Transiciones`), informe con cifras en acento, lista aireada con ✓ en píldora sólida y filtro consistente, iconos upload/trash en Cargar/Descartar. Sin tocar JS. Verificado: informe ok 21/17/0, filtro 6→17, salto a par 4 en Mapear, ruta inválida→`report err`, descartar→todo a 0, 2/2 máscaras, 0 pageerrors dark+light.

## D35 — Píldoras fantasma fuera + dock moderno (HTML+CSS only, v15)
Motivo: `#free-a/b-pill` mostraban su borde vacías junto a `#idx` antes de cargar (las "dos líneas"). `:empty{display:none}` → aparecen solo con contenido. Dock rehecho como `figure.shot` (`⌁ GLYPH_MAP EN VIVO`) + columna de problemas con título propio; placeholders `:empty` en `#gm-prev`/`#issues-dock`. Mismos IDs: JS intacto. Verificado: pre-carga ambas en `none`, con par código en vivo + píldoras visibles, 0 pageerrors.

## D36 — Sidebar consistente: scrollbars del tema, sin desbordes (CSS only, v16)
Motivo: scrollbars nativas grises sobre oscuro + conteos y filas algo amplios. Scrollbars finas del tema en `.tlist/.sidebar/.code` (webkit + `scrollbar-width`), conteos compactos con `word-break`, filas de libres más densas con badge fijo. Verificado: 0 desbordes horizontales, 12 items en lista A, 4/4 botones visibles, 0 pageerrors dark+light.

## D37 — Ctrl+K verificado + filtro acepta `eq1->eq2` (2 líneas en app.js)
Motivo: el atajo funcionaba (va a Mapear y enfoca el filtro, con `preventDefault` y guarda anti-robo en inputs), pero el filtro no entendía el formato con flecha que el propio desplegable muestra. `renderTList`/`buildPairSel` ahora incluyen `a->b` y `a → b` en el texto buscable. Verificado: Ctrl+K→tab+foco, `eq1->eq` filtra a 1 opción, Ctrl+K dentro de input no roba el foco, 0 pageerrors.

## D38 — Fotograma final de verdad (preview_worker, verificado a píxel)
Motivo: la escena terminaba justo al acabar la interpolación y el PNG se extraía a -0.3s: era un frame a mitad de transición (fantasmas en la captura del usuario). Ahora `self.wait(0.5)` fija el final en la fórmula asentada y ffmpeg extrae a -0.1s (dentro de la pausa). Evidencia: 22 frames extraídos, últimos 7 idénticos; MAD worker-vs-frame-final = 0.0 frente a 0.284 contra mitad de animación. `test_preview.py` verde.

## D36 — Sidebar consistente: scrollbars del tema, sin desbordes (CSS only, v16)
Motivo: scrollbars nativas grises sobre oscuro + conteos y filas algo amplios. Scrollbars finas del tema en `.tlist/.sidebar/.code` (webkit + `scrollbar-width`), conteos compactos con `word-break`, filas de libres más densas con badge fijo. Verificado: 0 desbordes horizontales, 12 items en lista A, 4/4 botones visibles, 0 pageerrors dark+light.
Motivo: `buildPairSel()` reconstruye las opciones y el `<select>` volvía al índice 0: mostraba otro par (y su ✓) distinto del visible → falsos positivos. `zoom.js` envuelve `buildPairSel` (igual que el wrap de `redraw`) y restaura `sel.value = S.pairIdx` si la opción existe (respeta filtros que ocultan el par). Al limpiar/recargar, ambas listas se reconstruyen desde `S.maps` y quedan a cero. Nota: el otro agente añadió persistencia en `localStorage` (`persistMaps/restoreMaps/autoSave`): recargar SIN borrar persistencia restaura ✓ correctamente (no es falso positivo). `zoom.js?v=2`. Verificado: t-list[2]→sel "2", ✓ con selección intacta, limpiar+recargar→0 chulos, 0 pageerrors.

## D39 — Arcos en abanico + sugerencias únicas 1:1 por forma (app.js, v23)
Motivo: las U rígidas tapaban fórmula; los arcos cuadráticos con pico escalonado (abanico por encima) distinguen cada conexión de un vistazo, como pedía el usuario. Sugerencias: firma de forma (puntos normalizados por centroide+tamaño, redondeo 0.005) agrupada por lado; solo se sugiere si la firma aparece EXACTAMENTE 1 vez en A y 1 en B (varias = manual). Gris punteado en abanico propio, clic en línea/fila/botón las acepta (una o todas), botón Ignorar las descarta; nunca cuentan para ✓/validar/exportar/guardar (pruneSugg las retira al aceptar/mapear).

## D40 — Paquete publicable GitHub (rendimiento + robustez + distribución)
Motivo: publicar exige gates verdes y cero fricción. Minimapa: solo mueve el rect del viewport (`S._miniKey`, sin reconstruir puntos por frame); métrica honesta dentro de un frame (el rAF headless falseaba 23ms; coste real 0.12ms). Servidor con `Cache-Control: no-store` (fin de `?v=` manual). Dedupe `layoutScale`. Desfase X de picos en arcos N→M. Demo `demo/escena_demo.py` (4 fórmulas/3 pares) + botón + endpoint `/api/demo`. Tour 4 pasos (`mf-tour`, relanzable desde `?`). `scripts/release_gates.py` (rápidos + `--full` Manim), `RELEASE_CHECKLIST.md`, `README.md`, `requirements.txt`, `LICENSE` MIT, `.gitignore`, `assets/icon.ico` (PIL), `iniciar.vbs` sin consola + script de acceso directo. Commit inicial limpio.
