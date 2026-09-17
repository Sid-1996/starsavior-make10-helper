"""使用者設定（目前僅 ROI）的儲存與載入。

設定以 JSON 儲存在專案根目錄 settings.json，
程式重新啟動後可載入上次的辨識區域。
檔案缺失或內容損毀時一律安全回退為「未設定」，不丟出例外。
"""

from __future__ import annotations

import json
from pathlib import Path

from core.roi_model import Roi

DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH

    def load_roi(self) -> Roi | None:
        """載入上次儲存的 ROI；缺失、損毀或內容無效時回傳 None。"""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        roi_data = data.get("roi")
        if not isinstance(roi_data, dict):
            return None
        try:
            roi = Roi(
                x=int(roi_data["x"]),
                y=int(roi_data["y"]),
                width=int(roi_data["width"]),
                height=int(roi_data["height"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
        return roi if roi.is_valid() else None

    def save_roi(self, roi: Roi) -> None:
        """儲存 ROI；保留檔案中其他既有鍵值。"""
        data: dict = {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            pass
        data["roi"] = {
            "x": roi.x,
            "y": roi.y,
            "width": roi.width,
            "height": roi.height,
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
