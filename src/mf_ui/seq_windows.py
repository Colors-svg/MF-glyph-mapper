"""Fase 7 (V2.0): ventana de secuencias. Carga un .py, lista transiciones
por fase, mapea cada par en la ventana 1 y exporta el bundle por nombres
reales para el agente (sobreescribe TransformMatchingTex)."""
from __future__ import annotations
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QListWidget, QLabel, QMessageBox, QFileDialog,
)

from mf_core.seq_extract import parse_file, SequenceFile
from mf_core.exporter import build_agent_bundle, build_agent_instructions
from mf_ui.icons import icon


class SeqWindow(QMainWindow):
    def __init__(self, mapwin):
        super().__init__()
        self.mapwin = mapwin
        self.ctl = mapwin.ctl
        self.sq: SequenceFile | None = None
        self.lines: list[str] = []
        self.phases: dict[int, str] = {}
        self.maps: dict[str, list] = {}  # tid -> glyph_map
        self.setWindowTitle("MF Glyph Mapper — Secuencias V2 (.py -> bundle)")
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        self.setAcceptDrops(True)
        pathrow = QHBoxLayout()
        self.path_edit = QLineEdit(r"D:\manim\ejercicios\cinetica_orden_cuatro.py")
        self.path_edit.setPlaceholderText("Pega la ruta del .py o arrastra el archivo aquí…")
        self.path_edit.setToolTip("Ruta directa: no usa el explorador de archivos")
        self.b_go = QPushButton("Cargar ruta")
        self.b_go.setToolTip("Lee el .py de la ruta escrita sin abrir el explorador")
        pathrow.addWidget(self.path_edit, 1)
        pathrow.addWidget(self.b_go)
        root.addLayout(pathrow)
        row = QHBoxLayout()
        self.b_load = QPushButton("Cargar .py (explorador)")
        self.b_pair = QPushButton("Cargar par en Mapear")
        self.b_save = QPushButton("Guardar mapa del par")
        self.b_bundle = QPushButton("Exportar bundle (.json)")
        for b in (self.b_load, self.b_pair, self.b_save, self.b_bundle):
            row.addWidget(b)
        self.b_load.setIcon(icon("open")); self.b_load.setToolTip("Lee MathTex y pares TransformMatchingTex de un .py (sin ejecutarlo)")
        self.b_pair.setIcon(icon("link")); self.b_pair.setToolTip("Carga el par seleccionado en la ventana Mapear")
        self.b_save.setIcon(icon("check")); self.b_save.setToolTip("Guarda el mapa validado de Mapear en esta transición")
        self.b_bundle.setIcon(icon("save")); self.b_bundle.setToolTip("Exporta bundle .json + AGENTE.md para tu agente")
        root.addLayout(row)
        self.info = QLabel("Carga un .py con MathTex + TransformMatchingTex.")
        root.addWidget(self.info)
        self.lst = QListWidget()
        self.lst.setMinimumHeight(300)
        root.addWidget(self.lst, 1)
        self.lst.itemDoubleClicked.connect(lambda *_: self.load_pair())
        self.b_load.clicked.connect(self.open_explorer)
        self.b_go.clicked.connect(lambda: self.load_file(self.path_edit.text().strip().strip('"')))
        self.b_pair.clicked.connect(self.load_pair)
        self.b_save.clicked.connect(self.save_map)
        self.b_bundle.clicked.connect(self.export_bundle)
        self._dlg: QFileDialog | None = None  # persistentes: no se recrean por clic
        self._save_dlg: QFileDialog | None = None
        self.resize(800, 600)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls:
            p = urls[0].toLocalFile()
            if p.lower().endswith(".py"):
                self.path_edit.setText(p)
                self.load_file(p)
            else:
                self.info.setText("Suelta un archivo .py.")

    def open_explorer(self) -> None:
        """Dialogo NO modal: la ventana jamas se congela aunque el dialogo tarde
        (unidades de red desconectadas etc.)."""
        if self._dlg is None:
            self._dlg = QFileDialog(self, "Abrir escena", "", "Python (*.py)")
            self._dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            self._dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
            self._dlg.fileSelected.connect(self.load_file)
        base = self.path_edit.text().strip().strip('"')
        try:
            import os
            d = os.path.dirname(os.path.abspath(base))
            self._dlg.setDirectory(d)
        except Exception:
            pass
        self._dlg.show()
        self._dlg.raise_()
        self._dlg.activateWindow()

    def load_file(self, path: str | None = None) -> None:
        if not path:
            self.info.setText("Pega una ruta y pulsa Cargar ruta, arrastra un .py o usa el explorador.")
            return
        self.maps.clear()
        try:
            self.sq, self.lines = parse_file(path)
            self.phases = self.sq.phases(self.lines)
        except Exception as e:  # noqa: BLE001 — un .py raro no debe tumbar la ventana
            QMessageBox.critical(self, "Error al leer", f"{type(e).__name__}: {e}")
            return
        self.refresh()
        n = len(self.sq.transitions)
        w = f" | avisos: {len(self.sq.warnings)}" if self.sq.warnings else ""
        self.info.setText(f"{Path(path).name}: {len(self.sq.formulas)} formulas, "
                         f"{n} transiciones{w}. Doble clic: cargar par.")
        if self.sq.warnings:
            QMessageBox.warning(self, "Avisos de extraccion", "\n".join(self.sq.warnings)[:1500])

    def _row(self, i: int):
        if self.sq is None or not (0 <= i < len(self.sq.transitions)):
            return None
        return self.sq.transitions[i]

    def refresh(self) -> None:
        self.lst.clear()
        if self.sq is None:
            return
        by_var = self.sq.by_var()
        for t in self.sq.transitions:
            tid = f"{t.from_var}->{t.to_var}"
            mark = "✓" if tid in self.maps else "·"
            fa = by_var[t.from_var].args[0][:40] if by_var[t.from_var].args else "?"
            self.lst.addItem(f"[{mark}] {tid} | {self.phases.get(id(t), '')} | {fa}...")

    def current_pair(self):
        t = self._row(self.lst.currentRow())
        if t is None or self.sq is None:
            return None
        by_var = self.sq.by_var()
        a, b = by_var[t.from_var], by_var[t.to_var]
        if not a.args or not b.args:
            QMessageBox.warning(self, "Par sin latex literal", f"{t.from_var}->{t.to_var}")
            return None
        return t, a.args[0], b.args[0]

    def load_pair(self) -> None:
        cur = self.current_pair()
        if cur is None:
            return
        _, la, lb = cur
        self.mapwin.open_pair(la, lb)
        self.mapwin.show()
        self.mapwin.raise_()
        self.info.setText(f"Par cargado en Mapear. Mapea, valida y vuelve a 'Guardar mapa del par'.")

    def save_map(self) -> None:
        cur = self.current_pair()
        if cur is None:
            return
        t, la, lb = cur
        if self.mapwin.left._rendered != la or self.mapwin.right._rendered != lb:
            QMessageBox.warning(self, "Par desalineado",
                                "Mapear no muestra este par. Pulsa 'Cargar par en Mapear' primero.")
            return
        block = self.ctl.blocked()
        if block:
            QMessageBox.warning(self, "Mapa con errores", block)
            return
        tid = f"{t.from_var}->{t.to_var}"
        self.maps[tid] = self.ctl.model.to_glyph_map()
        self.refresh()
        self.info.setText(f"Guardado {tid} ({len(self.maps)}/{len(self.sq.transitions)}).")

    def export_bundle(self) -> None:
        if self.sq is None or not self.maps:
            QMessageBox.warning(self, "Bundle", "Sin mapas guardados.")
            return
        if self._save_dlg is None:
            self._save_dlg = QFileDialog(self, "Guardar bundle", "agent_bundle.json", "JSON (*.json)")
            self._save_dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            self._save_dlg.setFileMode(QFileDialog.FileMode.AnyFile)
            self._save_dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            self._save_dlg.fileSelected.connect(self._do_export)
        self._save_dlg.show()
        self._save_dlg.raise_()
        self._save_dlg.activateWindow()

    def _do_export(self, path: str) -> None:
        if not path or self.sq is None:
            return
        by_var = self.sq.by_var()
        meta = {}
        for t in self.sq.transitions:
            tid = f"{t.from_var}->{t.to_var}"
            if tid in self.maps:
                meta[tid] = {"fase": self.phases.get(id(t), "Sin fase"),
                             "latex_a": by_var[t.from_var].args[0] if by_var[t.from_var].args else "",
                             "latex_b": by_var[t.to_var].args[0] if by_var[t.to_var].args else ""}
        bundle = build_agent_bundle(self.maps, meta)
        Path(path).write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path = Path(path).with_name("AGENTE.md")
        md_path.write_text(build_agent_instructions(bundle), encoding="utf-8")
        total = len(self.sq.transitions)
        self.info.setText(f"Bundle {Path(path).name} + AGENTE.md: {len(self.maps)}/{total} transiciones.")
