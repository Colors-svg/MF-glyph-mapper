"""QA Fase 5: vista previa real (mp4 + fotograma final)."""
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

MAP = [([0], [0]), ([1], [1]), ([2], [4]), ([3], [2]), ([4], [3]), ([5], [5])]


def test_preview_real() -> None:
    root = Path(__file__).resolve().parent.parent
    req = json.dumps({"latex_a": "x^2 + y=1", "latex_b": "x^2 = 1-y",
                      "glyph_map": MAP, "quality": "l"})
    p = subprocess.run([sys.executable, str(root / "src" / "mf_core" / "preview_worker.py")],
                       input=req, capture_output=True, text=True, timeout=300, cwd=str(root))
    pay = json.loads(p.stdout.strip().splitlines()[-1])
    assert pay.get("ok"), pay
    assert Path(pay["mp4"]).exists() and Path(pay["mp4"]).stat().st_size > 0
    assert Path(pay["png"]).exists() and Path(pay["png"]).stat().st_size > 0
    print(f"preview OK en {pay['seconds']}s: {Path(pay['mp4']).name} + {Path(pay['png']).name}")


if __name__ == "__main__":
    test_preview_real()
    print("ALL PREVIEW TESTS PASSED")
