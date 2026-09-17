"""透明 Click-through Overlay：只顯示矩形外框 + 起點 + 終點。

- 透明、置頂、不接收滑鼠（WindowTransparentForInput）、不搶焦點
  （WindowDoesNotAcceptFocus + ShowWithoutActivating）、工作列無圖示（Tool）。
- 一次只顯示一個推薦矩形；不顯示文字、不送出任何滑鼠事件、不操作遊戲。
- 座標沿用實體螢幕像素（與 ROI / Grid 同一座標系）；Overlay 佔滿整個
  虛擬桌面，繪製時再平移。
- Overlay 繪製層與 Screen Capture 必須分離：擷取前務必先隱藏 Overlay，
  否則框線會被截進去污染辨識（見 hide_hint，呼叫端在擷取前呼叫）。

純幾何部分（hint_shapes）不依賴 Qt，可獨立測試。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from core.grid import CellGeometry
from core.solver import Rectangle

_BORDER_WIDTH = 3
_DOT_RADIUS = 7


@dataclass(frozen=True)
class HintShapes:
    """實體螢幕像素座標：外框（左閉右開邊界）與起/終點（格子中心）。"""

    border: tuple[float, float, float, float]  # (x0, y0, x1, y1)
    start: tuple[float, float]  # 第一格 center（滑鼠按住點）
    end: tuple[float, float]  # 最後一格 center（滑鼠放開點）


def overlay_present(
    image,
    shapes: HintShapes,
    roi,
    overlay_origin: tuple[int, int] = (0, 0),
) -> bool:
    """檢查 ROI 截圖裡是否還殘留 Overlay 筆跡（乾淨重辨識前的驗證）。

    沿外框四邊中點 + 起終點共 6 個採樣點，找 Overlay 專用的亮綠/亮青
    （G>=200 且 G-R>=120；遊戲棋盤本身只有白/灰/黑，不會有這種顏色）。
    至少 2 點命中才算存在，避免抗鋸齒邊緣誤判。image 為 ROI 裁圖。
    """
    if not isinstance(image, QImage) or image.isNull():
        return False
    x0, y0, x1, y1 = shapes.border
    points = [
        ((x0 + x1) / 2, y0),
        ((x0 + x1) / 2, y1),
        (x0, (y0 + y1) / 2),
        (x1, (y0 + y1) / 2),
        shapes.start,
        shapes.end,
    ]
    hits = 0
    for sx, sy in points:
        px = round(sx - overlay_origin[0] - roi.x)
        py = round(sy - overlay_origin[1] - roi.y)
        if not 0 <= px < image.width() or not 0 <= py < image.height():
            continue
        color = image.pixelColor(px, py)
        if color.green() >= 200 and color.green() - color.red() >= 120:
            hits += 1
    return hits >= 2


def paint_hint(
    painter: QPainter,
    border: tuple[float, float, float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    """把外框 + 起終點畫到任意 QPainter（widget 座標）；供測試直接打到 QImage。"""
    x0, y0, x1, y1 = border
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    # 外框：先畫黑底襯線確保在白色 tile 上可見，再畫亮綠主線
    for color, width in (
        (QColor(0, 0, 0, 220), _BORDER_WIDTH + 3),
        (QColor(0, 255, 0, 255), _BORDER_WIDTH),
    ):
        pen = QPen(color)
        pen.setWidth(width)
        painter.setPen(pen)
        painter.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))
    # 起點（綠）/ 終點（青）：黑圈襯底 + 實心圓點
    for point, color in ((start, QColor(0, 255, 0, 255)), (end, QColor(0, 255, 255, 255))):
        painter.setPen(QPen(QColor(0, 0, 0, 220), 2))
        painter.drawEllipse(
            QRectF(
                point[0] - _DOT_RADIUS - 1,
                point[1] - _DOT_RADIUS - 1,
                2 * (_DOT_RADIUS + 1),
                2 * (_DOT_RADIUS + 1),
            )
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(
            QRectF(
                point[0] - _DOT_RADIUS,
                point[1] - _DOT_RADIUS,
                2 * _DOT_RADIUS,
                2 * _DOT_RADIUS,
            )
        )


def hint_shapes(rectangle: Rectangle, geometries: Sequence[CellGeometry]) -> HintShapes:
    """由矩形兩端格子算出外框與起終點；缺角格時丟 ValueError。"""
    by_pos = {(geometry.row, geometry.column): geometry for geometry in geometries}
    try:
        first = by_pos[(rectangle.row1, rectangle.col1)]
        last = by_pos[(rectangle.row2, rectangle.col2)]
    except KeyError as exc:
        raise ValueError(f"Grid 缺少矩形角落格：{exc}") from exc
    return HintShapes(
        border=(
            min(first.x, last.x),
            min(first.y, last.y),
            max(first.x1, last.x1),
            max(first.y1, last.y1),
        ),
        start=(first.center_x, first.center_y),
        end=(last.center_x, last.center_y),
    )


class HintOverlay(QWidget):
    """全螢幕透明提示層。"""

    def __init__(
        self,
        desktop: tuple[int, int, int, int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        if desktop is None:
            desktop = self._virtual_geometry()
        self._origin = (desktop[0], desktop[1])
        self.setGeometry(*desktop)
        self._shapes: HintShapes | None = None

    @staticmethod
    def _virtual_geometry() -> tuple[int, int, int, int]:
        geometries = [screen.geometry() for screen in QApplication.screens()]
        if not geometries:
            return (0, 0, 800, 600)
        left = min(geometry.left() for geometry in geometries)
        top = min(geometry.top() for geometry in geometries)
        right = max(geometry.right() + 1 for geometry in geometries)
        bottom = max(geometry.bottom() + 1 for geometry in geometries)
        return (left, top, right - left, bottom - top)

    @property
    def current_shapes(self) -> HintShapes | None:
        return self._shapes

    @property
    def origin(self) -> tuple[int, int]:
        """虛擬桌面原點（繪製座標 = 螢幕座標 - 原點）。"""
        return self._origin

    def show_hint(self, rectangle: Rectangle, geometries: Sequence[CellGeometry]) -> None:
        """顯示推薦矩形（會自動顯示視窗；不搶焦點）。"""
        self._shapes = hint_shapes(rectangle, geometries)
        self.update()
        self.show()

    def hide_hint(self) -> None:
        """隱藏提示（擷取螢幕前必須先呼叫，避免污染辨識）。"""
        self._shapes = None
        self.hide()

    def _to_local(
        self, shapes: HintShapes
    ) -> tuple[tuple[float, float, float, float], tuple[float, float], tuple[float, float]]:
        ox, oy = self._origin
        x0, y0, x1, y1 = shapes.border
        sx, sy = shapes.start
        ex, ey = shapes.end
        return ((x0 - ox, y0 - oy, x1 - ox, y1 - oy), (sx - ox, sy - oy), (ex - ox, ey - oy))

    def paintEvent(self, event) -> None:
        if self._shapes is None:
            return
        border, start, end = self._to_local(self._shapes)
        paint_hint(QPainter(self), border, start, end)
