"""10x15 棋盤自動對齊（ROI Auto-Align）。

在使用者粗略框選的區域附近偵測實際數字棋盤的位置：
1. Sobel 邊緣 + Otsu 自適應閾值建立前景遮罩（數字與格線）
2. 前景密度剖面 + 自相關估計 cell 週期（pitch）
3. 搜尋 (pitch, phase) 讓 15 欄 / 10 列對準前景質量
   （同時檢驗「質量在格中心」與「質量在格線」兩種假設）
4. 驗證對齊結果須涵蓋足夠比例的前景，失敗回傳 None（呼叫端退回原始選取）

純 numpy / OpenCV，不依賴 GUI；座標為傳入影像的像素座標。
"""

from __future__ import annotations

import cv2
import numpy as np

from core.roi_model import GRID_COLS, GRID_ROWS

MIN_CELL_PX = 8  # cell 至少幾 px 才可信
MIN_FOREGROUND_PX = 300  # 前景邊緣像素下限，低於此視為沒有棋盤
_AUTOCORR_MIN = 0.15  # 週期自相關強度下限
_DENSITY_KEEP = 0.5  # 對齊結果需涵蓋的前景比例
_MIN_CENTEREDNESS = 0.58  # 質量需落在 cell 中央半部的最低比例


def align_to_board(
    gray: np.ndarray,
    rect: tuple[int, int, int, int],
    expand_ratio: float = 0.3,
) -> tuple[int, int, int, int] | None:
    """在 gray 中偵測 10x15 棋盤，將 rect 吸附到實際棋盤位置。

    rect: 影像座標 (x, y, w, h)，使用者粗略框選的區域。
    expand_ratio: 搜尋時向外擴張的比例（允許吸附到比選取範圍略大的棋盤）。
    回傳對齊後 (x, y, w, h)；無法可靠偵測時回傳 None。
    """
    if gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValueError("gray 必須是 2D uint8 陣列")
    h, w = gray.shape[:2]
    x, y, rw, rh = rect
    if rw <= 0 or rh <= 0:
        return None
    ex = int(round(rw * expand_ratio))
    ey = int(round(rh * expand_ratio))
    x0, y0 = max(0, x - ex), max(0, y - ey)
    x1, y1 = min(w, x + rw + ex), min(h, y + rh + ey)
    crop = gray[y0:y1, x0:x1]
    found = _find_board_rect(crop)
    if found is None:
        return None
    fx, fy, fw, fh = found
    return (x0 + fx, y0 + fy, fw, fh)


def _foreground_mask(gray: np.ndarray) -> np.ndarray:
    """以 Sobel 邊緣量值 + Otsu 建立前景遮罩（0/255）。"""
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.clip(cv2.magnitude(gx, gy), 0, 255).astype(np.uint8)
    _, mask = cv2.threshold(mag, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return mask


def _tile_mask(gray: np.ndarray) -> np.ndarray | None:
    """偵測亮色格子 tile（如：灰面板上的白底數字格）。

    tile 內數字的深色筆畫只是元件中的洞，不會切斷元件；
    角色立繪、邊框、文字等干擾大多會被面積／長寬比過濾掉。
    偵測不到足夠 tile 時回傳 None（呼叫端退回邊緣遮罩）。

    全域 Otsu 的閾值可能落在「暗背景 vs 面板」之間，導致面板與 tile
    黏成單一巨大元件；因此依序嘗試多個候選閾值，直到找到足夠的方形 tile。
    """
    otsu_t, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    candidates = [int(otsu_t), int((otsu_t + 255) / 2), int(np.percentile(gray, 90))]
    seen: set[int] = set()
    for t in candidates:
        if t in seen or not (30 <= t <= 250):
            continue
        seen.add(t)
        mask = _tile_mask_at(gray, t)
        if mask is not None:
            return mask
    return None


def _tile_mask_at(gray: np.ndarray, threshold: int) -> np.ndarray | None:
    """以指定閾值偵測亮色 tile，找到足夠的方形元件才回傳遮罩。

    先以「實心率」(area / bbox 面積) 挑出實心亮塊：tile 是實心方塊（~0.87），
    文字筆畫（~0.2）與角色毛髮（~0.5）會被排除；再對 tile 母體取中位數面積，
    過濾大小差異過大的元件。
    """
    _, bright = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(bright)
    solid: list[int] = []
    for i in range(1, count):
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 100 or min(w, h) < 16:
            continue  # 太小：雜訊、文字筆畫
        if area / float(w * h) < 0.6:
            continue  # 中空／細碎：文字、毛髮、邊框
        if w > 3 * h or h > 3 * w:
            continue  # 長條形：文字列、框線
        solid.append(i)
    # 10x15 棋盤應存在大量 tile（允許部分已消除）
    if len(solid) < 30:
        return None
    med = float(np.median([stats[i, cv2.CC_STAT_AREA] for i in solid]))
    kept = np.zeros_like(bright)
    kept_count = 0
    for i in solid:
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 0.3 * med or area > 3.0 * med:
            continue
        kept[labels == i] = 255
        kept_count += 1
    if kept_count < 30:
        return None
    return kept


def _find_board_rect(crop: np.ndarray) -> tuple[int, int, int, int] | None:
    """在 crop 中搜尋 10x15 棋盤矩形，失敗回傳 None。"""
    # 優先偵測亮色 tile（白底數字格），失敗時退回邊緣遮罩
    mask = _tile_mask(crop)
    if mask is not None:
        # tile 質心是「點」，作為剖面可避免平台狀質量造成的相位模糊
        col, row = _centroid_histograms(mask)
    else:
        mask = _foreground_mask(crop)
        col = mask.mean(axis=0)
        row = mask.mean(axis=1)
    ys, xs = np.nonzero(mask)
    if xs.size < MIN_FOREGROUND_PX:
        return None
    # 百分位修剪去除零星離群邊緣，取得粗略內容範圍
    px0, px1 = np.percentile(xs, [1.0, 99.0])
    py0, py1 = np.percentile(ys, [1.0, 99.0])
    cx0, cx1, cy0, cy1 = int(px0), int(px1) + 1, int(py0), int(py1) + 1
    span_w, span_h = cx1 - cx0, cy1 - cy0
    if span_w < GRID_COLS * MIN_CELL_PX * 0.4 or span_h < GRID_ROWS * MIN_CELL_PX * 0.4:
        return None

    board_x, board_w = _fit_axis(col, GRID_COLS, cx0, cx1)
    board_y, board_h = _fit_axis(row, GRID_ROWS, cy0, cy1)
    if board_x is None or board_y is None:
        return None

    if board_w < GRID_COLS * MIN_CELL_PX or board_h < GRID_ROWS * MIN_CELL_PX:
        return None
    if board_x + board_w > crop.shape[1] or board_y + board_h > crop.shape[0]:
        return None
    # 對齊結果必須涵蓋大部分前景，否則視為誤偵測
    inside = mask[board_y : board_y + board_h, board_x : board_x + board_w].sum()
    if inside < _DENSITY_KEEP * mask.sum():
        return None
    return board_x, board_y, board_w, board_h


def _centroid_histograms(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """將 tile 元件質心轉為 x / y 直方圖（以面積加權）。

    tile 在遮罩剖面上是寬平台（~49px），相位擬合會有模糊帶；
    質心是單點（delta），讓週期與相位都有唯一解。
    """
    h, w = mask.shape[:2]
    count, _labels, stats, cents = cv2.connectedComponentsWithStats(mask)
    hist_x = np.zeros(w, dtype=np.float64)
    hist_y = np.zeros(h, dtype=np.float64)
    for i in range(1, count):
        area = float(stats[i, cv2.CC_STAT_AREA])
        ix = min(max(int(round(cents[i][0])), 0), w - 1)
        iy = min(max(int(round(cents[i][1])), 0), h - 1)
        hist_x[ix] += area
        hist_y[iy] += area
    return hist_x, hist_y


def _fit_axis(
    profile: np.ndarray, count: int, lo: float, hi: float
) -> tuple[int | None, int | None]:
    """在剖面上擬合 count 個 cell 的格線位置。

    回傳 (origin, board_len)：origin 為第 0 格的左/上邊界。
    流程：
    1. 產生多個 pitch 候選（自相關峰及其分諧波、跨度比例）
    2. 每個候選：粗搜相位 → 質量重心線性回歸精修 (origin, pitch)
       （回歸平均掉數字 glyph 在格子內的不對稱密度誤差）
    3. 以「置中度」評分（前景質量落在 cell 中央半部的比例），
       同時解決「質量在格中心」與「質量在格線上」兩種樣式
    失敗回傳 (None, None)。
    """
    span = hi - lo
    if span < count * MIN_CELL_PX * 0.4:
        return (None, None)
    best: tuple[float, float, float] | None = None  # (centeredness, origin, pitch)
    for p0 in _pitch_candidates(profile, span):
        rough = _rough_phase(profile, p0, count, lo, hi)
        if rough is None:
            continue
        fit = _refine_phase(profile, rough[0], rough[1], count)
        if fit is None:
            continue
        a, b = fit
        # 質量在格中心 → origin = a - b/2；質量在格線上 → origin = a
        for origin in (a - 0.5 * b, a):
            cen = _centeredness(profile, origin, b, count, lo, hi)
            if best is None or cen > best[0]:
                best = (cen, origin, b)
    if best is None or best[0] < _MIN_CENTEREDNESS:
        return (None, None)
    _, origin, b = best
    return (int(round(origin)), int(round(count * b)))


def _pitch_candidates(profile: np.ndarray, span: float) -> list[float]:
    """收集可能的 cell 週期候選（由小到大、去重）。

    內容範圍可能遠大於棋盤（角色、圖示等干擾），自相關可能抓到諧波，
    因此同時納入：跨度比例推測、自相關峰及其 1/2、1/3。
    """
    cands: list[float] = [span / k for k in range(8, 21)]
    max_pitch = max(span / 6.0, MIN_CELL_PX * 2.0)
    for peak in _autocorr_peaks(profile, MIN_CELL_PX, max_pitch):
        cands.extend([peak, peak / 2.0, peak / 3.0])
    cands.sort()
    result: list[float] = []
    for c in cands:
        if c < MIN_CELL_PX:
            continue
        if result and c - result[-1] < 1.5:
            continue
        result.append(c)
    return result


def _autocorr_peaks(profile: np.ndarray, min_pitch: float, max_pitch: float) -> list[float]:
    """剖面自相關的所有局部峰值（強度超過門檻）。"""
    p = profile.astype(np.float64)
    p = p - p.mean()
    n = p.size
    if n < 3 * min_pitch or min_pitch < 2:
        return []
    ac = np.correlate(p, p, "full")[n - 1 :]
    if ac[0] <= 0:
        return []
    ac /= ac[0]
    lo = max(2, int(min_pitch))
    hi = min(n - 2, int(max_pitch))
    peaks: list[float] = []
    for i in range(lo, hi + 1):
        if ac[i] > _AUTOCORR_MIN and ac[i] >= ac[i - 1] and ac[i] >= ac[i + 1]:
            peaks.append(float(i))
    return peaks


def _centeredness(
    profile: np.ndarray,
    origin: float,
    pitch: float,
    count: int,
    lo: float,
    hi: float,
) -> float:
    """衡量前景質量落在各 cell 中央半部的比例（0~1）。

    分母為整個內容範圍的質量，因此「格子數不足、漏掉部分內容」的
    錯誤候選（如 1/2 諧波）也會被扣分。
    正確的 pitch／相位：質量集中於 cell 中央（接近 1.0）；
    諧波錯誤或相位偏移：大量質量落在 cell 邊界或範圍外（~0.5 以下）。
    """
    n = profile.size
    total = float(profile[max(0, int(lo)) : min(n, int(hi))].sum())
    if total <= 0:
        return 0.0
    central = 0.0
    for i in range(count):
        c = origin + (i + 0.5) * pitch
        ja = int(max(0, np.floor(c - pitch / 4)))
        jb = int(min(n, np.ceil(c + pitch / 4)))
        if jb > ja:
            central += profile[ja:jb].sum()
    return float(central / total)


def _rough_phase(
    profile: np.ndarray,
    pitch: float,
    count: int,
    lo: float,
    hi: float,
) -> tuple[int, float] | None:
    """以滑動視窗質量總和粗搜相位（假設質量在格中心），回傳 (origin, pitch)。

    以前綴和向量化，避免三層 Python 迴圈。
    """
    n = profile.size
    cs = np.concatenate(([0.0], np.cumsum(profile, dtype=np.float64)))
    p_lo = max(0.0, lo - pitch)
    p_hi = min(hi, n - count * pitch)
    if p_hi <= p_lo:
        return None
    s_values = np.arange(int(p_lo), int(p_hi) + 1)
    if s_values.size == 0:
        return None
    best: tuple[float, int, float] | None = None  # (score, s, pitch_try)
    for pitch_try in np.arange(pitch - 1.0, pitch + 1.01, 0.25):
        if (count - 0.5) * pitch_try >= n:
            continue
        total = np.zeros(s_values.size, dtype=np.float64)
        for i in range(count):
            idx = s_values + (i + 0.5) * pitch_try
            ia = np.clip(idx.astype(int) - 3, 0, n)
            ib = np.clip(idx.astype(int) + 4, 0, n)
            total += cs[ib] - cs[ia]
        j = int(np.argmax(total))
        score = float(total[j]) / count
        if best is None or score > best[0]:
            best = (score, int(s_values[j]), float(pitch_try))
    if best is None:
        return None
    return (best[1], best[2])


def _refine_phase(
    profile: np.ndarray,
    s0: int,
    p0: float,
    count: int,
) -> tuple[float, float] | None:
    """以各 cell 前景質量重心的線性回歸精修，center_i = a + b * i。

    含收斂迭代：以擬合結果重新聚集重心再回歸，讓偏移數 px 的
    初始候選也能收斂到真實格距。失敗回傳 None。
    """
    n = profile.size
    s_cur, p_cur = float(s0), float(p0)
    a_coef = b_coef = None
    for _ in range(3):
        half = max(3, int(p_cur * 0.35))
        cents: list[float] = []
        idxs: list[int] = []
        for i in range(count):
            c = s_cur + (i + 0.5) * p_cur
            wa, wb = int(c - half), int(c + half) + 1
            if wa < 0 or wb > n:
                continue
            seg = profile[wa:wb].astype(float)
            total = seg.sum()
            if total < 1e-6:
                continue
            cents.append(float((np.arange(wa, wb) * seg).sum() / total))
            idxs.append(i)
        if len(cents) < max(4, count // 2):
            return None
        idxs_arr = np.asarray(idxs, dtype=float)
        cents_arr = np.asarray(cents, dtype=float)
        # 兩輪擬合：剔除殘差過大的離群重心（如棋盤外干擾物），再重新擬合
        for _ in range(2):
            b_coef, a_coef = np.polyfit(idxs_arr, cents_arr, 1)
            resid = np.abs(cents_arr - (a_coef + b_coef * idxs_arr))
            keep = resid <= max(3.0, 0.35 * b_coef)
            if keep.all() or int(keep.sum()) < max(4, count // 3):
                break
            idxs_arr, cents_arr = idxs_arr[keep], cents_arr[keep]
        b_coef, a_coef = np.polyfit(idxs_arr, cents_arr, 1)
        if b_coef < 2:
            return None
        # 收斂檢查：以新擬合更新搜尋中心，若變化極小則停止
        new_s = a_coef - 0.5 * b_coef
        new_p = b_coef
        if abs(new_p - p_cur) < 0.05 and abs(new_s - s_cur) < 0.5:
            break
        s_cur, p_cur = new_s, new_p
    if b_coef is None or b_coef < 2 or not (0.6 * p0 <= b_coef <= 1.5 * p0):
        return None
    return (a_coef, b_coef)
