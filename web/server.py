"""Fase 9 (V2.1 web local): backend stdlib, cero dependencias.

Reusa mf_core intacto. Sirve la SPA + API JSON:
  GET  / | /app.js | /styles.css | /previews/<f>
  POST /api/parse {path} -> formulas, transiciones, fases, avisos
  POST /api/render {latex, path} -> glifos (via glyph_worker)
  POST /api/validate {n_from,n_to,glyph_map,top_from,top_to,stale}
  POST /api/export {mode:snippet|project|bundle, ...} -> textos listos para descargar
  POST /api/preview {latex_a,latex_b,glyph_map,quality} -> {mp4,png} servidos en /previews/
"""
from __future__ import annotations
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mf_core.seq_extract import parse_file  # noqa: E402
from mf_core.validator import validate  # noqa: E402
from mf_core.exporter import (  # noqa: E402
    build_snippet, build_project, build_agent_bundle, build_agent_instructions,
)

WEB = Path(__file__).resolve().parent
PREVIEWS = ROOT / "previews"
CACHE = ROOT / "media" / "glyphcache"
DEMO = ROOT / "demo" / "escena_demo.py"
CACHE.mkdir(parents=True, exist_ok=True)


def _code_rev() -> str:
    try:
        import subprocess
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "nogit"
    except Exception:  # noqa: BLE001
        return "nogit"


_CODE_REV = _code_rev()
_STARTED = __import__("time").strftime("%H:%M:%S")


def _norm_gm(entries) -> list:
    """Normaliza glyph_map del frontend: [f,t] o [f,t,{path_arc}] -> lista limpia."""
    out = []
    for e in entries or []:
        if not isinstance(e, (list, tuple)) or len(e) < 2:
            continue
        try:
            f = [int(x) for x in e[0]]
            t = [int(x) for x in e[1]]
        except Exception:
            continue
        if len(e) > 2 and isinstance(e[2], dict) and "path_arc" in e[2]:
            try:
                out.append([f, t, {"path_arc": float(e[2]["path_arc"])}])
                continue
            except Exception:
                pass
        out.append([f, t])
    return out


def _worker_env() -> dict:
    """Entorno de workers: PYTHONPATH con el shim anti-ventanas (Windows)."""
    import os
    env = dict(os.environ)
    shim = str(ROOT / "src" / "mf_winshim")
    env["PYTHONPATH"] = shim + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _run_worker(script: str, payload: dict, timeout: int) -> dict:
    key = None
    if script == "glyph_worker.py":
        import hashlib
        key = CACHE / (hashlib.sha256(json.dumps(
            {"latex": payload.get("latex", ""), "path": payload.get("path", [0])},
            sort_keys=True).encode()).hexdigest() + ".json")
        if key.is_file():
            try:
                hit = json.loads(key.read_text(encoding="utf-8"))
                hit["cached"] = True
                return hit
            except Exception:
                pass
    p = subprocess.run([sys.executable, str(ROOT / "src" / "mf_core" / script)],
                       input=json.dumps(payload), capture_output=True,
                       text=True, timeout=timeout, env=_worker_env())
    out = (p.stdout or "").strip()
    if not out:
        return {"ok": False, "error": f"worker sin stdout rc={p.returncode}: {(p.stderr or '')[-2000:]}"}
    res = json.loads(out.splitlines()[-1])
    if key is not None and res.get("ok"):
        try:
            key.write_text(json.dumps(res), encoding="utf-8")
        except Exception:
            pass
    return res


class Handler(BaseHTTPRequestHandler):
    server_version = "MFGlyphMapper/1"

    def _send_json(self, obj: dict, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, ctype: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        # App local en desarrollo continuo: nunca cachear estáticos (adiós ?v= manual).
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send_file(WEB / "static" / "index.html", "text/html; charset=utf-8")
        if u.path == "/app.js":
            return self._send_file(WEB / "static" / "app.js", "text/javascript; charset=utf-8")
        if u.path == "/styles.css":
            return self._send_file(WEB / "static" / "styles.css", "text/css; charset=utf-8")
        if u.path.startswith("/static/"):
            # D19: ficheros estaticos extra (styleguides, css/). Sin traversals.
            fp = (WEB / unquote(u.path).lstrip("/")).resolve()
            if not str(fp).startswith(str(WEB.resolve())) or not fp.is_file():
                return self._send_json({"ok": False, "error": "no existe"}, 404)
            ct = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                  ".js": "text/javascript; charset=utf-8",
                  ".svg": "image/svg+xml"}.get(fp.suffix, "application/octet-stream")
            return self._send_file(fp, ct)
        if u.path == "/api/health":
            return self._send_json(_health())
        if u.path.startswith("/previews/"):
            name = Path(unquote(u.path)).name
            fp = PREVIEWS / name
            if fp.is_file() and fp.suffix in (".mp4", ".png"):
                ct = "video/mp4" if fp.suffix == ".mp4" else "image/png"
                return self._send_file(fp, ct)
        self.send_response(404)
        self.end_headers()

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            n = 0
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode())
        except Exception:
            return {}

    def do_POST(self) -> None:  # noqa: N802
        req = self._body()
        try:
            if self.path == "/api/parse":
                sq, lines = parse_file(req.get("path", ""))
                by_var = sq.by_var()
                ph = sq.phases(lines)
                self._send_json({
                    "ok": True, "path": sq.path,
                    "formulas": [{"var": f.var, "kind": f.kind, "args": f.args,
                                   "line": f.line, "dynamic": f.dynamic} for f in sq.formulas],
                    "transitions": [{"from_var": t.from_var, "to_var": t.to_var, "kind": t.kind,
                                      "line": t.line, "fase": ph.get(id(t), "Sin fase"),
                                      "latex_a": (by_var[t.from_var].args[0]
                                                  if t.from_var in by_var and by_var[t.from_var].args else ""),
                                      "latex_b": (by_var[t.to_var].args[0]
                                                  if t.to_var in by_var and by_var[t.to_var].args else "")}
                                     for t in sq.transitions],
                    "warnings": sq.warnings, "prefill": sq.prefill})
            elif self.path == "/api/demo":
                self._send_json({"ok": True, "path": str(DEMO),
                                 "exists": DEMO.is_file()})
            elif self.path == "/api/render":
                self._send_json(_run_worker("glyph_worker.py",
                                            {"latex": req.get("latex", ""), "path": req.get("path", [0])}, 180))
            elif self.path == "/api/validate":
                self._send_json({"ok": True, "issues": [
                    {"code": i.code, "level": i.level, "message": i.message,
                     "side": i.side, "indices": list(i.indices)}
                    for i in validate(req.get("n_from", 0), req.get("n_to", 0),
                                       _norm_gm(req.get("glyph_map", [])),
                                       top_from=req.get("top_from", 1), top_to=req.get("top_to", 1),
                                       path=tuple(req.get("path", [0])), stale=req.get("stale", False))]})
            elif self.path == "/api/export":
                mode = req.get("mode", "snippet")
                gm = _norm_gm(req.get("glyph_map", []))
                if mode == "snippet":
                    self._send_json({"ok": True, "snippet": build_snippet(gm)})
                elif mode == "project":
                    proj = build_project(req.get("latex_a", ""), req.get("latex_b", ""),
                                         req.get("path", [0]), req.get("n_from", 0),
                                         req.get("n_to", 0), gm)
                    self._send_json({"ok": True, "project": proj})
                elif mode == "bundle":
                    maps = req.get("maps", {})
                    bundle = build_agent_bundle(
                        {k: _norm_gm(v) for k, v in maps.items()},
                        req.get("meta", {}))
                    self._send_json({"ok": True, "bundle": bundle,
                                      "instructions": build_agent_instructions(bundle)})
                else:
                    self._send_json({"ok": False, "error": f"mode {mode}?"}, 400)
            elif self.path == "/api/preview":
                pay = _run_worker("preview_worker.py",
                                  {"latex_a": req.get("latex_a", ""), "latex_b": req.get("latex_b", ""),
                                   "glyph_map": _norm_gm(req.get("glyph_map", [])),
                                   "quality": req.get("quality", "l")}, 300)
                if pay.get("ok"):
                    pay["mp4"] = "/previews/" + Path(pay["mp4"]).name
                    pay["png"] = "/previews/" + Path(pay["png"]).name
                self._send_json(pay)
            else:
                self._send_json({"ok": False, "error": "ruta?"}, 404)
        except Exception as e:  # noqa: BLE001
            self._send_json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)

    def log_message(self, *a) -> None:
        pass


def _health() -> dict:
    """Chequeo de requisitos: la app funciona igual sin ellos, pero lo dice claro."""
    checks: list[dict] = []
    try:
        import manim  # noqa: F401
        checks.append({"name": "manim", "ok": True, "detail": manim.__version__})
    except Exception as e:  # noqa: BLE001
        checks.append({"name": "manim", "ok": False, "detail": str(e)[:150]})
    try:
        import MF_Tools  # noqa: F401
        checks.append({"name": "MF_Tools", "ok": True,
                       "detail": getattr(MF_Tools, "__file__", "")})
    except Exception as e:  # noqa: BLE001
        checks.append({"name": "MF_Tools", "ok": False, "detail": str(e)[:150]})
    import shutil
    for exe in ("latex", "dvisvgm"):
        path = shutil.which(exe)
        checks.append({"name": exe, "ok": bool(path), "detail": path or "no en PATH"})
    return {"ok": all(c["ok"] for c in checks), "checks": checks,
            "rev": _CODE_REV, "started": _STARTED}


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    PREVIEWS.mkdir(exist_ok=True)
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"MF Glyph Mapper web en http://{host}:{srv.server_address[1]}  (Ctrl+C para salir)")
    srv.serve_forever()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    run(port=ap.parse_args().port)
