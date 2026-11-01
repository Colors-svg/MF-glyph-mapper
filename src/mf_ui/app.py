"""Entrada Fase 6: tres ventanas (Mapear / Verificar+Exportar / Previa)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402
from mf_ui.flow_windows import Controller, MapWindow  # noqa: E402
from mf_ui.onboarding import WelcomeDialog, should_show  # noqa: E402


def load_fonts() -> list[str]:
    """Registra las fuentes empaquetadas en assets/fonts. Devuelve familias cargadas."""
    from PySide6.QtGui import QFontDatabase
    loaded = []
    d = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
    if d.is_dir():
        for fp in sorted(d.glob("*.ttf")) + sorted(d.glob("*.otf")):
            fid = QFontDatabase.addApplicationFont(str(fp))
            if fid >= 0:
                loaded += QFontDatabase.applicationFontFamilies(fid)
    return loaded


def load_theme(app: QApplication) -> bool:
    """Aplica theme.qss + fuentes. Nativo de Qt, sin dependencias. True si cargo."""
    load_fonts()
    try:
        qss = Path(__file__).with_name("theme.qss").read_text(encoding="utf-8")
    except OSError:
        return False
    app.setStyleSheet(qss)
    return True


def main() -> None:
    app = QApplication(sys.argv)
    app.setOrganizationName("MFGlyphMapper")
    load_theme(app)
    if should_show():
        WelcomeDialog().exec()
    ctl = Controller()
    win = MapWindow(ctl)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
