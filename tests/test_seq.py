"""QA Fase 7: extractor AST + bundle por nombres reales."""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from mf_core.seq_extract import parse_file
from mf_core.exporter import build_agent_bundle, build_agent_instructions

FIXTURE = '''
from manim import *
from MF_Tools import *

class Demo(Scene):
    def construct(self):
        # ====================================================
        # BLOQUE 1: PLANTEAMIENTO
        # ====================================================
        eq1 = MathTex(r"x^2 + y=1", font_size=52)
        eq2 = MathTex(r"x^2 = 1-y", font_size=52)
        self.play(TransformMatchingTex(eq1, eq2))
        # BLOQUE 2: CIERRE
        eq3 = MathTex("a", "+", "b")
        self.play(TransformMatchingTex(eq2, eq3))
        guia = Tex(r"hola")
        dyn = MathTex(f"x + {n}")
        self.play(TransformMatchingTex(eq1, nose))
'''


def test_fixture() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(FIXTURE)
        fp = f.name
    sq, lines = parse_file(fp)
    assert [x.var for x in sq.formulas] == ["eq1", "eq2", "eq3", "guia", "dyn"], \
        [x.var for x in sq.formulas]
    assert sq.formulas[2].args == ["a", "+", "b"]  # multi-arg se conserva
    assert sq.formulas[4].dynamic and any("dyn" in w for w in sq.warnings)
    assert [(t.from_var, t.to_var) for t in sq.transitions] == [("eq1", "eq2"), ("eq2", "eq3")]
    assert any("nose" in w for w in sq.warnings)  # par a var desconocida fuera
    ph = sq.phases(lines)
    assert ph[id(sq.transitions[0])].startswith("BLOQUE 1"), ph[id(sq.transitions[0])]
    assert ph[id(sq.transitions[1])].startswith("BLOQUE 2"), ph[id(sq.transitions[1])]
    print("fixture OK: formulas, multi-arg, dinamicos, pares, fases")


FIXTURE_TBGM = '''
from manim import *
from MF_Tools import TransformByGlyphMap

MAP_OK = [([0], [0]), ([1, 2], [3], {"path_arc": 1.57}), ([4], [])]
MAP_DIN = [([0], [k]) for k in range(2)]

class Demo(Scene):
    def construct(self):
        # BLOQUE 1: ida
        a = MathTex(r"x = y")
        b = MathTex(r"y = x")
        self.play(TransformByGlyphMap(a, b, *MAP_OK))
        self.play(TransformByGlyphMap(b, a, *MAP_DIN))
        self.play(TransformByGlyphMap(a, b))
'''


def test_tbgm() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(FIXTURE_TBGM)
        fp = f.name
    sq, lines = parse_file(fp)
    assert [(t.from_var, t.to_var) for t in sq.transitions] == [("a", "b"), ("b", "a"), ("a", "b")]
    assert sq.transitions[0].map_name == "MAP_OK"
    assert sq.transitions[2].map_name == ""
    assert sq.prefill["a->b"] == [[[0], [0]], [[1, 2], [3]], [[4], []]]
    assert "b->a" not in sq.prefill  # dinamico: transicion si, precarga no
    assert any("MAP_DIN" in w for w in sq.warnings)
    assert any("opciones por entrada" in w for w in sq.warnings)
    print("tbgm OK: ambos formatos, precarga literal, dinamico y opciones avisados")


def test_bundle() -> None:
    maps = {"eq1->eq2": [([0], [0]), ([1], [1])]}
    meta = {"eq1->eq2": {"fase": "BLOQUE 1", "latex_a": "x^2 + y=1", "latex_b": "x^2 = 1-y"}}
    b = build_agent_bundle(maps, meta)
    assert b["transitions"][0]["from_var"] == "eq1"
    assert b["transitions"][0]["glyph_map"] == [[[0], [0]], [[1], [1]]]
    s = json.dumps(b, ensure_ascii=False)
    assert json.loads(s) == b
    md = build_agent_instructions(b)
    assert "eq1->eq2" in md and "TransformByGlyphMap" in md
    assert "Prohibiciones" in md and "latex_a" in md and "show_indices" in md
    assert "1.1.1" in md
    print("bundle + AGENTE.md OK")


if __name__ == "__main__":
    test_fixture()
    test_tbgm()
    test_bundle()
    print("ALL SEQ TESTS PASSED")
