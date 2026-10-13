
import unittest

from scripts.validate_waiver_predictions import calculate_rank_correlation


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


if __name__ == '__main__':
    unittest.main()
