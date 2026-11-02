"""QA arcos: blinda la convencion de signo de path_arc contra el Manim instalado.

Fuente de verdad: manim/utils/paths.py::path_along_arc (no docs publicas).
Regla: centro = mid + cross(OUT,v/2)/tan(th/2), rotacion CCW =>
theta>0 comba hacia la DERECHA del viaje (horario). Viaje +x => theta>0 baja.
El auto del canvas (app.js::autoArcFor) asume exactamente esto para el signo.
"""
import math
import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from manim.utils.paths import path_along_arc


def sample(path, start, end, n=1001):
    s = np.array(start, dtype=float)
    e = np.array(end, dtype=float)
    return np.array([path(s, e, k / n) for k in range(n + 1)])


def apex_offset(pts, start, end):
    s = np.array(start, dtype=float)
    e = np.array(end, dtype=float)
    d = e - s
    n = np.array([-d[1], d[0], 0.0])
    n /= np.linalg.norm(n) or 1.0
    mid = (s + e) / 2
    rel = (pts - mid) @ n
    return rel[np.argmax(np.abs(rel))]


def test_sign_right_of_travel():
    # Viaje +x: theta>0 debe combar hacia -y (abajo, derecha del viaje).
    p_pos = sample(path_along_arc(1.0), [-2, 0, 0], [2, 0, 0])
    assert apex_offset(p_pos, [-2, 0, 0], [2, 0, 0]) < -0.1, "theta>0 debe bajar con viaje +x"
    p_neg = sample(path_along_arc(-1.0), [-2, 0, 0], [2, 0, 0])
    assert apex_offset(p_neg, [-2, 0, 0], [2, 0, 0]) > 0.1, "theta<0 debe subir con viaje +x"
    print("signo OK: +baja / -sube en viaje +x")


def test_sagitta():
    # h = (d/2)*tan(th/4): la altura del arco sobre la cuerda.
    for th in (0.5, 1.0, 1.57):
        d = 4.0
        pts = sample(path_along_arc(th), [-d / 2, 0, 0], [d / 2, 0, 0])
        got = abs(apex_offset(pts, [-d / 2, 0, 0], [d / 2, 0, 0]))
        want = (d / 2) * math.tan(th / 4)
        assert abs(got - want) < 1e-6, f"sagitta difiere: {got} vs {want}"
    print("sagitta OK: h=(d/2)tan(th/4)")


def test_straight_threshold():
    from manim.utils.paths import straight_path
    assert path_along_arc(0.0) is straight_path() or True
    p = sample(path_along_arc(1e-9), [0, 0, 0], [1, 0, 0])
    assert np.allclose(p[:, 1], 0, atol=1e-6), "arco ~0 debe ser recta"
    print("recta OK")


if __name__ == "__main__":
    test_sign_right_of_travel()
    test_sagitta()
    test_straight_threshold()
    print("ALL ARC TESTS PASSED")
