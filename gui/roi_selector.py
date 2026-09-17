"""全螢幕 ROI 框選視窗（Phase 1）。

行為：
- 顯示凍結的螢幕截圖作為背景
- 按住滑鼠左鍵拖曳：即時顯示選取框與 X/Y/Width/Height
- 任意方向拖曳皆可（自動正規化）
- 放開後自動對齊 10×15 棋盤（A 鍵切換自動對齊）
- 確認階段顯示 10×15 格線預覽
- Enter（或雙擊）確認 / Esc 取消 / 重新拖曳可重選
- 選取框座標限制在虛擬桌面範圍內（安全處理螢幕邊界）
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen
from PyQt6.QtWidgets import QDialog

from core.board_align import align_to_board
from core.roi_model import GRID_COLS, GRID_ROWS, Roi
from gui.image_utils import qimage_to_gray

_HINT_IDLE = "按住滑鼠左鍵拖曳，框選 10 × 15 棋盤辨識區域（Esc 取消）"
_HINT_DRAG = "X: {x}  Y: {y}  W: {w}  H: {h}"
_HINT_ALIGNED = "✓ 已自動對齊 10×15 棋盤 — Enter／雙擊確認　Esc 取消　拖曳重選　A 切換自動對齊"
_HINT_NOT_ALIGNED = (
    "⚠ 自動對齊失敗，使用原始選取 — Enter／雙擊確認　Esc 取消　拖曳重選　A 切換自動對齊"
)
_HINT_ALIGN_OFF = "自動對齊：關 — Enter／雙擊確認　Esc 取消　拖曳重選　A 切換自動對齊"


class RoiSelectorDialog(QDialog):
    """凍結畫面上的全螢幕矩形選取器。"""

    def __init__(
        self,
        background: QImage,
        screen_left: int,
        screen_top: int,
        screen_width: int,
        screen_height: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setModal(True)
        self._screen_left = screen_left
        self._screen_top = screen_top
        self._bg = background
        # 預先轉灰階，放開滑鼠時即可直接做自動對齊
        self._bg_gray = qimage_to_gray(background)
        self._drag_origin: QPoint | None = None
        self._drag_current: QPoint | None = None
        self._pending_rect: QRect | None = None  # 放開後等待確認的選取框
        self._raw_pending_rect: QRect | None = None  # 自動對齊前的原始選取
        self._auto_align = True
        self._align_status: str | None = None  # "ok" / "failed" / "off"
        self._confirmed: Roi | None = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(screen_left, screen_top, screen_width, screen_height)

    @property
    def roi(self) -> Roi | None:
        """確認後的 ROI（實體螢幕座標）；未確認時為 None。"""
        return self._confirmed

    # ------------------------------------------------------------------ #
    # 滑鼠 / 鍵盤事件
    # ------------------------------------------------------------------ #
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.position().toPoint()
            self._drag_current = self._drag_origin
            self._pending_rect = None
            self.update()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_origin is not None:
            self._drag_current = event.position().toPoint()
            self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_origin is not None:
            rect = self._normalized_rect()
            self._drag_origin = None
            self._drag_current = None
            if rect is not None and rect.width() > 0 and rect.height() > 0:
                self._raw_pending_rect = QRect(rect)
                self._pending_rect = self._maybe_align(rect)
            self.update()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._pending_rect is not None:
            self._confirm()
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._pending_rect is not None:
                self._confirm()
            else:
                event.accept()
        elif key == Qt.Key.Key_Escape:
            self.reject()
        elif key == Qt.Key.Key_A:
            # 切換自動對齊，並以原始選取重新計算
            self._auto_align = not self._auto_align
            if self._raw_pending_rect is not None:
                self._pending_rect = self._maybe_align(self._raw_pending_rect)
            self.update()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------ #
    # 繪製
    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.drawImage(self.rect(), self._bg)

        if self._drag_origin is not None:
            rect = self._normalized_rect()
        else:
            rect = self._pending_rect

        if rect is not None and rect.width() > 0 and rect.height() > 0:
            painter.fillRect(rect, QColor(0, 220, 0, 40))
            pen = QPen(QColor(0, 230, 0), 3)
            painter.setPen(pen)
            painter.drawRect(rect)
            # 確認階段顯示 10×15 格線，協助檢查對齊結果
            if self._pending_rect is not None:
                self._draw_grid(painter, rect)

        if self._drag_origin is not None and rect is not None:
            text = _HINT_DRAG.format(
                x=self._screen_left + rect.x(),
                y=self._screen_top + rect.y(),
                w=rect.width(),
                h=rect.height(),
            )
        elif self._pending_rect is not None:
            if self._align_status == "ok":
                text = _HINT_ALIGNED
            elif self._align_status == "failed":
                text = _HINT_NOT_ALIGNED
            else:
                text = _HINT_ALIGN_OFF
        else:
            text = _HINT_IDLE
        self._draw_hint(painter, text)

    def _draw_grid(self, painter: QPainter, rect: QRect) -> None:
        pen = QPen(QColor(140, 255, 140, 120), 1)
        painter.setPen(pen)
        cw = rect.width() / GRID_COLS
        ch = rect.height() / GRID_ROWS
        for i in range(1, GRID_COLS):
            x = rect.x() + round(i * cw)
            painter.drawLine(x, rect.top() + 2, x, rect.bottom() - 2)
        for j in range(1, GRID_ROWS):
            y = rect.y() + round(j * ch)
            painter.drawLine(rect.left() + 2, y, rect.right() - 2, y)

    def _draw_hint(self, painter: QPainter, text: str) -> None:
        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_rect = metrics.boundingRect(text)
        margin = 12
        x = (self.width() - text_rect.width()) // 2
        y = margin + text_rect.height()
        bg = QRect(
            x - margin,
            y - text_rect.height() - 6,
            text_rect.width() + margin * 2,
            text_rect.height() + 12,
        )
        painter.fillRect(bg, QColor(0, 0, 0, 170))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QPoint(x, y), text)

    # ------------------------------------------------------------------ #
    # 內部邏輯
    # ------------------------------------------------------------------ #
    def _maybe_align(self, rect: QRect) -> QRect:
        """嘗試將選取框吸附到實際 10×15 棋盤；失敗時退回原始選取。"""
        if not self._auto_align:
            self._align_status = "off"
            return rect
        result = align_to_board(
            self._bg_gray,
            (rect.x(), rect.y(), rect.width(), rect.height()),
        )
        if result is None:
            self._align_status = "failed"
            return rect
        self._align_status = "ok"
        ax, ay, aw, ah = result
        snapped = QRect(ax, ay, aw, ah).intersected(self.rect())
        if snapped.width() <= 0 or snapped.height() <= 0:
            self._align_status = "failed"
            return rect
        return snapped

    def _normalized_rect(self) -> QRect | None:
        """將拖曳中（任意方向）的兩點正規化為 QRect，並限制在視窗範圍內。"""
        if self._drag_origin is None or self._drag_current is None:
            return None
        return QRect(self._drag_origin, self._drag_current).normalized().intersected(self.rect())

    def _confirm(self) -> None:
        rect = self._pending_rect
        if rect is None:
            return
        self._confirmed = Roi(
            x=self._screen_left + rect.x(),
            y=self._screen_top + rect.y(),
            width=rect.width(),
            height=rect.height(),
        )
        self.accept()
