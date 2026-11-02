"""Core sin dependencias de UI: extrae glifos reales de MathTex."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class GlyphInfo:
    """Un glifo en la ruta de MF_Tools (indice dentro de A=mob[path])."""
    index: int
    type_name: str
    center: list[float]
    width: float
    height: float
    points: list[list[float]]  # bezier points (x,y,z) tal cual Manim


def extract_glyphs(latex: str, mob_submobject_index: list[int] | None = None,
                   args: list[str] | None = None) -> dict[str, Any]:
    """Instancia el MathTex real y devuelve glifos en la ruta dada.

    Nunca parsea LaTeX a mano: pregunta a Manim por sus submobjects.
    Retorna dict JSON-serializable con ok/glyphs o ok=False/error.
    Si `args` (multi-arg) viene dado, calcula `spans`: fronteras de cada
    arg en el espacio single-string, verificadas por conteo y anchos.
    """
    from manim import MathTex
    path = [0] if mob_submobject_index is None else list(mob_submobject_index)
    try:
        mob = MathTex(latex)
    except Exception as e:  # error de LaTeX visible, nunca silencioso
        return {"ok": False, "error": f"MathTex fallo: {type(e).__name__}: {e}", "latex": latex}
    try:
        top_len = len(mob)
        target = mob
        for i in path:
            target = target[i]
        resolved_len = len(target)
        glyphs: list[dict[str, Any]] = []
        for idx in range(resolved_len):
            g = target[idx]
            try:
                c = g.get_center()
                center = [float(c[0]), float(c[1]), float(c[2])]
            except Exception:
                center = [0.0, 0.0, 0.0]
            try:
                w, h = float(g.width), float(g.height)
            except Exception:
                w, h = 0.0, 0.0
            try:
                pts = [[float(x), float(y), float(z)] for x, y, z in g.points.tolist()]
            except Exception:
                pts = []
            glyphs.append(asdict(GlyphInfo(
                index=idx, type_name=type(g).__name__,
                center=center, width=w, height=h, points=pts,
            )))
        warnings: list[str] = []
        if top_len != 1 and path == [0]:
            warnings.append(
                f"top_len={top_len} con path [0]: solo se ve la primera parte. "
                "Tipico de {{...}} o MathTex multi-arg. Cambia la ruta o usa single-string."
            )
        spans: dict[str, list[int]] = {}
        spans_ok = True
        if args is not None and len(args) > 1 and top_len == 1 and path == [0]:
            try:
                ref = MathTex(*args)
                counts = [len(g.submobjects) for g in ref.submobjects]
                bounds: list[tuple[int, int]] = []
                acc = 0
                for c in counts:
                    bounds.append((acc, acc + c))
                    acc += c
                ok = acc == resolved_len
                if ok:
                    for j, (a, b) in enumerate(bounds):
                        sl = [round(float(x.width), 6) for x in target[a:b]]
                        rf = [round(float(x.width), 6) for x in ref[j].submobjects]
                        if sl != rf:
                            ok = False
                            break
                if ok:
                    spans = {str(j): [a, b] for j, (a, b) in enumerate(bounds)}
                else:
                    spans_ok = False
                    warnings.append("spans no verificados: el multi-arg no reparte igual; se omiten.")
            except Exception as e:  # noqa: BLE001
                spans_ok = False
                warnings.append(f"spans fallo: {type(e).__name__}; se omiten.")
        return {"ok": True, "latex": latex, "path": path,
                "top_len": top_len, "resolved_len": resolved_len,
                "glyphs": glyphs, "warnings": warnings,
                "spans": spans, "spans_ok": spans_ok}
    except Exception as e:
        return {"ok": False, "error": f"Resolucion de ruta {path} fallo: {type(e).__name__}: {e}",
                "latex": latex, "path": path}
