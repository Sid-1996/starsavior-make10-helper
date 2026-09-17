"""SettingsStore 單元測試。"""

import json

from core.game_window import DEFAULT_GAME_TITLE
from core.roi_model import Roi, RoiFrac
from core.settings_store import SettingsStore


class TestSettingsStore:
    def test_save_then_load_roundtrip(self, tmp_path):
        store = SettingsStore(tmp_path / "settings.json")
        roi = Roi(x=123, y=45, width=450, height=300)
        store.save_roi(roi)
        assert store.load_roi() == roi

    def test_load_missing_file_returns_none(self, tmp_path):
        store = SettingsStore(tmp_path / "not_exist.json")
        assert store.load_roi() is None

    def test_load_corrupt_json_returns_none(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("{ not valid json !!", encoding="utf-8")
        assert SettingsStore(path).load_roi() is None

    def test_load_non_dict_json_returns_none(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        assert SettingsStore(path).load_roi() is None

    def test_load_missing_keys_returns_none(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"roi": {"x": 1, "y": 2}}), encoding="utf-8")
        assert SettingsStore(path).load_roi() is None

    def test_load_non_numeric_returns_none(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"roi": {"x": "a", "y": 2, "width": 3, "height": 4}}),
            encoding="utf-8",
        )
        assert SettingsStore(path).load_roi() is None

    def test_load_invalid_roi_returns_none(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"roi": {"x": 0, "y": 0, "width": 0, "height": 100}}),
            encoding="utf-8",
        )
        assert SettingsStore(path).load_roi() is None

    def test_save_preserves_other_keys(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"some_future_key": {"a": 1}}, ensure_ascii=False),
            encoding="utf-8",
        )
        store = SettingsStore(path)
        store.save_roi(Roi(x=1, y=2, width=3, height=4))
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["some_future_key"] == {"a": 1}
        assert data["roi"] == {"x": 1, "y": 2, "width": 3, "height": 4}

    def test_save_overwrites_previous_roi(self, tmp_path):
        store = SettingsStore(tmp_path / "settings.json")
        store.save_roi(Roi(x=1, y=2, width=3, height=4))
        store.save_roi(Roi(x=10, y=20, width=300, height=200))
        assert store.load_roi() == Roi(x=10, y=20, width=300, height=200)


class TestSettingsV2:
    def test_roi_frac_roundtrip_and_migrates_legacy(self, tmp_path):
        store = SettingsStore(tmp_path / "settings.json")
        store.save_roi(Roi(x=1, y=2, width=3, height=4))  # 先有舊格式
        frac = RoiFrac(x=0.25, y=0.25, width=0.5, height=0.5)
        store.save_roi_frac(frac)
        assert store.load_roi_frac() == frac
        data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
        assert "roi" not in data  # 遷移完成移除舊鍵

    def test_roi_frac_invalid_returns_none(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"roi_frac": {"x": 0.5, "y": 0.5, "width": 0.6, "height": 0.6}}),
            encoding="utf-8",
        )
        assert SettingsStore(path).load_roi_frac() is None

    def test_window_title_default_and_save(self, tmp_path):
        store = SettingsStore(tmp_path / "settings.json")
        assert store.load_window_title() == DEFAULT_GAME_TITLE
        store.save_window_title("MyGame")
        assert store.load_window_title() == "MyGame"

    def test_always_on_top_default_true(self, tmp_path):
        store = SettingsStore(tmp_path / "settings.json")
        assert store.load_always_on_top() is True
        store.save_always_on_top(False)
        assert store.load_always_on_top() is False
        store.save_always_on_top(True)
        assert store.load_always_on_top() is True
