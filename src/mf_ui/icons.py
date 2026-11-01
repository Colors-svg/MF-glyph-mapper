"""Iconos SVG inline (Fase 8). Sin paquetes: QtSvg nativo, trazo 1.8px."""
from __future__ import annotations
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer

_FG = "#dfe3ea"
_ACC = "#4c8dff"

SVG = {
    # dos nodos unidos: conectar N->M
    "link": f'<circle cx="6" cy="12" r="3.2" fill="none" stroke="{_FG}" stroke-width="1.8"/>'
            f'<circle cx="18" cy="12" r="3.2" fill="none" stroke="{_FG}" stroke-width="1.8"/>'
            f'<path d="M9 12h6" stroke="{_FG}" stroke-width="1.8"/>',
    # flecha saliendo: fade out / siguiente
    "out": f'<path d="M4 12h11M12 6l6 6-6 6" fill="none" stroke="{_FG}" stroke-width="1.8" '
           'stroke-linecap="round" stroke-linejoin="round"/>',
    # flecha entrando: fade in / atras
    "in": f'<path d="M20 12H9M12 6l-6 6 6 6" fill="none" stroke="{_FG}" stroke-width="1.8" '
          'stroke-linecap="round" stroke-linejoin="round"/>',
    "trash": f'<path d="M5 7h14M10 7V5h4v2M8 7l1 13h6l1-13" fill="none" stroke="{_FG}" '
             'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "undo": f'<path d="M8 7H4v4M4 11c0 5 4 8 10 8 3 0 5-1 6-2" fill="none" stroke="{_FG}" '
            'stroke-width="1.8" stroke-linecap="round"/>',
    "redo": f'<path d="M16 7h4v4M20 11c0 5-4 8-10 8-3 0-5-1-6-2" fill="none" stroke="{_FG}" '
            'stroke-width="1.8" stroke-linecap="round"/>',
    "clear": f'<path d="M6 6l12 12M18 6L6 18" stroke="{_FG}" stroke-width="1.8" stroke-linecap="round"/>',
    "save": f'<path d="M5 4h11l3 3v13H5zM8 4v5h7V4M8 20v-6h8v6" fill="none" stroke="{_FG}" '
            'stroke-width="1.8" stroke-linejoin="round"/>',
    "copy": f'<rect x="8" y="8" width="12" height="12" rx="2" fill="none" stroke="{_FG}" stroke-width="1.8"/>'
            f'<path d="M4 16V6a2 2 0 012-2h10" fill="none" stroke="{_FG}" stroke-width="1.8"/>',
    "open": f'<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z" '
            f'fill="none" stroke="{_FG}" stroke-width="1.8" stroke-linejoin="round"/>',
    "play": f'<path d="M8 5l11 7-11 7z" fill="{_ACC}"/>',
    "video": f'<rect x="3" y="7" width="12" height="10" rx="2" fill="none" stroke="{_FG}" stroke-width="1.8"/>'
             f'<path d="M15 10l6-3v10l-6-3" fill="none" stroke="{_FG}" stroke-width="1.8" '
             'stroke-linejoin="round"/>',
    "check": f'<path d="M4 13l5 5L20 7" fill="none" stroke="{_ACC}" stroke-width="2.2" '
             'stroke-linecap="round" stroke-linejoin="round"/>',
    "help": f'<circle cx="12" cy="12" r="8.5" fill="none" stroke="{_FG}" stroke-width="1.8"/>'
            f'<path d="M9.5 9.5A2.5 2.5 0 0112 8c1.4 0 2.5 1 2.5 2.2 0 1.7-2.3 2-2.3 3.6" fill="none" '
            f'stroke="{_FG}" stroke-width="1.8" stroke-linecap="round"/>'
            f'<circle cx="12.2" cy="17" r="1.1" fill="{_FG}"/>',
}

_cache: dict[tuple[str, int], QIcon] = {}


def icon(name: str, size: int = 18) -> QIcon:
    """QIcon desde SVG inline. Cacheado por (nombre, tamano)."""
    key = (name, size)
    if key not in _cache:
        body = SVG.get(name, SVG["check"])
        data = QByteArray(f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
                          f'viewBox="0 0 24 24">{body}</svg>'.encode())
        ren = QSvgRenderer(data)
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        from PySide6.QtGui import QPainter
        p = QPainter(pm)
        ren.render(p)
        p.end()
        _cache[key] = QIcon(pm)
    return _cache[key]
