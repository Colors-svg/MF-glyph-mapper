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
    """Genera el AGENTE.md que acompana al bundle V3: contexto + reglas de reescritura."""
    n = len(bundle.get("transitions", []))
    ids = "\n".join(f"- `{t['id']}` ({t.get('fase', '')})" for t in bundle.get("transitions", []))
    nerr = sum(1 for t in bundle.get("transitions", []) for _ in (t.get("validation") or {}).get("errors", []))
    return f"""# Instrucciones para el agente — MF Glyph Mapper (bundle V3)

## Objetivo
Sustituir los `TransformMatchingTex(a, b)` / `ReplacementTransform` con carries
de la escena por `TransformByGlyphMap(a, b, *glyph_map)` usando `agent_bundle.json`.
No recalcules NADA: constructores, mapas y validacion ya vienen verificados por maquina.

## REGLA DE ORO (no negociable)
Los indices del bundle solo valen sobre el objeto **single-string**
`MathTex("...")` tal cual aparece en `construct_a` / `construct_b`
(`mob[0]` = todos los glifos). NO reconstruyas `MathTex(*args)` multi-arg:
ahi `mob[0]` es solo el primer arg y los indices fallan con `show_indices`.
Pega los constructores tal cual; ya traen `font_size` y colores por rangos.

## Archivos
- `agent_bundle.json` (v3): `formulas` (constructores + `tex_single`, `args`,
  `colors` {{arg: hex}}, `spans` {{arg: [a, b]}} verificados, `font_size`,
  `n`/`top` reales) y {n} transiciones con `glyph_map`, `construct_a`,
  `construct_b`, `play` listo y `validation` de maquina.
- Este `.md`: reglas. La escena `.py` original: solo lectura para localizar.

## Regla de reemplazo (unica operacion permitida)
```python
# ANTES
self.play(TransformMatchingTex(eq1, eq2), run_time=2.0)
# DESPUES (mismo run_time, mismos efectos vecinos intactos)
f1 = MathTex("...", font_size=48)   # <- pega construct_a tal cual
for _i in range(5, 25): f1[0][_i].set_color("#...")  # <- ya viene hecho
self.play(TransformByGlyphMap(f1, f2, *GLYPH_MAP_F1_F2), run_time=2.0)
```
`validation.errors == []` significa verificado por maquina (validador Fase 3
contra conteos reales de Manim): **confia y no dudes**. Estado global:
{nerr} errores en {n} transiciones.

## Transiciones incluidas
{ids}

## Prohibiciones
1. No inventes ni reordenes indices: usa `glyph_map` tal cual.
2. No reescribas los constructores a multi-arg (ver REGLA DE ORO).
3. No toques `run_time`, `Flash`, `Indicate`, `SurroundingRectangle` ni guias `Tex`.
4. Entradas `([a], [])` = fade out del origen; `([],[b])` = fade in del destino.
   No las conviertas en `ReplacementTransform`.
5. `var` duplicada (`fx`, `fx_2`...) = bucle desenrollado: son mobs distintos,
   respeta los nombres `cname` del bundle.

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


def _py_str(tex: str) -> str:
    """Literal Python para un latex: comillas dobles, escapes correctos."""
    import json as _j
    return _j.dumps(tex, ensure_ascii=False)


def _norm_colors(colors) -> dict[int, str]:
    out: dict[int, str] = {}
    if isinstance(colors, dict):
        for k, v in colors.items():
            try:
                out[int(k)] = str(v)
            except Exception:
                continue
    return out


def _norm_spans(spans) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    if isinstance(spans, dict):
        for k, v in spans.items():
            try:
                a, b = int(v[0]), int(v[1])
                out[int(k)] = [a, b]
            except Exception:
                continue
    return out


def _construct_block(cname: str, tex_single: str, font_size, colors, spans) -> str:
    """Constructor MathTex listo para pegar: single-string + color por rangos.

    Los rangos vienen de spans verificados (conteo + anchos contra Manim).
    Sin spans para un arg coloreado: comentario, nunca indices inventados.
    """
    fs = f", font_size={int(font_size)}" if isinstance(font_size, int) and not isinstance(font_size, bool) else ""
    lines = [f"{cname} = MathTex({_py_str(tex_single)}{fs})"]
    for j in sorted(colors):
        col = colors[j]
        if j in spans:
            a, b = spans[j]
            lines.append(f"for _i in range({a}, {b}): {cname}[0][_i].set_color({col!r})")
        else:
            lines.append(f"# {cname}: color del arg {j} ({col}) sin spans verificados: aplica a mano")
    return "\n".join(lines)


def _occurrences(formulas) -> list[dict]:
    """Ocurrencias unicas (var, tex_single) con nombre de constructor.

    var repetida (bucles desenrollados) -> var_1, var_2...; el resto conserva
    el nombre del .py para que los plays caigan directos.
    """
    seen: dict[tuple[str, str], dict] = {}
    for f in formulas or []:
        if not isinstance(f, dict):
            continue
        var = str(f.get("var", "mob"))
        tex = str(f.get("tex_single", "") or "")
        if not tex:
            continue
        if (var, tex) not in seen:
            seen[(var, tex)] = {"var": var, "tex_single": tex,
                                "args": list(f.get("args", []) or []),
                                "colors": _norm_colors(f.get("colors")),
                                "spans": _norm_spans(f.get("spans")),
                                "font_size": f.get("font_size"),
                                "n": f.get("n"), "top": f.get("top")}
    counts: dict[str, int] = {}
    for (var, _tex) in seen:
        counts[var] = counts.get(var, 0) + 1
    kth: dict[str, int] = {}
    for key, o in seen.items():
        var = o["var"]
        if counts[var] > 1:
            kth[var] = kth.get(var, 0) + 1
            o["cname"] = f"{var}_{kth[var]}"
            o["dup"] = True
        else:
            o["cname"] = var
            o["dup"] = False
    return list(seen.values())


def _resolve_occ(occs: list[dict], var: str, latex: str) -> dict | None:
    for o in occs:
        if o["var"] == var and o["tex_single"] == latex:
            return o
    for o in occs:
        if o["var"] == var:
            return o
    return None


def _consts_block(tids: list[str], maps: dict) -> tuple[str, dict[str, str]]:
    """Bloque de constantes GLYPH_MAP_* + nombres usados (autoconsistente)."""
    seen: set[str] = set()
    names: dict[str, str] = {}
    chunks: list[str] = []
    for tid in tids:
        name = _const_name(tid, seen)
        names[tid] = name
        chunks.append(f"# ---- {tid}")
        chunks.append(f"{name} = [")
        for e in maps.get(tid, []):
            n = _norm_entry(e)
            if n is None:
                continue
            f, t, o = n
            chunks.append("    " + _fmt_entry([f, t, {"path_arc": o["path_arc"]}] if o else [f, t]).strip())
        chunks.append("]")
    return "\n".join(chunks), names


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


def build_agent_bundle(maps: dict, meta: dict[str, dict], formulas: list[dict] | None = None,
                       validations: dict[str, dict] | None = None,
                       order: list[str] | None = None) -> dict:
    """Bundle V3 para el agente: lo mapeado, listo para pegar, verificado por maquina.

    maps: {"eq1->eq2": [([0],[0]), ([1],[0],{"path_arc": 1.57}), ...]}.
    meta: {"eq1->eq2": {"fase":..., "latex_a":..., "latex_b":...,
                        "counts": {"n_from":..,"n_to":..,"top_from":..,"top_to":..}}}.
    formulas: [{"var":..., "tex_single":..., "args":[...], "colors":{arg:hex},
                "spans":{arg:[a,b]}, "font_size":..|None, "n":..|None, "top":..|None}].
    validations: {tid: {"errors":[{code,message}], "warnings":[...]}} (server-side).
    order: [tid...] en orden de guion para transiciones y parche.
    """
    occs = _occurrences(formulas)
    tids = [t for t in (order or []) if t in maps] + [t for t in maps if t not in (order or [])]
    _, names = _consts_block(tids, maps)
    out = []
    for tid in tids:
        gm = maps[tid]
        m = meta.get(tid, {})
        a, b = tid.split("->", 1) if "->" in tid else (tid, "")
        entries = []
        for e in gm:
            n = _norm_entry(e)
            if n is None:
                continue
            f, t, o = n
            entries.append([list(f), list(t), {"path_arc": o["path_arc"]}] if o else [list(f), list(t)])
        oa = _resolve_occ(occs, a, m.get("latex_a", ""))
        ob = _resolve_occ(occs, b, m.get("latex_b", ""))
        na = oa["cname"] if oa else a
        nb = ob["cname"] if ob else b
        val = (validations or {}).get(tid, {"errors": [], "warnings": []})
        out.append({"id": tid, "from_var": a, "to_var": b,
                    "fase": m.get("fase", "Sin fase"),
                    "latex_a": m.get("latex_a", ""), "latex_b": m.get("latex_b", ""),
                    "counts": m.get("counts", {}),
                    "glyph_map": entries,
                    "construct_a": _construct_block(
                        oa["cname"] if oa else a, (oa or {}).get("tex_single", m.get("latex_a", "")),
                        (oa or {}).get("font_size"), (oa or {}).get("colors", {}), (oa or {}).get("spans", {})) if oa else "",
                    "construct_b": _construct_block(
                        ob["cname"] if ob else b, (ob or {}).get("tex_single", m.get("latex_b", "")),
                        (ob or {}).get("font_size"), (ob or {}).get("colors", {}), (ob or {}).get("spans", {})) if ob else "",
                    "play": f"self.play(TransformByGlyphMap({na}, {nb}, *{names[tid]}))",
                    "validation": val})
    forms = []
    for o in occs:
        forms.append({"var": o["var"], "cname": o["cname"], "tex_single": o["tex_single"],
                      "args": o["args"], "colors": {str(k): v for k, v in o["colors"].items()},
                      "spans": {str(k): v for k, v in o["spans"].items()},
                      "font_size": o.get("font_size"), "n": o.get("n"), "top": o.get("top"),
                      "dup": o.get("dup", False)})
    return {"app": "mf-glyph-mapper", "version": 3, "formulas": forms, "transitions": out}


def build_scene_patch(maps: dict, meta: dict[str, dict], formulas: list[dict] | None = None,
                      validations: dict[str, dict] | None = None,
                      order: list[str] | None = None) -> str:
    """Parche Python completo listo para pegar: consts + constructores + plays.

    Elimina las dudas del LLM: constructores single-string exactos (indices
    garantizados), colores por rangos verificados, plays con nombres reales,
    cada par con su estado de validacion de maquina.
    """
    bundle = build_agent_bundle(maps, meta, formulas, validations, order)
    tids = [t["id"] for t in bundle["transitions"]]
    consts_txt, _ = _consts_block(tids, maps)
    by_id = {t["id"]: t for t in bundle["transitions"]}
    lines = [
        "# Parche MF Glyph Mapper "
        + datetime.now().strftime("%Y-%m-%d %H:%M"),
        "# PEGALO en tu escena: reemplaza cada TransformMatchingTex / ReplacementTransform",
        "# por su linea `self.play(...)` de abajo, y los MathTex mapeados por sus",
        "# constructores. Requiere: Manim CE + MF_Tools (TransformByGlyphMap).",
        "# REGLA DE ORO: los indices solo valen sobre el objeto single-string",
        "# construido aqui (mob[0] = todos los glifos). NO reconstruyas multi-arg.",
        "from MF_Tools import TransformByGlyphMap",
        "",
        "# ---- 1) mapas ----",
        consts_txt,
        "",
        "# ---- 2) constructores (sustituyen tus MathTex(*args, ...) mapeados) ----",
    ]
    done_c = set()
    for t in bundle["transitions"]:
        for key in ("construct_a", "construct_b"):
            c = t[key]
            if c and c not in done_c:
                done_c.add(c)
                lines.append(c)
                lines.append("")
    lines.append("# ---- 3) plays en orden de guion (sustituyen tus plays) ----")
    for t in bundle["transitions"]:
        tid = t["id"]
        errs = (t.get("validation") or {}).get("errors", [])
        estado = "VERIFICADO: 0 errores" if not errs else "OJO: " + "; ".join(
            f"{e.get('code', '?')}: {str(e.get('message', ''))[:90]}" for e in errs)
        fase = t.get("fase", "")
        lines.append(f"# {tid}" + (f"  ({fase})" if fase else "") + f" — {estado}")
        if t["construct_a"]:
            ca = t["construct_a"].splitlines()[0]
            lines.append(f"#   de: {ca}")
        if t["construct_b"]:
            cb = t["construct_b"].splitlines()[0]
            lines.append(f"#   a:  {cb}")
        play = t.get("play") or ""
        lines.append(play)
        lines.append("")
    # re-emite el bundle con los plays ya rellenos
    return "\n".join(lines)
