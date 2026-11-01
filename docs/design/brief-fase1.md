# Brief de dirección visual — MF Glyph Mapper web (Fase 1, 1 página)

**Idea:** un banco de trabajo de precisión, no una página. Fondo tinta profunda con
rejilla de plano técnico muy sutil; glifos RELLENOS en blanco cálido (tiza sobre
pizarra, coherente con Manim, que dibuja trazos claros sobre negro); UN solo
acento eléctrico para acciones; cada conexión con su propio tono (paleta
Okabe-Ito de 10, distinguible con daltonismo); paneles como capas con borde de
1px a baja opacidad, sin sombras pesadas; todo en escala de 4px; Inter para UI
y mono tabular para índices y código.

**Jerarquía:** 1) canvas (domina), 2) conexión activa (color propio),
3) acciones (primaria única por pantalla), 4) código/datos, 5) cromo. Los
números (índices) siempre en pastilla mono tabular; el texto explicativo nunca
compite con el canvas.

**Las dos variantes:**
- **A · Pizarra:** cálida y editorial. Blanco tiza `#f5f1e6`, acento azul
  eléctrico, radio 10px, respiro generoso. El canvas parece la pizarra de Manim.
- **B · Instrumento:** fría y técnica. Acento verde azulado, radio 6px,
  micro-etiquetas en mayúsculas, densidad mayor. El canvas parece un osciloscopio.

Comparten: tokens de espacio/radio/motion, paleta categórica, mono tabular,
modo claro opcional, y la Regla de Oro (las insignias muestran `glyph.index`
tal cual; el estilo jamás reordena ni recalcula).
