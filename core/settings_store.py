"""使用者設定（ROI、視窗綁定、UI 偏好）的儲存與載入。

設定以 JSON 儲存在專案根目錄 settings.json，
程式重新啟動後可載入上次的狀態並自動恢復監控。
檔案缺失或內容損毀時一律安全回退為「未設定」，不丟出例外。

格式演進：
- v1（舊）：{"roi": {x, y, width, height}} 螢幕絕對座標
- v2（現行）：{"window": {"title": ...}, "roi_frac": {...}, "ui": {...}}
  首次綁定成功時自動由 v1 遷移（之後移除 "roi" 鍵）。
"""

from __future__ import annotations

import json
from pathlib import Path

from core.game_window import DEFAULT_GAME_TITLE
from core.roi_model import Roi, RoiFrac

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

    # ------------------------------------------------------------------ #
    # v2：視窗綁定 + 相對 ROI + UI 偏好
    # ------------------------------------------------------------------ #
    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_window_title(self) -> str:
        """綁定的遊戲視窗標題；缺失時回預設。"""
        window = self._read().get("window")
        if isinstance(window, dict) and isinstance(window.get("title"), str) and window["title"]:
            return window["title"]
        return DEFAULT_GAME_TITLE

    def save_window_title(self, title: str) -> None:
        data = self._read()
        data["window"] = {"title": title}
        self._write(data)

    def load_roi_frac(self) -> RoiFrac | None:
        """載入視窗相對 ROI；缺失或無效回傳 None。"""
        data = self._read().get("roi_frac")
        if not isinstance(data, dict):
            return None
        try:
            frac = RoiFrac(
                x=float(data["x"]),
                y=float(data["y"]),
                width=float(data["width"]),
                height=float(data["height"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
        return frac if frac.is_valid() else None

    def save_roi_frac(self, frac: RoiFrac) -> None:
        data = self._read()
        data["roi_frac"] = {"x": frac.x, "y": frac.y, "width": frac.width, "height": frac.height}
        data.pop("roi", None)  # 遷移完成：移除舊絕對座標
        self._write(data)

    def load_always_on_top(self) -> bool:
        """主視窗置頂偏好；預設開啟（單螢幕全螢幕用戶必需）。"""
        ui = self._read().get("ui")
        if isinstance(ui, dict) and isinstance(ui.get("always_on_top"), bool):
            return ui["always_on_top"]
        return True

    def save_always_on_top(self, enabled: bool) -> None:
        data = self._read()
        ui = data.get("ui")
        if not isinstance(ui, dict):
            ui = {}
            data["ui"] = ui
        ui["always_on_top"] = enabled
        self._write(data)
