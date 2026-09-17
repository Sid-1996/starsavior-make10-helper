"""設定對話框：平常不需要碰的東西全收在這裡。

- ROI：框選辨識區域、X/Y/W/H 微調、自動校正、ROI 預覽（含格線）
- 辨識矩陣：監控中的即時 10×15 棋盤（唯讀鏡像）
- 主視窗置頂偏好、UI 語言（切換立即生效）

主視窗只留狀態＋監控開關＋提示數；本對話框由 MainWindow 建立並接線，
邏輯（框選/對齊/預覽/儲存）仍住在 MainWindow，這裡只有排版。
切換語言時 MainWindow 呼叫 retranslate() 重設全部文字。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.i18n import PREF_AUTO, SUPPORTED_LANGUAGES, t
from gui.recognition_panel import RecognitionPanel, make_group_box

PREVIEW_MIN_SIZE = (450, 300)

# 下拉選單顯示（母語名稱，不翻譯；順序對應 _LANG_CODES）
_LANG_NAMES = ("自動（跟隨系統）", "繁體中文", "English", "日本語", "한국어")
_LANG_CODES = (PREF_AUTO, *SUPPORTED_LANGUAGES)


class SettingsDialog(QDialog):
    """設定對話框（子元件由 MainWindow 接線驅動）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.roi_group = QGroupBox()
        self.spin_x = self._make_spin()
        self.spin_y = self._make_spin()
        self.spin_w = self._make_spin(min_value=0)
        self.spin_h = self._make_spin(min_value=0)
        self._spin_labels = [QLabel("X:"), QLabel("Y:"), QLabel("Width:"), QLabel("Height:")]
        self.btn_select = QPushButton()
        self.btn_align = QPushButton()
        self.chk_topmost = QCheckBox()
        self.preview_group = QGroupBox()
        self.preview_label = QLabel()
        self.recognition_panel = RecognitionPanel()
        self.recognition_group = make_group_box(self.recognition_panel)
        self.language_label = QLabel()
        self.language_combo = QComboBox()
        self.language_combo.addItems(_LANG_NAMES)
        self.btn_close = QPushButton()
        self._build_layout()
        self.retranslate()

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)

        # ---- 辨識區域 ----
        roi_layout = QGridLayout(self.roi_group)
        for row, (label, spin) in enumerate(
            zip(self._spin_labels, (self.spin_x, self.spin_y, self.spin_w, self.spin_h))
        ):
            roi_layout.addWidget(label, row, 0)
            roi_layout.addWidget(spin, row, 1)
        btn_box = QVBoxLayout()
        for btn in (self.btn_select, self.btn_align):
            btn_box.addWidget(btn)
        btn_box.addWidget(self.chk_topmost)
        lang_row = QHBoxLayout()
        lang_row.addWidget(self.language_label)
        lang_row.addWidget(self.language_combo, 1)
        btn_box.addLayout(lang_row)
        roi_layout.addLayout(btn_box, 0, 2, 4, 1)
        root.addWidget(self.roi_group)

        # ---- 預覽 ----
        preview_layout = QVBoxLayout(self.preview_group)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(*PREVIEW_MIN_SIZE)
        self.preview_label.setStyleSheet("background-color: #202020;")
        preview_layout.addWidget(self.preview_label)
        root.addWidget(self.preview_group)

        # ---- 辨識結果 ----
        root.addWidget(self.recognition_group)

        # ---- 關閉 ----
        self.btn_close.clicked.connect(self.accept)
        root.addWidget(self.btn_close)

    def retranslate(self) -> None:
        """重設全部文字（建立時與語言切換時呼叫）。"""
        self.setWindowTitle(t("settings.title"))
        self.roi_group.setTitle(t("settings.roi_group"))
        self.btn_select.setText(t("settings.select"))
        self.btn_align.setText(t("settings.align"))
        self.btn_align.setToolTip(t("settings.align_tip"))
        self.chk_topmost.setText(t("settings.topmost"))
        self.chk_topmost.setToolTip(t("settings.topmost_tip"))
        self.preview_group.setTitle(t("settings.preview_group"))
        self.recognition_group.setTitle(t("panel.group"))
        self.recognition_panel.retranslate()
        self.language_label.setText(t("settings.language"))
        self.language_label.setToolTip(t("settings.language_tip"))
        self.language_combo.setToolTip(t("settings.language_tip"))
        for spin in (self.spin_x, self.spin_y, self.spin_w, self.spin_h):
            spin.setToolTip(t("settings.spin_tip"))
        self.btn_close.setText(t("settings.close"))

    def sync_language_combo(self, pref: str) -> None:
        """把目前語言偏好同步進下拉選單（不觸發訊號）。"""
        try:
            index = _LANG_CODES.index(pref)
        except ValueError:
            index = 0
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(index)
        self.language_combo.blockSignals(False)

    @staticmethod
    def language_code(index: int) -> str:
        """下拉選單索引 → 偏好碼（auto/zh/en/ja/ko）。"""
        if 0 <= index < len(_LANG_CODES):
            return _LANG_CODES[index]
        return PREF_AUTO

    @staticmethod
    def _make_spin(min_value: int = -100000) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_value, 100000)
        spin.setMaximumWidth(120)
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
