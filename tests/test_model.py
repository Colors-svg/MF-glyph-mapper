"""QA Fase 2: modelo sin ventana."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from mf_core.glyph_map_model import GlyphMapModel, Connection


def test_basic_n_m_reuse_undo() -> None:
    m = GlyphMapModel(n_from=4, n_to=3)
    m.add((0, 1), (0,))       # N->M
    m.add((0,), (1,))         # reutiliza origen 0: permitido
    assert m.mentioned_from() == {0, 1}
    assert m.to_glyph_map() == [([0, 1], [0]), ([0], [1])]
    assert m.undo() and len(m.connections) == 1
    assert m.redo() and len(m.connections) == 2
    m.remove(Connection((0,), (1,)))
    assert len(m.connections) == 1
    assert m.undo() and len(m.connections) == 2
    print("basic N->M + reuse + undo/redo OK")


def test_rechazos() -> None:
    m = GlyphMapModel(n_from=2, n_to=2)
    m.add((0,), (0,))
    try:
        m.add((0,), (0,))
        raise AssertionError("duplicada debio fallar")
    except ValueError:
        pass
    for bad in [((5,), (0,)), ((0,), (9,))]:
        try:
            m.add(*bad)
            raise AssertionError(f"fuera de rango debio fallar {bad}")
        except IndexError:
            pass
    try:
        m.add((), ())
        raise AssertionError("vacia debio fallar")
    except ValueError:
        pass
    assert not GlyphMapModel().undo() and not GlyphMapModel().redo()
    print("rechazos OK (duplicada, rango, vacia, undo vacio)")


def test_serialize() -> None:
    m = GlyphMapModel(n_from=3, n_to=3)
    m.add((0,), (2,))
    m.add((), (1,))  # introduce permitido (validador avisara si es accidente)
    d = m.to_dict()
    m2 = GlyphMapModel.from_dict(d)
    assert m2.to_glyph_map() == m.to_glyph_map()
    print("serialize round-trip OK")


if __name__ == "__main__":
    test_basic_n_m_reuse_undo()
    test_rechazos()
    test_serialize()
    print("ALL MODEL TESTS PASSED")
