"""Inspector + conexiones (Fase 2). Modelo separado en mf_core.glyph_map_model."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Qt, QUrl, QRectF
from PySide6.QtGui import QPainterPath, QColor, QPen, QBrush, QWheelEvent, QShortcut, QKeySequence, QPixmap, QDesktopServices, QFont, QFontMetricsF, QPainter
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QGraphicsView, QGraphicsScene,
    QGraphicsPathItem, QGraphicsSimpleTextItem, QGraphicsItem, QLabel, QMessageBox,
    QListWidget, QGroupBox, QGraphicsLineItem, QTextEdit, QPlainTextEdit,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # src/ para mf_core al lanzar archivo directo
from mf_core.glyph_map_model import GlyphMapModel, Connection
from mf_core.validator import validate
from mf_core.exporter import build_snippet, build_project, project_to_glyph_map, dumps_project

WORKER = Path(__file__).resolve().parent.parent / "mf_core" / "glyph_worker.py"
PREVIEW_WORKER = Path(__file__).resolve().parent.parent / "mf_core" / "preview_worker.py"
SCALE = 120.0  # manim-units -> pixeles

# Hilos vivos: si la ventana se cierra con un render en curso, el hilo sigue
# hasta terminar en vez de destruirse a mitad (eso corrompia la pila: 0xC0000409).
import atexit as _atexit

_ACTIVE_THREADS: set = set()
_ACTIVE_WORKERS: set = set()


def _track(thread, worker) -> None:
    _ACTIVE_THREADS.add(thread)
    if worker is not None:
        _ACTIVE_WORKERS.add(worker)


def _untrack(thread, worker) -> None:
    _ACTIVE_THREADS.discard(thread)
    _ACTIVE_WORKERS.discard(worker)
    try:
        thread.deleteLater()
    except Exception:
        pass


def _shutdown_all() -> None:
    for w in list(_ACTIVE_WORKERS):
        try:
            w.cancel()
        except Exception:
            pass
    for t in list(_ACTIVE_THREADS):
        try:
            t.quit()
            t.wait(10000)
        except Exception:
            pass


_atexit.register(_shutdown_all)


def _stop_thread(thread, worker) -> None:
    """Cancela el subprocess y espera el hilo (cierre limpio)."""
    if thread is not None and thread.isRunning():
        try:
            if worker is not None:
                worker.cancel()
        except Exception:
            pass
        thread.quit()
        thread.wait(10000)


def glyph_path(points: list[list[float]]) -> QPainterPath:
    """Convierte points de Manim a QPainterPath. Y-flip.

    Cada grupo de 4 puntos es un bezier independiente (ancla, h1, h2, ancla).
    Si el inicio del grupo no coincide con el punto actual, es un salto de
    subpath (ej. las dos barras del "=") y se hace moveTo: asi no aparecen
    curvas colgando entre trazos.
    """
    path = QPainterPath()
    if not points:
        return path
    pts = [(p[0] * SCALE, -p[1] * SCALE) for p in points]
    cur = pts[0]
    path.moveTo(*cur)
    i = 0
    eps2 = 1e-9
    while i + 3 < len(pts):
        sx, sy = pts[i]
        dx, dy = sx - cur[0], sy - cur[1]
        if dx * dx + dy * dy > eps2:
            path.moveTo(sx, sy)
        path.cubicTo(*pts[i + 1], *pts[i + 2], *pts[i + 3])
        cur = pts[i + 3]
        i += 4
    return path


class _CancelableWorker(QObject):
    """Base: subprocess via Popen para poder cancelarlo al cerrar la ventana."""
    finished = Signal(dict)

    def __init__(self):
        super().__init__()
        self._proc: subprocess.Popen | None = None

    def _kill(self) -> None:
        p = self._proc
        if p is not None and p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass

    def cancel(self) -> None:
        self._kill()


class RenderWorker(_CancelableWorker):
    """Ejecuta el subprocess fuera del hilo UI. Se comunica por stdin (evita quoting Windows)."""

    def __init__(self, latex: str, path: list[int]):
        super().__init__()
        self.latex = latex
        self.path = path

    def run(self) -> None:
        try:
            req = json.dumps({"latex": self.latex, "path": self.path})
            self._proc = subprocess.Popen(
                [sys.executable, str(WORKER)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
            try:
                out, err = self._proc.communicate(input=req, timeout=180)
            except subprocess.TimeoutExpired:
                self._kill()
                out, err = self._proc.communicate()
                self.finished.emit({"ok": False, "error": "timeout de render (>180s)"})
                return
            out = (out or "").strip()
            if out:
                payload = json.loads(out.splitlines()[-1])
            else:
                payload = {"ok": False,
                           "error": f"worker sin stdout rc={self._proc.returncode}: {(err or '')[-2000:]}"}
        except Exception as e:  # noqa: BLE001 - error visible en UI
            payload = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        finally:
            self._proc = None
        self.finished.emit(payload)


class PreviewWorker(_CancelableWorker):
    """Renderiza la vista previa en proceso aparte (Manim real)."""

    def __init__(self, req: dict):
        super().__init__()
        self.req = req

    def run(self) -> None:
        try:
            self._proc = subprocess.Popen(
                [sys.executable, str(PREVIEW_WORKER)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
            try:
                out, _ = self._proc.communicate(input=json.dumps(self.req), timeout=300)
            except subprocess.TimeoutExpired:
                self._kill()
                self._proc.communicate()
                self.finished.emit({"ok": False, "error": "timeout de vista previa (>300s)"})
                return
            out = (out or "").strip()
            payload = json.loads(out.splitlines()[-1]) if out else {
                "ok": False, "error": f"preview sin stdout rc={self._proc.returncode}"}
        except Exception as e:  # noqa: BLE001
            payload = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        finally:
            self._proc = None
        self.finished.emit(payload)


class GlyphView(QGraphicsView):
    """Pan con arrastre + zoom con rueda."""
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class GlyphItem(QGraphicsPathItem):
    """Glifo seleccionable con indice real. Relleno + color por tipo."""
    COLORS = {
        "content": (QColor("#4c8dff"), QColor(76, 141, 255, 55)),
        "bar": (QColor("#f0a832"), QColor(240, 168, 50, 70)),
    }

    def __init__(self, idx: int, path: QPainterPath, type_name: str = ""):
        super().__init__(path)
        self.idx = idx
        self.kind = "bar" if type_name == "Rectangle" else "content"
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._apply_style(False)

    def _apply_style(self, selected: bool) -> None:
        pen_c, fill_c = self.COLORS[self.kind]
        if selected:
            self.setPen(QPen(QColor("#ff7b00"), 2.5))
            fill_c = QColor(fill_c)
            fill_c.setAlpha(min(140, fill_c.alpha() + 50))
        else:
            self.setPen(QPen(pen_c, 1.4))
        self.setBrush(QBrush(fill_c))

    def itemChange(self, change, value):  # resalta seleccion sin mutar en paint
        if change == QGraphicsPathItem.GraphicsItemChange.ItemSelectedChange:
            self._apply_style(bool(value))
        return super().itemChange(change, value)


class BadgeItem(QGraphicsItem):
    """Pastilla con el indice. type() = UserType+1 para localizarla en tests."""

    def __init__(self, text: str, accent: QColor):
        super().__init__()
        self.text = text
        self.accent = accent
        self.font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        fm = QFontMetricsF(self.font)
        w = fm.horizontalAdvance(text) + 16
        self._rect = QRectF(-w / 2, -11, w, 22)

    def boundingRect(self) -> QRectF:
        return self._rect

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor("#0f172a")))
        painter.setPen(QPen(self.accent, 1.6))
        painter.drawRoundedRect(self._rect, 11, 11)
        painter.setFont(self.font)
        painter.setPen(QPen(QColor("white")))
        painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self.text)


class GlyphPanel(QWidget):
    def __init__(self, title: str, default_latex: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{title}</b>  (path MF_Tools = [0])"))
        row = QHBoxLayout()
        self.edit = QLineEdit(default_latex)
        self.btn = QPushButton("Renderizar")
        row.addWidget(self.edit)
        row.addWidget(self.btn)
        layout.addLayout(row)
        self.status = QLabel("sin renderizar")
        layout.addWidget(self.status)
        legend = QLabel("<span style='color:#4c8dff'>●</span> contenido/símbolo &nbsp; "
                        "<span style='color:#f0a832'>●</span> barra (frac/sqrt) &nbsp; "
                        "<span style='color:#ff7b00'>●</span> seleccionado")
        legend.setStyleSheet("color:#8b93a5; font-size:11px;")
        layout.addWidget(legend)
        self.scene = QGraphicsScene()
        self.view = GlyphView(self.scene)
        layout.addWidget(self.view)
        self.btn.clicked.connect(self.render_async)
        self._thread: QThread | None = None
        self._worker: RenderWorker | None = None  # ref viva: evita GC del worker
        self._n: int = 0
        self._top: int = 1
        self._rendered: str = ""
        self._changed: callable | None = None  # callback (n_from/n_to cambiaron)
        self._edited_cb: callable | None = None  # callback (texto editado tras render)
        self.scene.selectionChanged.connect(self._on_sel)
        self.edit.textChanged.connect(self._on_text_changed)

    def render_async(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            self.status.setText("render en curso, espera a que termine...")
            return
        self.status.setText("renderizando en proceso aparte...")
        self.btn.setEnabled(False)
        self._thread = QThread()
        self._worker = RenderWorker(self.edit.text(), [0])
        assert self._worker is not None and self._thread is not None
        _track(self._thread, self._worker)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self.on_result)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(lambda t=self._thread, w=self._worker: _untrack(t, w))
        self._thread.start()

    def cancel(self) -> None:
        """Cancela un render en curso (cierre limpio)."""
        _stop_thread(self._thread, self._worker)

    def on_result(self, payload: dict) -> None:
        self.btn.setEnabled(True)
        if not payload.get("ok"):
            self.status.setText("ERROR LaTeX: " + str(payload.get("error"))[:300])
            QMessageBox.warning(self, "Error LaTeX", str(payload.get("error"))[:2000])
            return
        self.draw(payload)

    def draw(self, payload: dict) -> None:
        self.scene.clear()
        for g in payload["glyphs"]:
            item = GlyphItem(g["index"], glyph_path(g["points"]), g.get("type_name", ""))
            self.scene.addItem(item)
            # badge con el indice real en A=mob[0], sobre el glifo
            accent = GlyphItem.COLORS[item.kind][0]
            badge = BadgeItem(str(g["index"]), accent)
            c = g["center"]
            badge.setPos(c[0] * SCALE, -(c[1] + g.get("height", 0) / 2) * SCALE - 14)
            self.scene.addItem(badge)
        n = payload["resolved_len"]
        self._n = n
        self._top = payload.get("top_len", 1)
        self._rendered = payload.get("latex", "")
        warn = " | ".join(payload.get("warnings", []))
        self.status.setText(f"{n} glifos (indices 0..{n-1})" + (f" | AVISO: {warn}" if warn else ""))
        if self._changed is not None:
            self._changed()

    def get_selected(self) -> tuple[int, ...]:
        try:
            items = self.scene.selectedItems()
        except RuntimeError:  # teardown: C++ ya destruido
            return ()
        return tuple(sorted(i.idx for i in items if isinstance(i, GlyphItem)))

    def _on_text_changed(self) -> None:
        if self.edit.text() != self._rendered and self._edited_cb is not None:
            self._edited_cb()

    def _on_sel(self) -> None:
        sel = self.get_selected()
        base = str(self.status.text()).split(" | sel=")[0]
        self.status.setText(f"{base} | sel={list(sel)}")


class MapView(QGraphicsView):
    """Bipartito origen->destino. Click en linea = selecciona fila para eliminar."""

    def __init__(self, on_pick: callable):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._on_pick = on_pick
        self._scene.selectionChanged.connect(self._forward_pick)
        self.setMinimumHeight(140)

    def _forward_pick(self) -> None:
        for it in self._scene.selectedItems():
            if isinstance(it, QGraphicsLineItem):
                self._on_pick(it.data(0))

    def refresh(self, model: GlyphMapModel) -> None:
        sc = self.scene()
        assert sc is not None
        sc.clear()
        conns = model.connections
        for row, c in enumerate(conns):
            y = row * 22 + 12
            line = QGraphicsLineItem(30, y, 230, y)
            line.setPen(QPen(QColor("#1f6feb"), 2))
            line.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsSelectable, True)
            line.setData(0, row)
            sc.addItem(line)
            for txt, x in ((f"{list(c.from_indices)}", 4), (f"{list(c.to_indices)}", 236)):
                lab = QGraphicsSimpleTextItem(f"{txt} {c.kind[0]}")
                lab.setPos(x, y - 10)
                sc.addItem(lab)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class InspectorWindow(QMainWindow):
    """Fase 3: + validador, fades explicitos, STALE, issues localizadas. Clic izq selecciona, clic der 1->1 conecta; Ctrl = multiple; zoom rueda, pan arrastre."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MF Glyph Mapper — Fase 3 (validador)")
        self.model = GlyphMapModel()
        self._stale = False
        self._issues: list = []
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        top = QHBoxLayout()
        self.left = GlyphPanel("INICIAL (clic=origen, Ctrl=multiple)", r"x^2 + y=1")
        self.right = GlyphPanel("FINAL (clic con origen=conectar)", r"x^2 = 1-y")
        top.addWidget(self.left)
        top.addWidget(self.right)
        root.addLayout(top)
        self.left._changed = self._sync_model_size
        self.right._changed = self._sync_model_size
        self.left._edited_cb = self._mark_stale
        self.right._edited_cb = self._mark_stale
        # Click en destino con origen seleccionado crea conexion automaticamente
        self.right.scene.selectionChanged.connect(self._auto_connect)

        dock = QGroupBox("Conexiones (lineas clicables para eliminar)")
        dl = QVBoxLayout(dock)
        btns = QHBoxLayout()
        self.b_conn = QPushButton("Conectar sel. (N->M)")
        self.b_fade_out = QPushButton("Origen sin destino (fade out)")
        self.b_fade_in = QPushButton("Destino sin origen (fade in)")
        self.b_del = QPushButton("Eliminar")
        self.b_undo = QPushButton("Deshacer (Ctrl+Z)")
        self.b_redo = QPushButton("Rehacer (Ctrl+Y)")
        self.b_clear = QPushButton("Limpiar")
        for b in (self.b_conn, self.b_fade_out, self.b_fade_in, self.b_del,
                  self.b_undo, self.b_redo, self.b_clear):
            btns.addWidget(b)
        dl.addLayout(btns)
        mid = QHBoxLayout()
        self.lst = QListWidget()
        self.map = MapView(on_pick=self._pick_row)
        mid.addWidget(self.lst, 2)
        mid.addWidget(self.map, 3)
        dl.addLayout(mid)
        dl.addWidget(QLabel("<b>Validacion (clic en issue = localizar glifos):</b>"))
        self.issues = QListWidget()
        self.issues.setMinimumHeight(110)
        dl.addWidget(self.issues)
        self.info = QLabel("Sin conexiones. Renderiza ambos paneles primero.")
        dl.addWidget(self.info)
        root.addWidget(dock)

        exp = QGroupBox("Exportar (Fase 4: bloqueado si hay errores)")
        el = QVBoxLayout(exp)
        erow = QHBoxLayout()
        self.b_copy = QPushButton("Copiar snippet")
        self.b_save = QPushButton("Guardar proyecto (.json + .py)")
        self.b_open = QPushButton("Abrir proyecto (.json)")
        for b in (self.b_copy, self.b_save, self.b_open):
            erow.addWidget(b)
        el.addLayout(erow)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(130)
        self.preview.setFontFamily("Consolas")
        el.addWidget(self.preview)
        root.addWidget(exp)

        pv = QGroupBox("Vista previa (Fase 5: Manim real en proceso aparte)")
        pl = QVBoxLayout(pv)
        prow = QHBoxLayout()
        self.b_prev = QPushButton("Generar vista previa")
        self.b_play = QPushButton("Reproducir/Pausar")
        self.b_openmp4 = QPushButton("Abrir mp4")
        for b in (self.b_prev, self.b_play, self.b_openmp4):
            prow.addWidget(b)
        pl.addLayout(prow)
        self.pstatus = QLabel("Sin vista previa. Requiere mapa sin errores.")
        pl.addWidget(self.pstatus)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(QAudioOutput(self))
        self.video = QVideoWidget()
        self.video.setMinimumHeight(240)
        self.player.setVideoOutput(self.video)
        pl.addWidget(self.video)
        self.frame = QLabel("Fotograma final: —")
        self.frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(self.frame)
        self.plog = QPlainTextEdit()
        self.plog.setReadOnly(True)
        self.plog.setMaximumHeight(90)
        pl.addWidget(self.plog)
        root.addWidget(pv)
        self._prev_thread: QThread | None = None
        self._prev_worker: PreviewWorker | None = None
        self._save_dlg = None
        self._open_dlg = None
        self._mp4: str | None = None

        self.b_conn.clicked.connect(self.connect_selected)
        self.b_fade_out.clicked.connect(self.fade_out_selected)
        self.b_fade_in.clicked.connect(self.fade_in_selected)
        self.b_del.clicked.connect(self.delete_selected)
        self.b_undo.clicked.connect(self.do_undo)
        self.b_redo.clicked.connect(self.do_redo)
        self.b_clear.clicked.connect(self.do_clear)
        self.b_copy.clicked.connect(self.copy_snippet)
        self.b_save.clicked.connect(self.save_project)
        self.b_open.clicked.connect(self.open_project)
        self.b_prev.clicked.connect(self.generate_preview)
        self.b_play.clicked.connect(self.toggle_play)
        self.b_openmp4.clicked.connect(self.open_mp4)
        self.issues.itemClicked.connect(self._locate_issue)
        self.sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.sc_undo.activated.connect(self.do_undo)
        self.sc_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.sc_redo.activated.connect(self.do_redo)
        self.resize(1150, 950)

    def _mark_stale(self) -> None:
        if not self._stale:
            self._stale = True
            self.refresh()

    def _sync_model_size(self) -> None:
        before = len(self.model.connections)
        self.model.configure(self.left._n, self.right._n)
        pruned = before - len(self.model.connections)
        if (self.left.edit.text() == self.left._rendered
                and self.right.edit.text() == self.right._rendered):
            self._stale = False
        if getattr(self, "_pending", None) and self.model.n_from > 0 and self.model.n_to > 0:
            for f, t in self._pending:
                try:
                    self.model.add(f, t)
                except (ValueError, IndexError):
                    continue  # fuera de rango tras re-render: se descarta
            self._pending = None
        self.refresh()
        if pruned:
            self.info.setText(f"{self.info.text()} | {pruned} conexiones podadas (fuera de rango tras re-render).")

    def _clear_selections(self) -> None:
        """Toda accion exitosa consume ambas selecciones: evita pares rancios y duplicados."""
        self._suppress = True
        try:
            self.left.scene.clearSelection()
            self.right.scene.clearSelection()
        finally:
            self._suppress = False

    def _auto_connect(self) -> None:
        """Clic simple en destino (1 origen + 1 destino) conecta al instante. Multi (N->M) usa el boton Conectar."""
        if self._suppress or self.left._n == 0 or self.right._n == 0:
            return
        f, t = self.left.get_selected(), self.right.get_selected()
        if len(f) == 1 and len(t) == 1:
            try:
                self.model.add(f, t)
            except ValueError as e:  # duplicada: se ignora con aviso
                self.info.setText(str(e))
                return
            self._clear_selections()
            self.refresh()

    _suppress = False

    def connect_selected(self) -> None:
        f, t = self.left.get_selected(), self.right.get_selected()
        if not f or not t:
            self.info.setText("Selecciona al menos 1 glifo en cada panel (Ctrl=multiple).")
            return
        try:
            self.model.add(f, t)
        except (ValueError, IndexError) as e:
            self.info.setText(str(e))
            return
        self._clear_selections()
        self.refresh()

    def _pick_row(self, row: int) -> None:
        self.lst.setCurrentRow(row)

    def delete_selected(self) -> None:
        row = self.lst.currentRow()
        if 0 <= row < len(self.model.connections):
            self.model.remove(self.model.connections[row])
            self.refresh()

    def do_undo(self) -> None:
        self._suppress = True
        try:
            if not self.model.undo():
                self.info.setText("Nada que deshacer.")
        finally:
            self._suppress = False
        self.refresh()

    def do_redo(self) -> None:
        if not self.model.redo():
            self.info.setText("Nada que rehacer.")
        self.refresh()

    def do_clear(self) -> None:
        self.model.clear()
        self.refresh()

    def fade_out_selected(self) -> None:
        f = self.left.get_selected()
        if not f:
            self.info.setText("Selecciona glifos de origen para fade out.")
            return
        try:
            self.model.add(f, ())
        except (ValueError, IndexError) as e:
            self.info.setText(str(e))
            return
        self._clear_selections()
        self.refresh()

    def fade_in_selected(self) -> None:
        t = self.right.get_selected()
        if not t:
            self.info.setText("Selecciona glifos de destino para fade in.")
            return
        try:
            self.model.add((), t)
        except (ValueError, IndexError) as e:
            self.info.setText(str(e))
            return
        self._clear_selections()
        self.refresh()

    def _locate_issue(self, item) -> None:
        row = self.issues.row(item)
        if 0 <= row < len(self._issues):
            iss = self._issues[row]
            self._suppress = True
            try:
                for panel, side in ((self.left, "from"), (self.right, "to")):
                    if iss.side in (side, "both"):
                        panel.scene.clearSelection()
                        for g in panel.scene.items():
                            if isinstance(g, GlyphItem) and (
                                    not iss.indices or g.idx in iss.indices):
                                g.setSelected(True)
            finally:
                self._suppress = False

    def refresh(self) -> None:
        self.lst.clear()
        stale_mark = "⚠ STALE " if self._stale else ""
        for c in self.model.connections:
            self.lst.addItem(f"{stale_mark}{list(c.from_indices)} -> {list(c.to_indices)}  [{c.kind}]")
        self.map.refresh(self.model)
        gm = self.model.to_glyph_map()
        self._issues = validate(self.model.n_from, self.model.n_to, gm,
                                top_from=self.left._top, top_to=self.right._top,
                                path=(0,), stale=self._stale)
        self.issues.clear()
        for iss in self._issues:
            self.issues.addItem(f"[{iss.level.upper()}] {iss.code}: {iss.message}")
        errs = sum(1 for i in self._issues if i.level == "error")
        warns = sum(1 for i in self._issues if i.level == "warning")
        self.info.setText(f"{len(gm)} conexiones | errores={errs} avisos={warns} | glyph_map={gm}")
        self._refresh_preview()

    # ---- Fase 4: exportador ----
    def _current_snippet(self) -> str:
        return build_snippet(self.model.to_glyph_map())

    def _refresh_preview(self) -> None:
        if hasattr(self, "preview"):
            self.preview.setPlainText(self._current_snippet())

    def _export_blocked(self) -> str | None:
        errs = [i for i in self._issues if i.level == "error"]
        if self._stale or any(i.code == "STALE" for i in errs):
            return "Hay STALE pendiente: re-renderiza ambos paneles antes de exportar."
        if errs:
            return "Hay errores de validacion: " + "; ".join(i.code for i in errs)
        if self.model.n_from == 0 or self.model.n_to == 0:
            return "Renderiza ambos paneles primero."
        return None

    def copy_snippet(self) -> None:
        block = self._export_blocked()
        if block:
            QMessageBox.warning(self, "Exportar bloqueado", block)
            return
        QApplication.clipboard().setText(self._current_snippet())
        self.info.setText(self.info.text() + " | snippet copiado")

    def save_project(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        block = self._export_blocked()
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
        proj = build_project(self.left.edit.text(), self.right.edit.text(), [0],
                             self.model.n_from, self.model.n_to,
                             self.model.to_glyph_map())
        Path(path).write_text(dumps_project(proj), encoding="utf-8")
        Path(path).with_suffix(".py").write_text(self._current_snippet(), encoding="utf-8")
        self.info.setText(self.info.text() + f" | guardado {Path(path).name}")

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
        self.load_project(proj)

    # ---- Fase 5: vista previa ----
    def generate_preview(self) -> None:
        block = self._export_blocked()
        if block:
            QMessageBox.warning(self, "Vista previa bloqueada", block)
            return
        self.b_prev.setEnabled(False)
        self.pstatus.setText("Renderizando vista previa en proceso aparte (~10s)...")
        if self._prev_thread is not None and self._prev_thread.isRunning():
            self.pstatus.setText("Vista previa en curso, espera a que termine...")
            self.b_prev.setEnabled(True)
            return
        self._prev_thread = QThread()
        self._prev_worker = PreviewWorker({
            "latex_a": self.left.edit.text(), "latex_b": self.right.edit.text(),
            "glyph_map": self.model.to_glyph_map(), "quality": "l"})
        assert self._prev_worker is not None and self._prev_thread is not None
        _track(self._prev_thread, self._prev_worker)
        self._prev_worker.moveToThread(self._prev_thread)
        self._prev_thread.started.connect(self._prev_worker.run)
        self._prev_worker.finished.connect(self.on_preview)
        self._prev_worker.finished.connect(self._prev_thread.quit)
        self._prev_thread.finished.connect(lambda t=self._prev_thread, w=self._prev_worker: _untrack(t, w))
        self._prev_thread.start()

    def on_preview(self, payload: dict) -> None:
        self.b_prev.setEnabled(True)
        if not payload.get("ok"):
            self.pstatus.setText("ERROR Manim: " + str(payload.get("error", ""))[:200])
            self.plog.setPlainText(str(payload.get("error", "")) + "\n" + str(payload.get("log", ""))[-1500:])
            QMessageBox.warning(self, "Vista previa", str(payload.get("error", ""))[:1000])
            return
        self._mp4 = payload["mp4"]
        self.player.setSource(QUrl.fromLocalFile(payload["mp4"]))
        self.player.play()
        pm = QPixmap(payload["png"])
        if not pm.isNull():
            self.frame.setPixmap(pm.scaledToWidth(420, Qt.TransformationMode.SmoothTransformation))
        self.pstatus.setText(f"Vista previa OK en {payload.get('seconds', '?')}s | {Path(payload['mp4']).name}")
        self.plog.setPlainText(str(payload.get("log", ""))[-500:])

    def toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self._mp4:
            self.player.play()

    def open_mp4(self) -> None:
        if self._mp4:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._mp4))

    def load_project(self, proj: dict) -> None:
        """Reabre un proyecto: fija LaTeX, re-renderiza y aplica conexiones al sincronizar."""
        self.model.clear()
        self._pending = [(tuple(c.get("from", [])), tuple(c.get("to", [])))
                         for c in proj.get("connections", [])]
        self.left.edit.setText(proj.get("latex_a", ""))
        self.right.edit.setText(proj.get("latex_b", ""))
        self.left.render_async()
        self.right.render_async()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.left.cancel()
        self.right.cancel()
        _stop_thread(self._prev_thread, self._prev_worker)
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    try:
        from mf_ui.app import load_theme
        load_theme(app)
    except Exception:
        pass
    win = InspectorWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
