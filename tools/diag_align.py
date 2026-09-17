"""診斷：擷取目前畫面並輸出自動對齊的內部過程。

請在遊戲畫面可見（棋盤有數字）時執行：uv run python tools/diag_align.py
連續監測模式：uv run python tools/diag_align.py --loop 40 --interval 2
輸出到 debug/：全螢幕截圖、搜尋 crop、前景遮罩、對齊過程統計。
"""

import argparse
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

app = QApplication([])

from core import board_align, screen_capture  # noqa: E402
from core.settings_store import SettingsStore  # noqa: E402
from gui.image_utils import qimage_to_gray  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--delay", type=int, default=0, help="擷取前等待秒數")
parser.add_argument("--loop", type=int, default=1, help="擷取次數（連續監測）")
parser.add_argument("--interval", type=float, default=2.0, help="每次擷取的間隔秒數")
args = parser.parse_args()

if args.delay > 0:
    print(f"waiting {args.delay}s before capture...")
    time.sleep(args.delay)

os.makedirs("debug", exist_ok=True)

roi = SettingsStore().load_roi()
left, top, vw, vh = screen_capture.get_virtual_screen_geometry()
print(f"virtual screen: {vw}x{vh} at ({left},{top})")

if roi is not None:
    rect = (roi.x, roi.y, roi.width, roi.height)
    print(f"saved ROI: x={roi.x} y={roi.y} w={roi.width} h={roi.height}")
else:
    rect = (vw // 4, vh // 4, vw // 2, vh // 2)
    print("no saved ROI, using center half as test rect")


def capture_screen_rgb():
    img = screen_capture.capture_virtual_screen()
    rgb_img = img.convertToFormat(QImage.Format.Format_RGB888)
    h, w = rgb_img.height(), rgb_img.width()
    stride = rgb_img.bytesPerLine()
    bits = rgb_img.constBits()
    bits.setsize(stride * h)
    rgb_arr = (
        np.frombuffer(bits, dtype=np.uint8, count=stride * h)
        .reshape(h, stride)[:, : w * 3]
        .reshape(h, w, 3)
    )
    return img, rgb_arr


def run_once(index: int) -> tuple[bool, tuple | None]:
    """擷取一次並跑完整對齊流程，回傳 (是否成功, 對齊結果)。"""
    img, rgb_arr = capture_screen_rgb()
    h, w = rgb_arr.shape[:2]
    cv2.imwrite(f"debug/screen_{index:02d}.png", cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR))
    gray_full = qimage_to_gray(img)

    x, y, rw, rh = rect
    ex, ey = int(round(rw * 0.3)), int(round(rh * 0.3))
    x0, y0 = max(0, x - ex), max(0, y - ey)
    x1, y1 = min(w, x + rw + ex), min(h, y + rh + ey)
    crop = gray_full[y0:y1, x0:x1]
    cv2.imwrite(f"debug/crop_{index:02d}.png", crop)

    result = board_align.align_to_board(gray_full, rect)
    print(f"[{index:02d}] align result: {result}", flush=True)

    if result is None:
        # 輸出失敗樣本的遮罩供分析
        mask = board_align._tile_mask(crop)
        kind = "tile"
        if mask is None:
            mask = board_align._foreground_mask(crop)
            kind = "edge"
        cv2.imwrite(f"debug/mask_{index:02d}_{kind}.png", mask)
        return False, None

    ax, ay, aw, ah = result
    vis = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)
    cv2.rectangle(vis, (ax, ay), (ax + aw - 1, ay + ah - 1), (0, 255, 0), 2)
    cv2.imwrite(f"debug/aligned_{index:02d}.png", vis)
    print(f"     cell={aw / 15:.1f}x{ah / 10:.1f}, saved aligned_{index:02d}.png")
    return True, result


success_count = 0
last_result = None
for i in range(args.loop):
    ok, result = run_once(i)
    if ok:
        success_count += 1
        last_result = result
    if i < args.loop - 1:
        time.sleep(args.interval)

print(f"SUMMARY: {success_count}/{args.loop} aligned")
if last_result is not None:
    print(f"last successful result: {last_result}")
print("DONE")
