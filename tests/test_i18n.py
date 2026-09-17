"""i18n 測試：語言偵測、字串表完整性、切換即生效（offscreen GUI）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core import i18n  # noqa: E402
from core.i18n import (  # noqa: E402
    SUPPORTED_LANGUAGES,
    detect_system_language,
    get_language,
    resolve_preference,
    set_language,
    t,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _restore_language():
    yield
    set_language(None)  # 還原跟系統，避免污染其他測試檔


class TestDetection:
    def test_known_prefixes(self, monkeypatch):
        from PyQt6.QtCore import QLocale

        for system_name, want in [
            ("zh_TW", "zh"),
            ("zh_CN", "zh"),
            ("zh_HK", "zh"),
            ("en_US", "en"),
            ("ja_JP", "ja"),
            ("ko_KR", "ko"),
        ]:
            monkeypatch.setattr(QLocale, "system", classmethod(lambda cls: _FakeLocale(system_name)))
            set_language(None)
            assert detect_system_language() == want, system_name

    def test_unknown_falls_back_to_english(self, monkeypatch):
        from PyQt6.QtCore import QLocale

        monkeypatch.setattr(QLocale, "system", classmethod(lambda cls: _FakeLocale("fr_FR")))
        set_language(None)
        assert detect_system_language() == "en"
        assert get_language() == "en"
        assert "Monitoring" in t("main.toggle_start")

    def test_detection_failure_falls_back_to_english(self, monkeypatch):
        from PyQt6.QtCore import QLocale

        def boom():
            raise RuntimeError("no locale")

        monkeypatch.setattr(QLocale, "system", classmethod(lambda cls: boom()))
        monkeypatch.setattr("locale.getlocale", lambda: (_raise(), None))
        set_language(None)
        assert detect_system_language() == "en"


def _raise():
    raise RuntimeError("no locale")


class _FakeLocale:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class TestTable:
    def test_key_parity_across_languages(self):
        tables = {lang: getattr(i18n, f"_{lang}")() for lang in SUPPORTED_LANGUAGES}
        reference = set(tables["zh"])
        assert len(reference) > 40  # 有一定覆蓋量
        for lang, table in tables.items():
            assert set(table) == reference, f"{lang} 缺 key 或多 key"

    def test_no_empty_strings(self):
        for lang in SUPPORTED_LANGUAGES:
            for key, value in getattr(i18n, f"_{lang}")().items():
                assert value.strip(), f"{lang}.{key} 是空字串"

    def test_format_params_survive(self):
        set_language("en")
        assert "Monitoring #3 stable 2/3" in t(
            "main.status_monitoring", ticks=3, run=2, required=3, note=""
        )
        set_language("ja")
        assert t("panel.stats", digit=1, empty=2, unknown=3) != "panel.stats"

    def test_missing_key_never_crashes(self):
        set_language("ko")
        assert t("no.such.key") == "no.such.key"


class TestPreference:
    def test_resolve_and_set(self):
        assert resolve_preference("ja") == "ja"
        assert get_language() == "ja"
        assert resolve_preference("auto") == detect_system_language()
        assert resolve_preference("xx") == detect_system_language()
        assert set_language("xx") == detect_system_language()  # 非法值視為跟系統

    def test_store_roundtrip(self, tmp_path):
        from core.settings_store import SettingsStore

        store = SettingsStore(tmp_path / "settings.json")
        assert store.load_language() == "auto"
        store.save_language("ko")
        assert store.load_language() == "ko"
        store.save_language("xx")
        assert store.load_language() == "auto"


class TestGuiSwitch:
    def _window(self, tmp_path):
        from core.roi_model import Roi
        from core.settings_store import SettingsStore
        from gui.main_window import MainWindow

        win = MainWindow(
            auto_repair=False,
            auto_start=False,
            store=SettingsStore(tmp_path / "settings.json"),
            log_dir=tmp_path,
        )
        win._apply_roi(Roi(x=0, y=0, width=450, height=300))
        return win

    def test_main_window_follows_preference(self, qapp, tmp_path):
        from core.settings_store import SettingsStore

        store = SettingsStore(tmp_path / "settings.json")
        store.save_language("en")
        from gui.main_window import MainWindow

        win = MainWindow(auto_repair=False, auto_start=False, store=store, log_dir=tmp_path)
        try:
            assert get_language() == "en"
            assert win.btn_toggle.text() == "Start Monitoring (F8)"
            assert "Welcome" in win.lbl_status.text()  # 無 ROI → 英文引導
            assert win.windowTitle() == "Star Savior 10 Match Helper"
        finally:
            win.close()

    def test_combo_switch_applies_immediately(self, qapp, tmp_path):
        from core.settings_store import SettingsStore
        from gui.settings_dialog import SettingsDialog

        win = self._window(tmp_path)
        try:
            set_language("zh")
            win.retranslate_all()
            assert "開始監控" in win.btn_toggle.text()
            dlg = win._settings
            dlg.sync_language_combo("zh")
            dlg.language_combo.setCurrentIndex(3)  # 日本語
            assert SettingsStore(tmp_path / "settings.json").load_language() == "ja"
            assert get_language() == "ja"
            assert "監視開始" in win.btn_toggle.text()
            assert dlg.windowTitle() == "設定"
            assert win._settings.btn_select.text() == "盤面領域を選択"
            # 切回來也即時
            dlg.language_combo.setCurrentIndex(2)  # English
            assert win.btn_toggle.text() == "Start Monitoring (F8)"
            assert SettingsDialog.language_code(99) == "auto"
        finally:
            win.close()

    def test_monitor_note_retranslated(self, qapp, tmp_path):
        win = self._window(tmp_path)
        try:
            set_language("zh")
            win._monitor_note = ("note.keep_same", {})
            win._monitor_timer.start()  # 假裝監控中（不斷開即可）
            win._refresh_ui()
            assert "棋盤未變" in win.lbl_status.text()
            set_language("en")
            win._refresh_ui()
            assert "unchanged" in win.lbl_status.text()
            win._monitor_timer.stop()
        finally:
            win.close()
