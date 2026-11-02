"""Puerta verde de release: gates rápidos siempre, gates Manim con --full."""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fails: list[str] = []


def gate(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'OK' if ok else 'FAIL'}] {name} {detail}", flush=True)
    if not ok:
        fails.append(name)


def main() -> int:
    full = "--full" in sys.argv
    # 1) sintaxis JS
    for js in ("web/static/app.js", "web/static/zoom.js"):
        p = subprocess.run(["node", "--check", js], cwd=ROOT,
                           capture_output=True, text=True)
        gate(f"node --check {js}", p.returncode == 0,
             (p.stderr or "").strip()[:200])
    # 2) ids únicos
    p = subprocess.run([sys.executable, "tests/test_ids.py"], cwd=ROOT,
                       capture_output=True, text=True)
    gate("tests/test_ids.py", p.returncode == 0,
         (p.stderr or p.stdout).strip().splitlines()[-1][:200] if (p.stderr or p.stdout) else "")
    # 2b) arcos: signo y sagita contra el Manim instalado
    p = subprocess.run([sys.executable, "tests/test_arcs.py"], cwd=ROOT,
                       capture_output=True, text=True)
    gate("tests/test_arcs.py", p.returncode == 0,
         (p.stderr or p.stdout).strip().splitlines()[-1][:200] if (p.stderr or p.stdout) else "")
    # 3) demo parseable
    sys.path.insert(0, str(ROOT / "src"))
    from mf_core.seq_extract import parse_file
    sq, _ = parse_file(str(ROOT / "demo" / "escena_demo.py"))
    gate("demo 4 formulas/3 transiciones",
         len(sq.formulas) == 4 and len(sq.transitions) == 3,
         f"f={len(sq.formulas)} t={len(sq.transitions)}")
    # 4) humo web (sin renders Manim: solo carga + tour + demo)
    srv = subprocess.Popen(
        [sys.executable, "-u", "web/server.py", "--port", "0"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    port = None
    for _ in range(60):
        m = re.search(r"http://\S+:(\d+)", srv.stdout.readline())
        if m:
            port = int(m.group(1))
            break
    try:
        assert port, "servidor no arranco"
        from playwright.sync_api import sync_playwright
        errs: list[str] = []
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            pg.goto(f"http://127.0.0.1:{port}/")
            pg.wait_for_timeout(2500)
            checks = {
                "tour visible": pg.evaluate("!document.getElementById('tour-scrim').hidden"),
                "health ok": pg.evaluate("fetch('/api/health').then(r=>r.json()).then(h=>h.ok)"),
                "boton demo": pg.evaluate("!!document.getElementById('b-demo')"),
                "boton idioma": pg.evaluate("!!document.getElementById('tb-lang')"),
                "boton sugerencias": pg.evaluate("!!document.getElementById('b-sugg')"),
                "23 botones mapa": pg.evaluate(
                    "['b-quick','b-conn','b-curves','b-fout','b-fin','b-del','b-undo','b-redo',"
                    "'b-clear','b-savemap','b-sugg','b-suggno','e-snip','e-snipdl','e-bundle',"
                    "'e-bdl','e-adl','e-glob','e-globdl','e-patch','e-patchdl','b-autoarc','b-learnclear']"
                    ".every(id=>!!document.getElementById(id))"),
            }
            for k, v in checks.items():
                gate(f"humo: {k}", bool(v))
            gate("humo: 0 pageerrors", not errs, "; ".join(errs[:3]))
            b.close()
    finally:
        srv.terminate()
    # 5-7) gates lentos con Manim real
    if full:
        p = subprocess.run([sys.executable, "tests/test_canvas.py"], cwd=ROOT,
                           capture_output=True, text=True, timeout=1800)
        tail = (p.stdout or "").strip().splitlines()[-5:]
        gate("tests/test_canvas.py", p.returncode == 0, " | ".join(tail)[:300])
    else:
        print("[--] gates Manim omitidos (usa --full)", flush=True)
    print("RESULTADO:", "VERDE" if not fails else f"ROJO: {fails}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
