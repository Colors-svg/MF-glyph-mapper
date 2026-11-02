"""Fase 7 (V2.0): extraccion estatica de .py con AST. Sin ejecutar la escena.

Extrae: formulas MathTex/Tex (variable -> literales), pares de
TransformMatchingTex(a, b) y TransformByGlyphMap(a, b, *MAPA, ...),
fases desde comentarios BLOQUE y precarga de mapas literales GLYPH_MAP_*.
"""
from __future__ import annotations
import ast
import re
from dataclasses import dataclass, field

BLOQUE_RE = re.compile(r"#\s*BLOQUE\s+(\d+)\s*:?\s*(.*)", re.IGNORECASE)


@dataclass
class Formula:
    var: str
    kind: str  # MathTex | Tex
    args: list[str]  # literales tal cual (multi-arg se conserva)
    line: int
    dynamic: bool = False  # True si algun arg no es literal


@dataclass
class Transition:
    from_var: str
    to_var: str
    line: int
    map_name: str = ""  # *GLYPH_MAP_X si viene de TransformByGlyphMap
    kind: str = "tmt"  # tmt | tbgm | repl (ReplacementTransform migrable)


@dataclass
class SequenceFile:
    path: str
    formulas: list[Formula] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    prefill: dict[str, list] = field(default_factory=dict)  # tid -> [[[f],[t],...]

    def by_var(self) -> dict[str, Formula]:
        return {f.var: f for f in self.formulas}

    def phases(self, source_lines: list[str]) -> dict[int, str]:
        """line -> 'BLOQUE n: titulo' vigente en esa linea."""
        marks: list[tuple[int, str]] = []
        for i, ln in enumerate(source_lines, start=1):
            m = BLOQUE_RE.search(ln)
            if m:
                marks.append((i, f"BLOQUE {m.group(1)}" + (f": {m.group(2).strip()}" if m.group(2).strip() else "")))
        out: dict[int, str] = {}
        # formulas y transiciones heredan la ultima marca anterior
        for f in self.formulas:
            out[id(f)] = _vigente(marks, f.line)
        for t in self.transitions:
            out[id(t)] = _vigente(marks, t.line)
        return out


def _vigente(marks: list[tuple[int, str]], line: int) -> str:
    cur = "Sin fase"
    for ln, name in marks:
        if ln <= line:
            cur = name
        else:
            break
    return cur


def _base_call(node: ast.AST) -> ast.Call | None:
    """Desenvuelve cadenas `MathTex(...).shift(...).scale(...)` hasta la llamada base."""
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and isinstance(node.func.value, ast.Call):
        node = node.func.value
    return node if isinstance(node, ast.Call) else None


def _int_list(node: ast.AST) -> list[int] | None:
    """[0, 1] literal o None."""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    vals: list[int] = []
    for x in node.elts:
        if isinstance(x, ast.Constant) and isinstance(x.value, int) \
                and not isinstance(x.value, bool):
            vals.append(x.value)
        else:
            return None
    return vals


def _eval_number(node: ast.AST) -> float | None:
    """Evalua numeros y expresiones tipo 2/3*PI, -PI/2, 1.57. Solo numeros y PI."""
    import math
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id in ("PI", "pi"):
        return math.pi
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _eval_number(node.operand)
        if v is None:
            return None
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
        a, b = _eval_number(node.left), _eval_number(node.right)
        if a is None or b is None:
            return None
        try:
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b if b else None
            return a ** b
        except Exception:
            return None
    return None


def _parse_opts(node: ast.AST) -> tuple[dict | None, bool]:
    """{path_arc: ...} literal -> ({"path_arc": float} | None, unknown_flag)."""
    if not isinstance(node, ast.Dict):
        return None, True
    out: dict = {}
    unknown = False
    for k, v in zip(node.keys, node.values):
        ks = k.value if isinstance(k, ast.Constant) and isinstance(k.value, str) else None
        if ks == "path_arc":
            num = _eval_number(v)
            if num is None:
                return None, True
            out["path_arc"] = num
        elif ks is not None:
            unknown = True  # otra opcion: se conserva f->t, se avisa
        else:
            unknown = True
    if not out and unknown:
        return None, True
    if not out:
        return None, False
    return out, unknown


def _as_glyph_map(node: ast.AST) -> tuple[list, bool] | None:
    """[([f],[t]), ([f],[t],{path_arc}), ...] -> (entradas, hubo_no_soportado) o None.

    Preserva path_arc numerico (incluye expresiones k*PI). Otras opciones o
    valores no literales marcan hubo_no_soportado (aviso, f->t se conserva)."""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    out: list = []
    bad_opts = False
    for e in node.elts:
        if not isinstance(e, (ast.List, ast.Tuple)) or not 2 <= len(e.elts) <= 3:
            return None
        f, t = _int_list(e.elts[0]), _int_list(e.elts[1])
        if f is None or t is None:
            return None
        if len(e.elts) == 3:
            opts, unknown = _parse_opts(e.elts[2])
            if opts:
                out.append([f, t, opts])
            else:
                out.append([f, t])
            bad_opts = bad_opts or unknown or opts is None
        else:
            out.append([f, t])
    return out, bad_opts


def _as_inline_entries(args: list[ast.AST]) -> list | None:
    """Entradas inline de TransformByGlyphMap(a, b, ([f],[t],{...}), ...).

    Retorna lista de entradas o None si no hay ninguna inline."""
    out: list = []
    found = False
    for a in args:
        if isinstance(a, (ast.List, ast.Tuple)) and 2 <= len(getattr(a, "elts", [])) <= 3:
            elts = a.elts
            f, t = _int_list(elts[0]), _int_list(elts[1])
            if f is not None and t is not None:
                found = True
                if len(elts) == 3:
                    opts, _ = _parse_opts(elts[2])
                    out.append([f, t, opts] if opts else [f, t])
                else:
                    out.append([f, t])
    return out if found else None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def parse_file(path: str) -> tuple[SequenceFile, list[str]]:
    """Retorna (SequenceFile, source_lines). Solo lee, nunca ejecuta."""
    src = open(path, encoding="utf-8").read()
    lines = src.splitlines()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        sq = SequenceFile(path=path, warnings=[f"Sintaxis invalida: {e}"])
        return sq, lines
    sq = SequenceFile(path=path)
    # Pasada 1: formulas + constantes de mapa (orden en archivo irrelevante).
    map_consts: dict[str, list] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            base = _base_call(node.value)
            if base is None:
                gm = _as_glyph_map(node.value)
                if gm is not None:
                    map_consts[node.targets[0].id] = gm[0]
                    if gm[1]:
                        sq.warnings.append(
                            f"*{node.targets[0].id} (linea {node.lineno}): opciones no soportadas "
                            "ignoradas (solo path_arc numerico se precarga); el mapeo f->t se conserva.")
                continue
            name = _call_name(base.func)
            if name in ("MathTex", "Tex"):
                args: list[str] = []
                dyn = False
                for a in base.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        args.append(a.value)
                    else:
                        dyn = True
                sq.formulas.append(Formula(node.targets[0].id, name, args, node.lineno, dyn))
                if dyn:
                    sq.warnings.append(
                        f"{node.targets[0].id} (linea {node.lineno}): arg no literal, se omite valor.")
    # Pasada 2: transiciones (ambos formatos conviven).
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node.func) == "TransformMatchingTex":
            if len(node.args) >= 2 and all(isinstance(a, ast.Name) for a in node.args[:2]):
                sq.transitions.append(Transition(node.args[0].id, node.args[1].id, node.lineno))
        elif isinstance(node, ast.Call) and _call_name(node.func) == "TransformByGlyphMap":
            if len(node.args) >= 2 and all(isinstance(a, ast.Name) for a in node.args[:2]):
                mname = ""
                for a in node.args[2:]:
                    if isinstance(a, ast.Starred) and isinstance(a.value, ast.Name):
                        mname = a.value.id
                        break
                t = Transition(node.args[0].id, node.args[1].id, node.lineno, mname, "tbgm")
                sq.transitions.append(t)
                if mname and mname not in map_consts:
                    sq.warnings.append(
                        f"Par {t.from_var}->{t.to_var} (linea {t.line}): *{mname} no es lista literal, precarga omitida.")
                elif not mname:
                    # Entradas inline: ([f],[t]), ([f],[t],{"path_arc": ...}), ...
                    inl = _as_inline_entries(list(node.args[2:]))
                    if inl:
                        key = f"{t.from_var}->{t.to_var}"
                        if key not in sq.prefill:
                            sq.prefill[key] = inl
        elif isinstance(node, ast.Call) and _call_name(node.func) == "ReplacementTransform":
            # Migrable: la escena reemplaza en bloque; la app permite mapearlo y exportar TBGMap.
            if len(node.args) >= 2 and all(isinstance(a, ast.Name) for a in node.args[:2]):
                sq.transitions.append(Transition(node.args[0].id, node.args[1].id, node.lineno, "", "repl"))
    # orden de fuente (ast.walk es BFS) + precarga de mapas literales
    sq.formulas.sort(key=lambda f: f.line)
    sq.transitions.sort(key=lambda t: t.line)
    for t in sq.transitions:
        if t.map_name and t.map_name in map_consts:
            sq.prefill[f"{t.from_var}->{t.to_var}"] = map_consts[t.map_name]
    # pares que apuntan a variables desconocidas
    known = {f.var for f in sq.formulas}
    sq.transitions = [t for t in sq.transitions
                      if not _warn_unknown(sq, t, known)]
    if any(t.kind == "repl" for t in sq.transitions):
        sq.warnings.append(
            "Hay pares con ReplacementTransform: se importan como migrables; "
            "mapea y exporta TransformByGlyphMap.")
    return sq, lines


def _warn_unknown(sq: SequenceFile, t: Transition, known: set[str]) -> bool:
    missing = [v for v in (t.from_var, t.to_var) if v not in known]
    if missing:
        sq.warnings.append(f"Par {t.from_var}->{t.to_var} (linea {t.line}): sin MathTex: {missing}.")
        return True
    return False
