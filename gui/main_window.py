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
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core import board_align, game_window, screen_capture, window_capture
from core.board_builder import build_board_state
from core.game_window import WindowInfo
from core.grid import build_grid
from core.hint_selector import MAX_HINT_COUNT, select_hints
from core.monitor import BoardMonitor, MonitorConfig
from core.recognition import DigitRecognizer
from core.roi_model import GRID_COLS, GRID_ROWS, Roi, RoiFrac, rect_iou
from core.settings_store import SettingsStore
from core.solver import find_rectangles
from core.templates import TemplateStore
from core.window_capture import WindowCaptureSession
from gui.global_hotkey import GlobalHotkey
from gui.hint_overlay import HintOverlay, overlay_present
from gui.image_utils import qimage_to_gray
from gui.recognition_panel import RecognitionPanel
from gui.roi_selector import RoiSelectorDialog

_PREVIEW_MIN_SIZE = (450, 300)


class MainWindow(QMainWindow):
    def __init__(
        self,
        store: SettingsStore | None = None,
        parent=None,
        log_dir: Path | None = None,
        auto_repair: bool = True,
        auto_start: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Star Savior 10 消除提示器")
        self.setMinimumWidth(560)
        self._store = store if store is not None else SettingsStore()
        self._log_dir = (
            Path(log_dir)
            if log_dir is not None
            else Path(__file__).resolve().parent.parent / "debug"
        )
        self._monitor_ticks = 0
        self._monitor_note = ""
        self._roi: Roi | None = self._store.load_roi()
        self._roi_frac: RoiFrac | None = self._store.load_roi_frac()
        self._game: WindowInfo | None = None
        self._wgc: WindowCaptureSession | None = None
        self._last_win_rect: tuple[int, int, int, int] | None = None
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
        topmost = self._store.load_always_on_top()
        self.chk_topmost.blockSignals(True)
        self.chk_topmost.setChecked(topmost)
        self.chk_topmost.blockSignals(False)
        self._apply_topmost(topmost)
        self.spin_hints.blockSignals(True)
        self.spin_hints.setValue(self._store.load_max_hints())
        self.spin_hints.blockSignals(False)
        if not self._hotkey.start():
            self.btn_hide_hint.setToolTip(
                "隱藏 Overlay 提示（F8 全域快捷鍵註冊失敗，只能用此按鈕）。"
            )
        if auto_repair or auto_start:
            window_ok = self._bind_window()
        else:
            window_ok = False
        if auto_repair and window_ok:
            # 先解析（含舊格式遷移），再用後台幀驗證／吸附
            self._resolve_roi()
            self._auto_repair_roi()
        if auto_start and window_ok and self._resolve_roi():
            # 偏好都記住了：直接進監控，零點擊
            self._on_start_monitor()

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
        self.chk_topmost = QCheckBox("主視窗置頂")
        self.chk_topmost.setToolTip("單螢幕全螢幕遊戲時保持主視窗可操作；偏好會記住。")
        self.spin_hints = QSpinBox()
        self.spin_hints.setRange(1, MAX_HINT_COUNT)
        self.spin_hints.setToolTip("同時顯示幾組提示（首選＋備選）；偏好會記住。")
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
        btn_box.addWidget(self.chk_topmost)
        hints_row = QHBoxLayout()
        hints_row.addWidget(QLabel("同時提示數："))
        hints_row.addWidget(self.spin_hints)
        hints_row.addStretch(1)
        btn_box.addLayout(hints_row)
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
        self.btn_hide_hint.clicked.connect(self._on_hide_hint)
        self.btn_start.clicked.connect(self._on_start_monitor)
        self.btn_stop.clicked.connect(self._on_stop_monitor)
        self.chk_topmost.toggled.connect(self._on_topmost_toggled)
        self.spin_hints.valueChanged.connect(self._on_hints_count_changed)
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
            background, origin = self._selector_background()
            selector = RoiSelectorDialog(
                background, origin[0], origin[1], background.width(), background.height()
            )
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

    def _selector_background(self) -> tuple[object, tuple[int, int]]:
        """框選背景：後台遊戲幀優先（被蓋也能框）；否則前景全螢幕。

        回傳 (QImage, (left, top))；背景座標系＝回傳影像座標系。
        後台幀的座標系是遊戲客戶區，框選結果可直接換算成比例。
        """
        if self._game is not None:
            frame = window_capture.grab_one(self._game.hwnd, timeout_sec=3.0)
            if frame is not None:
                return self._bgr_to_qimage(frame), (self._game.left, self._game.top)
        if self._game is not None:
            game_window.bring_to_front(self._game.hwnd)
            time.sleep(0.3)
        left, top, width, height = screen_capture.get_virtual_screen_geometry()
        return screen_capture.capture_virtual_screen(), (left, top)

    @staticmethod
    def _bgr_to_qimage(bgr) -> object:
        """BGR numpy → QImage（複製 buffer，呼叫端可安全持有）。"""
        import cv2
        from PyQt6.QtGui import QImage

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        height, width, _ = rgb.shape
        return QImage(rgb.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()

    def _restore_main_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _apply_roi(self, roi: Roi) -> None:
        if self._monitor_timer.isActive():
            self._on_stop_monitor()  # ROI 變更時先停監控，避免用舊基準比對
        self._roi = roi
        self._store.save_roi(roi)
        if self._game is not None:
            # 視窗已知：同步存一份比例（之後搬窗／換解析度自動跟著走）
            try:
                frac = RoiFrac.from_absolute(
                    roi, self._game.left, self._game.top, self._game.width, self._game.height
                )
            except ValueError:
                frac = None
            if frac is not None and frac.is_valid():
                self._roi_frac = frac
                self._store.save_roi_frac(frac)
        self._sync_spinboxes()
        self._update_status()
        self._render_preview()

    # ------------------------------------------------------------------ #
    # 目標視窗綁定 + ROI 解析 + 偏好
    # ------------------------------------------------------------------ #
    def _bind_window(self) -> bool:
        """綁定遊戲視窗；找不到時狀態列說明原因並回傳 False。"""
        title = self._store.load_window_title()
        info = game_window.find_game_window(title)
        if info is None or not info.is_valid():
            self._game = None
            self.lbl_roi_status.setText(f"辨識區域：未綁定（找不到「{title}」視窗，請先開啟遊戲）")
            return False
        self._game = info
        self._last_win_rect = (info.left, info.top, info.width, info.height)
        return True

    def _resolve_roi(self) -> bool:
        """比例→絕對座標（＋舊格式遷移）；失敗回傳 False。"""
        if self._roi_frac is not None and self._roi_frac.is_valid() and self._game is not None:
            roi = self._roi_frac.to_absolute(
                self._game.left, self._game.top, self._game.width, self._game.height
            )
            if roi.is_valid():
                self._roi = roi
                self._sync_spinboxes()
                self._update_status()
                return True
            return False
        if self._game is not None:
            legacy = self._store.load_roi()
            if legacy is not None and legacy.is_valid():
                try:
                    frac = RoiFrac.from_absolute(
                        legacy,
                        self._game.left,
                        self._game.top,
                        self._game.width,
                        self._game.height,
                    )
                except ValueError:
                    frac = None
                if frac is not None and frac.is_valid():
                    self._roi_frac = frac
                    self._store.save_roi_frac(frac)
                    return self._resolve_roi()
        if self._roi is not None and self._roi.is_valid():
            return True  # 舊絕對座標沿用（僅供顯示；監控仍需綁定視窗）
        self.lbl_roi_status.setText("辨識區域：未設定（請框選辨識區域）")
        return False

    def _apply_topmost(self, enabled: bool) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)

    def _on_topmost_toggled(self, checked: bool) -> None:
        self._store.save_always_on_top(checked)
        self._apply_topmost(checked)
        self.show()  # flag 變更需重秀才生效

    def _on_hints_count_changed(self, value: int) -> None:
        self._store.save_max_hints(value)

    def _on_hide_hint(self) -> None:
        self._overlay_muted = True
        self._overlay.hide_hint()

    def _on_hotkey_toggle(self) -> None:
        """F8：監控總開關（開始／停止），只控制提示流程，不操作遊戲。"""
        if self._monitor_timer.isActive():
            self._on_stop_monitor()
        else:
            self._on_start_monitor()

    # ------------------------------------------------------------------ #
    # 自動校正
    # ------------------------------------------------------------------ #
    @staticmethod
    def _align_to_roi(gray, rect, origin) -> Roi | None:
        """在灰階圖上吸附棋盤並換算回螢幕座標；失敗回傳 None（不丟例外）。

        gray: 灰階影像；rect: 影像座標 (x, y, w, h) 粗框；origin: 影像原點的螢幕座標。
        """
        try:
            found = board_align.align_to_board(gray, rect, expand_ratio=0.0)
        except Exception:
            return None
        if found is None:
            return None
        roi = Roi(x=origin[0] + found[0], y=origin[1] + found[1], width=found[2], height=found[3])
        return roi if roi.is_valid() else None

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
        result = self._align_to_roi(gray, rect, (left, top))
        if result is None:
            QMessageBox.information(
                self,
                "自動校正",
                "無法偵測 10×15 棋盤位置。\n"
                "請確認遊戲畫面完整可見且辨識區域已大致框住棋盤後重試，"
                "或使用「重新框選」。",
            )
            return
        self._apply_roi(result)

    def _auto_repair_roi(self) -> None:
        """啟動時自動修復：用後台幀驗證比例 ROI，跑掉就地吸附並儲存。

        驗證＝在比例框內重跑對齊，結果≈原框（IoU>0.9）即正確；
        失配→放大範圍重找→尺寸合理才採用。
        無比例／無視窗／模板不全／抓不到幀／遊戲不在對戰畫面 → 沿用現狀並提示，不擋啟動。
        """
        if (
            self._roi_frac is None
            or not self._roi_frac.is_valid()
            or self._game is None
            or not self._templates.is_complete()
        ):
            return
        frame = window_capture.grab_one(self._game.hwnd, timeout_sec=2.0)
        if frame is None:
            return
        gray = window_capture.to_grayscale(frame)
        win = self._game
        frac = self._roi_frac
        frame_h, frame_w = gray.shape[:2]
        lx, ly = round(frac.x * frame_w), round(frac.y * frame_h)
        lw, lh = round(frac.width * frame_w), round(frac.height * frame_h)
        box = frac.to_absolute(win.left, win.top, win.width, win.height)
        check = self._align_to_roi(gray, (lx, ly, lw, lh), (win.left, win.top))
        if check is not None and rect_iou(check, box) > 0.9:
            return  # 對得上，無事發生
        # 放大範圍重找（±1/3，夾在幀內）
        ex0 = max(0, lx - lw // 3)
        ey0 = max(0, ly - lh // 3)
        ex1 = min(frame_w, lx + lw + lw // 3)
        ey1 = min(frame_h, ly + lh + lh // 3)
        found = self._align_to_roi(gray, (ex0, ey0, ex1 - ex0, ey1 - ey0), (win.left, win.top))
        if found is None:
            self._note_roi_status("（未在畫面上找到棋盤：若遊戲不在對戰畫面可忽略）")
            return
        if (
            abs(found.width - box.width) / box.width > 0.15
            or abs(found.height - box.height) / box.height > 0.15
        ):
            return  # 尺寸差太多：不敢認，沿用舊設定
        try:
            new_frac = RoiFrac.from_absolute(found, win.left, win.top, win.width, win.height)
        except ValueError:
            return
        if not new_frac.is_valid():
            return
        self._roi_frac = new_frac
        self._store.save_roi_frac(new_frac)
        self._roi = found
        self._sync_spinboxes()
        self._update_status()
        self._note_roi_status("（啟動時已自動對齊到新位置）")

    def _note_roi_status(self, suffix: str) -> None:
        """在狀態列追加一次性說明（下次 _update_status 會恢復正常文字）。"""
        self.lbl_roi_status.setText(self.lbl_roi_status.text() + suffix)

    # ------------------------------------------------------------------ #
    # 測試辨識（Phase 2）
    # ------------------------------------------------------------------ #
    def _grab_roi_bgr(self):
        """後台 ROI 的 BGR 影像；無視窗/無比例/抓不到幀回傳 None（呼叫端走前景備援）。"""
        if self._game is None or self._roi_frac is None or not self._roi_frac.is_valid():
            return None
        frame = window_capture.grab_one(self._game.hwnd, timeout_sec=3.0)
        if frame is None:
            return None
        height, width, _ = frame.shape
        frac = self._roi_frac
        x0 = max(0, min(round(frac.x * width), width))
        y0 = max(0, min(round(frac.y * height), height))
        x1 = max(0, min(x0 + round(frac.width * width), width))
        y1 = max(0, min(y0 + round(frac.height * height), height))
        if x1 <= x0 or y1 <= y0:
            return None
        return frame[y0:y1, x0:x1].copy()

    def _grab_roi_image(self) -> object:
        """ROI 彩色圖：後台幀按比例裁；無後台幀則 mss 前景。失敗丟例外。"""
        bgr = self._grab_roi_bgr()
        if bgr is not None:
            return self._bgr_to_qimage(bgr)
        if self._roi is None or not self._roi.is_valid():
            raise ValueError("未設定辨識區域")
        return screen_capture.capture_roi(self._roi)

    def _on_test_recognition(self) -> None:
        if self._roi is None or not self._roi.is_valid():
            QMessageBox.warning(self, "測試辨識", "請先設定辨識區域。")
            return
        # 後台幀不可能含 Overlay；前景備援才需先隱藏
        background = self._grab_roi_bgr()
        if background is None:
            self._overlay.hide_hint()
            QApplication.processEvents()
        try:
            if background is not None:
                gray = window_capture.to_grayscale(background)
            else:
                gray = qimage_to_gray(screen_capture.capture_roi(self._roi))
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
            hints = self._show_board_hints(board)
        except Exception:
            self.recognition_panel.show_message(
                self.recognition_panel._matrix_label.text()
                + "\n\n提示計算失敗：\n"
                + traceback.format_exc()
            )
            return
        if not hints:
            self.recognition_panel.show_message(
                self.recognition_panel._matrix_label.text() + "\n\n此盤面無合法矩形（總和=10）。"
            )
            return
        rect = hints[0].rectangle
        extra = f"（另有 {len(hints) - 1} 個備選）" if len(hints) > 1 else ""
        self.recognition_panel.show_message(
            self.recognition_panel._matrix_label.text()
            + f"\n\n已在 Overlay 顯示提示：({rect.row1},{rect.col1})→({rect.row2},{rect.col2})"
            f" area={rect.area}（共 {hints[0].candidate_count} 個候選）{extra}。"
            "可用「隱藏提示」關閉。"
        )

    def _hint_limit(self) -> int:
        """同時顯示的提示數量（使用者偏好，存檔記住）。"""
        return self._store.load_max_hints()

    def _show_board_hints(self, board) -> list:
        """對無 UNKNOWN 的棋盤計算前 N 個提示並顯示 Overlay；回傳 Hint 列。"""
        self._overlay_muted = False  # 使用者手動要求顯示，解除靜音
        hints = select_hints(find_rectangles(board), limit=self._hint_limit())
        if not hints or self._roi is None:
            return []
        self._overlay.show_hints([hint.rectangle for hint in hints], build_grid(self._roi))
        return hints

    # ------------------------------------------------------------------ #
    # 監控迴圈：畫面變化 → 等待穩定 → 乾淨重辨識 → Hint Lock
    # 抓圖雙管線：WGC 後台（被蓋也活，不含 Overlay）優先；不可用退回 mss 前景
    # ------------------------------------------------------------------ #
    def _on_start_monitor(self) -> None:
        if not self._bind_window():
            QMessageBox.warning(self, "開始監控", "找不到遊戲視窗，請先開啟遊戲。")
            return
        if not self._resolve_roi():
            QMessageBox.warning(self, "開始監控", "尚未設定辨識區域，請先框選。")
            return
        self._begin_session()

    def _begin_session(self) -> None:
        """建立監控狀態＋抓圖會話＋timer（綁定/解析已就緒時呼叫）。"""
        self._monitor = BoardMonitor()
        self._monitor_ticks = 0
        self._monitor_note = "啟動，等待穩定畫面"
        self._start_wgc()
        self._monitor_timer.start()
        self._update_monitor_status()
        self._update_status()
        self._monitor_log(f"start roi={self._roi} wgc={self._wgc is not None}")

    def _start_wgc(self) -> None:
        """啟動後台會話；失敗就維持 None（前景備援），不丟例外。"""
        self._stop_wgc()
        if self._game is None:
            return
        session = WindowCaptureSession(self._game.hwnd)
        if session.start():
            self._wgc = session
            self._monitor_log(f"wgc session hwnd={self._game.hwnd}")
        else:
            self._wgc = None
            self._monitor_note = "前景模式（遊戲需保持可見）"
            self._monitor_log("wgc unavailable, foreground fallback")

    def _stop_wgc(self) -> None:
        if self._wgc is not None:
            self._wgc.stop()
            self._wgc = None

    def _live_window(self) -> WindowInfo | None:
        """刷新遊戲客戶區（跟著移動走）；死了就試著重綁，否則 None。"""
        if self._game is None:
            return self._rebind_window()
        live = game_window.refresh_window(self._game.hwnd)
        if live is not None and live.is_valid():
            self._game = live
            return live
        return self._rebind_window()

    def _rebind_window(self) -> WindowInfo | None:
        info = game_window.find_game_window(self._store.load_window_title())
        if info is None or not info.is_valid():
            return None
        self._game = info
        self._last_win_rect = None  # 強制重定位 Overlay
        self._stop_wgc()
        if self._monitor is not None:
            self._start_wgc()
        if self._roi_frac is not None:
            self._resolve_roi()
        self._monitor_log(f"rebind window {info.left},{info.top},{info.width}x{info.height}")
        return info

    def _grab_roi_gray(self) -> object:
        """ROI 灰階：WGC 按比例裁；無 WGC 則 mss 前景絕對座標。失敗丟例外。"""
        if self._wgc is not None and self._roi_frac is not None and self._roi_frac.is_valid():
            latest = self._wgc.latest()
            assert latest is not None, "尚無後台幀"
            full = window_capture.to_grayscale(latest[0])
            height, width = full.shape[:2]
            frac = self._roi_frac
            x0 = max(0, min(round(frac.x * width), width))
            y0 = max(0, min(round(frac.y * height), height))
            x1 = max(0, min(x0 + round(frac.width * width), width))
            y1 = max(0, min(y0 + round(frac.height * height), height))
            if x1 <= x0 or y1 <= y0:
                raise ValueError("ROI 比例超出後台幀範圍")
            return full[y0:y1, x0:x1].copy()
        if self._roi is None or not self._roi.is_valid():
            raise ValueError("未設定辨識區域")
        return qimage_to_gray(screen_capture.capture_roi(self._roi))

    def _frame_is_stale(self) -> bool:
        """後台幀是否過舊（最小化/凍結時為 True；無 WGC 回傳 False）。"""
        if self._wgc is None or self._monitor is None:
            return False
        latest = self._wgc.latest()
        if latest is None:
            return True
        interval = self._monitor.config.frame_interval_ms / 1000
        return time.monotonic() - latest[1] > max(2.0, 3 * interval)

    def _refresh_rect_and_overlay(self, live: WindowInfo) -> None:
        """視窗移動/縮放時刷新絕對 ROI 並原地重定位 Overlay。"""
        rect = (live.left, live.top, live.width, live.height)
        if self._last_win_rect == rect:
            return
        self._last_win_rect = rect
        if self._roi_frac is not None and self._roi_frac.is_valid():
            roi = self._roi_frac.to_absolute(live.left, live.top, live.width, live.height)
            if roi.is_valid():
                self._roi = roi
                self._sync_spinboxes()
                self._update_status()
        if (
            self._monitor is not None
            and self._monitor.hints
            and self._roi is not None
            and not self._overlay_muted
        ):
            self._overlay.show_hints(
                [hint.rectangle for hint in self._monitor.hints], build_grid(self._roi)
            )

    def _on_stop_monitor(self) -> None:
        self._monitor_timer.stop()
        self._stop_wgc()
        self._monitor = None
        self._overlay_muted = False
        self._overlay.hide_hint()
        self.lbl_monitor.setText("監控狀態：停止")
        self._update_status()
        self._monitor_log("stop")

    def _monitor_log(self, message: str) -> None:
        """監控除錯日誌（debug/monitor.log，超過 1MB 自動輪替；失敗不影響監控）。"""
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            path = self._log_dir / "monitor.log"
            if path.exists() and path.stat().st_size > 1_000_000:
                path.unlink()
            with path.open("a", encoding="utf-8") as log_file:
                log_file.write(f"{datetime.now():%H:%M:%S} {message}\n")
        except OSError:
            pass

    def _update_monitor_status(self) -> None:
        tracker_run = self._monitor.tracker.run_length if self._monitor else 0
        required = self._monitor.config.stable_required if self._monitor else 0
        note = f" · {self._monitor_note}" if self._monitor_note else ""
        self.lbl_monitor.setText(
            f"監控狀態：監控中 #{self._monitor_ticks} 穩定{tracker_run}/{required}{note}"
        )

    def _capture_clean(self, shapes: list) -> object | None:
        """隱藏 Overlay 後擷取；殘留筆跡則重試（有上限，不無限等待）。

        shapes: 隱藏前的提示幾何列（空串列表示本來就沒顯示，無需驗證）。
        回傳彩色 QImage（呼叫端再轉灰階）；重試用盡回傳 None（呼叫端放棄本次重建，
        避免把污染幀餵給辨識器）；擷取失敗直接丟例外。
        """
        assert self._roi is not None
        assert self._monitor is not None
        config = self._monitor.config
        retries = 0
        while True:
            image = screen_capture.capture_roi(self._roi)
            polluted = any(
                overlay_present(image, shapes_one, self._roi, self._overlay.origin)
                for shapes_one in shapes
            )
            if not polluted:
                if retries:
                    self._monitor_log(f"clean capture ok after {retries} retries")
                return image
            retries += 1
            self._monitor_log(f"overlay residue detected, retry {retries}")
            if retries > config.max_clean_retries:
                self._monitor_log("clean retry exhausted, skip rebuild")
                return None
            time.sleep(config.settle_delay_sec)

    def _dump_frame(self, name: str, image) -> None:
        """把關鍵幀存到日誌目錄（除錯用；失敗不影響監控）。"""
        try:
            from PyQt6.QtGui import QImage

            path = str(self._log_dir / name)
            if isinstance(image, QImage):
                image.save(path)
            else:
                import cv2

                cv2.imwrite(path, image)
        except Exception:
            pass

    def _log_board_summary(self, board) -> None:
        """記錄重辨識結果摘要：三態計數 + UNKNOWN 格位（最多 20 格）。"""
        from core.board_state import CellState

        counts = board.counts()
        unknowns = [
            (cell.row, cell.column) for cell in board.cells if cell.state == CellState.UNKNOWN
        ][:20]
        self._monitor_log(
            f"board digit={counts[CellState.DIGIT]} "
            f"empty={counts[CellState.EMPTY]} unknown={counts[CellState.UNKNOWN]} "
            f"unknown_at={unknowns}"
        )

    def _on_monitor_tick(self) -> None:
        if self._monitor is None or self._roi is None or not self._roi.is_valid():
            return
        self._monitor_ticks += 1
        live = self._live_window()
        if live is None:
            self._on_stop_monitor()
            QMessageBox.critical(self, "監控失敗", "遊戲視窗已關閉，已停止監控。")
            return
        if game_window.is_minimized(live.hwnd):
            self._monitor_note = "等待遊戲視窗（最小化中）"
            self._update_monitor_status()
            return
        if self._wgc is not None:
            if self._wgc.closed:
                self._monitor_log("wgc closed, restart session")
                self._overlay.hide_hint()
                self._begin_session()
                return
            if self._frame_is_stale():
                self._monitor_note = "等待後台畫面更新…"
                self._update_monitor_status()
                return
        self._refresh_rect_and_overlay(live)
        try:
            frame = self._grab_roi_gray()
        except Exception:  # 擷取失敗就停下來讓使用者處理，不無聲空轉
            self._on_stop_monitor()
            QMessageBox.critical(
                self,
                "監控失敗",
                "擷取畫面時發生錯誤，已停止監控：\n" + traceback.format_exc(),
            )
            return
        if not self._monitor.note_frame(frame):
            self._update_monitor_status()
            return  # 無有效變化：保持目前 Hint（Hint Lock）
        ratio = self._monitor.tracker.last_ratio
        self._monitor_log(f"stable new frame tick={self._monitor_ticks} ratio={ratio:.4f}")
        self._dump_frame("last_stable.png", frame)
        self._monitor_note = "重辨識中…"
        self._update_monitor_status()
        if self._wgc is not None:
            # 後台幀不可能含本工具 Overlay：直接辨識，無需隱藏重試
            self._dump_frame("last_clean.png", frame)
            board = build_board_state(frame, self._roi, DigitRecognizer(self._templates))
        else:
            # 前景備援：隱藏 Overlay 後稍候，乾淨重辨識（框線不可入鏡）
            config = self._monitor.config
            shapes_before = self._overlay.current_shapes
            self._overlay.hide_hint()
            QApplication.processEvents()
            time.sleep(config.settle_delay_sec)
            try:
                color = self._capture_clean(shapes_before)
                if color is None:  # 殘留消不掉：放棄本次重建，等下次變化
                    self._monitor_note = "維持提示（Overlay 未消失，跳過本次）"
                    self._update_monitor_status()
                    self._restore_overlay()
                    try:
                        self._monitor.rebaseline(self._grab_roi_gray())
                    except Exception:
                        pass
                    return
                self._dump_frame("last_clean.png", color)
                board = build_board_state(
                    qimage_to_gray(color), self._roi, DigitRecognizer(self._templates)
                )
            except Exception:
                self._on_stop_monitor()
                QMessageBox.critical(
                    self,
                    "監控失敗",
                    "重新辨識時發生錯誤，已停止監控：\n" + traceback.format_exc(),
                )
                return
            self._restore_overlay()
        self._log_board_summary(board)
        snapshot = self._monitor.commit_board(board, max_hints=self._hint_limit())
        if snapshot.changed:
            self.recognition_panel.show_board(board, self._templates.missing())
            if not snapshot.hints or self._overlay_muted:
                if not self._overlay_muted:
                    self._overlay.hide_hint()
            else:
                assert self._roi is not None
                self._overlay.show_hints(
                    [hint.rectangle for hint in snapshot.hints], build_grid(self._roi)
                )
            first = snapshot.hints[0].rectangle if snapshot.hints else None
            self._monitor_note = (
                f"已更新提示 {first}（共 {len(snapshot.hints)} 組）" if first else "此盤無合法矩形"
            )
            self._monitor_log(f"hints updated count={len(snapshot.hints)} first={first}")
        elif board.has_unknown():
            self._monitor_note = "維持提示（UNKNOWN，等下次穩定畫面）"
            self._monitor_log("keep hint (UNKNOWN)")
        else:
            self._monitor_note = "維持提示（棋盤未變）"
        self._update_monitor_status()
        try:  # 吸收目前畫面（含 Overlay 像素），避免為自己的提示空轉
            self._monitor.rebaseline(self._grab_roi_gray())
        except Exception:
            pass

    def _restore_overlay(self) -> None:
        """把隱藏前的提示顯示回來（乾淨擷取後的過渡，避免畫面閃爍太久）。"""
        if (
            not self._overlay_muted
            and self._monitor is not None
            and self._monitor.hints
            and self._roi is not None
        ):
            self._overlay.show_hints(
                [hint.rectangle for hint in self._monitor.hints], build_grid(self._roi)
            )

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
            image = self._grab_roi_image()
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
