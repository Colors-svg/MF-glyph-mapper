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
    assert sq.prefill["a->b"] == [[[0], [0]], [[1, 2], [3], {"path_arc": 1.57}], [[4], []]]
    assert "b->a" not in sq.prefill  # dinamico: transicion si, precarga no
    assert any("MAP_DIN" in w for w in sq.warnings)
    assert not any("opciones por entrada" in w for w in sq.warnings)
    print("tbgm OK: ambos formatos, precarga literal con path_arc, dinamico avisado")


FIXTURE_TBGMINLINE = '''
from manim import *
from MF_Tools import TransformByGlyphMap
import math

class Demo(Scene):
    def construct(self):
        exp1 = MathTex("ax^2 + bx + c = 0")
        exp2 = MathTex("x^2 = 1")
        self.add(exp1)
        self.wait()
        self.play(TransformByGlyphMap(exp1, exp2,
            ([0], [5], {"path_arc": 2/3*PI}),
            ([0], [10], {"path_arc": 1/2*PI}),
            ([], [4, 9]),
            run_time=2
        ))
        self.wait()
'''


def test_tbgm_inline() -> None:
    import math
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(FIXTURE_TBGMINLINE)
        fp = f.name
    sq, _ = parse_file(fp)
    assert len(sq.transitions) == 1 and sq.transitions[0].kind == "tbgm"
    gm = sq.prefill["exp1->exp2"]
    assert gm[0][:2] == [[0], [5]] and abs(gm[0][2]["path_arc"] - 2 / 3 * math.pi) < 1e-9
    assert abs(gm[1][2]["path_arc"] - math.pi / 2) < 1e-9
    assert gm[2] == [[], [4, 9]]
    from mf_core.exporter import build_snippet
    sn = build_snippet(gm)
    assert "path_arc" in sn and "PI" in sn
    print("tbgm inline OK: path_arc 2/3PI y 1/2PI, fade [], export con PI")


FIXTURE_REPL = '''
from manim import *

class Demo(Scene):
    def construct(self):
        # BLOQUE 1: reemplazo
        a = MathTex(r"x = y")
        b = MathTex(r"y = x")
        self.play(ReplacementTransform(a, b))
        self.play(ReplacementTransform(a, b, run_time=1.2))
'''


def test_repl() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(FIXTURE_REPL)
        fp = f.name
    sq, lines = parse_file(fp)
    assert [(t.from_var, t.to_var, t.kind) for t in sq.transitions] == [("a", "b", "repl"), ("a", "b", "repl")]
    assert sq.prefill == {}
    assert any("ReplacementTransform" in w for w in sq.warnings)
    print("repl OK: pares migrables, sin precarga, aviso unico")


FIXTURE_LOCALS = '''
from manim import *
from MF_Tools import TransformMatchingTex

P_NOR = r"\\left( \\frac{P_t}{P_K} \\right)^{m} N"
CH = r"\\left[" + P_NOR + r"\\right]"

class Demo(Scene):
    def construct(self):
        # BLOQUE 9: locales
        f1 = pintar_partes(MathTex(*F1, font_size=48), {1: "red"})
        f2 = MathTex(r"I_t = \\epsilon (", r"K^*", r"- K_t)")
        self.play(ReplacementTransform(f1[1].copy(), f2[1], path_arc=0.5))
        self.play(TransformMatchingTex(f1, f2))
        l1 = MathTex(F3[0], font_size=40)
        for tag, key in (("F9", F9), ("F10", F10)):
            fx = pintar_partes(MathTex(key, font_size=48), {}, tag)
            self.play(TransformMatchingTex(f8 if tag == "F9" else f9, fx))
            if tag == "F9":
                f9 = fx
'''


def test_locals() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("F1 = [r\"a\", r\"b\"]\nF3 = [r\"c\", r\"d\"]\n"
                "F9 = r\"e\"\nF10 = r\"g\"\n"
                "f8 = MathTex(r\"h\")\n" + FIXTURE_LOCALS)
        fp = f.name
    sq, lines = parse_file(fp)
    by_var = sq.by_var()
    assert by_var["f1"].args == ["a", "b"], by_var["f1"].args  # *F1 desenrollado
    assert by_var["l1"].args == ["c"], by_var.get("l1")
    assert by_var["f2"].args[1] == "K^*"
    tids = [(t.from_var, t.to_var, t.kind) for t in sq.transitions]
    assert ("f1", "f2", "tmt") in tids, tids  # TMT con Names
    assert ("f8", "fx", "tmt") in tids, tids  # loop desenrollado, if resuelto
    assert ("f9", "fx", "tmt") in tids, tids
    snap = {f"{t.from_var}->{t.to_var}": (t.latex_a, t.latex_b) for t in sq.transitions}
    assert snap["f8->fx"][1] == "e", snap  # snapshot iteracion 1 (F9)
    assert snap["f9->fx"][1] == "g", snap  # snapshot iteracion 2 (F10)
    assert snap["f9->fx"][0] == "e", snap  # f9 nacio en iteracion 1
    assert not any("sin MathTex" in w for w in sq.warnings), sq.warnings
    print("locals OK: consts, starred, subscript, wrapper, loop+if, snapshots")


def test_carry() -> None:
    src = (
        "from manim import *\n"
        "import numpy as np\n"
        "class D(Scene):\n"
        "    def construct(self):\n"
        "        f1 = MathTex(r\"a\", r\"B\", r\"c\")\n"
        "        f2 = MathTex(r\"a(\", r\"K\", r\"c)\")\n"
        "        fly = f1[1].copy()\n"
        "        self.play(ReplacementTransform(fly, f2[1], path_arc=-np.pi / 3))\n"
        "        self.play(ReplacementTransform(f1[0].copy(), f2[0]))\n"
        "        self.play(ReplacementTransform(f1, f2, run_time=1.0))\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(src)
        fp = f.name
    sq, _ = parse_file(fp)
    tids = [(t.from_var, t.to_var, t.kind) for t in sq.transitions]
    assert ("f1", "f2", "tbgm") in tids, tids  # carry con indice precargado
    assert ("f1", "f2", "repl") in tids, tids  # Replacement pleno intacto
    pre = sq.prefill["f1->f2"]
    assert [[1], [1]] == pre[0][:2], pre
    import math
    assert abs(pre[0][2]["path_arc"] + math.pi / 3) < 1e-9, pre
    assert [[0], [0]] == [x for x in pre[1][:2]], pre  # copy inline sin path_arc
    assert not any("sin MathTex" in w for w in sq.warnings), sq.warnings
    print("carry OK: f1[1].copy()->f2[1] precarga con path_arc np.pi, repl intacto")


def test_demo_real() -> None:
    from pathlib import Path as _P
    demo = _P(r"D:\\manim\\escenas\\demo_tobin_premium.py")
    if not demo.is_file():
        print("demo real ausente, salto")
        return
    sq, _ = parse_file(str(demo))
    tids = sorted(f"{t.from_var}->{t.to_var}" for t in sq.transitions)
    assert tids == ["f1->f2", "f2->f4", "f5->f6", "f6->f7", "f7->f8",
                    "f8->fx", "f9->fx"], tids
    assert len(sq.formulas) >= 10, len(sq.formulas)
    assert not any("sin MathTex" in w for w in sq.warnings), sq.warnings
    assert any("l1" in w and "l2" in w and "Sin transicion" in w
               for w in sq.warnings), sq.warnings
    import math as _m
    pre = sq.prefill
    assert pre["f1->f2"][0][:2] == [[1], [1]]
    assert abs(pre["f1->f2"][0][2]["path_arc"] + _m.pi / 3) < 1e-9
    assert abs(pre["f5->f6"][0][2]["path_arc"] - _m.pi / 3) < 1e-9
    assert abs(pre["f7->f8"][0][2]["path_arc"] + _m.pi / 4) < 1e-9
    print(f"demo real OK: {len(sq.formulas)} formulas, {tids}")


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
    test_tbgm_inline()
    test_repl()
    test_locals()
    test_carry()
    test_demo_real()
    test_bundle()
    print("ALL SEQ TESTS PASSED")
