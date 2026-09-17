"""模板系統單元測試（用合成灰階圖，不依賴真實遊戲畫面）。"""

import numpy as np
import pytest

from core.templates import DIGITS, TEMPLATE_SIZE, TemplateSet, TemplateStore


def _gray(value: int, size: tuple[int, int] = (48, 48)) -> np.ndarray:
    return np.full((size[1], size[0]), value, dtype=np.uint8)


class TestTemplateSet:
    def test_missing_lists_absent_digits(self):
        template_set = TemplateSet(templates={1: _gray(10), 9: _gray(200)})
        assert template_set.has(1) is True
        assert template_set.has(2) is False
        assert template_set.missing() == [2, 3, 4, 5, 6, 7, 8]
        assert template_set.is_complete() is False

    def test_complete_when_all_digits_present(self):
        template_set = TemplateSet(templates={digit: _gray(digit) for digit in DIGITS})
        assert template_set.is_complete() is True


class TestTemplateStore:
    def test_rejects_non_digit(self, tmp_path):
        store = TemplateStore(tmp_path)
        with pytest.raises(ValueError):
            store.template_path(0)
        with pytest.raises(ValueError):
            store.save_template(10, _gray(100))

    def test_rejects_bad_image(self, tmp_path):
        store = TemplateStore(tmp_path)
        with pytest.raises(ValueError):
            store.save_template(3, np.zeros((10, 10, 3), dtype=np.uint8))
        with pytest.raises(ValueError):
            store.save_template(3, np.zeros((0, 0), dtype=np.uint8))

    def test_save_and_load_roundtrip(self, tmp_path):
        store = TemplateStore(tmp_path)
        # 非標準尺寸也會被統一縮放
        path = store.save_template(5, np.full((62, 62), 180, dtype=np.uint8))
        assert path == tmp_path / "5.png"
        assert path.is_file()

        loaded = store.load_all()
        assert loaded.has(5) is True
        assert loaded.templates[5].shape == (TEMPLATE_SIZE[1], TEMPLATE_SIZE[0])
        assert loaded.missing() == [1, 2, 3, 4, 6, 7, 8, 9]

    def test_load_all_skips_missing_and_broken(self, tmp_path):
        store = TemplateStore(tmp_path)
        store.save_template(1, _gray(50))
        (tmp_path / "2.png").write_bytes(b"not an image")
        (tmp_path / "note.txt").write_text("ignore me")
        loaded = store.load_all()
        assert loaded.has(1) is True
        assert loaded.has(2) is False
        assert 2 in loaded.missing()
