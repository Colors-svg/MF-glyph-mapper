"""Fase 7 (V2.0): extraccion estatica de .py con AST. Sin ejecutar la escena.

Extrae: formulas MathTex/Tex (variable -> literales), pares de
TransformMatchingTex(a, b) y fases desde comentarios BLOQUE.
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


@dataclass
class SequenceFile:
    path: str
    formulas: list[Formula] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

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
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            base = _base_call(node.value)
            if base is None:
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
        elif isinstance(node, ast.Call) and _call_name(node.func) == "TransformMatchingTex":
            if len(node.args) >= 2 and all(isinstance(a, ast.Name) for a in node.args[:2]):
                sq.transitions.append(Transition(node.args[0].id, node.args[1].id, node.lineno))
    # pares que apuntan a variables desconocidas
    known = {f.var for f in sq.formulas}
    sq.transitions = [t for t in sq.transitions
                      if not _warn_unknown(sq, t, known)]
    return sq, lines


def _warn_unknown(sq: SequenceFile, t: Transition, known: set[str]) -> bool:
    missing = [v for v in (t.from_var, t.to_var) if v not in known]
    if missing:
        sq.warnings.append(f"Par {t.from_var}->{t.to_var} (linea {t.line}): sin MathTex: {missing}.")
        return True
    return False
