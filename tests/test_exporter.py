"""QA exporter V3: bundle con constructores + validacion + parche listo."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from mf_core.exporter import build_agent_bundle, build_agent_instructions, build_scene_patch


def test_v3() -> None:
    maps = {"f1->f2": [([0, 1], [0, 1]), ([2], []), ([], [2])]}
    meta = {"f1->f2": {"fase": "BLOQUE 1", "latex_a": "a b", "latex_b": "a c",
                       "counts": {"n_from": 3, "n_to": 3, "top_from": 1, "top_to": 1}}}
    formulas = [
        {"var": "f1", "tex_single": "a b", "args": ["a", "b"],
         "colors": {"1": "#f9d66b"}, "spans": {"0": [0, 1], "1": [1, 2]},
         "font_size": 48, "n": 2, "top": 1},
        {"var": "f2", "tex_single": "a c", "args": ["a", "c"],
         "colors": {}, "spans": {"0": [0, 1], "1": [1, 2]},
         "font_size": 48, "n": 2, "top": 1},
    ]
    validations = {"f1->f2": {"errors": [], "warnings": [
        {"code": "DEST_REUSED", "message": "x"}]}}
    b = build_agent_bundle(maps, meta, formulas=formulas,
                           validations=validations, order=["f1->f2"])
    assert b["version"] == 3, b.get("version")
    assert len(b["formulas"]) == 2 and b["formulas"][0]["cname"] == "f1"
    t = b["transitions"][0]
    assert "MathTex" in t["construct_a"] and "font_size=48" in t["construct_a"], t["construct_a"]
    assert 'range(1, 2)' in t["construct_a"] and "#f9d66b" in t["construct_a"]
    assert t["validation"]["errors"] == [] and len(t["validation"]["warnings"]) == 1
    assert t["play"] == "self.play(TransformByGlyphMap(f1, f2, *GLYPH_MAP_F1_F2))", t["play"]
    assert t["counts"] == {"n_from": 3, "n_to": 3, "top_from": 1, "top_to": 1}
    md = build_agent_instructions(b)
    assert "REGLA DE ORO" in md and "single-string" in md and "0 errores" in md
    p = build_scene_patch(maps, meta, formulas=formulas,
                          validations=validations, order=["f1->f2"])
    assert "GLYPH_MAP_F1_F2" in p and "TransformByGlyphMap(f1, f2, *GLYPH_MAP_F1_F2)" in p, p[:500]
    assert "VERIFICADO" in p and "REGLA DE ORO" in p
    s = json.dumps(b, ensure_ascii=False)
    assert json.loads(s)["version"] == 3
    print("exporter V3 OK: bundle + parche + AGENTE.md")


def test_dup_vars() -> None:
    # bucle desenrollado: mismo var, distinto tex -> cnames fx_1, fx_2
    maps = {"f8->fx": [([0], [0])], "f9->fx": [([0], [0])]}
    meta = {"f8->fx": {"fase": "", "latex_a": "A", "latex_b": "B9", "counts": {}},
            "f9->fx": {"fase": "", "latex_a": "B9", "latex_b": "B10", "counts": {}}}
    formulas = [
        {"var": "f8", "tex_single": "A", "args": ["A"], "colors": {},
         "spans": {}, "font_size": None, "n": 1, "top": 1},
        {"var": "fx", "tex_single": "B9", "args": ["B9"], "colors": {},
         "spans": {}, "font_size": None, "n": 1, "top": 1},
        {"var": "f9", "tex_single": "B9", "args": ["B9"], "colors": {},
         "spans": {}, "font_size": None, "n": 1, "top": 1},
        {"var": "fx", "tex_single": "B10", "args": ["B10"], "colors": {},
         "spans": {}, "font_size": None, "n": 1, "top": 1},
    ]
    b = build_agent_bundle(maps, meta, formulas=formulas, order=["f8->fx", "f9->fx"])
    cnames = [f["cname"] for f in b["formulas"]]
    assert cnames.count("fx_1") == 1 and cnames.count("fx_2") == 1, cnames
    p = build_scene_patch(maps, meta, formulas=formulas, order=["f8->fx", "f9->fx"])
    assert "fx_1" in p and "fx_2" in p
    # el play f9->fx usa el fx de la primera iteracion como origen (alias f9 = fx)
    assert "TransformByGlyphMap(" in p
    print("dup vars OK: fx_1/fx_2 sin colision")


if __name__ == "__main__":
    test_v3()
    test_dup_vars()
    print("ALL EXPORTER TESTS PASSED")
