"""Test scripts/eval_stats.py — thống kê thuần dùng trong eval-report.md (mean/std, win rate,
calibrate). Không phụ thuộc DB/mạng."""

import pytest

from scripts import eval_stats


class TestMeanStd:
    def test_single_value_has_zero_std(self):
        mean, std = eval_stats.mean_std([5.0])
        assert mean == 5.0
        assert std == 0.0

    def test_multiple_values(self):
        mean, std = eval_stats.mean_std([1.0, 2.0, 3.0])
        assert mean == 2.0
        assert std == pytest.approx(0.8164965809, rel=1e-6)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            eval_stats.mean_std([])

    def test_identical_values_zero_std(self):
        mean, std = eval_stats.mean_std([4.0, 4.0, 4.0])
        assert mean == 4.0
        assert std == 0.0


class TestWinRate:
    def test_all_ai_wins(self):
        assert eval_stats.win_rate([5, 5, 5], [3, 3, 3]) == 1.0

    def test_all_baseline_wins(self):
        assert eval_stats.win_rate([2, 2], [4, 4]) == 0.0

    def test_ties_do_not_count_as_win(self):
        # bằng điểm KHÔNG tính là AI thắng — chỉ tính strictly greater
        assert eval_stats.win_rate([3, 5], [3, 4]) == 0.5

    def test_mismatched_length_raises(self):
        with pytest.raises(ValueError):
            eval_stats.win_rate([1, 2], [1])

    def test_empty_lists_return_zero(self):
        assert eval_stats.win_rate([], []) == 0.0


class TestCalibrationAgreementRate:
    def test_perfect_agreement(self):
        assert eval_stats.calibration_agreement_rate([4, 3, 5], [4, 3, 5]) == 1.0

    def test_within_tolerance_counts_as_agree(self):
        # |4-3|=1 <= tolerance mặc định 1.0 -> tính là đồng ý
        assert eval_stats.calibration_agreement_rate([4], [3]) == 1.0

    def test_outside_tolerance_counts_as_disagree(self):
        # |5-3|=2 > tolerance 1.0
        assert eval_stats.calibration_agreement_rate([5], [3]) == 0.0

    def test_mixed_case(self):
        # lệch: [0,1,1,3] với tolerance=1 -> 3/4 đồng ý
        human = [4, 3, 5, 2]
        judge = [4, 4, 4, 5]
        assert eval_stats.calibration_agreement_rate(human, judge) == 0.75

    def test_mismatched_length_raises(self):
        with pytest.raises(ValueError):
            eval_stats.calibration_agreement_rate([1, 2], [1])

    def test_empty_returns_zero(self):
        assert eval_stats.calibration_agreement_rate([], []) == 0.0

    def test_custom_tolerance(self):
        assert eval_stats.calibration_agreement_rate([5], [3], tolerance=2.0) == 1.0
