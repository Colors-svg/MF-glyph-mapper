"""Onboarding Fase 8: dialogo de bienvenida (una vez) + textos de ayuda."""
from __future__ import annotations
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QPushButton, QHBoxLayout

ORG = "MFGlyphMapper"
KEY_SEEN = "welcome/seen_v1"


def should_show() -> bool:
    return not bool(QSettings(ORG, "app").value(KEY_SEEN, False, type=bool))


def mark_seen() -> None:
    QSettings(ORG, "app").setValue(KEY_SEEN, True)


class WelcomeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bienvenido a MF Glyph Mapper")
        root = QVBoxLayout(self)
        root.addWidget(QLabel("<h2>Mapea glifos, no los adivines</h2>"))
        for i, txt in enumerate([
            "<b>1. Mapea.</b> Renderiza inicial y final, haz clic en origen y destino "
            "(Ctrl = múltiple). Zoom con rueda, pan con arrastre.",
            "<b>2. Verifica y exporta.</b> Corrige lo que marque el validador "
            "(duplicados, restantes, STALE) y copia el snippet o guarda el proyecto.",
            "<b>3. Previsualiza.</b> Genera el clip real con Manim antes de pegarlo en tu escena.",
        ], start=1):
            lab = QLabel(txt)
            lab.setWordWrap(True)
            root.addWidget(lab)
        root.addWidget(QLabel("V2: <i>Secuencias</i> carga tu .py y arma un bundle por nombres reales "
                             "para que tu agente reescriba los TransformMatchingTex."))
        self.again = QCheckBox("No mostrar de nuevo")
        self.again.setChecked(True)
        row = QHBoxLayout()
        row.addWidget(self.again)
        ok = QPushButton("Empezar")
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        root.addLayout(row)
        self.resize(460, 340)

    def accept(self) -> None:  # noqa: N802
        if self.again.isChecked():
            mark_seen()
        super().accept()
