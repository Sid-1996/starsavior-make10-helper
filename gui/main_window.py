"""主視窗：ROI 設定、辨識預覽與狀態顯示（Phase 1 + Phase 2）。

Phase 1：
- 框選辨識區域（全螢幕選取器）
- X / Y / Width / Height 手動微調
- 設定儲存 / 載入
- ROI 預覽（含 10x15 格線輔助對齊）

Phase 2：
- ROI 固定切成 10x15（grid.build_grid）
- Cell 三態（board_state.CellState）+ BoardState
- Template Matching（recognition.DigitRecognizer，模板來自 TemplateStore）
- 「測試辨識」：擷取 ROI → 建立 BoardState → GUI 顯示 10x15 辨識矩陣

「開始監控 / 停止監控」為 Phase 6+ 功能，
目前僅保留 disabled 按鈕佔位，明確標示尚未實作。
"""

from __future__ import annotations

import time
import traceback

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core import board_align, screen_capture
from core.board_builder import build_board_state
from core.grid import build_grid
from core.hint_selector import Hint, select_hint
from core.monitor import BoardMonitor, MonitorConfig
from core.recognition import DigitRecognizer
from core.roi_model import GRID_COLS, GRID_ROWS, Roi
from core.settings_store import SettingsStore
from core.solver import find_rectangles
from core.templates import TemplateStore
from gui.global_hotkey import GlobalHotkey
from gui.hint_overlay import HintOverlay
from gui.image_utils import qimage_to_gray
from gui.recognition_panel import RecognitionPanel
from gui.roi_selector import RoiSelectorDialog

_PREVIEW_MIN_SIZE = (450, 300)


class MainWindow(QMainWindow):
    def __init__(self, store: SettingsStore | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Star Savior 10 消除提示器")
        self.setMinimumWidth(560)
        self._store = store if store is not None else SettingsStore()
        self._roi: Roi | None = self._store.load_roi()
        self._templates = TemplateStore().load_all()
        self._overlay = HintOverlay()
        self._overlay_muted = False  # F8 隱藏後，監控迴圈不再自動顯示
        self._hotkey = GlobalHotkey(self._on_hotkey_toggle)
        self._monitor: BoardMonitor | None = None
        self._monitor_timer = QTimer(self)
        self._monitor_timer.setInterval(MonitorConfig.frame_interval_ms)
        self._monitor_timer.timeout.connect(self._on_monitor_tick)
        self._build_ui()
        self._sync_spinboxes()
        self._update_status()
        if not self._hotkey.start():
            self.btn_hide_hint.setToolTip(
                "隱藏 Overlay 提示（F8 全域快捷鍵註冊失敗，只能用此按鈕）。"
            )

    # ------------------------------------------------------------------ #
    # UI 建構
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ---- 辨識區域群組 ----
        roi_group = QGroupBox("辨識區域 (ROI)")
        roi_layout = QGridLayout(roi_group)

        self.spin_x = self._make_spin()
        self.spin_y = self._make_spin()
        self.spin_w = self._make_spin(min_value=0)
        self.spin_h = self._make_spin(min_value=0)
        for row, (name, spin) in enumerate(
            (
                ("X:", self.spin_x),
                ("Y:", self.spin_y),
                ("Width:", self.spin_w),
                ("Height:", self.spin_h),
            )
        ):
            roi_layout.addWidget(QLabel(name), row, 0)
            roi_layout.addWidget(spin, row, 1)

        btn_box = QVBoxLayout()
        self.btn_select = QPushButton("框選辨識區域")
        self.btn_reselect = QPushButton("重新框選")
        self.btn_align = QPushButton("自動校正")
        self.btn_test = QPushButton("測試辨識")
        self.btn_hide_hint = QPushButton("隱藏提示")
        self.btn_hide_hint.setToolTip(
            "隱藏 Overlay 提示（Overlay 本身不接收滑鼠，只能在這裡關；F8 也可切換）。"
        )
        self.btn_start = QPushButton("開始監控")
        self.btn_stop = QPushButton("停止監控")
        self.btn_align.setToolTip(
            "以即時畫面偵測 10×15 棋盤位置，自動微調目前的辨識區域。\n"
            "使用時請確保遊戲畫面完整可見、未被遮擋。"
        )
        self.btn_test.setToolTip("擷取目前 ROI 並跑一次辨識，在下方顯示 10×15 結果。")
        self.btn_start.setToolTip("開始監控：畫面變化 → 等待穩定 → 重新辨識 → 更新提示。")
        self.btn_stop.setToolTip("停止監控並隱藏提示。")
        for btn in (
            self.btn_select,
            self.btn_reselect,
            self.btn_align,
            self.btn_test,
            self.btn_hide_hint,
            self.btn_start,
            self.btn_stop,
        ):
            btn_box.addWidget(btn)
        roi_layout.addLayout(btn_box, 0, 2, 4, 1)
        root.addWidget(roi_group)

        # ---- 預覽 ----
        preview_group = QGroupBox("ROI 預覽（含 10 × 15 格線）")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("尚未設定辨識區域")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(*_PREVIEW_MIN_SIZE)
        self.preview_label.setStyleSheet("background-color: #202020;")
        preview_layout.addWidget(self.preview_label)
        root.addWidget(preview_group)

        # ---- 辨識結果預覽 ----
        from gui.recognition_panel import make_group_box

        self.recognition_panel = RecognitionPanel()
        root.addWidget(make_group_box(self.recognition_panel))

        # ---- 狀態群組 ----
        status_group = QGroupBox("狀態")
        status_layout = QVBoxLayout(status_group)
        self.lbl_roi_status = QLabel("辨識區域：未設定")
        self.lbl_board_size = QLabel(f"棋盤尺寸：{GRID_ROWS} × {GRID_COLS}")
        self.lbl_cell_size = QLabel("Cell 大小：-")
        self.lbl_monitor = QLabel("監控狀態：停止")
        for lbl in (
            self.lbl_roi_status,
            self.lbl_board_size,
            self.lbl_cell_size,
            self.lbl_monitor,
        ):
            status_layout.addWidget(lbl)
        root.addWidget(status_group)

        # ---- 訊號 ----
        self.btn_select.clicked.connect(self._on_select_roi)
        self.btn_reselect.clicked.connect(self._on_select_roi)
        self.btn_align.clicked.connect(self._on_auto_align)
        self.btn_test.clicked.connect(self._on_test_recognition)
        self.btn_hide_hint.clicked.connect(self._overlay.hide_hint)
        self.btn_start.clicked.connect(self._on_start_monitor)
        self.btn_stop.clicked.connect(self._on_stop_monitor)
        self.spin_x.valueChanged.connect(self._on_spin_changed)
        self.spin_y.valueChanged.connect(self._on_spin_changed)
        self.spin_w.valueChanged.connect(self._on_spin_changed)
        self.spin_h.valueChanged.connect(self._on_spin_changed)

    def _make_spin(self, min_value: int = -100000) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_value, 100000)
        spin.setToolTip("可直接輸入數值微調，也可用上下鍵調整")
        return spin

    # ------------------------------------------------------------------ #
    # ROI 框選流程
    # ------------------------------------------------------------------ #
    def _on_select_roi(self) -> None:
        # 先隱藏主視窗，避免被截進選取背景
        self.hide()
        QApplication.processEvents()
        time.sleep(0.2)
        try:
            left, top, width, height = screen_capture.get_virtual_screen_geometry()
            background = screen_capture.capture_virtual_screen()
            selector = RoiSelectorDialog(background, left, top, width, height)
        except Exception:  # 框選流程任何錯誤都以對話框呈現，避免程式直接中止
            self._restore_main_window()
            QMessageBox.critical(
                self,
                "框選失敗",
                "建立框選介面時發生錯誤：\n" + traceback.format_exc(),
            )
            return

        result = selector.exec()
        self._restore_main_window()

        if result and selector.roi is not None:
            self._apply_roi(selector.roi)

    def _restore_main_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _apply_roi(self, roi: Roi) -> None:
        if self._monitor_timer.isActive():
            self._on_stop_monitor()  # ROI 變更時先停監控，避免用舊基準比對
        self._roi = roi
        self._store.save_roi(roi)
        self._sync_spinboxes()
        self._update_status()
        self._render_preview()

    # ------------------------------------------------------------------ #
    # 自動校正
    # ------------------------------------------------------------------ #
    def _on_auto_align(self) -> None:
        """以即時畫面偵測 10×15 棋盤，微調目前的 ROI。"""
        if self._roi is None or not self._roi.is_valid():
            return
        # 向外擴張 30% 擷取搜尋範圍（允許吸附到比目前 ROI 略大的棋盤）
        margin_x = int(round(self._roi.width * 0.3))
        margin_y = int(round(self._roi.height * 0.3))
        vl, vt, vw, vh = screen_capture.get_virtual_screen_geometry()
        left = max(self._roi.x - margin_x, vl)
        top = max(self._roi.y - margin_y, vt)
        right = min(self._roi.x + self._roi.width + margin_x, vl + vw)
        bottom = min(self._roi.y + self._roi.height + margin_y, vt + vh)
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            QMessageBox.warning(self, "自動校正", "目前的辨識區域不在螢幕範圍內。")
            return
        try:
            image = screen_capture.capture_region(left, top, width, height)
            gray = qimage_to_gray(image)
        except Exception:  # 擷取或轉換失敗時以對話框呈現，避免程式直接中止
            QMessageBox.critical(
                self,
                "自動校正失敗",
                "擷取或處理畫面時發生錯誤：\n" + traceback.format_exc(),
            )
            return
        rect = (self._roi.x - left, self._roi.y - top, self._roi.width, self._roi.height)
        result = board_align.align_to_board(gray, rect, expand_ratio=0.0)
        if result is None:
            QMessageBox.information(
                self,
                "自動校正",
                "無法偵測 10×15 棋盤位置。\n"
                "請確認遊戲畫面完整可見且辨識區域已大致框住棋盤後重試，"
                "或使用「重新框選」。",
            )
            return
        ax, ay, aw, ah = result
        self._apply_roi(Roi(x=left + ax, y=top + ay, width=aw, height=ah))

    # ------------------------------------------------------------------ #
    # 測試辨識（Phase 2）
    # ------------------------------------------------------------------ #
    def _on_test_recognition(self) -> None:
        if self._roi is None or not self._roi.is_valid():
            QMessageBox.warning(self, "測試辨識", "請先設定辨識區域。")
            return
        # 擷取前先隱藏 Overlay：不能把自己的提示框一起截進去污染辨識
        self._overlay.hide_hint()
        QApplication.processEvents()
        try:
            image = screen_capture.capture_roi(self._roi)
            gray = qimage_to_gray(image)
        except Exception:  # 擷取或轉換失敗時以對話框呈現，避免程式直接中止
            QMessageBox.critical(
                self,
                "測試辨識失敗",
                "擷取或處理畫面時發生錯誤：\n" + traceback.format_exc(),
            )
            return
        try:
            recognizer = DigitRecognizer(self._templates)
            board = build_board_state(gray, self._roi, recognizer)
        except Exception:
            self.recognition_panel.show_message("辨識過程發生錯誤：\n" + traceback.format_exc())
            return
        self.recognition_panel.show_board(board, self._templates.missing())
        if board.has_unknown():
            self.recognition_panel.show_message(
                self.recognition_panel._matrix_label.text()
                + "\n\n※ 含 UNKNOWN：第一版不產生新的提示，可重新截圖/重新辨識。"
            )
            return
        try:
            hint = self._show_board_hint(board)
        except Exception:
            self.recognition_panel.show_message(
                self.recognition_panel._matrix_label.text()
                + "\n\n提示計算失敗：\n"
                + traceback.format_exc()
            )
            return
        if hint is None:
            self.recognition_panel.show_message(
                self.recognition_panel._matrix_label.text() + "\n\n此盤面無合法矩形（總和=10）。"
            )
            return
        rect = hint.rectangle
        self.recognition_panel.show_message(
            self.recognition_panel._matrix_label.text()
            + f"\n\n已在 Overlay 顯示提示：({rect.row1},{rect.col1})→({rect.row2},{rect.col2})"
            f" area={rect.area}（共 {hint.candidate_count} 個候選）。"
            "可用「隱藏提示」關閉。"
        )

    def _on_hotkey_toggle(self) -> None:
        """F8：有提示時切換 Overlay 顯示/隱藏（只控制顯示，不操作遊戲）。"""
        state = self._overlay.toggle_display()
        if state is not None:
            self._overlay_muted = not state

    def _show_board_hint(self, board):
        """對無 UNKNOWN 的棋盤計算提示並顯示 Overlay；回傳 Hint（供測試直接呼叫）。"""
        self._overlay_muted = False  # 使用者手動要求顯示，解除 F8 靜音
        hint: Hint | None = select_hint(find_rectangles(board))
        if hint is None or self._roi is None:
            return None
        self._overlay.show_hint(hint.rectangle, build_grid(self._roi))
        return hint

    # ------------------------------------------------------------------ #
    # 監控迴圈（Phase 6）：畫面變化 → 等待穩定 → 乾淨重辨識 → Hint Lock
    # ------------------------------------------------------------------ #
    def _on_start_monitor(self) -> None:
        if self._roi is None or not self._roi.is_valid():
            QMessageBox.warning(self, "開始監控", "請先設定辨識區域。")
            return
        self._monitor = BoardMonitor()
        self._monitor_timer.start()
        self.lbl_monitor.setText("監控狀態：監控中")
        self._update_status()

    def _on_stop_monitor(self) -> None:
        self._monitor_timer.stop()
        self._monitor = None
        self._overlay_muted = False
        self._overlay.hide_hint()
        self.lbl_monitor.setText("監控狀態：停止")
        self._update_status()

    def _on_monitor_tick(self) -> None:
        if self._monitor is None or self._roi is None or not self._roi.is_valid():
            return
        try:
            frame = qimage_to_gray(screen_capture.capture_roi(self._roi))
        except Exception:  # 擷取失敗就停下來讓使用者處理，不無聲空轉
            self._on_stop_monitor()
            QMessageBox.critical(
                self,
                "監控失敗",
                "擷取畫面時發生錯誤，已停止監控：\n" + traceback.format_exc(),
            )
            return
        if not self._monitor.note_frame(frame):
            return  # 無有效變化：保持目前 Hint（Hint Lock）
        # 穩定新畫面 → 隱藏 Overlay 後稍候，乾淨重辨識（框線不可入鏡）
        config = self._monitor.config
        self._overlay.hide_hint()
        QApplication.processEvents()
        time.sleep(config.settle_delay_sec)
        try:
            clean = qimage_to_gray(screen_capture.capture_roi(self._roi))
            board = build_board_state(clean, self._roi, DigitRecognizer(self._templates))
        except Exception:
            self._on_stop_monitor()
            QMessageBox.critical(
                self,
                "監控失敗",
                "重新辨識時發生錯誤，已停止監控：\n" + traceback.format_exc(),
            )
            return
        self._restore_overlay()
        snapshot = self._monitor.commit_board(board)
        if snapshot.changed:
            self.recognition_panel.show_board(board, self._templates.missing())
            if snapshot.hint is None or self._overlay_muted:
                if not self._overlay_muted:
                    self._overlay.hide_hint()
            else:
                assert self._roi is not None
                self._overlay.show_hint(snapshot.hint.rectangle, build_grid(self._roi))
        try:  # 吸收目前畫面（含 Overlay 像素），避免為自己的提示空轉
            self._monitor.rebaseline(qimage_to_gray(screen_capture.capture_roi(self._roi)))
        except Exception:
            pass

    def _restore_overlay(self) -> None:
        """把隱藏前的提示顯示回來（乾淨擷取後的過渡，避免畫面閃爍太久）。"""
        if (
            not self._overlay_muted
            and self._monitor is not None
            and self._monitor.hint is not None
            and self._roi is not None
        ):
            self._overlay.show_hint(self._monitor.hint.rectangle, build_grid(self._roi))

    def closeEvent(self, event) -> None:
        self._hotkey.stop()
        self._on_stop_monitor()
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    # 手動微調
    # ------------------------------------------------------------------ #
    def _on_spin_changed(self) -> None:
        roi = Roi(
            x=self.spin_x.value(),
            y=self.spin_y.value(),
            width=self.spin_w.value(),
            height=self.spin_h.value(),
        )
        if roi.is_valid():
            self._roi = roi
            self._store.save_roi(roi)
        else:
            self._roi = None
        self._update_status()
        self._render_preview()

    def _sync_spinboxes(self) -> None:
        spins = (
            (self.spin_x, self._roi.x if self._roi else 0),
            (self.spin_y, self._roi.y if self._roi else 0),
            (self.spin_w, self._roi.width if self._roi else 0),
            (self.spin_h, self._roi.height if self._roi else 0),
        )
        for spin, value in spins:
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)

    # ------------------------------------------------------------------ #
    # 狀態與預覽
    # ------------------------------------------------------------------ #
    def _update_status(self) -> None:
        monitoring = self._monitor_timer.isActive()
        if self._roi is not None and self._roi.is_valid():
            r = self._roi
            self.lbl_roi_status.setText(
                f"辨識區域：已設定 (X={r.x}, Y={r.y}, W={r.width}, H={r.height})"
            )
            cell = r.cell_size()
            assert cell is not None
            self.lbl_cell_size.setText(f"Cell 大小：{cell[0]:.1f} × {cell[1]:.1f} px")
            self.btn_align.setEnabled(True)
            self.btn_test.setEnabled(True)
            self.btn_start.setEnabled(not monitoring)
        else:
            self.lbl_roi_status.setText("辨識區域：未設定")
            self.lbl_cell_size.setText("Cell 大小：-")
            self.btn_align.setEnabled(False)
            self.btn_test.setEnabled(False)
            self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(monitoring)

    def _render_preview(self) -> None:
        if self._roi is None or not self._roi.is_valid():
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("尚未設定辨識區域")
            return
        try:
            image = screen_capture.capture_roi(self._roi)
        except Exception as exc:  # ROI 落在螢幕外或擷取環境異常時不中斷 UI
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(f"預覽失敗：{exc}")
            return

        painter = QPainter(image)
        pen = QPen(QColor(0, 220, 0, 200))
        pen.setWidth(1)
        painter.setPen(pen)
        cell_w = self._roi.width / GRID_COLS
        cell_h = self._roi.height / GRID_ROWS
        for i in range(1, GRID_COLS):
            x = round(i * cell_w)
            painter.drawLine(x, 0, x, image.height() - 1)
        for j in range(1, GRID_ROWS):
            y = round(j * cell_h)
            painter.drawLine(0, y, image.width() - 1, y)
        painter.end()

        pixmap = QPixmap.fromImage(image).scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(pixmap)
