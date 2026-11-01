"""QA Fase 4: el snippet ejecuta en escena minima real + ida y vuelta identica."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from mf_core.exporter import build_snippet, build_project, project_to_glyph_map, dumps_project

LATEX_A = "x^2 + y=1"
LATEX_B = "x^2 = 1-y"
MAP = [([0], [0]), ([1], [1]), ([2], [4]), ([3], [2]), ([4], [3]), ([5], [5])]


def test_roundtrip() -> None:
    proj = build_project(LATEX_A, LATEX_B, [0], 6, 6, MAP)
    s1 = build_snippet(project_to_glyph_map(proj))
    proj2 = json.loads(dumps_project(proj))
    s2 = build_snippet(project_to_glyph_map(proj2))
    assert s1 == s2, "exportar->importar->exportar debe ser identico"
    assert "TransformByGlyphMap(mobA, mobB, *glyph_map)" in s1
    print("round-trip identico OK")


def test_ejecuta_en_manim() -> None:
    root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(dir=str(root), prefix=".tmp_probe_") as tmp:
        scene = Path(tmp) / "test_scene.py"
        snippet = "\n".join("        " + ln if ln.strip() else ""
                              for ln in build_snippet(MAP).splitlines()
                              if not ln.startswith(("from MF_Tools", "# Generado", "# Requiere")))
        scene.write_text(
            "from manim import *\nfrom MF_Tools import TransformByGlyphMap\n\n"
            "class GlyphMapProbe(Scene):\n"
            "    def construct(self):\n"
            f"        mobA = MathTex(r\"{LATEX_A}\")\n"
            f"        mobB = MathTex(r\"{LATEX_B}\")\n"
            "        self.add(mobA)\n"
            + snippet + "\n",
            encoding="utf-8",
        )
        print("--- escena ---\n" + scene.read_text(encoding="utf-8"))
        p = subprocess.run(
            [sys.executable, "-m", "manim", "render", "-ql",
             "--media_dir", str(Path(tmp) / "media"), str(scene), "GlyphMapProbe"],
            capture_output=True, text=True, timeout=300,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        tail = (p.stdout + p.stderr)[-1500:]
        print("--- manim tail ---\n" + tail)
        assert p.returncode == 0, f"manim fallo rc={p.returncode}"
        assert "Showing indices" not in tail and "do not match" not in tail, \
            "cayo en show_indices: el mapa no cuadra"
        mp4s = list(Path(tmp).rglob("*.mp4"))
        assert mp4s, "no se genero mp4"
        print("render OK:", mp4s[0].name)


if __name__ == "__main__":
    test_roundtrip()
    test_ejecuta_en_manim()
    print("ALL EXPORTER TESTS PASSED")
