"""模板建立工具：從實際遊戲畫面裁切 cell 並存成/更新模板。

用途（Phase 2 模板機制）：
- 從 debug/ 或使用者指定的遊戲截圖 + 已知 ROI，按 10x15 固定切割
- 互動式（或批次）指定每個 cell 的 digit，把該 cell 存成 templates/{digit}.png
- 之後 DigitRecognizer 就能用真實模板比對，不再回 UNKNOWN

這個工具自己不玩遊戲、不操作滑鼠；digit 標註由使用者提供。
一般使用者不需要每次啟動都跑這個；模板建好後存在 templates/ 即可。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.board_builder import cut_cells  # noqa: E402
from core.roi_model import Roi  # noqa: E402
from core.settings_store import SettingsStore  # noqa: E402
from core.templates import TemplateStore  # noqa: E402


def build_templates_from_labels(
    screenshot_path: Path,
    labels: dict[tuple[int, int], int],
    roi: Roi,
    templates_dir: Path,
) -> list[Path]:
    """依 (row, column) -> digit 的標註，從截圖切 cell 並存成模板。"""
    image = cv2.imread(str(screenshot_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"讀不到截圖：{screenshot_path}")
    # screenshot 是全螢幕截圖：先裁出 ROI 再切格。
    # cut_cells 吃的是「ROI 原點」的畫面，直接餵全圖會切錯位置。
    height, width = image.shape[:2]
    x0 = max(0, min(roi.x, width))
    y0 = max(0, min(roi.y, height))
    x1 = max(0, min(roi.x + roi.width, width))
    y1 = max(0, min(roi.y + roi.height, height))
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"ROI {roi} 超出截圖範圍 {width}x{height}")
    cells = cut_cells(image[y0:y1, x0:x1], roi)
    store = TemplateStore(templates_dir)
    saved: list[Path] = []
    for (row, column), digit in sorted(labels.items()):
        if not 0 <= row < 10 or not 0 <= column < 15:
            raise ValueError(f"標註座標超出 10x15：({row}, {column})")
        if not 1 <= digit <= 9:
            raise ValueError(f"標註 digit 必須是 1~9：{digit}")
        saved.append(store.save_template(digit, cells[row * 15 + column]))
    return saved


def main() -> int:
    parser = argparse.ArgumentParser(description="從遊戲截圖建立 1~9 數字模板")
    parser.add_argument("screenshot", type=Path, help="遊戲截圖（灰階/彩色皆可）")
    parser.add_argument("labels", type=Path, help='標註 JSON：{"row,col": digit, ...}')
    parser.add_argument("--templates-dir", type=Path, default=None, help="模板輸出目錄")
    parser.add_argument(
        "--roi",
        type=str,
        default=None,
        help="ROI，格式 x,y,w,h；沒給就用 settings.json 的 ROI",
    )
    args = parser.parse_args()

    if args.roi:
        x, y, w, h = (int(value) for value in args.roi.split(","))
        roi = Roi(x=x, y=y, width=w, height=h)
    else:
        roi = SettingsStore().load_roi()
        if roi is None:
            print("settings.json 沒有 ROI，請用 --roi x,y,w,h 指定", file=sys.stderr)
            return 1

    raw_labels = json.loads(args.labels.read_text(encoding="utf-8"))
    labels: dict[tuple[int, int], int] = {}
    for key, digit in raw_labels.items():
        row, column = (int(value) for value in str(key).split(","))
        labels[(row, column)] = int(digit)

    store_dir = args.templates_dir or TemplateStore().templates_dir
    saved = build_templates_from_labels(args.screenshot, labels, roi, store_dir)
    for path in saved:
        print(f"saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
