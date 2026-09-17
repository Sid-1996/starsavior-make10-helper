"""Star Savior 10 消除提示器 - 程式進入點。"""

from __future__ import annotations

import ctypes
import os
import sys

# 關閉 Qt High-DPI 縮放，讓 Qt 座標與 mss 擷取的實體像素座標一致。
# 必須在建立 QApplication 之前設定。
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from gui.main_window import MainWindow  # noqa: E402


def _enable_dpi_awareness() -> None:
    """設定 Per-Monitor DPI awareness，確保座標為實體像素。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
    except (AttributeError, OSError):
        # 非 Windows 環境或已被設定時忽略
        pass


def main() -> int:
    _enable_dpi_awareness()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
