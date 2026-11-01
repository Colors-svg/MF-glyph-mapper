"""Validador Fase 3. Puro, sin UI. Replica la logica de MF_Tools/transforms.py:99-106 para predecir show_indices."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Issue:
    code: str  # BAD_INDEX | DUPLICATE | DEST_REUSED | UNMENTIONED | COUNT_MISMATCH | BAD_PATH | STALE
    level: str  # error | warning | info
    message: str
    side: str = ""  # from | to | both | ""
    indices: tuple[int, ...] = ()


def validate(n_from: int, n_to: int, glyph_map: list[tuple[list[int], list[int]]],
             top_from: int = 1, top_to: int = 1, path: tuple[int, ...] = (0,),
             stale: bool = False) -> list[Issue]:
    """Valida un glyph_map contra las reglas de TransformByGlyphMap instalado."""
    issues: list[Issue] = []
    if stale:
        issues.append(Issue("STALE", "error",
                            "LaTeX modificado tras crear conexiones: re-renderiza. Conexiones marcadas STALE, no usar hasta validar.",
                            "both", ()))
    if not glyph_map:
        issues.append(Issue("UNMENTIONED", "info", "Mapa vacio: MF_Tools entraria en show_indices (transforms.py:38).", "both", ()))
        return issues
    if top_from != 1 and tuple(path) == (0,):
        issues.append(Issue("BAD_PATH", "error",
                            f"Origen top_len={top_from} con path [0]: solo se ve la primera parte ({{{{...}}}} o multi-arg). Cambia la ruta.",
                            "from", ()))
    if top_to != 1 and tuple(path) == (0,):
        issues.append(Issue("BAD_PATH", "error",
                            f"Destino top_len={top_to} con path [0]: solo se ve la primera parte. Cambia la ruta.",
                            "to", ()))
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    mf = set(range(n_from))
    mt = set(range(n_to))
    men_f: set[int] = set()
    men_t: set[int] = set()
    use_f: dict[int, int] = {}
    use_t: dict[int, int] = {}
    for entry in glyph_map:
        f = tuple(sorted(entry[0])) if len(entry) > 0 else ()
        t = tuple(sorted(entry[1])) if len(entry) > 1 else ()
        if (f, t) in seen:
            issues.append(Issue("DUPLICATE", "error", f"Conexion duplicada {list(f)}->{list(t)}.", "both", f + t))
        seen.add((f, t))
        if not f and not t:
            issues.append(Issue("BAD_INDEX", "error", "Entrada ([],[]) invalida: fuerza show_indices.", "both", ()))
            continue
        for i in f:
            if i not in mf:
                issues.append(Issue("BAD_INDEX", "error", f"Indice origen {i} inexistente (0..{n_from - 1}).", "from", (i,)))
            else:
                men_f.add(i)
                use_f[i] = use_f.get(i, 0) + 1
        for j in t:
            if j not in mt:
                issues.append(Issue("BAD_INDEX", "error", f"Indice destino {j} inexistente (0..{n_to - 1}).", "to", (j,)))
            else:
                men_t.add(j)
                use_t[j] = use_t.get(j, 0) + 1
    for j, c in sorted(use_t.items()):
        if c > 1:
            issues.append(Issue("DEST_REUSED", "warning",
                                f"Destino {j} reutilizado en {c} conexiones: posible accidente (MF_Tools lo permite pero duplica ReplacementTransform).",
                                "to", (j,)))
    rem_f = sorted(set(range(n_from)) - men_f)
    rem_t = sorted(set(range(n_to)) - men_t)
    if rem_f or rem_t:
        if len(rem_f) != len(rem_t):
            issues.append(Issue("COUNT_MISMATCH", "error",
                                f"Restantes desigual: origen {rem_f} ({len(rem_f)}) vs destino {rem_t} ({len(rem_t)}). "
                                "MF_Tools entraria en show_indices (transforms.py:102-106). Cubre con fade out/in explicitos.",
                                "both", ()))
        else:
            issues.append(Issue("UNMENTIONED", "info",
                                f"Sin correspondencia explicita pero auto-emparejables por orden: {rem_f}->{rem_t}.",
                                "both", ()))
    return issues
