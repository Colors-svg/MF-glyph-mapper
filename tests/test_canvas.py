"""Fase 3: test Regla de Oro (DOM == API), anti-solape y 60fps con 200 glifos."""
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / ".tmp_canvas_fixture.py"
FIX.write_text(
    "from manim import *\n"
    "class F(Scene):\n    def construct(self):\n"
    '        a = MathTex(r"\\frac{a}{b}")\n'
    '        b = MathTex(r"\\sqrt{x+1}")\n'
    '        c = MathTex(r"e^{i\\pi}")\n'
    '        d = MathTex(r"x_{i+1}")\n'
    '        e = MathTex(r"{{x}}+{{y}}")\n'
    '        f = MathTex(r"\\frac{d}{dx}f(x)g(x)=f(x)\\frac{d}{dx}g(x)+g(x)\\frac{d}{dx}f(x)")\n'
    "        self.play(TransformMatchingTex(a, b))\n"
    "        self.play(TransformMatchingTex(c, d))\n"
    "        self.play(TransformMatchingTex(e, f))\n",
    encoding="utf-8",
)
srv = subprocess.Popen([sys.executable, "-u", "web/server.py", "--port", "0"],
                       cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
# puerto efimero: lo leemos del log (evita colisiones con servidores huerfanos)
actual = None
for _ in range(60):
    line = srv.stdout.readline()
    m = re.search(r"http://\S+:(\d+)", line)
    if m:
        actual = int(m.group(1))
        break
assert actual, "el servidor no arranco"
PORT = actual


def api(path, obj, timeout=200):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}",
                                 data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


try:
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2)
            break
        except Exception:
            time.sleep(1)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(f"http://127.0.0.1:{PORT}/")
        pg.evaluate("localStorage.setItem('mf-tour','1')")
        pg.goto(f"http://127.0.0.1:{PORT}/")
        pg.fill("#f-path", str(FIX))
        pg.click("#f-go")
        pg.wait_for_function("document.querySelectorAll('#pair-sel option').length === 3", timeout=60000)

        # 1) REGLA DE ORO: insignias DOM == indices API, en los 6 tipos (3 pares x 2 lados)
        for i in range(3):
            pg.evaluate(f"loadPair({i})")
            pg.wait_for_function("document.querySelectorAll('#stage g.bdg').length > 0", timeout=180000)
            pg.wait_for_timeout(400)
            dom = pg.evaluate("window.__mf.badges()")
            t = pg.evaluate(f"({json.dumps(None)} , window.__mf ? 1 : 0)")
            lat = pg.evaluate("({a: S.latexA, b: S.latexB})")
            pa = api("/api/render", {"latex": lat["a"], "path": [0]})
            pb = api("/api/render", {"latex": lat["b"], "path": [0]})
            ea = sorted(g["index"] for g in pa["glyphs"])
            eb = sorted(g["index"] for g in pb["glyphs"])
            assert sorted(dom["A"]) == ea, f"par {i} lado A: DOM {sorted(dom['A'])} != API {ea}"
            assert sorted(dom["B"]) == eb, f"par {i} lado B: DOM {sorted(dom['B'])} != API {eb}"
            print(f"par {i}: DOM==API OK ({len(ea)} vs {len(eb)} glifos)")
            # 2) anti-solape por lado
            boxes = pg.evaluate("window.__mf.badgeBoxes()")
            for side in ("A", "B"):
                bs = sorted([x for x in boxes if x["side"] == side], key=lambda x: x["y0"])
                for x, y in zip(bs, bs[1:]):
                    assert y["y0"] >= x["y1"] - 1.5, f"solape en {side}: {x} vs {y} (par {i})"
            print(f"par {i}: anti-solape OK")

        # 3) 60fps con 200 glifos sinteticos (payload real xN, reindexado)
        perf = pg.evaluate("""async () => {
          const r = await (await fetch('/api/render', {method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({latex: 'x^2 + y=1', path:[0]})})).json();
          const gs = [];
          for (let k = 0; k < 34 && gs.length < 200; k++)
            r.glyphs.forEach((g, j) => { if (gs.length < 200) {
              const pts = g.points.map(p => [p[0] + k*3, p[1], p[2]]);
              gs.push({...g, index: gs.length, points: pts,
                center: [g.center[0] + k*3, g.center[1], g.center[2]]}); } });
          S.conns = []; S.gB = {ok:true, resolved_len:200, top_len:1, glyphs:gs};
          S.gA = {ok:true, resolved_len:1, top_len:1, glyphs:[r.glyphs[0]]};
          S.view = null; redraw();
          return window.__mf.measurePan(90);
        }""")
        print(f"perf 200 glifos: avg={perf['avg']:.2f}ms p95={perf['p95']:.2f}ms n={perf['n']}")
        assert perf["avg"] < 16.7, f"bajo 60fps: avg {perf['avg']:.2f}ms"
        assert not errs, errs
        b.close()
    print("GOLDEN+OVERLAP+FPS OK")
finally:
    srv.terminate()
    FIX.unlink(missing_ok=True)
print("ALL CANVAS TESTS PASSED")
