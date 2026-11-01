"""Modelo de datos del glyph_map. Puro, sin UI. Testeable sin ventana."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Connection:
    """Una entrada del glyph_map. kind se deriva: ambos lados -> transform; solo destino -> introduce; solo origen -> remove."""
    from_indices: tuple[int, ...]
    to_indices: tuple[int, ...]

    @property
    def kind(self) -> str:
        if self.from_indices and self.to_indices:
            return "transform"
        if self.to_indices:
            return "introduce"
        return "remove"

    def to_entry(self) -> tuple[list[int], list[int]]:
        return (list(self.from_indices), list(self.to_indices))


@dataclass
class GlyphMapModel:
    """Guarda conexiones + undo/redo. Permisivo a proposito: el validador (Fase 3) avisa de destinos reutilizados, no el modelo."""
    n_from: int = 0
    n_to: int = 0
    connections: list[Connection] = field(default_factory=list)
    _undo: list[list[Connection]] = field(default_factory=list, repr=False)
    _redo: list[list[Connection]] = field(default_factory=list, repr=False)

    def _snap(self) -> None:
        self._undo.append(list(self.connections))
        self._redo.clear()

    def _check(self, idx: tuple[int, ...], side: str) -> tuple[int, ...]:
        n = self.n_from if side == "from" else self.n_to
        norm = tuple(sorted(set(idx)))
        for i in norm:
            if not (0 <= i < n):
                raise IndexError(f"indice {side} {i} fuera de 0..{n - 1}")
        return norm

    def configure(self, n_from: int, n_to: int) -> None:
        self._snap()
        self.n_from, self.n_to = n_from, n_to
        self.connections = [c for c in self.connections
                            if all(i < n_from for i in c.from_indices)
                            and all(i < n_to for i in c.to_indices)]

    def add(self, from_indices: tuple[int, ...] | list[int], to_indices: tuple[int, ...] | list[int]) -> Connection:
        f = self._check(tuple(from_indices), "from")
        t = self._check(tuple(to_indices), "to")
        if not f and not t:
            raise ValueError("conexion vacia ([],[]) invalida")
        conn = Connection(f, t)
        if conn in self.connections:
            raise ValueError(f"conexion duplicada {conn}")
        self._snap()
        self.connections.append(conn)
        return conn

    def remove(self, conn: Connection) -> None:
        if conn not in self.connections:
            raise KeyError(f"conexion inexistente {conn}")
        self._snap()
        self.connections.remove(conn)

    def clear(self) -> None:
        if self.connections:
            self._snap()
            self.connections.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(list(self.connections))
        self.connections = self._undo.pop()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(list(self.connections))
        self.connections = self._redo.pop()
        return True

    def mentioned_from(self) -> set[int]:
        return {i for c in self.connections for i in c.from_indices}

    def mentioned_to(self) -> set[int]:
        return {i for c in self.connections for i in c.to_indices}

    def to_glyph_map(self) -> list[tuple[list[int], list[int]]]:
        return [c.to_entry() for c in self.connections]

    def to_dict(self) -> dict:
        return {"n_from": self.n_from, "n_to": self.n_to,
                "connections": [{"from": list(c.from_indices), "to": list(c.to_indices)}
                                for c in self.connections]}

    @classmethod
    def from_dict(cls, d: dict) -> "GlyphMapModel":
        m = cls(n_from=d.get("n_from", 0), n_to=d.get("n_to", 0))
        for c in d.get("connections", []):
            m.connections.append(Connection(tuple(c.get("from", [])), tuple(c.get("to", []))))
        return m
