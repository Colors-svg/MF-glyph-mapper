# -*- coding: utf-8 -*-
"""Fase 7 (V2.x): extraccion estatica de .py con AST. Sin ejecutar la escena.

Extrae: formulas MathTex/Tex (variable -> literales), pares de
TransformMatchingTex(a, b), TransformByGlyphMap(a, b, *MAPA, ...) y
ReplacementTransform(a, b) migrables, fases desde comentarios BLOQUE y
precarga de mapas literales GLYPH_MAP_*.

V2.1 (constantes y locales): ademas resuelve constantes de modulo
(`K = "..."`, `M = ["...", ...]`, concatenacion con `+`), llamadas
envueltas (`pintar_partes(MathTex(...))`), `*MAPA`, subindices (`M[0]`),
asignaciones en locales de metodos y bucles `for` sobre tuplas literales
(con `if` evaluable e IfExp) con snapshot del latex por transicion.
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
    latex_a: str = ""  # snapshot del latex en ese punto ("" = ver by_var)
    latex_b: str = ""


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


# ---------------------------------------------------------------------------
# V2.1: constantes, locales y bucles (todo estatico, sin ejecutar)
# ---------------------------------------------------------------------------

def _eval_str_const(node: ast.AST, env: dict) -> str | list[str] | None:
    """Constante de cadena: "lit", [lit, ...], NAME (ya resuelto) o "a"+B."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        out = []
        for x in node.elts:
            v = _eval_str_const(x, env)
            if not isinstance(v, str):
                return None
            out.append(v)
        return out
    if isinstance(node, ast.Name):
        v = env.get(node.id)
        return v if isinstance(v, (str, list)) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _eval_str_const(node.left, env), _eval_str_const(node.right, env)
        if isinstance(a, str) and isinstance(b, str):
            return a + b
        return None
    return None


def _collect_consts(tree: ast.AST) -> dict:
    """NAME -> str | [str] para literales de modulo (con punto fijo)."""
    cands: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            cands[node.targets[0].id] = node.value
    env: dict = {}
    for _ in range(10):
        changed = False
        for k, v in cands.items():
            if k in env:
                continue
            r = _eval_str_const(v, env)
            if r is not None:
                env[k] = r
                changed = True
        if not changed:
            break
    return env


def _resolve_arg(node: ast.AST, env: dict) -> list[str] | None:
    """Un argumento de MathTex -> lista de literales, o None si dinamico."""
    if isinstance(node, ast.Starred):
        return _resolve_arg(node.value, env)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name):
        v = env.get(node.id)
        if isinstance(v, str):
            return [v]
        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            return list(v)
        return None
    if isinstance(node, ast.Subscript):
        base = node.value
        sl = node.slice
        if isinstance(base, ast.Name):
            v = env.get(base.id)
            idx = sl.value if isinstance(sl, ast.Constant) else getattr(sl, "value", None)
            if isinstance(v, list) and isinstance(idx, int) and not isinstance(idx, bool) \
                    and -len(v) <= idx < len(v):
                return [v[idx]]
        return None
    return None


def _formula_from_value(value: ast.AST, env: dict) -> tuple[bool, list[str] | None]:
    """(es_tex, args | None). Desenvuelve pintar_partes(MathTex(...))."""
    v = value
    while isinstance(v, ast.Call) and isinstance(v.func, ast.Name) \
            and v.func.id not in ("MathTex", "Tex") \
            and len(v.args) >= 1 and isinstance(v.args[0], ast.Call):
        v = v.args[0]
    v = _base_call(v)
    if v is None or _call_name(v.func) not in ("MathTex", "Tex"):
        return False, None
    args: list[str] = []
    for a in v.args:
        r = _resolve_arg(a, env)
        if r is None:
            return True, None
        args.extend(r)
    return True, args


def _eval_test(test: ast.AST, env: dict):
    """Condicion estatica (==, != sobre str/int/bool) -> True/False/None."""
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
        op = test.ops[0]
        if not isinstance(op, (ast.Eq, ast.NotEq)):
            return None
        vals = []
        for n in (test.left, test.comparators[0]):
            if isinstance(n, ast.Constant) and isinstance(n.value, (str, int, float, bool)):
                vals.append(n.value)
            elif isinstance(n, ast.Name) and isinstance(env.get(n.id), (str, int, float, bool)):
                vals.append(env[n.id])
            else:
                return None
        eq = vals[0] == vals[1]
        return eq if isinstance(op, ast.Eq) else not eq
    if isinstance(test, ast.Constant) and isinstance(test.value, bool):
        return test.value
    return None


def _eval_name_or_none(node: ast.AST, env: dict):
    """IfExp/Name de transicion -> nombre de variable o None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.IfExp):
        c = _eval_test(node.test, env)
        if c is None:
            return None
        return _eval_name_or_none(node.body if c else node.orelse, env)
    return None


def _snapshot(env: dict, var: str) -> str:
    v = env.get(var)
    if isinstance(v, str):
        return v
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return " ".join(v)
    return ""


def _walk_no_for(node: ast.AST):
    """Yield node y descendientes sin entrar en bucles for (ya desenrollados)."""
    yield node
    for ch in ast.iter_child_nodes(node):
        if isinstance(ch, ast.For):
            continue
        yield from _walk_no_for(ch)


def _process_transition_call(node: ast.Call, env: dict, sq: SequenceFile,
                             seen_tids: set[str]) -> None:
    name = _call_name(node.func)
    if name == "TransformMatchingTex":
        if len(node.args) >= 2:
            a = _eval_name_or_none(node.args[0], env)
            b = _eval_name_or_none(node.args[1], env)
            if a and b:
                _add_transition(sq, a, b, node.lineno, "", "tmt",
                                _snapshot(env, a), _snapshot(env, b), seen_tids)
    elif name == "TransformByGlyphMap":
        if len(node.args) >= 2:
            a = _eval_name_or_none(node.args[0], env)
            b = _eval_name_or_none(node.args[1], env)
            if not (a and b):
                return
            mname = ""
            for x in node.args[2:]:
                if isinstance(x, ast.Starred) and isinstance(x.value, ast.Name):
                    mname = x.value.id
                    break
            t_kind = "tbgm"
            _add_transition(sq, a, b, node.lineno, mname, t_kind,
                            _snapshot(env, a), _snapshot(env, b), seen_tids)
            if mname and mname not in _MAP_CONSTS.get(id(sq), set()):
                sq.warnings.append(
                    f"Par {a}->{b} (linea {node.lineno}): *{mname} no es lista literal, precarga omitida.")
            elif not mname:
                inl = _as_inline_entries(list(node.args[2:]))
                if inl:
                    key = f"{a}->{b}"
                    if key not in sq.prefill:
                        sq.prefill[key] = inl
    elif name == "ReplacementTransform":
        if len(node.args) >= 2:
            a = _eval_name_or_none(node.args[0], env)
            b = _eval_name_or_none(node.args[1], env)
            if a and b:
                _add_transition(sq, a, b, node.lineno, "", "repl",
                                _snapshot(env, a), _snapshot(env, b), seen_tids)


_MAP_CONSTS: dict[int, set] = {}


def _add_transition(sq: SequenceFile, a: str, b: str, line: int, mname: str,
                    kind: str, la: str, lb: str, seen: set[str]) -> None:
    tid = f"{a}->{b}"
    if tid in seen:
        i = 2
        while f"{tid}#{i}" in seen:
            i += 1
        tid = f"{tid}#{i}"
    seen.add(tid)
    # el tid publico conserva from/to (el sufijo solo desempata duplicados)
    t = Transition(a, b, line, mname, kind, la, lb)
    t.tid = tid  # type: ignore[attr-defined]
    sq.transitions.append(t)


def _unroll_for(node: ast.For, env: dict):
    """for a, b in ((..), (..)): -> lista de dicts de ligaduras o None."""
    tgt = node.target
    if not isinstance(tgt, (ast.Tuple, ast.List)):
        return None
    names = [e.id for e in tgt.elts if isinstance(e, ast.Name)]
    if len(names) != len(tgt.elts):
        return None
    if not isinstance(node.iter, (ast.Tuple, ast.List)):
        return None
    rows = []
    for elt in node.iter.elts:
        if isinstance(elt, (ast.Tuple, ast.List)) and len(elt.elts) == len(names):
            row = {}
            ok = True
            for n, v in zip(names, elt.elts):
                if isinstance(v, ast.Constant) and isinstance(v.value, (str, int, float, bool)):
                    row[n] = v.value
                elif isinstance(v, ast.Name):
                    row[n] = ("__name__", v.id)
                else:
                    ok = False
                    break
            if ok:
                rows.append(row)
                continue
        return None
    return rows


def _process_block(stmts: list[ast.stmt], env: dict, sq: SequenceFile,
                   seen_tids: set[str]) -> None:
    for st in stmts:
        if isinstance(st, ast.Assign) and len(st.targets) == 1 \
                and isinstance(st.targets[0], ast.Name):
            var = st.targets[0].id
            is_tex, args = _formula_from_value(st.value, env)
            if is_tex:
                if args is None:
                    sq.formulas.append(Formula(var, "MathTex", [], st.lineno, True))
                    sq.warnings.append(
                        f"{var} (linea {st.lineno}): arg no literal, se omite valor.")
                    env[var] = None
                else:
                    sq.formulas.append(Formula(var, "MathTex", args, st.lineno, False))
                    env[var] = list(args)
            elif isinstance(st.value, ast.Name) and st.value.id in env:
                v = env[st.value.id]  # alias: f9 = fx propaga el latex vigente
                if isinstance(v, str):
                    sq.formulas.append(Formula(var, "MathTex", [v], st.lineno, False))
                    env[var] = v
                elif isinstance(v, list) and all(isinstance(x, str) for x in v):
                    sq.formulas.append(Formula(var, "MathTex", list(v), st.lineno, False))
                    env[var] = list(v)
                else:
                    sq.formulas.append(Formula(var, "MathTex", [], st.lineno, True))
                    env[var] = None
            # no-tex: se ignora en silencio (copias .copy(), VGroup, badges...)
        elif isinstance(st, ast.For):
            rows = _unroll_for(st, env)
            if rows is None:
                # bucle no estatico: mejor esfuerzo sin snapshots
                for sub in _walk_no_for(st):
                    if isinstance(sub, ast.Call):
                        _process_transition_call(sub, env, sq, seen_tids)
                for sub in ast.walk(st):
                    if isinstance(sub, ast.Assign) and len(sub.targets) == 1 \
                            and isinstance(sub.targets[0], ast.Name):
                        is_tex, args = _formula_from_value(sub.value, env)
                        if is_tex:
                            if args is None:
                                sq.formulas.append(
                                    Formula(sub.targets[0].id, "MathTex", [], sub.lineno, True))
                                env[sub.targets[0].id] = None
                            else:
                                sq.formulas.append(
                                    Formula(sub.targets[0].id, "MathTex", args, sub.lineno, False))
                                env[sub.targets[0].id] = list(args)
                continue
            for row in rows:
                local = dict(env)
                for k, v in row.items():
                    if isinstance(v, tuple) and v[0] == "__name__":
                        # liga al VALOR de la constante homonima si existe
                        local[k] = env.get(v[1], ("__name__", v[1]))
                    else:
                        local[k] = v
                _process_block(st.body, local, sq, seen_tids)
                # propaga asignaciones simples de vuelta (fx, f9, ...)
                for k, v in local.items():
                    if k not in env or env.get(k) != v:
                        if isinstance(v, (str, list)) or v is None:
                            env[k] = v
        elif isinstance(st, ast.If):
            c = _eval_test(st.test, env)
            if c is True:
                _process_block(st.body, env, sq, seen_tids)
            elif c is False:
                _process_block(st.orelse, env, sq, seen_tids)
            else:
                a, b = dict(env), dict(env)
                _process_block(st.body, a, sq, seen_tids)
                _process_block(st.orelse, b, sq, seen_tids)
                for k in set(a) | set(b):
                    env[k] = a.get(k) if a.get(k) == b.get(k) else None
        else:
            for sub in _walk_no_for(st):
                if isinstance(sub, ast.Call):
                    _process_transition_call(sub, env, sq, seen_tids)


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
    consts = _collect_consts(tree)
    # Pasada 1: mapas literales GLYPH_MAP_* (orden irrelevante).
    map_consts: dict[str, list] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            gm = _as_glyph_map(node.value)
            if gm is not None:
                map_consts[node.targets[0].id] = gm[0]
                if gm[1]:
                    sq.warnings.append(
                        f"*{node.targets[0].id} (linea {node.lineno}): opciones no soportadas "
                        "ignoradas (solo path_arc numerico se precarga); el mapeo f->t se conserva.")
    _MAP_CONSTS[id(sq)] = set(map_consts)
    try:
        # Pasada 2: ambitos (modulo + cada funcion/metodo) en orden de fuente.
        seen_tids: set[str] = set()
        scopes: list[tuple[str, list[ast.stmt]]] = [(
            "<module>",
            [s for s in tree.body
             if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))])]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append((node.name,
                               [s for s in node.body
                                if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]))
        for _name, body in scopes:
            env = dict(consts)
            _process_block(sorted(body, key=lambda s: getattr(s, "lineno", 0)),
                           env, sq, seen_tids)
        # orden de fuente + precarga de mapas literales
        sq.formulas.sort(key=lambda f: f.line)
        sq.transitions.sort(key=lambda t: t.line)
        for t in sq.transitions:
            if t.map_name and t.map_name in map_consts:
                sq.prefill[f"{t.from_var}->{t.to_var}"] = map_consts[t.map_name]
        # pares que apuntan a variables desconocidas
        known = {f.var for f in sq.formulas}
        kept = []
        for t in sq.transitions:
            if not _warn_unknown(sq, t, known):
                kept.append(t)
        sq.transitions = kept
        if any(t.kind == "repl" for t in sq.transitions):
            sq.warnings.append(
                "Hay pares con ReplacementTransform: se importan como migrables; "
                "mapea y exporta TransformByGlyphMap.")
    finally:
        _MAP_CONSTS.pop(id(sq), None)
    return sq, lines


def _warn_unknown(sq: SequenceFile, t: Transition, known: set[str]) -> bool:
    missing = [v for v in (t.from_var, t.to_var) if v not in known]
    if missing:
        sq.warnings.append(f"Par {t.from_var}->{t.to_var} (linea {t.line}): sin MathTex: {missing}.")
        return True
    return False
