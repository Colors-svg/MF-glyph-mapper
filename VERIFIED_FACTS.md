# VERIFIED_FACTS.md — MF Glyph Mapper, Fase 0
Fuente de verdad: código instalado. Nada de docs públicas.

## Entorno
- Python 3.12.4 (verificado `sys.version`).
- Manim CE 0.20.0 (verificado `manim.__version__`). Discrepancia: se asumía 0.19.0.
- MF_Tools 1.1.1 en `C:\...\site-packages\MF_Tools\__init__.py:1` (`__version__='1.1.1'`).

## TransformByGlyphMap — firma
- `MF_Tools/transforms.py:3-23`: `__init__(self, mobA, mobB, *glyph_map, from_copy=False, mobA_submobject_index=[0], mobB_submobject_index=[0], default_introducer=FadeIn, default_remover=FadeOut, introduce_individually=False, remove_individually=False, shift_fades=True, show_indices=False, A_index_labels_color, B_index_labels_color, index_label_height=0.18, printing=False, **kwargs)`.

## Resolución de ruta (Regla de Oro)
- `transforms.py:25-30`: `A = mobA.copy() if from_copy else mobA; for i in mobA_submobject_index: A = A[i]`. Igual para B (sin copy).
- Por defecto `[0]`: los índices del mapa son índices directos de `mob[0]`, NO del `MathTex` completo.
- `manim/utils/debug.py:index_labels`: enumera submobjects directos (`for n, submob in enumerate(mobject)`). En modo `show_indices` (`transforms.py:111-119`) se etiqueta `A` y `B` ya resueltos.

## Estructura real de MathTex (experimentos ejecutados)
- `MathTex("x^2 + y")`: `len=1`, `len(m[0])=4`. `m[0]` = glyphs.
- `MathTex("\\frac{a}{b}")`: `len=1`, `len(m[0])=3` (a, barra Rectangle, b).
- `MathTex("\\sqrt{x+1}")`: `len=1`, `len(m[0])=5`.
- `MathTex("x_{i+1}")`: `len=1`, `len(m[0])=4`.
- `MathTex("e^{i\\pi}")`: `len=1`, `len(m[0])=3`.
- Ecuación larga: `len=1`, `len(m[0])=38`.
- `MathTex("{{x}}+{{y}}")`: `len=3` (cada parte `len=1`). Default `[0]` solo ve `x`.
- `MathTex("x","+","y")`: `len=3`. Mismo efecto.
- Conclusión: `\frac`, `\sqrt`, `^`, `_` NO dividen nivel superior; `{{...}}` y multi-arg SÍ. Hojas = `VMobjectFromSVGPath` / `Rectangle`, con `get_center()/width/height` utilizables para posiciones UI.

## Formato de entradas del mapa
- `transforms.py:35-36`: `VG(mob, idx) = VGroup(*[mob[i] for i in idx])`.
- `transforms.py:43-44`: cada entry len 2 o 3; `entry[2]` = dict kwargs (`delay` → `Succession(Wait, anim)`).
- `transforms.py:46-48`: `([],[])` → `show_indices=True`.
- `transforms.py:49-63`: `([], [b])` → `default_introducer` (FadeIn); `(AnimClass, [b])` → introducer custom. Flags `introduce_individually`, `shift_fades`.
- `transforms.py:64-78`: `([a], [])` → `default_remover` (FadeOut); `([a], AnimClass)` → remover custom. Flag `remove_individually`.
- `transforms.py:79-91`: `([a],[b])` → `ReplacementTransform`. Reutilizar origen permitido: `transforms.py:81` hace `.copy()` si `i in mentioned_from_indices`.
- Reutilización de destino: el código solo acumula `mentioned_to_indices` (`:63,:91`), nunca lo valida. No verificado visualmente; el validador deberá advertir.

## No mencionados / show_indices
- `transforms.py:38`: mapa vacío → `show_indices=True`.
- `transforms.py:99-100`: restantes = `[i for i in range(len(A/B)) if i not in mentioned]`.
- `transforms.py:102-106`: si cantidades restantes difieren → print Error + `show_indices=True` (ignora el mapa).
- `transforms.py:121-122`: si coinciden → `ReplacementTransform(A[i], B[j])` por orden.
- `transforms.py:111-119`: `show_indices` descarta animaciones y muestra `index_labels(A) + index_labels(B) + Wait(5)`.
