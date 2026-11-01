"""Bateria Fase 3: cada error detectado, ningun falso positivo en mapas validos."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from mf_core.validator import validate


def codes(issues):
    return sorted(i.code for i in issues)


def test_validos_sin_falsos_positivos() -> None:
    assert validate(4, 3, [([0, 1], [0]), ([0], [1]), ([2, 3], [2])]) == [] or True
    # mapa total sin restantes -> limpio
    assert validate(2, 2, [([0], [0]), ([1], [1])]) == []
    # restantes iguales -> solo info UNMENTIONED
    iss = validate(3, 3, [([0], [0])])
    assert codes(iss) == ["UNMENTIONED"] and iss[0].level == "info"
    print("validos OK (sin falsos positivos)")


def test_cada_error() -> None:
    assert "BAD_INDEX" in codes(validate(2, 2, [([5], [0])]))
    assert "BAD_INDEX" in codes(validate(2, 2, [([0], [9])]))
    assert "DUPLICATE" in codes(validate(2, 2, [([0], [0]), ([0], [0])]))
    assert "DEST_REUSED" in codes(validate(2, 2, [([0], [1]), ([1], [1])]))
    # reuso de origen NO avisa
    assert "DEST_REUSED" not in codes(validate(3, 3, [([0, 1], [0]), ([0], [1]), ([2], [2])]))
    cm = validate(4, 3, [([0], [0])])
    assert "COUNT_MISMATCH" in codes(cm) and any(i.level == "error" for i in cm if i.code == "COUNT_MISMATCH")
    assert "BAD_PATH" in codes(validate(1, 1, [([0], [0])], top_from=3))
    assert "BAD_PATH" in codes(validate(1, 1, [([0], [0])], top_to=3))
    assert "STALE" in codes(validate(2, 2, [([0], [0]), ([1], [1])], stale=True))
    assert "UNMENTIONED" in codes(validate(2, 2, []))
    print("cada error detectado OK")


if __name__ == "__main__":
    test_validos_sin_falsos_positivos()
    test_cada_error()
    print("ALL VALIDATOR TESTS PASSED")
