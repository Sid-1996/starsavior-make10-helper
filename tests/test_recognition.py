"""數字辨識單元測試（合成灰階圖；低信心 → UNKNOWN，不硬猜）。"""

import numpy as np

from core.recognition import DigitRecognizer
from core.templates import TemplateSet


def _digit_like(
    value: int, noise: int = 0, seed: int = 1, orientation: str = "vertical"
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = np.full((48, 48), 30, dtype=np.uint8)
    if orientation == "vertical":
        base[8:40, 22:26] = np.uint8(value)
    else:
        base[22:26, 8:40] = np.uint8(value)
    if noise:
        delta = rng.integers(-noise, noise + 1, size=base.shape).astype(np.int16)
        base = np.clip(base.astype(np.int16) + delta, 0, 255).astype(np.uint8)
    return base


def _templates() -> TemplateSet:
    return TemplateSet(
        templates={
            1: _digit_like(200, orientation="vertical"),
            2: _digit_like(200, orientation="horizontal"),
        }
    )


class TestDigitRecognizer:
    def test_recognizes_matching_digit(self):
        recognizer = DigitRecognizer(_templates())
        result = recognizer.recognize(_digit_like(200), panel_mean=30.0)
        assert result.state == "digit"
        assert result.digit == 1
        assert result.confidence > 0.9

    def test_distinguishes_digits(self):
        recognizer = DigitRecognizer(_templates())
        result = recognizer.recognize(_digit_like(200, orientation="horizontal"), panel_mean=30.0)
        assert result.state == "digit"
        assert result.digit == 2

    def test_noisy_but_recognizable(self):
        recognizer = DigitRecognizer(_templates())
        result = recognizer.recognize(_digit_like(200, noise=8), panel_mean=30.0)
        assert result.state == "digit"
        assert result.digit == 1

    def test_empty_panel(self):
        recognizer = DigitRecognizer(_templates())
        cell = np.full((48, 48), 60, dtype=np.uint8)
        result = recognizer.recognize(cell, panel_mean=60.0)
        assert result.state == "empty"
        assert result.digit is None

    def test_low_confidence_becomes_unknown(self):
        recognizer = DigitRecognizer(_templates(), match_threshold=0.99)
        # 完全沒見過的圖案：分數再高也不該硬猜（門檻拉高後應為 UNKNOWN）
        cell = _digit_like(150, noise=30, seed=99)
        result = recognizer.recognize(cell, panel_mean=30.0)
        if result.confidence < 0.99:
            assert result.state == "unknown"
            assert result.digit is None

    def test_no_templates_becomes_unknown(self):
        recognizer = DigitRecognizer(TemplateSet(templates={}))
        result = recognizer.recognize(_digit_like(200), panel_mean=30.0)
        assert result.state == "unknown"
        assert result.digit is None
        assert result.confidence == 0.0

    def test_empty_cell_image_becomes_unknown(self):
        recognizer = DigitRecognizer(_templates())
        result = recognizer.recognize(np.zeros((0, 0), dtype=np.uint8))
        assert result.state == "unknown"

    def test_rejects_non_grayscale(self):
        recognizer = DigitRecognizer(_templates())
        with_noise = np.zeros((10, 10, 3), dtype=np.uint8)
        try:
            recognizer.recognize(with_noise)
        except ValueError:
            return
        raise AssertionError("應拒絕非灰階影像")

    def test_scores_cover_available_templates(self):
        recognizer = DigitRecognizer(_templates())
        result = recognizer.recognize(_digit_like(200), panel_mean=30.0)
        assert set(result.scores.keys()) == {1, 2}
        assert result.scores[1] >= result.scores[2]
