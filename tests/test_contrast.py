"""Fase 1: contraste AA verificado por script (WCAG 2.1, texto normal >= 4.5)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = (ROOT / "web" / "static" / "css" / "tokens.css").read_text(encoding="utf-8")


def lum(hex6: str) -> float:
    h = hex6.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a: str, b: str) -> float:
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


# Pares que existen tal cual en tokens.css (consistencia incluida).
PAIRS = [
    ("A ink/bg0", "#f5f1e6", "#0c1017", 4.5),
    ("A dim/bg1", "#a8b0bf", "#141a24", 4.5),
    ("A accent-ink/accent", "#06121f", "#5aa0ff", 4.5),
    ("B ink/bg0", "#e8edf3", "#161b22", 4.5),
    ("B dim/bg1", "#98a4b5", "#1d232e", 4.5),
    ("B accent-ink/accent", "#06231f", "#2dd4bf", 4.5),
    ("light ink/bg0", "#17202e", "#f4f5f7", 4.5),
    ("light A accent-ink/accent", "#ffffff", "#1f6feb", 4.5),
    ("light B accent-ink/accent", "#ffffff", "#0e7c6f", 4.5),
]


def main() -> None:
    for name, fg, bg, _ in PAIRS:
        assert fg.lower() in TOKENS.lower(), f"{name}: {fg} no esta en tokens.css"
        assert bg.lower() in TOKENS.lower(), f"{name}: {bg} no esta en tokens.css"
    bad = []
    for name, fg, bg, need in PAIRS:
        r = ratio(fg, bg)
        print(f"{name}: {r:.2f} (min {need})")
        if r < need:
            bad.append(name)
    assert not bad, f"contraste insuficiente: {bad}"
    print("CONTRAST AA OK")


if __name__ == "__main__":
    sys.exit(main() or 0)
