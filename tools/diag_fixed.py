"""固定截圖驗證：tile 質心是否符合 10x15 等間距格子排列。

只讀取 --image（預設 debug/screen_01.png），不做即時擷取。
步驟：
1. 列出閾值遮罩的外輪廓位置（bbox/面積/質心），確認是否對應白色數字格。
2. 對質心做 10x15 等間距最小平方法擬合（沿用 core.board_align 的軸向擬合）。
3. 輸出殘差（RMSE、最大值、inlier 數量、欄列覆蓋數）。
4. 畫中心圓點：藍圈 = 擬合格子中心，綠點 = inlier 質心，紅點 = outlier。
5. 若質心不符合格子排列，判定方法失敗（不硬湊答案）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.board_align import (  # noqa: E402
    _centroid_histograms,
    _fit_axis,
    _tile_mask,
)

INLIER_TOL_PX = 10.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="debug/screen_01.png")
    parser.add_argument("--rect", default="494,265,934,620")
    parser.add_argument("--out", default="debug/fixed_centers.png")
    args = parser.parse_args()

    gray = cv2.imread(args.image, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        print(f"讀不到圖：{args.image}")
        return 1
    color = cv2.imread(args.image, cv2.IMREAD_COLOR)
    x, y, rw, rh = (int(v) for v in args.rect.split(","))
    ex, ey = int(round(rw * 0.3)), int(round(rh * 0.3))
    x0 = max(0, x - ex)
    y0 = max(0, y - ey)
    crop = gray[y0 : y0 + rh + 2 * ey, x0 : x0 + rw + 2 * ex]
    print(f"crop 原點=({x0},{y0}) 大小={crop.shape[1]}x{crop.shape[0]}")

    mask = _tile_mask(crop)
    if mask is None:
        print("VERDICT=FAIL：tile 遮罩找不到足夠方形元件")
        return 2
    count, _labels, stats, cents = cv2.connectedComponentsWithStats(mask)
    print(f"元件數（含背景）={count}，tile 候選={count - 1}")
    areas = []
    for i in range(1, count):
        w = int(stats[i, cv2.CC_STAT_WIDTH])
        h = int(stats[i, cv2.CC_STAT_HEIGHT])
        area = int(stats[i, cv2.CC_STAT_AREA])
        areas.append(area)
        if i <= 8:
            print(
                f"  #{i} bbox=({stats[i, 0]},{stats[i, 1]},{w},{h}) "
                f"area={area} fill={area / (w * h):.2f} "
                f"centroid=({cents[i][0]:.1f},{cents[i][1]:.1f})"
            )
    areas = np.array(areas, dtype=float)
    print(f"面積：min={areas.min():.0f} med={np.median(areas):.0f} max={areas.max():.0f}")

    col, row = _centroid_histograms(mask)
    ys, xs = np.nonzero(mask)
    px0, px1 = int(np.percentile(xs, 1)), int(np.percentile(xs, 99))
    py0, py1 = int(np.percentile(ys, 1)), int(np.percentile(ys, 99))
    fx = _fit_axis(col, 15, px0, px1)
    fy = _fit_axis(row, 10, py0, py1)
    print(f"x 軸擬合(crop 座標)={fx}")
    print(f"y 軸擬合(crop 座標)={fy}")
    if fx[0] is None or fy[0] is None:
        print("VERDICT=FAIL：軸向擬合失敗")
        return 2
    bx, bw = fx
    by, bh = fy
    pw, ph = bw / 15.0, bh / 10.0

    pts = cents[1:]
    res_x, res_y, inliers, outliers = [], [], [], []
    cols_hit, rows_hit = set(), set()
    for cx, cy in pts:
        kx = int(round((cx - bx) / pw - 0.5))
        ky = int(round((cy - by) / ph - 0.5))
        if 0 <= kx < 15 and 0 <= ky < 10:
            rx = cx - (bx + (kx + 0.5) * pw)
            ry = cy - (by + (ky + 0.5) * ph)
            if abs(rx) <= INLIER_TOL_PX and abs(ry) <= INLIER_TOL_PX:
                res_x.append(rx)
                res_y.append(ry)
                inliers.append((cx, cy))
                cols_hit.add(kx)
                rows_hit.add(ky)
                continue
        outliers.append((cx, cy))
    res_x = np.array(res_x)
    res_y = np.array(res_y)
    print(f"質心總數={len(pts)} inlier={len(inliers)} outlier={len(outliers)}")
    if len(inliers):
        print(f"欄覆蓋={len(cols_hit)}/15 列覆蓋={len(rows_hit)}/10")
        print(f"x 殘差：RMSE={np.sqrt((res_x**2).mean()):.2f} max={np.abs(res_x).max():.2f}")
        print(f"y 殘差：RMSE={np.sqrt((res_y**2).mean()):.2f} max={np.abs(res_y).max():.2f}")
    ok = (
        len(inliers) >= 0.85 * len(pts)
        and len(cols_hit) >= 12
        and len(rows_hit) >= 8
        and (np.sqrt((res_x**2).mean()) <= 5.0 if len(inliers) else False)
        and (np.sqrt((res_y**2).mean()) <= 5.0 if len(inliers) else False)
    )

    # 畫圖：紅框 = 擬合 ROI（螢幕座標），藍圈 = 150 格子中心，
    # 綠點 = inlier 質心，紅點 = outlier 質心
    rx0, ry0 = x0 + bx, y0 + by
    cv2.rectangle(color, (rx0, ry0), (rx0 + bw, ry0 + bh), (0, 0, 255), 2)
    for r in range(10):
        for c in range(15):
            gx = int(round(rx0 + (c + 0.5) * pw))
            gy = int(round(ry0 + (r + 0.5) * ph))
            cv2.circle(color, (gx, gy), 6, (255, 0, 0), 2)
    for cx, cy in inliers:
        cv2.circle(color, (int(round(x0 + cx)), int(round(y0 + cy))), 3, (0, 255, 0), -1)
    for cx, cy in outliers:
        cv2.circle(color, (int(round(x0 + cx)), int(round(y0 + cy))), 4, (0, 0, 255), -1)
    small = cv2.resize(color, (960, 540))
    cv2.imwrite(args.out, small)
    print(f"已輸出 {args.out}")
    print(f"擬合 ROI（螢幕座標）=({rx0},{ry0},{bw},{bh})")
    print("VERDICT=" + ("PASS：質心符合 10x15 等間距排列" if ok else "FAIL：質心不符合格子排列"))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
