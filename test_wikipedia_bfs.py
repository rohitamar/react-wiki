import unittest

from wikipedia_bfs import shortest_path


class ShortestPathTests(unittest.TestCase):
    def test_returns_shortest_path(self):
        graph = {
            "Start": ["Long route"],
            "Long route": ["Detour", "Target"],
            "Detour": ["Target"],
            "Target": [],
        }

        self.assertEqual(shortest_path("Start", "Target", graph.__getitem__), ["Start", "Long route", "Target"])

    def test_searches_frontier_concurrently_without_changing_bfs_depth(self):
        graph = {
            "Start": ["A", "B", "C"],
            "A": ["A1"],
            "B": ["B1"],
            "C": ["Target"],
            "A1": ["Target"],
            "B1": [],
            "Target": [],
        }

        self.assertEqual(
            shortest_path("Start", "Target", graph.__getitem__, max_workers=3),
            ["Start", "C", "Target"],
        )

    def test_returns_none_when_depth_limit_is_too_small(self):
        graph = {"Start": ["Middle"], "Middle": ["Target"], "Target": []}

        self.assertIsNone(shortest_path("Start", "Target", graph.__getitem__, max_depth=1))

    def test_start_is_target(self):
        self.assertEqual(shortest_path("Start", "Start", lambda _: []), ["Start"])


if __name__ == "__main__":
    unittest.main()
