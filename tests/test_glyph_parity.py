"""QA Fase 1: paridad 100% entre inspector y MF_Tools (misma ruta [0])."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mf_core.extractor import extract_glyphs  # noqa: E402

CASES = [
    r"x^2 + y",
    r"\frac{a}{b}",
    r"\sqrt{x+1}",
    r"x_{i+1}",
    r"e^{i\pi}",
    r"\frac{d}{dx}f(x)g(x)=f(x)\frac{d}{dx}g(x)+g(x)\frac{d}{dx}f(x)",
    r"{{x}}+{{y}}",  # caso limite: top>1
]


def mftools_resolved_len(latex: str, path=(0,)) -> tuple[int, int, list[int]]:
    """Replica exacta de transforms.py:25-30 para comparar."""
    from manim import MathTex
    mob = MathTex(latex)
    top = len(mob)
    target = mob
    for i in path:
        target = target[i]
    return top, len(target), list(range(len(target)))


def test_parity() -> None:
    rows = []
    for latex in CASES:
        payload = extract_glyphs(latex, [0])
        assert payload["ok"], payload
        top, n, idx = mftools_resolved_len(latex)
        got = [g["index"] for g in payload["glyphs"]]
        ok = (payload["top_len"] == top and payload["resolved_len"] == n and got == idx)
        rows.append((latex[:40], top, n, payload["resolved_len"], ok))
        assert ok, f"mismatch {latex}: MF_Tools={n} vs inspector={payload['resolved_len']}"
    print("PARITY TABLE (latex | top | mf_len | inspector_len | ok)")
    for r in rows:
        print(r)
    # {{...}} debe avisar ruta
    w = extract_glyphs(r"{{x}}+{{y}}", [0])
    assert w["top_len"] == 3 and w["warnings"], "caso limite {{...}} debe advertir"


def test_worker_subprocess() -> None:
    worker = ROOT / "src" / "mf_core" / "glyph_worker.py"
    req = json.dumps({"latex": r"\frac{a}{b}", "path": [0]})
    p = subprocess.run([sys.executable, str(worker), req], capture_output=True, text=True, timeout=120)
    payload = json.loads(p.stdout.strip().splitlines()[-1])
    assert payload["ok"] and payload["resolved_len"] == 3, payload
    print("worker subprocess OK:", payload["resolved_len"], "glifos")

    bad = json.dumps({"latex": r"\frac{", "path": [0]})
    p2 = subprocess.run([sys.executable, str(worker), bad], capture_output=True, text=True, timeout=120)
    payload2 = json.loads(p2.stdout.strip().splitlines()[-1])
    assert not payload2["ok"] and "error" in payload2, payload2
    print("worker LaTeX-error visible OK")


if __name__ == "__main__":
    test_parity()
    test_worker_subprocess()
    print("ALL QA PASSED")
