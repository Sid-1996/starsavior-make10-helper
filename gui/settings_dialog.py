"""設定對話框：平常不需要碰的東西全收在這裡。

- ROI：框選辨識區域、X/Y/W/H 微調、自動校正、ROI 預覽（含格線）
- 辨識矩陣：監控中的即時 10×15 棋盤（唯讀鏡像）
- 主視窗置頂偏好

主視窗只留狀態＋監控開關＋提示數；本對話框由 MainWindow 建立並接線，
邏輯（框選/對齊/預覽/儲存）仍住在 MainWindow，這裡只有排版。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.recognition_panel import RecognitionPanel, make_group_box

PREVIEW_MIN_SIZE = (450, 300)


class SettingsDialog(QDialog):
    """設定對話框（子元件由 MainWindow 接線驅動）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("設定")
        root = QVBoxLayout(self)

        # ---- 辨識區域 ----
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
        self.btn_align = QPushButton("自動校正")
        self.btn_align.setToolTip(
            "以即時畫面偵測 10×15 棋盤位置，自動微調目前的辨識區域。\n"
            "使用時請確保遊戲畫面完整可見、未被遮擋。"
        )
        for btn in (self.btn_select, self.btn_align):
            btn_box.addWidget(btn)
        self.chk_topmost = QCheckBox("主視窗置頂")
        self.chk_topmost.setToolTip("單螢幕全螢幕遊戲時保持主視窗可操作；偏好會記住。")
        btn_box.addWidget(self.chk_topmost)
        roi_layout.addLayout(btn_box, 0, 2, 4, 1)
        root.addWidget(roi_group)

        # ---- 預覽 ----
        preview_group = QGroupBox("ROI 預覽（含 10 × 15 格線）")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("尚未設定辨識區域")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(*PREVIEW_MIN_SIZE)
        self.preview_label.setStyleSheet("background-color: #202020;")
        preview_layout.addWidget(self.preview_label)
        root.addWidget(preview_group)

        # ---- 辨識結果 ----
        self.recognition_panel = RecognitionPanel()
        root.addWidget(make_group_box(self.recognition_panel))

        # ---- 關閉 ----
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _make_spin(min_value: int = -100000) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_value, 100000)
        spin.setMaximumWidth(120)
        spin.setToolTip("可直接輸入數值微調，也可用上下鍵調整")
        return spin

    def sync_spinboxes(self, values: tuple[int, int, int, int]) -> None:
        """MainWindow 呼叫：把目前 ROI 同步進微調欄（不觸發訊號）。"""
        for spin, value in (
            (self.spin_x, values[0]),
            (self.spin_y, values[1]),
            (self.spin_w, values[2]),
            (self.spin_h, values[3]),
        ):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
