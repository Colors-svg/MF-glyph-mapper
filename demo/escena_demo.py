"""Escena demo de MF Glyph Mapper: 3 pares, 2 BLOQUEs, LaTeX mínimo (render rápido).

Úsala con el botón «Probar demo» sin necesidad de tener escena propia.
Extracción esperada: 4 fórmulas, 3 transiciones, 0 avisos.
"""
from manim import Scene, MathTex, Write, TransformMatchingTex


class DemoFisica(Scene):
    def construct(self) -> None:
        # BLOQUE 1: definicion
        eq1 = MathTex(r"x = v t")
        eq2 = MathTex(r"x = v_0 t")
        eq3 = MathTex(r"x = v_0 t + x_0")
        self.play(Write(eq1))
        self.play(TransformMatchingTex(eq1, eq2))
        self.play(TransformMatchingTex(eq2, eq3))
        # BLOQUE 2: cierre
        eq4 = MathTex(r"\Delta x = v_0 t")
        self.play(TransformMatchingTex(eq3, eq4))
