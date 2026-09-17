"""路徑解析：原始碼執行 vs PyInstaller 打包（frozen）兩種模式。

- 唯讀資源（數字模板）：原始碼跑專案根目錄；frozen 跑解包暫存（sys._MEIPASS）。
- 可寫資料（settings.json、debug 日誌）：原始碼放專案根目錄；
  frozen 放 exe 旁邊（綠色軟體：免安裝、設定跟著走、刪 exe 即乾淨移除）。
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """是否為 PyInstaller 打包後的 exe。"""
    return bool(getattr(sys, "frozen", False))


def resource_path(relative: str) -> Path:
    """唯讀資源路徑（打包時由 --add-data 帶入）。"""
    if is_frozen():
        return Path(sys._MEIPASS) / relative  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent / relative


def writable_dir() -> Path:
    """可寫資料目錄（設定＋日誌）：frozen 放 exe 旁，否則放專案根目錄。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
