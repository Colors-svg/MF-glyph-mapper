"""Exportador Fase 4. Forma exacta aceptada por MF_Tools 1.1.1 instalado (VERIFIED_FACTS.md)."""
from __future__ import annotations
import json
from datetime import datetime


def _fmt_entry(entry) -> str:
    """([f],[t]) o ([f],[t],{"path_arc": x}) con path_arc compacto (k*PI si cuadra)."""
    import math
    f = sorted(entry[0]) if len(entry) > 0 else []
    t = sorted(entry[1]) if len(entry) > 1 else []
    if len(entry) > 2 and isinstance(entry[2], dict) and "path_arc" in entry[2]:
        try:
            v = float(entry[2]["path_arc"])
        except Exception:
            return f"    ({f}, {t}),"
        # k*PI exacto cuando cuadra (2/3 PI, 1/2 PI...), si no numero corto
        k = v / math.pi
        for num, den in [(1, 1), (1, 2), (1, 3), (2, 3), (1, 4), (3, 4), (2, 1)]:
            for sgn in (1, -1):
                if abs(k - sgn * num / den) < 1e-9:
                    ks = "" if (num == 1 and den == 1) else (f"{sgn * num}" if den == 1 else f"{sgn * num}/{den}")
                    return f"    ({f}, {t}, {{\"path_arc\": {ks}*PI}}),"
        return f"    ({f}, {t}, {{\"path_arc\": {v:.6g}}}),"
    return f"    ({f}, {t}),"


def _norm_entry(entry):
    """Normaliza [f,t] o [f,t,opts] a (f, t, opts|None). Ignora basura con (None,)."""
    if not isinstance(entry, (list, tuple)) or len(entry) < 2:
        return None
    try:
        f = [int(x) for x in entry[0]]
        t = [int(x) for x in entry[1]]
    except Exception:
        return None
    opts = None
    if len(entry) > 2 and isinstance(entry[2], dict) and "path_arc" in entry[2]:
        try:
            opts = {"path_arc": float(entry[2]["path_arc"])}
        except Exception:
            opts = None
    return (f, t, opts)


def build_snippet(glyph_map: list, var_a: str = "mobA",
                  var_b: str = "mobB", map_name: str = "glyph_map") -> str:
    """Genera Python ejecutable: `TransformByGlyphMap(mobA, mobB, *glyph_map)`."""
    lines = [
        "# Generado por MF Glyph Mapper "
        + datetime.now().strftime("%Y-%m-%d %H:%M"),
        "# Requiere: Manim CE + MF_Tools (TransformByGlyphMap).",
        "from manim import PI",
        "from MF_Tools import TransformByGlyphMap",
        "",
        f"{map_name} = [",
    ]
    for e in glyph_map:
        n = _norm_entry(e)
        if n is None:
            continue
        f, t, o = n
        lines.append(_fmt_entry([f, t, {"path_arc": o["path_arc"]}] if o else [f, t]))
    lines += [
        "]",
        "",
        f"self.play(TransformByGlyphMap({var_a}, {var_b}, *{map_name}))",
        "",
    ]
    return "\n".join(lines)


def build_project(latex_a: str, latex_b: str, path: list[int],
                  n_from: int, n_to: int, glyph_map: list) -> dict:
    conns = []
    for e in glyph_map:
        n = _norm_entry(e)
        if n is None:
            continue
        f, t, o = n
        c = {"from": list(f), "to": list(t)}
        if o:
            c["opts"] = {"path_arc": o["path_arc"]}
        conns.append(c)
    return {"app": "mf-glyph-mapper", "version": 1,
            "latex_a": latex_a, "latex_b": latex_b, "path": list(path),
            "n_from": n_from, "n_to": n_to, "connections": conns}


def project_to_glyph_map(project: dict) -> list:
    out = []
    for c in project.get("connections", []):
        f, t = list(c.get("from", [])), list(c.get("to", []))
        o = c.get("opts")
        if isinstance(o, dict) and "path_arc" in o:
            try:
                out.append((f, t, {"path_arc": float(o["path_arc"])}))
                continue
            except Exception:
                pass
        out.append((f, t))
    return out


def dumps_project(project: dict) -> str:
    return json.dumps(project, indent=2, ensure_ascii=False)


def build_agent_instructions(bundle: dict) -> str:
    """Genera el AGENTE.md que acompana al bundle V2: contexto + reglas de reescritura."""
    n = len(bundle.get("transitions", []))
    ids = "\n".join(f"- `{t['id']}` ({t.get('fase', '')})" for t in bundle.get("transitions", []))
    return f"""# Instrucciones para el agente — MF Glyph Mapper (bundle V2)

## Objetivo
Sustituir los `TransformMatchingTex(a, b)` de la escena por
`TransformByGlyphMap(a, b, *glyph_map)` usando los mapas de `agent_bundle.json`.
No recalcules indices: los del bundle son reales (instancia `MathTex` + ruta `[0]`).

## Archivos
- `agent_bundle.json`: {n} transiciones con `id`, `from_var`, `to_var`, `fase`,
  `latex_a`, `latex_b` (solo verificacion) y `glyph_map`.
- Este `.md`: reglas. La escena `.py` original: solo lectura para localizar.

## Regla de reemplazo (unica operacion permitida)
```python
# ANTES
self.play(TransformMatchingTex(eq1, eq2), run_time=2.0)
# DESPUES (mismo run_time, mismos efectos vecinos intactos)
self.play(TransformByGlyphMap(eq1, eq2, *glyph_map_eq1_eq2), run_time=2.0)
```
donde `glyph_map_eq1_eq2` es el `glyph_map` del `id == "eq1->eq2"` del bundle,
emitido como literales `([0], [0]), ...` dentro de la llamada o como variable
`glyph_map = [...]` justo antes del `play`.

## Transiciones incluidas
{ids}

## Prohibiciones
1. No inventes ni reordenes indices: usa `glyph_map` tal cual.
2. Antes de sustituir, verifica que el `latex_a`/`latex_b` del bundle coincide
   con el `MathTex` de `from_var`/`to_var` en el `.py`. Si difiere, DETENTE y reporta.
3. No toques `run_time`, `Flash`, `Indicate`, `SurroundingRectangle` ni guias `Tex`.
4. Entradas `([a], [])` = fade out del origen; `([],[b])` = fade in del destino.
   No las conviertas en `ReplacementTransform`.
5. Si los no mencionados restantes no cuadran en cantidad, Manim entra en
   `show_indices` (etiquetas en vez de animacion): eso es error, reportalo.

## Contexto MF_Tools 1.1.1 (instalado, no docs publicas)
- `TransformByGlyphMap(mobA, mobB, *glyph_map, mobA_submobject_index=[0], ...)`.
- Indices = submobjects directos de `mob[0]`. Reutilizar origen permitido
  (copia interna); destino reutilizado genera doble `ReplacementTransform`.
- Restantes no mencionados se emparejan por orden solo si las cantidades coinciden.

## Verificacion final
Renderiza la escena (`manim render -ql`) y confirma: sin `show_indices`,
sin `Error: lengths of unmentioned indices do not match`, y cada transicion
del bundle aplicada una sola vez.
"""


def _const_name(tid: str, seen: set[str]) -> str:
    """Nombre de constante valido y unico para un id 'a->b'."""
    import re
    base = "GLYPH_MAP_" + re.sub(r"\W+", "_", tid).strip("_").upper()[:60]
    name, k = base or "GLYPH_MAP_X", 2
    while name in seen:
        name, k = f"{base}_{k}", k + 1
    seen.add(name)
    return name


def build_global_maps(maps: dict, meta: dict[str, dict]) -> str:
    """Genera un .py funcional simple con TODOS los mapas: una constante por par.

    Lenguaje de siempre: `TransformByGlyphMap(a, b, *GLYPH_MAP_...)` listo para pegar.
    """
    import math
    lines = [
        "# Generado por MF Glyph Mapper "
        + datetime.now().strftime("%Y-%m-%d %H:%M"),
        "# Todos los mapas en el lenguaje de siempre: pega las constantes y los plays",
        "# en tu escena. Requiere: Manim CE + MF_Tools (TransformByGlyphMap).",
        "from manim import PI",
        "from MF_Tools import TransformByGlyphMap",
        "",
    ]
    if not maps:
        lines.append("# (sin mapas guardados)")
        return "\n".join(lines) + "\n"
    seen: set[str] = set()
    for tid in sorted(maps):
        entries = []
        for e in maps[tid]:
            n = _norm_entry(e)
            if n is not None:
                entries.append(n)
        if not entries:
            continue
        m = meta.get(tid, {})
        a, b = tid.split("->", 1) if "->" in tid else (tid, "")
        name = _const_name(tid, seen)
        fase = m.get("fase", "")
        lines.append(f"# ---- {tid}" + (f"  ({fase})" if fase else ""))
        lines.append(f"{name} = [")
        for f, t, o in entries:
            lines.append("    " + _fmt_entry([f, t, {"path_arc": o["path_arc"]}] if o else [f, t]).strip())
        lines.append("]")
        lines.append(f"# self.play(TransformByGlyphMap({a}, {b}, *{name}))")
        lines.append("")
    return "\n".join(lines)


def build_agent_bundle(maps: dict, meta: dict[str, dict]) -> dict:
    """Bundle V2 para el agente: claves = nombres reales del .py.

    maps: {"eq1->eq2": [([0],[0]), ([1],[0],{"path_arc": 1.57}), ...]}.
    meta: {"eq1->eq2": {"fase":..., "latex_a":..., "latex_b":...}}.
    """
    out = []
    for tid, gm in maps.items():
        m = meta.get(tid, {})
        a, b = tid.split("->", 1) if "->" in tid else (tid, "")
        entries = []
        for e in gm:
            n = _norm_entry(e)
            if n is None:
                continue
            f, t, o = n
            entries.append([list(f), list(t), {"path_arc": o["path_arc"]}] if o else [list(f), list(t)])
        out.append({"id": tid, "from_var": a, "to_var": b,
                    "fase": m.get("fase", "Sin fase"),
                    "latex_a": m.get("latex_a", ""), "latex_b": m.get("latex_b", ""),
                    "glyph_map": entries})
    return {"app": "mf-glyph-mapper", "version": 2, "transitions": out}
