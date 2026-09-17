"""路徑解析測試（原始碼 vs frozen exe 兩種模式）。"""

import sys

from core import paths


class TestPaths:
    def test_source_mode_uses_project_root(self, tmp_path, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        root = paths.Path(paths.__file__).resolve().parent.parent
        assert paths.resource_path("templates") == root / "templates"
        assert paths.writable_dir() == root

    def test_frozen_mode_splits_resource_and_writable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "mei"), raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "app" / "tool.exe"), raising=False)
        assert paths.is_frozen() is True
        assert paths.resource_path("templates") == tmp_path / "mei" / "templates"
        assert paths.writable_dir() == tmp_path / "app"  # 設定跟著 exe 走
