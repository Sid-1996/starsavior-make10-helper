"""透明 Click-through Overlay：顯示前 N 個推薦矩形的外框 + 起點 + 終點 + 編號。

- 透明、置頂、不接收滑鼠（WindowTransparentForInput）、不搶焦點
  （WindowDoesNotAcceptFocus + ShowWithoutActivating）、工作列無圖示（Tool）。
- 第 1 個是首選（亮綠粗框＋大圓點，照著打），第 2..N 個是備選
  （各用不同的高飽和色，細框＋小圓點）；每個框左上角有編號徽章
  （黑底白字 1..N），重疊時靠「顏色＋編號」雙重區分；不送出任何
  滑鼠事件、不操作遊戲。
- 座標沿用實體螢幕像素（與 ROI / Grid 同一座標系）；Overlay 佔滿整個
  虛擬桌面，繪製時再平移。
- Overlay 繪製層與 Screen Capture 必須分離：前景擷取前務必先隱藏 Overlay，
  否則框線會被截進去污染辨識（見 hide_hint，呼叫端在擷取前呼叫；
  後台幀不可能含 Overlay，無此問題）。

純幾何部分（hint_shapes）不依賴 Qt，可獨立測試。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from core.grid import CellGeometry
from core.hint_selector import MAX_HINT_COUNT
from core.solver import Rectangle

_PRIMARY_BORDER_WIDTH = 4
_PRIMARY_DOT_RADIUS = 7
_SECONDARY_BORDER_WIDTH = 2
_SECONDARY_DOT_RADIUS = 5
_BADGE_RADIUS = 12

# 提示調色盤：第 i 個提示用第 i 個顏色（0＝首選亮綠）。
# 全部是「亮＋高飽和」色：棋盤只有白/灰/黑，_is_overlay_pixel 永遠不會誤判。
_HINT_PALETTE: tuple[QColor, ...] = (
    QColor(0, 255, 0),  # 1 首選：亮綠
    QColor(0, 229, 255),  # 2 青
    QColor(255, 214, 0),  # 3 黃
    QColor(255, 61, 255),  # 4 洋紅
    QColor(255, 145, 0),  # 5 橘
    QColor(255, 70, 70),  # 6 紅
    QColor(77, 140, 255),  # 7 藍
    QColor(170, 110, 255),  # 8 紫
    QColor(255, 110, 180),  # 9 粉
    QColor(0, 255, 180),  # 10 碧綠
)
assert len(_HINT_PALETTE) == MAX_HINT_COUNT, "調色盤數量必須覆蓋 MAX_HINT_COUNT"

_PRIMARY_END_COLOR = QColor(0, 255, 255)  # 首選終點：青色圓點（維持舊外觀）


@dataclass(frozen=True)
class HintShapes:
    """實體螢幕像素座標：外框（左閉右開邊界）與起/終點（格子中心）。"""

    border: tuple[float, float, float, float]  # (x0, y0, x1, y1)
    start: tuple[float, float]  # 第一格 center（滑鼠按住點）
    end: tuple[float, float]  # 最後一格 center（滑鼠放開點）


def _is_overlay_pixel(color) -> bool:
    """是否為 Overlay 筆跡（調色盤任一色＋舊琥珀殘留；棋盤白/灰/黑不會命中）。

    通用規則：最亮通道 >= 200 且三通道極差 >= 100（亮＋高飽和）。
    白 tile（三通道皆亮但無飽和）、灰/黑（不夠亮）永遠不會命中。
    """
    brightest = max(color.red(), color.green(), color.blue())
    dimmest = min(color.red(), color.green(), color.blue())
    return brightest >= 200 and brightest - dimmest >= 100


def overlay_present(
    image,
    shapes: HintShapes,
    roi,
    overlay_origin: tuple[int, int] = (0, 0),
) -> bool:
    """檢查 ROI 截圖裡是否還殘留 Overlay 筆跡（乾淨重辨識前的驗證）。

    沿外框四邊中點 + 起終點共 6 個採樣點，找 Overlay 專用的亮色高飽和
    筆跡（遊戲棋盤本身只有白/灰/黑，不會有這種顏色）。
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
        if _is_overlay_pixel(color):
            hits += 1
    return hits >= 2


def paint_hint(
    painter: QPainter,
    border: tuple[float, float, float, float],
    start: tuple[float, float],
    end: tuple[float, float],
    index: int = 0,
) -> None:
    """把外框 + 起終點 + 編號徽章畫到任意 QPainter（widget 座標）；供測試直接打到 QImage。

    index=0 是首選（亮綠粗框大圓點），index>=1 是備選（調色盤色細框小圓點）。
    徽章數字 = index + 1（1-based，人類視角）。
    """
    x0, y0, x1, y1 = border
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    main_color = _HINT_PALETTE[index % len(_HINT_PALETTE)]
    if index == 0:
        end_color = _PRIMARY_END_COLOR
        border_width = _PRIMARY_BORDER_WIDTH
        dot_radius = _PRIMARY_DOT_RADIUS
    else:
        end_color = main_color
        border_width = _SECONDARY_BORDER_WIDTH
        dot_radius = _SECONDARY_DOT_RADIUS
    # 外框：只描邊不填充（brush 必須每次重設 NoBrush，否則圓點的實心 brush
    # 會洩漏到下一個框的 drawRect造成填滿蓋字）；黑襯線打底確保白色 tile 可見
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for color, width in (
        (QColor(0, 0, 0, 220), border_width + 3),
        (main_color, border_width),
    ):
        pen = QPen(color)
        pen.setWidth(width)
        painter.setPen(pen)
        painter.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))
    # 起點 / 終點：黑圈襯底 + 實心圓點
    for point, color in ((start, main_color), (end, end_color)):
        painter.setPen(QPen(QColor(0, 0, 0, 220), 2))
        painter.drawEllipse(
            QRectF(
                point[0] - dot_radius - 1,
                point[1] - dot_radius - 1,
                2 * (dot_radius + 1),
                2 * (dot_radius + 1),
            )
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(
            QRectF(
                point[0] - dot_radius,
                point[1] - dot_radius,
                2 * dot_radius,
                2 * dot_radius,
            )
        )
    # 編號徽章：左上角黑底圓＋調色盤填色＋白字（重疊時靠顏色＋編號區分）
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 220))
    painter.drawEllipse(
        QRectF(x0 - _BADGE_RADIUS - 1, y0 - _BADGE_RADIUS - 1, 2 * (_BADGE_RADIUS + 1), 2 * (_BADGE_RADIUS + 1))
    )
    painter.setBrush(main_color)
    painter.drawEllipse(QRectF(x0 - _BADGE_RADIUS, y0 - _BADGE_RADIUS, 2 * _BADGE_RADIUS, 2 * _BADGE_RADIUS))
    painter.setPen(QColor(255, 255, 255))
    painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
    painter.drawText(
        QRectF(x0 - _BADGE_RADIUS, y0 - _BADGE_RADIUS, 2 * _BADGE_RADIUS, 2 * _BADGE_RADIUS),
        Qt.AlignmentFlag.AlignCenter,
        str(index + 1),
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
        self._shapes: list[HintShapes] = []

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
    def current_shapes(self) -> list[HintShapes]:
        return list(self._shapes)

    @property
    def origin(self) -> tuple[int, int]:
        """虛擬桌面原點（繪製座標 = 螢幕座標 - 原點）。"""
        return self._origin

    def show_hints(
        self, rectangles: Sequence[Rectangle], geometries: Sequence[CellGeometry]
    ) -> None:
        """顯示前 N 個推薦（第 1 個是首選；會自動顯示視窗；不搶焦點）。"""
        self._shapes = [hint_shapes(rect, geometries) for rect in rectangles]
        self.update()
        if self._shapes:
            self.show()
        else:
            self.hide()

    def show_hint(self, rectangle: Rectangle, geometries: Sequence[CellGeometry]) -> None:
        """顯示單一推薦矩形（show_hints 的特例）。"""
        self.show_hints([rectangle], geometries)

    def hide_hint(self) -> None:
        """隱藏提示（前景擷取前必須先呼叫，避免污染辨識）。"""
        self._shapes = []
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
        if not self._shapes:
            return
        painter = QPainter(self)
        # 備選先畫，首選最後畫（壓在上層）；index 決定顏色＋徽章編號
        for index, shapes in enumerate(self._shapes[1:], start=1):
            border, start, end = self._to_local(shapes)
            paint_hint(painter, border, start, end, index=index)
        border, start, end = self._to_local(self._shapes[0])
        paint_hint(painter, border, start, end, index=0)
