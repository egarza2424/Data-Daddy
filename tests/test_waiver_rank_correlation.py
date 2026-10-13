
import unittest

from scripts.validate_waiver_predictions import (
    calculate_rank_correlation,
    calculate_overall_rank_correlation,
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

if __name__ == '__main__':
    unittest.main()
