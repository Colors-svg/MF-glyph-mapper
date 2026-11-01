"""QA Fase 9: API web local contra servidor real (urllib, sin dependencias)."""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "web"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from server import Handler  # noqa: E402

srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
base = f"http://127.0.0.1:{srv.server_address[1]}"
threading.Thread(target=srv.serve_forever, daemon=True).start()


def post(path, obj, timeout=320):
    req = urllib.request.Request(base + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def test_parse_real():
    r = post("/api/parse", {"path": r"D:\manim\ejercicios\cinetica_orden_cuatro.py"})
    assert r["ok"] and len(r["transitions"]) == 17, (r.get("warnings"), len(r.get("transitions", [])))
    assert r["transitions"][0]["from_var"] == "eq1" and r["transitions"][0]["fase"].startswith("BLOQUE 1")
    assert r["transitions"][0]["latex_a"].startswith("- \\frac")
    print("parse API OK: 17 transiciones + latex inline")


def test_render_validate_export():
    r = post("/api/render", {"latex": "x^2 + y=1", "path": [0]}, timeout=200)
    assert r["ok"] and r["resolved_len"] == 6, r
    assert all("points" in g and g["points"] for g in r["glyphs"])
    v = post("/api/validate", {"n_from": 6, "n_to": 6,
                               "glyph_map": [[[0], [0]], [[3], []]]})
    assert v["ok"] and any(i["code"] == "COUNT_MISMATCH" for i in v["issues"])
    e = post("/api/export", {"mode": "snippet", "glyph_map": [[[0], [0]]]})
    assert "TransformByGlyphMap(mobA, mobB, *glyph_map)" in e["snippet"]
    b = post("/api/export", {"mode": "bundle", "maps": {"eq1->eq2": [[[0], [0]]]},
                             "meta": {"eq1->eq2": {"f": 1}}})
    assert "TransformByGlyphMap" in b["instructions"] and b["bundle"]["transitions"][0]["from_var"] == "eq1"
    print("render+validate+export API OK")


if __name__ == "__main__":
    test_parse_real()
    test_render_validate_export()
    srv.shutdown()
    print("ALL WEB API TESTS PASSED")
