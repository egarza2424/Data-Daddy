
import unittest

from scripts.validate_waiver_predictions import (
    calculate_rank_correlation,
    calculate_overall_rank_correlation,
    calculate_top_five_hit_rate,
)


class TestWaiverRankCorrelation(unittest.TestCase):

    def test_perfect_ranking(self):
        rows = [
            {'rank': 1, 'actual_ppr': 30},
            {'rank': 2, 'actual_ppr': 20},
            {'rank': 3, 'actual_ppr': 10},
        ]
        self.assertEqual(calculate_rank_correlation(rows), 1.0)

    def test_reversed_ranking(self):
        rows = [
            {'rank': 1, 'actual_ppr': 10},
            {'rank': 2, 'actual_ppr': 20},
            {'rank': 3, 'actual_ppr': 30},
        ]
        self.assertEqual(calculate_rank_correlation(rows), -1.0)

    def test_tied_results(self):
        rows = [
            {'rank': 1, 'actual_ppr': 20},
            {'rank': 2, 'actual_ppr': 20},
            {'rank': 3, 'actual_ppr': 10},
        ]
        self.assertEqual(calculate_rank_correlation(rows), 0.866)

    def test_insufficient_data(self):
        rows = [
            {'rank': 1, 'actual_ppr': 20},
            {'rank': 2, 'actual_ppr': 10},
        ]
        self.assertIsNone(calculate_rank_correlation(rows))

    def test_identical_results(self):
        rows = [
            {'rank': 1, 'actual_ppr': 10},
            {'rank': 2, 'actual_ppr': 10},
            {'rank': 3, 'actual_ppr': 10},
        ]
        self.assertIsNone(calculate_rank_correlation(rows))

    def test_overall_single_week(self):
        weekly = {'2026_week_06': 0.750}
        self.assertEqual(calculate_overall_rank_correlation(weekly), 0.750)

    def test_overall_multiple_weeks(self):
        weekly = {
            '2026_week_06': 0.600,
            '2026_week_07': 0.800,
        }
        self.assertEqual(calculate_overall_rank_correlation(weekly), 0.700)

    def test_overall_ignores_unavailable_weeks(self):
        weekly = {
            '2026_week_06': None,
            '2026_week_07': 0.800,
        }
        self.assertEqual(calculate_overall_rank_correlation(weekly), 0.800)
        self.assertIsNone(calculate_overall_rank_correlation({}))
        self.assertIsNone(
            calculate_overall_rank_correlation({'2026_week_06': None})
        )

    def test_top_five_hit_rate(self):
        rows = [
            {'rank': 1, 'actual_ppr': 20},
            {'rank': 2, 'actual_ppr': 12},
            {'rank': 3, 'actual_ppr': 5},
        ]
        self.assertEqual(
            calculate_top_five_hit_rate(rows),
            (3, 2, 66.67)
        )

    def test_top_five_exact_threshold(self):
        rows = [
            {'rank': 1, 'actual_ppr': 10},
            {'rank': 2, 'actual_ppr': 9.99},
        ]
        self.assertEqual(
            calculate_top_five_hit_rate(rows),
            (2, 1, 50.0)
        )

    def test_top_five_excludes_lower_rankings(self):
        rows = [
            {'rank': 5, 'actual_ppr': 15},
            {'rank': 6, 'actual_ppr': 25},
            {'rank': 10, 'actual_ppr': 30},
        ]
        self.assertEqual(
            calculate_top_five_hit_rate(rows),
            (1, 1, 100.0)
        )

    def test_top_five_no_eligible_results(self):
        self.assertEqual(
            calculate_top_five_hit_rate([]),
            (0, 0, None)
        )

if __name__ == '__main__':
    unittest.main()
