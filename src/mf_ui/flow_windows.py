"""Fase 6: tres ventanas dedicadas (Mapear / Verificar+Exportar / Vista previa).

Un Controlador compartido guarda modelo, tamanos, STALE e issues.
Los widgets pesados (GlyphPanel, MapView) se reutilizan de inspector.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Qt, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QGroupBox, QLabel, QMessageBox,
    QSplitter, QTextEdit, QPlainTextEdit, QFileDialog,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mf_core.glyph_map_model import GlyphMapModel  # noqa: E402
from mf_core.validator import validate  # noqa: E402
from mf_core.exporter import build_snippet, build_project, project_to_glyph_map, dumps_project  # noqa: E402
from mf_ui.inspector import GlyphPanel, MapView, GlyphItem, PreviewWorker  # noqa: E402
from mf_ui.icons import icon  # noqa: E402
from mf_ui.onboarding import WelcomeDialog  # noqa: E402
from mf_ui.inspector import _track, _untrack, _stop_thread  # noqa: E402 (hilos que sobreviven al cierre)


class Controller(QObject):
    """Estado compartido. Sin widgets; avisa con updated."""
    updated = Signal()
    locate = Signal(str, tuple)  # side, indices

    def __init__(self):
        super().__init__()
        self.model = GlyphMapModel()
        self.latex_a = "x^2 + y=1"
        self.latex_b = "x^2 = 1-y"
        self.n_from = 0
        self.n_to = 0
        self.top_from = 1
        self.top_to = 1
        self.stale = False
        self.issues: list = []
        self.pending: list | None = None

    def set_sizes(self, nf: int, nt: int, tf: int, tt: int) -> None:
        before = len(self.model.connections)
        self.model.configure(nf, nt)
        self.n_from, self.n_to, self.top_from, self.top_to = nf, nt, tf, tt
        pruned = before - len(self.model.connections)
        if self.pending and nf > 0 and nt > 0:
            for f, t in self.pending:
                try:
                    self.model.add(f, t)
                except (ValueError, IndexError):
                    continue
            self.pending = None
        self.validate_now()
        self.updated.emit()
        if pruned:
            self.pruned_msg = f"{pruned} conexiones podadas (fuera de rango)."
        else:
            self.pruned_msg = ""

    pruned_msg = ""

    def mark_stale(self) -> None:
        if not self.stale:
            self.stale = True
            self.validate_now()
            self.updated.emit()

    def clear_stale(self) -> None:
        if self.stale:
            self.stale = False
            self.validate_now()
            self.updated.emit()

    def validate_now(self) -> None:
        self.issues = validate(self.model.n_from, self.model.n_to,
                               self.model.to_glyph_map(),
                               top_from=self.top_from, top_to=self.top_to,
                               path=(0,), stale=self.stale)

    def errors(self) -> list:
        return [i for i in self.issues if i.level == "error"]

    def warnings(self) -> list:
        return [i for i in self.issues if i.level == "warning"]

    def blocked(self) -> str | None:
        errs = self.errors()
        if self.stale or any(i.code == "STALE" for i in errs):
            return "Hay STALE pendiente: re-renderiza ambos paneles en Mapear."
        if errs:
            return "Hay errores de validacion: " + "; ".join(i.code for i in errs)
        if self.n_from == 0 or self.n_to == 0:
            return "Renderiza ambos paneles en Mapear primero."
        return None

    def snippet(self) -> str:
        return build_snippet(self.model.to_glyph_map())


class MapWindow(QMainWindow):
    """Ventana 1: mapeo visual espacioso."""

    def __init__(self, ctl: Controller):
        super().__init__()
        self.ctl = ctl
        self._suppress = False
        self.setWindowTitle("MF Glyph Mapper — 1. Mapear")
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.left = GlyphPanel("INICIAL (clic=origen, Ctrl=multiple)", "x^2 + y=1")
        self.right = GlyphPanel("FINAL (clic 1+1 conecta, Ctrl=multiple)", "x^2 = 1-y")
        split.addWidget(self.left)
        split.addWidget(self.right)
        split.setSizes([600, 600])
        root.addWidget(split, 3)
        self.left._changed = self._sync
        self.right._changed = self._sync
        self.left._edited_cb = ctl.mark_stale
        self.right._edited_cb = ctl.mark_stale
        self.right.scene.selectionChanged.connect(self._auto_connect)

        dock = QGroupBox("Conexiones")
        dl = QVBoxLayout(dock)
        btns = QHBoxLayout()
        self.b_conn = QPushButton("Conectar sel. (N->M)")
        self.b_fade_out = QPushButton("Origen sin destino (fade out)")
        self.b_fade_in = QPushButton("Destino sin origen (fade in)")
        self.b_del = QPushButton("Eliminar")
        self.b_undo = QPushButton("Deshacer (Ctrl+Z)")
        self.b_redo = QPushButton("Rehacer (Ctrl+Y)")
        self.b_clear = QPushButton("Limpiar")
        self.b_next = QPushButton("Siguiente: Verificar y exportar →")
        self.b_seq = QPushButton("Secuencias V2 (.py)")
        self.b_help = QPushButton("?")
        self.b_help.setFixedWidth(36)
        for b in (self.b_conn, self.b_fade_out, self.b_fade_in, self.b_del,
                  self.b_undo, self.b_redo, self.b_clear, self.b_next, self.b_seq):
            btns.addWidget(b)
        btns.addWidget(self.b_help)
        self.b_conn.setIcon(icon("link")); self.b_conn.setToolTip("Crea conexión con lo seleccionado en ambos paneles (Ctrl = múltiple)")
        self.b_fade_out.setIcon(icon("out")); self.b_fade_out.setToolTip("El origen seleccionado desaparece con FadeOut: ([a], [])")
        self.b_fade_in.setIcon(icon("in")); self.b_fade_in.setToolTip("El destino seleccionado aparece con FadeIn: ([], [b])")
        self.b_del.setIcon(icon("trash")); self.b_del.setToolTip("Elimina la conexión seleccionada de la lista")
        self.b_undo.setIcon(icon("undo")); self.b_undo.setToolTip("Deshacer (Ctrl+Z)")
        self.b_redo.setIcon(icon("redo")); self.b_redo.setToolTip("Rehacer (Ctrl+Y)")
        self.b_clear.setIcon(icon("clear")); self.b_clear.setToolTip("Borra todas las conexiones")
        self.b_next.setIcon(icon("out")); self.b_next.setToolTip("Abre la ventana 2: verificar y exportar")
        self.b_seq.setIcon(icon("video")); self.b_seq.setToolTip("V2: carga un .py y arma un bundle de transiciones para tu agente")
        self.b_help.setIcon(icon("help")); self.b_help.setToolTip("Mostrar la guía de inicio")
        dl.addLayout(btns)
        mid = QHBoxLayout()
        self.lst = QListWidget()
        self.map = MapView(on_pick=self._pick_row)
        mid.addWidget(self.lst, 2)
        mid.addWidget(self.map, 3)
        dl.addLayout(mid)
        self.info = QLabel("Renderiza ambos paneles.")
        dl.addWidget(self.info)
        root.addWidget(dock, 2)

        self.b_conn.clicked.connect(self.connect_selected)
        self.b_fade_out.clicked.connect(lambda: self._fade("from"))
        self.b_fade_in.clicked.connect(lambda: self._fade("to"))
        self.b_del.clicked.connect(self.delete_selected)
        self.b_undo.clicked.connect(self.do_undo)
        self.b_redo.clicked.connect(self.do_redo)
        self.b_clear.clicked.connect(self.do_clear)
        self.b_next.clicked.connect(self._open_next)
        self.b_seq.clicked.connect(self._open_seq)
        self.b_help.clicked.connect(lambda: WelcomeDialog(self).exec())
        ctl.updated.connect(self.refresh)
        ctl.locate.connect(self._locate)
        self.verify_win: VerifyWindow | None = None
        self.seq_win = None
        self.resize(1280, 860)

    def _sync(self) -> None:
        self.ctl.latex_a = self.left._rendered or self.left.edit.text()
        self.ctl.latex_b = self.right._rendered or self.right.edit.text()
        self.ctl.set_sizes(self.left._n, self.right._n, self.left._top, self.right._top)
        if (self.left.edit.text() == self.left._rendered
                and self.right.edit.text() == self.right._rendered):
            self.ctl.clear_stale()

    def _clear_selections(self) -> None:
        self._suppress = True
        try:
            self.left.scene.clearSelection()
            self.right.scene.clearSelection()
        finally:
            self._suppress = False

    def _auto_connect(self) -> None:
        if self._suppress or self.left._n == 0 or self.right._n == 0:
            return
        f, t = self.left.get_selected(), self.right.get_selected()
        if len(f) == 1 and len(t) == 1:
            try:
                self.ctl.model.add(f, t)
            except ValueError as e:
                self.info.setText(str(e))
                return
            self._clear_selections()
            self.ctl.validate_now()
            self.ctl.updated.emit()

    def connect_selected(self) -> None:
        f, t = self.left.get_selected(), self.right.get_selected()
        if not f or not t:
            self.info.setText("Selecciona al menos 1 glifo en cada panel (Ctrl=multiple).")
            return
        try:
            self.ctl.model.add(f, t)
        except (ValueError, IndexError) as e:
            self.info.setText(str(e))
            return
        self._clear_selections()
        self.ctl.validate_now()
        self.ctl.updated.emit()

    def _fade(self, side: str) -> None:
        sel = self.left.get_selected() if side == "from" else self.right.get_selected()
        if not sel:
            self.info.setText("Selecciona glifos primero.")
            return
        try:
            self.ctl.model.add(sel if side == "from" else (), () if side == "from" else sel)
        except (ValueError, IndexError) as e:
            self.info.setText(str(e))
            return
        self._clear_selections()
        self.ctl.validate_now()
        self.ctl.updated.emit()

    def _pick_row(self, row: int) -> None:
        self.lst.setCurrentRow(row)

    def delete_selected(self) -> None:
        row = self.lst.currentRow()
        if 0 <= row < len(self.ctl.model.connections):
            self.ctl.model.remove(self.ctl.model.connections[row])
            self.ctl.validate_now()
            self.ctl.updated.emit()

    def do_undo(self) -> None:
        if not self.ctl.model.undo():
            self.info.setText("Nada que deshacer.")
        else:
            self.ctl.validate_now()
            self.ctl.updated.emit()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.left.cancel()
        self.right.cancel()
        super().closeEvent(event)

    def do_redo(self) -> None:
        if not self.ctl.model.redo():
            self.info.setText("Nada que rehacer.")
        else:
            self.ctl.validate_now()
            self.ctl.updated.emit()

    def do_clear(self) -> None:
        self.ctl.model.clear()
        self.ctl.validate_now()
        self.ctl.updated.emit()

    def _locate(self, side: str, indices: tuple) -> None:
        self._suppress = True
        try:
            for panel, s in ((self.left, "from"), (self.right, "to")):
                if side in (s, "both"):
                    panel.scene.clearSelection()
                    for g in panel.scene.items():
                        if isinstance(g, GlyphItem) and (not indices or g.idx in indices):
                            g.setSelected(True)
        finally:
            self._suppress = False
        self.raise_()
        self.activateWindow()

    def _open_next(self) -> None:
        if self.verify_win is None:
            self.verify_win = VerifyWindow(self.ctl, self)
        self.verify_win.show()
        self.verify_win.raise_()

    def _open_seq(self) -> None:
        from mf_ui.seq_windows import SeqWindow  # lazy: evita import circular
        if self.seq_win is None:
            self.seq_win = SeqWindow(self)
        self.seq_win.show()
        self.seq_win.raise_()

    def open_pair(self, latex_a: str, latex_b: str) -> None:
        """Carga un par de la secuencia: limpia modelo y renderiza."""
        self.ctl.model.clear()
        self.ctl.pending = None
        self.left.edit.setText(latex_a)
        self.right.edit.setText(latex_b)
        self.left.render_async()
        self.right.render_async()

    def open_project_dict(self, proj: dict) -> None:
        self.ctl.model.clear()
        self.ctl.pending = [(tuple(c.get("from", [])), tuple(c.get("to", [])))
                            for c in proj.get("connections", [])]
        self.left.edit.setText(proj.get("latex_a", ""))
        self.right.edit.setText(proj.get("latex_b", ""))
        self.left.render_async()
        self.right.render_async()

    def refresh(self) -> None:
        self.lst.clear()
        mark = "⚠ STALE " if self.ctl.stale else ""
        for c in self.ctl.model.connections:
            self.lst.addItem(f"{mark}{list(c.from_indices)} -> {list(c.to_indices)}  [{c.kind}]")
        self.map.refresh(self.ctl.model)
        errs = len(self.ctl.errors())
        warns = len(self.ctl.warnings())
        extra = f" | {self.ctl.pruned_msg}" if self.ctl.pruned_msg else ""
        self.info.setText(f"{len(self.ctl.model.connections)} conexiones | "
                          f"errores={errs} avisos={warns}{extra}")


class VerifyWindow(QMainWindow):
    """Ventana 2: verificacion + exportacion de codigo."""

    def __init__(self, ctl: Controller, mapwin: MapWindow):
        super().__init__()
        self.ctl = ctl
        self.mapwin = mapwin
        self.setWindowTitle("MF Glyph Mapper — 2. Verificar y exportar")
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.addWidget(QLabel("<b>Validacion (clic en issue = localizar glifos en Mapear):</b>"))
        self.issues = QListWidget()
        self.issues.setMinimumHeight(200)
        root.addWidget(self.issues, 1)
        self.info = QLabel("")
        root.addWidget(self.info)
        btns = QHBoxLayout()
        self.b_back = QPushButton("← Volver a mapear")
        self.b_copy = QPushButton("Copiar snippet")
        self.b_save = QPushButton("Guardar proyecto (.json + .py)")
        self.b_open = QPushButton("Abrir proyecto (.json)")
        self.b_prev = QPushButton("Siguiente: Vista previa →")
        for b in (self.b_back, self.b_copy, self.b_save, self.b_open, self.b_prev):
            btns.addWidget(b)
        root.addLayout(btns)
        self.b_back.setIcon(icon("in")); self.b_back.setToolTip("Volver a la ventana de mapeo")
        self.b_copy.setIcon(icon("copy")); self.b_copy.setToolTip("Copia el snippet al portapapeles (bloqueado si hay errores)")
        self.b_save.setIcon(icon("save")); self.b_save.setToolTip("Guarda proyecto .json + snippet .py")
        self.b_open.setIcon(icon("open")); self.b_open.setToolTip("Abre un proyecto .json y re-renderiza")
        self.b_prev.setIcon(icon("play")); self.b_prev.setToolTip("Abre la ventana 3: vista previa")
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFontFamily("Consolas")
        self.preview.setMinimumHeight(220)
        root.addWidget(self.preview, 2)
        self.b_back.clicked.connect(lambda: (self.hide(), mapwin.show(), mapwin.raise_()))
        self.b_copy.clicked.connect(self.copy_snippet)
        self.b_save.clicked.connect(self.save_project)
        self.b_open.clicked.connect(self.open_project)
        self.b_prev.clicked.connect(self._open_prev)
        self.issues.itemClicked.connect(self._locate_issue)
        ctl.updated.connect(self.refresh)
        self.prev_win: PreviewWindow | None = None
        self._save_dlg = None
        self._open_dlg = None
        self.resize(900, 700)
        self.refresh()

    def _locate_issue(self, item) -> None:
        row = self.issues.row(item)
        if 0 <= row < len(self.ctl.issues):
            iss = self.ctl.issues[row]
            self.ctl.locate.emit(iss.side, tuple(iss.indices))

    def copy_snippet(self) -> None:
        block = self.ctl.blocked()
        if block:
            QMessageBox.warning(self, "Exportar bloqueado", block)
            return
        QApplication.clipboard().setText(self.ctl.snippet())

    def save_project(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        block = self.ctl.blocked()
        if block:
            QMessageBox.warning(self, "Exportar bloqueado", block)
            return
        if self._save_dlg is None:
            self._save_dlg = QFileDialog(self, "Guardar proyecto", "glyph_map.json",
                                          "Proyecto JSON (*.json)")
            self._save_dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            self._save_dlg.setFileMode(QFileDialog.FileMode.AnyFile)
            self._save_dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            self._save_dlg.fileSelected.connect(self._do_save)
        self._save_dlg.show()
        self._save_dlg.raise_()
        self._save_dlg.activateWindow()

    def _do_save(self, path: str) -> None:
        if not path:
            return
        proj = build_project(self.mapwin.left.edit.text(), self.mapwin.right.edit.text(),
                             [0], self.ctl.n_from, self.ctl.n_to,
                             self.ctl.model.to_glyph_map())
        Path(path).write_text(dumps_project(proj), encoding="utf-8")
        Path(path).with_suffix(".py").write_text(self.ctl.snippet(), encoding="utf-8")

    def open_project(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        if self._open_dlg is None:
            self._open_dlg = QFileDialog(self, "Abrir proyecto", "", "Proyecto JSON (*.json)")
            self._open_dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            self._open_dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
            self._open_dlg.fileSelected.connect(self._do_open)
        self._open_dlg.show()
        self._open_dlg.raise_()
        self._open_dlg.activateWindow()

    def _do_open(self, path: str) -> None:
        if not path:
            return
        try:
            proj = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Abrir proyecto", f"JSON invalido: {e}")
            return
        self.mapwin.open_project_dict(proj)
        self.mapwin.show()
        self.mapwin.raise_()

    def _open_prev(self) -> None:
        if self.prev_win is None:
            self.prev_win = PreviewWindow(self.ctl)
        self.prev_win.show()
        self.prev_win.raise_()

    def refresh(self) -> None:
        self.issues.clear()
        for iss in self.ctl.issues:
            self.issues.addItem(f"[{iss.level.upper()}] {iss.code}: {iss.message}")
        gm = self.ctl.model.to_glyph_map()
        self.info.setText(f"{len(gm)} conexiones | errores={len(self.ctl.errors())} "
                          f"avisos={len(self.ctl.warnings())}")
        self.preview.setPlainText(self.ctl.snippet())


class PreviewWindow(QMainWindow):
    """Ventana 3: resultado final."""

    def __init__(self, ctl: Controller):
        super().__init__()
        self.ctl = ctl
        self.setWindowTitle("MF Glyph Mapper — 3. Vista previa")
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        row = QHBoxLayout()
        self.b_gen = QPushButton("Generar vista previa")
        self.b_play = QPushButton("Reproducir/Pausar")
        self.b_mp4 = QPushButton("Abrir mp4")
        for b in (self.b_gen, self.b_play, self.b_mp4):
            row.addWidget(b)
        self.b_gen.setIcon(icon("video")); self.b_gen.setToolTip("Renderiza la transformación real con Manim (~10s)")
        self.b_play.setIcon(icon("play")); self.b_play.setToolTip("Reproducir / pausar el clip")
        self.b_mp4.setIcon(icon("open")); self.b_mp4.setToolTip("Abrir el mp4 en tu reproductor")
        root.addLayout(row)
        self.status = QLabel("Requiere mapa sin errores.")
        root.addWidget(self.status)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(QAudioOutput(self))
        self.video = QVideoWidget()
        self.video.setMinimumSize(640, 360)
        self.player.setVideoOutput(self.video)
        root.addWidget(self.video, 2)
        self.frame = QLabel("Fotograma final: —")
        self.frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.frame)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
        root.addWidget(self.log)
        self.b_gen.clicked.connect(self.generate)
        self.b_play.clicked.connect(self.toggle)
        self.b_mp4.clicked.connect(lambda: self._mp4 and QDesktopServices.openUrl(
            QUrl.fromLocalFile(self._mp4)))
        self._thread: QThread | None = None
        self._worker: PreviewWorker | None = None
        self._mp4: str | None = None
        self.resize(760, 720)

    def generate(self) -> None:
        block = self.ctl.blocked()
        if block:
            QMessageBox.warning(self, "Vista previa bloqueada", block)
            return
        self.b_gen.setEnabled(False)
        self.status.setText("Renderizando en proceso aparte (~10s)...")
        if self._thread is not None and self._thread.isRunning():
            self.status.setText("Vista previa en curso, espera a que termine...")
            self.b_gen.setEnabled(True)
            return
        self._thread = QThread()
        _track(self._thread, self._worker)
        self._worker = PreviewWorker({"latex_a": self.ctl.latex_a,
                                      "latex_b": self.ctl.latex_b,
                                      "glyph_map": self.ctl.model.to_glyph_map(),
                                      "quality": "l"})
        assert self._worker is not None and self._thread is not None
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self.on_done)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(lambda t=self._thread, w=self._worker: _untrack(t, w))
        self._thread.start()

    def on_done(self, payload: dict) -> None:
        self.b_gen.setEnabled(True)
        if not payload.get("ok"):
            self.status.setText("ERROR Manim: " + str(payload.get("error", ""))[:200])
            self.log.setPlainText(str(payload.get("error", "")) + "\n"
                                  + str(payload.get("log", ""))[-1500:])
            QMessageBox.warning(self, "Vista previa", str(payload.get("error", ""))[:1000])
            return
        self._mp4 = payload["mp4"]
        self.player.setSource(QUrl.fromLocalFile(payload["mp4"]))
        self.player.play()
        pm = QPixmap(payload["png"])
        if not pm.isNull():
            self.frame.setPixmap(pm.scaledToWidth(420, Qt.TransformationMode.SmoothTransformation))
        self.status.setText(f"Vista previa OK en {payload.get('seconds', '?')}s | "
                            f"{Path(payload['mp4']).name}")
        self.log.setPlainText(str(payload.get("log", ""))[-500:])

    def toggle(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self._mp4:
            self.player.play()

    def closeEvent(self, event) -> None:  # noqa: N802
        _stop_thread(self._thread, self._worker)
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    ctl = Controller()
    win = MapWindow(ctl)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
