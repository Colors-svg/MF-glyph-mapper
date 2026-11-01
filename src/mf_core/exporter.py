"""Exportador Fase 4. Forma exacta aceptada por MF_Tools 1.1.1 instalado (VERIFIED_FACTS.md)."""
from __future__ import annotations
import json
from datetime import datetime


def build_snippet(glyph_map: list[tuple[list[int], list[int]]],
                  var_a: str = "mobA", var_b: str = "mobB",
                  map_name: str = "glyph_map") -> str:
    """Genera Python ejecutable: `TransformByGlyphMap(mobA, mobB, *glyph_map)`."""
    lines = [
        "# Generado por MF Glyph Mapper "
        + datetime.now().strftime("%Y-%m-%d %H:%M"),
        "# Requiere: Manim CE + MF_Tools (TransformByGlyphMap).",
        "from MF_Tools import TransformByGlyphMap",
        "",
        f"{map_name} = [",
    ]
    for f, t in glyph_map:
        lines.append(f"    ({sorted(f)}, {sorted(t)}),")
    lines += [
        "]",
        "",
        f"self.play(TransformByGlyphMap({var_a}, {var_b}, *{map_name}))",
        "",
    ]
    return "\n".join(lines)


def build_project(latex_a: str, latex_b: str, path: list[int],
                  n_from: int, n_to: int,
                  glyph_map: list[tuple[list[int], list[int]]]) -> dict:
    return {"app": "mf-glyph-mapper", "version": 1,
            "latex_a": latex_a, "latex_b": latex_b, "path": list(path),
            "n_from": n_from, "n_to": n_to,
            "connections": [{"from": list(f), "to": list(t)} for f, t in glyph_map]}


def project_to_glyph_map(project: dict) -> list[tuple[list[int], list[int]]]:
    return [(list(c.get("from", [])), list(c.get("to", [])))
            for c in project.get("connections", [])]


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


def build_agent_bundle(maps: dict[str, list[tuple[list[int], list[int]]]],
                       meta: dict[str, dict]) -> dict:
    """Bundle V2 para el agente: claves = nombres reales del .py.

    maps: {"eq1->eq2": [([0],[0]), ...]}.
    meta: {"eq1->eq2": {"fase":..., "latex_a":..., "latex_b":...}}.
    """
    out = []
    for tid, gm in maps.items():
        m = meta.get(tid, {})
        a, b = tid.split("->", 1) if "->" in tid else (tid, "")
        out.append({"id": tid, "from_var": a, "to_var": b,
                    "fase": m.get("fase", "Sin fase"),
                    "latex_a": m.get("latex_a", ""), "latex_b": m.get("latex_b", ""),
                    "glyph_map": [[list(f), list(t)] for f, t in gm]})
    return {"app": "mf-glyph-mapper", "version": 2, "transitions": out}
