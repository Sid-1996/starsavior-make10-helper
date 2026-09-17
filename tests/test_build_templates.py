"""build_templates 迴歸測試：輸入是全螢幕截圖時，必須先裁 ROI 再切格。

曾經的 bug：直接把全圖餵給 cut_cells（它要吃 ROI 原點的畫面），
導致切錯位置、存下空白面板當模板，全板辨識率歸零。
"""

import cv2
import numpy as np
import pytest

from core.roi_model import Roi
from tools.build_templates import build_templates_from_labels


def _canvas_with_mark(tmp_path, roi: Roi, mark: tuple[int, int]) -> object:
    """300x200 畫布，ROI 內指定格塗白(200)，其餘維持 60；回傳截圖路徑。"""
    canvas = np.full((200, 300), 60, dtype=np.uint8)
    row, column = mark
    cell_w = roi.width / 15
    cell_h = roi.height / 10
    x0 = int(round(roi.x + column * cell_w))
    x1 = int(round(roi.x + (column + 1) * cell_w))
    y0 = int(round(roi.y + row * cell_h))
    y1 = int(round(roi.y + (row + 1) * cell_h))
    canvas[y0:y1, x0:x1] = 200
    path = tmp_path / "screen.png"
    assert cv2.imwrite(str(path), canvas)
    return path


class TestBuildTemplatesFromLabels:
    def test_full_screenshot_crops_roi_first(self, tmp_path):
        roi = Roi(x=50, y=30, width=150, height=100)
        shot = _canvas_with_mark(tmp_path, roi, mark=(2, 3))
        templates_dir = tmp_path / "templates"
        saved = build_templates_from_labels(shot, {(2, 3): 5}, roi, templates_dir)
        assert saved == [templates_dir / "5.png"]
        template = cv2.imread(str(saved[0]), cv2.IMREAD_GRAYSCALE)
        # 切對位置才會是白格；切錯會是底色 60
        assert float(template.mean()) > 150

    def test_roi_outside_screenshot_raises(self, tmp_path):
        roi = Roi(x=5000, y=5000, width=150, height=100)
        shot = _canvas_with_mark(tmp_path, Roi(x=50, y=30, width=150, height=100), mark=(0, 0))
        with pytest.raises(ValueError):
            build_templates_from_labels(shot, {(0, 0): 1}, roi, tmp_path / "templates")

    def test_bad_label_rejected(self, tmp_path):
        roi = Roi(x=50, y=30, width=150, height=100)
        shot = _canvas_with_mark(tmp_path, roi, mark=(0, 0))
        with pytest.raises(ValueError):
            build_templates_from_labels(shot, {(10, 0): 1}, roi, tmp_path / "templates")
        with pytest.raises(ValueError):
            build_templates_from_labels(shot, {(0, 0): 10}, roi, tmp_path / "templates")
